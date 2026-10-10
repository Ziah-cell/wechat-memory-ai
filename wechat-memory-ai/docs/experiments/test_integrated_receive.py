"""Controlled own-process Hook -> bounded mapping -> consumer -> fictional ledger."""
import argparse
import hashlib
import json
import shutil
import sys
import time
import traceback
import uuid
from pathlib import Path
from test_resident_publisher import Child

ROOT=Path(__file__).resolve().parents[2]
CACHE=ROOT/'data/integrated-receive-20261011'
SOURCE=Path(__file__).with_name('resident_delivery_ledger.py')
EXE=CACHE/'integrated_receive_fixture.exe'
CASES=['restart_dedup','consumer_exit_backlog','pending_copy_stop','pending_batch_stop',
       'ledger_crash_before_commit','ledger_crash_after_commit','ledger_busy_stop',
       'capacity_full','gate_busy','invalid_length','target_exit_pending',
       'target_killed_pending','parallel_overflow','ack_after_stop']
DEPENDENCIES=['integrated_receive_fixture.c','resident_publisher_fixture.c',
              'executed_trampoline_fixture.c','trampoline_register_caller.S',
              'resident_delivery_ledger.py','test_resident_publisher.py']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ok(x,**values):
    assert x.get('ok') is True,x
    for k,v in values.items():assert x[k]==v,x
    return x
def denied(x,reason):assert x.get('ok') is False and x['reason']==reason,x

def run_case(name,mode,run,index):
    folder=ROOT/'data/resident-delivery-20261010/integrated-20261011'/run.name/f'{index:03d}-{name}'
    folder.mkdir(parents=True);db=folder/'ledger.sqlite3'
    log=[];children=[];target=None
    epoch=uuid.uuid4().hex;mapping='Local\\VXOwnPublisher-'+uuid.uuid4().hex
    out=dict(case=name,mode=mode,passed=False,observations=log,database=db.relative_to(ROOT).as_posix())
    def spawn(exe,args):
        c=Child(exe,args,log);children.append(c);return c
    def ledger():
        p=spawn(sys.executable,['-u',str(SOURCE),'--database',str(db)])
        r=p.get();assert r['event']=='ready' and r['journal_mode']=='wal' and r['synchronous']==2,r
        return p
    def cmd(p,op,**kwargs):return p.send(json.dumps(dict(op=op,**kwargs)))
    def accept(p,batch,**kwargs):return cmd(p,'accept',epoch=epoch,records=batch,**kwargs)
    def consumer():
        c=spawn(EXE,['consumer',mapping,epoch]);r=c.get()
        assert r['read_only'] is True and r['target_pid']==target.p.pid,r
        return c
    def batch(c,ids):
        r=c.send('read');assert r['event']=='read' and r['reason']=='ok',r
        assert [x['id'] for x in r['records']]==ids,r
        for x in r['records']:
            assert (x['seq'],x['a'],x['b'],x['c'])==(x['id'],x['id']^0xa5a5a5a5,x['id']+7,x['id']*3),x
        return r['records']
    def status(count,state=None,published=None):
        r=target.send('status')
        assert r['original']==r['hook_entries']==r['hook_returns']==count and r['errors']==0,r
        if state is not None:assert r['state']==state,r
        if published is not None:assert r['published']==published,r
        return r
    def snapshot(p,count,closed=True):
        x=ok(cmd(p,'snapshot'));assert x['integrity']=='ok' and len(x['records'])==count,x
        s=x['sessions'];assert len(s)==1 and s[0]['last_seq']==count,x
        assert s[0]['state']==('closed' if closed else 'active'),x
        if closed:assert all(r['commit_op']<s[0]['stop_op'] for r in x['records']),x
        out['snapshot']=x;return x
    def stop(p):
        mark=ok(cmd(p,'stop',epoch=epoch))['stop_op']
        if target.p.poll() is None:assert target.send('stop')['state']!=1
        return mark
    def target_quit():
        x=target.send('quit')
        assert x==dict(event='bye',prefix_restored=True,table_deleted=True,lookups_absent=True,
                       freed=True,mapping_closed=True),x
        target.wait();out['target_cleanup']=x
    started=time.perf_counter()
    try:
        target=spawn(EXE,['target',mapping,epoch]+(['skip_publish'] if mode=='skip_publish' else []))
        ready=target.get()
        assert ready['event']=='ready' and ready['registered_entries']==3 and ready['all_lookups_match'] and ready['lock_free'],ready
        p=ledger();ok(cmd(p,'begin',epoch=epoch));c=consumer()
        if name=='restart_dedup':
            target.send('call 3 32');first=batch(c,[1,2,3]);ok(accept(p,first),added=3,duplicates=0)
            c.kill();p.kill();c=consumer();p=ledger()
            ok(accept(p,batch(c,[1,2,3])),added=0,duplicates=3)
            target.send('call 1 32');ok(accept(p,batch(c,[4])),added=1)
            stop(p);target.send('call 1 32');status(5,2,4);snapshot(p,4)
        elif name=='consumer_exit_backlog':
            target.send('call 1 32');target.send('workers 1 4 5');c.kill()
            target.send('join');target.send('call 1 32');status(6,1,6)
            c=consumer();ok(accept(p,batch(c,list(range(1,7)))),added=6);stop(p);snapshot(p,6)
        elif name in ('pending_copy_stop','pending_batch_stop'):
            target.send('call 3 32')
            if name=='pending_copy_stop':assert c.send('copy')['count']==3
            else:pending=batch(c,[1,2,3])
            stop(p)
            if name=='pending_copy_stop':
                r=c.send('commit');assert r['reason']=='inactive' and r['records']==[],r
            else:denied(accept(p,pending),'closed')
            target.send('call 2 32');status(5,2,3);snapshot(p,0)
        elif name.startswith('ledger_crash_'):
            target.send('call 3 32');pending=batch(c,[1,2,3]);stage=name.removeprefix('ledger_crash_')
            assert accept(p,pending,checkpoint=stage)['stage']==stage
            p.kill();p=ledger();committed=stage=='after_commit'
            snapshot(p,3 if committed else 0,False)
            ok(accept(p,pending),added=0 if committed else 3,duplicates=3 if committed else 0)
            stop(p);status(3,2,3);snapshot(p,3)
        elif name=='ledger_busy_stop':
            target.send('call 2 32');pending=batch(c,[1,2]);q=ledger()
            assert accept(p,pending,checkpoint='before_commit')['stage']=='before_commit'
            target.send('workers 1 4 5');denied(cmd(q,'stop',epoch=epoch),'busy')
            p.kill();stop(q);target.send('join');status(6,2)
            denied(accept(q,pending),'closed');snapshot(q,0)
        elif name=='capacity_full':
            target.send('call 8 32');status(8,1,8);ok(accept(p,batch(c,list(range(1,9)))),added=8)
            target.send('call 51 32');status(59,4,8)
            r=c.send('read');assert r['reason']=='inactive' and not r['records'],r
            stop(p);snapshot(p,8)
        elif name in ('gate_busy','invalid_length'):
            target.send('busy' if name=='gate_busy' else 'call 1 31')
            target.send('call 3 32');status(4,5 if name=='gate_busy' else 6,0)
            r=c.send('read');assert r['reason']=='inactive' and not r['records'],r
            stop(p);snapshot(p,0)
        elif name in ('target_exit_pending','target_killed_pending'):
            target.send('call 3 32');assert c.send('copy')['count']==3;status(3,1,3)
            if name=='target_exit_pending':target_quit()
            else:target.kill()
            r=c.send('commit');assert r['reason']=='target_dead' and not r['records'],r
            stop(p);snapshot(p,0)
        elif name=='parallel_overflow':
            target.send('workers 4 1000 0');target.send('join');r=status(4000)
            assert r['state'] in (4,5) and 0<=r['published']<=8,r
            r=c.send('read');assert r['reason']=='inactive' and not r['records'],r
            stop(p);snapshot(p,0)
        elif name=='ack_after_stop':
            target.send('call 3 32');pending=batch(c,[1,2,3]);q=ledger()
            assert accept(p,pending,checkpoint='after_commit')['stage']=='after_commit'
            mark=stop(q);ok(p.send('resume'),added=3)
            denied(accept(p,pending),'closed');x=snapshot(q,3)
            assert all(r['commit_op']<mark for r in x['records'])
            out['boundary']='accept ACK can follow STOP ACK for rows committed before STOP'
        else:raise AssertionError(name)
        out['passed']=True
    except Exception as e:
        out.update(error=repr(e),traceback=traceback.format_exc())
    finally:
        for child in reversed(children):
            try:
                if child is target and child.p.poll() is None:target_quit()
                child.cleanup()
            except Exception as e:
                out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(e))
                if child.p.poll() is None:child.kill()
        out['all_children_exited']=all(c.p.poll() is not None for c in children)
        out['passed'] &= out['all_children_exited']
        out['seconds']=time.perf_counter()-started
        out['database_files']={p.name:sha(p) for p in folder.glob('ledger.sqlite3*')}
    return out

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['exact','skip_publish'],default='exact')
    parser.add_argument('--case',choices=CASES,action='append');parser.add_argument('--repeat',type=int,default=1)
    args=parser.parse_args();assert 1<=args.repeat<=3
    run=CACHE/('run-'+uuid.uuid4().hex[:12]);run.mkdir(parents=True)
    sources=[Path(__file__),*[Path(__file__).with_name(n) for n in DEPENDENCIES],EXE,CACHE/'build.json']
    hashes={}
    for p in sources:
        if p.exists():shutil.copyfile(p,run/p.name);hashes[p.name]=sha(p)
    if EXE.exists():
        build=json.loads((CACHE/'build.json').read_text());assert build['exe_sha256']==sha(EXE)
        for name,h in build['source_hashes'].items():assert sha(Path(__file__).with_name(name))==h
    cases=[run_case(n,args.mode,run,i) for i,n in enumerate((args.case or CASES)*args.repeat)]
    result=dict(source_hashes=hashes,cases=cases,total=len(cases),passed=sum(c['passed'] for c in cases),mode=args.mode,live_wechat_hook=False)
    (run/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=run.relative_to(ROOT).as_posix(),passed=result['passed'],total=result['total'],failures=[(c['case'],c.get('error')) for c in cases if not c['passed']])))
    return int(result['passed']!=result['total'])

if __name__=='__main__':raise SystemExit(main())
