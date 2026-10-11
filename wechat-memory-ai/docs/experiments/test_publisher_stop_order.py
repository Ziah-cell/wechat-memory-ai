"""Own publisher stop-order race fixture with a real consumer and fictional ledger."""
import argparse,hashlib,json,shutil,sys,time,traceback,uuid
from pathlib import Path
from test_resident_publisher import Child
ROOT=Path(__file__).resolve().parents[2];CACHE=ROOT/'data/publisher-stop-order-20261011'
EXE=CACHE/'publisher_stop_order_fixture.exe';LEDGER=Path(__file__).with_name('resident_delivery_ledger.py')
RACES=[p+'_'+q for p in ['gate_enter','gate_partial','gate_precommit','gate_postcommit'] for q in ['fresh','prepared','prechecked']]
CASES=['normal','original_fault','reentrant_original_fault']+RACES
DEPENDENCIES=['publisher_stop_order_fixture.c','capture_copy_site.S','resident_publisher_fixture.c','executed_trampoline_fixture.c','trampoline_register_caller.S','resident_delivery_ledger.py','test_resident_publisher.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ok(x):assert x.get('ok') is True,x;return x
def run_case(name,mode,run,index):
    folder=ROOT/'data/resident-delivery-20261010/publisher-stop-order-20261011'/run.name/f'{index:03d}-{name}';folder.mkdir(parents=True)
    db=folder/'ledger.sqlite3';log=[];children=[];target=None;race_open=False
    epoch=uuid.uuid4().hex;mapping='Local\\VXOwnPublisher-'+uuid.uuid4().hex
    out=dict(case=name,mode=mode,passed=False,observations=log,database=db.relative_to(ROOT).as_posix())
    def spawn(exe,args):
        p=Child(exe,args,log);children.append(p);return p
    def cmd(p,op,**kwargs):return p.send(json.dumps(dict(op=op,**kwargs)))
    def target_quit():
        x=target.send('quit');assert x==dict(event='bye',prefix_restored=True,table_deleted=True,lookups_absent=True,freed=True,mapping_closed=True,guard_freed=True),x
        target.wait();out['target_cleanup']=x
    started=time.perf_counter()
    try:
        target=spawn(EXE,['target',mapping,epoch]+([mode] if mode!='exact' else []))
        r=target.get();assert r['registered_entries']==3 and r['all_lookups_match'],r
        p=spawn(sys.executable,['-u',str(LEDGER),'--database',str(db)]);r=p.get();assert r['event']=='ready' and r['synchronous']==2 and r['journal_mode']=='wal',r
        ok(cmd(p,'begin',epoch=epoch))
        c=spawn(EXE,['consumer',mapping,epoch]);assert c.get()['read_only']
        race=name in RACES
        first=target.send(('race ' if race else 'scenario ')+name);out['first']=first
        race_open=race
        if race:
            # Read and actually commit any leak before resuming the fault handler.
            batch=c.send('read');out['window_batch']=batch
            if batch['records']:out['window_accept']=ok(cmd(p,'accept',epoch=epoch,records=batch['records']))
            out['resumed']=target.send('resume');race_open=False
        later=target.send('scenario normal');out['later']=later
        if not race:
            batch=c.send('read');out['normal_batch']=batch
            if batch['records']:ok(cmd(p,'accept',epoch=epoch,records=batch['records']))
        else:out['after_batch']=c.send('read')
        stop=ok(cmd(p,'stop',epoch=epoch))['stop_op'];target.send('stop')
        snap=ok(cmd(p,'snapshot'));out['snapshot']=snap
        ids=[] if race else [1] if name=='original_fault' else [2] if name=='reentrant_original_fault' else [1,2]
        out['expected_ids']=ids
        assert snap['integrity']=='ok' and snap['sessions'][0]['state']=='closed'
        assert all(x['commit_op']<stop for x in snap['records'])
        for state in (first,later):assert state['depth']==state['errors']==state['gate']==0,state
        entries=3 if race or name=='reentrant_original_fault' else 2
        returns=3 if race else 2 if name=='normal' else 1
        assert later['hook_entries']==entries and later['hook_returns']==later['original']==returns,later
        assert later['capture_faults']==int(race) and later['nested_skips']==int(name=='reentrant_original_fault'),later
        assert later['original_exceptions']==int(name in ['original_fault','reentrant_original_fault']),later
        assert later['copy_fault_offset']==(0 if race else -1),later
        assert later['state']==(6 if race else 1),later
        assert later['published']==(int(name.startswith('gate_postcommit')) if race else len(ids)),later
        if race:
            # Stop must already be visible at release, even for a prepared candidate.
            assert first['window_state']==first['state']==6,first
            assert first['window_gate']==0 and first['window_published']==int(name.startswith('gate_postcommit')),first
            assert first['capture_faults']==0 and first['tls_workers']==first['tls_depth_zero']==1,first
            assert first['second_candidate']==first['second_publish_entered']==int(not name.endswith('_fresh')),first
            assert first['second_gate_acquired']==int(name.endswith('_prechecked')),first
            assert later['tls_workers']==later['tls_depth_zero']==2 and later['tls_distinct'] is True,later
            assert batch['reason']=='inactive' and batch['records']==[],batch
            assert out['after_batch']['reason']=='inactive' and out['after_batch']['records']==[]
        else:assert batch['reason']=='ok',batch
        assert [r['id'] for r in batch['records']]==ids,batch
        assert [r['seq'] for r in batch['records']]==list(range(1,len(ids)+1)),batch
        assert len(snap['records'])==len(ids),snap
        for rec in batch['records']:
            ident=rec['id'];assert (rec['a'],rec['b'],rec['c'])==(ident^0xa5a5a5a5,ident+7,ident*3)
        out['passed']=True
    except Exception as e:out.update(error=repr(e),traceback=traceback.format_exc())
    finally:
        for child in reversed(children):
            try:
                if child is target and child.p.poll() is None:
                    if race_open:child.send('resume');race_open=False
                    target_quit()
                child.cleanup()
            except Exception as e:
                out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(e))
                if child.p.poll() is None:child.kill()
        out['all_children_exited']=all(c.p.poll() is not None for c in children);out['passed'] &= out['all_children_exited']
        out['database_files']={p.name:sha(p) for p in folder.glob('ledger.sqlite3*')};out['seconds']=time.perf_counter()-started
    return out
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',action='append',choices=CASES);parser.add_argument('--mode',choices=['exact','late_stop','skip_recheck'],default='exact');parser.add_argument('--races-only',action='store_true');parser.add_argument('--repeat',type=int,default=1)
    args=parser.parse_args();assert 1<=args.repeat<=3
    run=CACHE/('run-'+uuid.uuid4().hex[:12]);run.mkdir(parents=True);hashes={}
    for p in [Path(__file__),*[Path(__file__).with_name(n) for n in DEPENDENCIES],EXE,CACHE/'build.json']:
        if p.exists():shutil.copyfile(p,run/p.name);hashes[p.name]=sha(p)
    if EXE.exists():
        b=json.loads((CACHE/'build.json').read_text());assert b['exe_sha256']==sha(EXE)
        for n,h in b['source_hashes'].items():assert sha(Path(__file__).with_name(n))==h
    cases=[run_case(n,args.mode,run,i) for i,n in enumerate((args.case or (RACES if args.races_only else CASES))*args.repeat)]
    d=dict(source_hashes=hashes,cases=cases,total=len(cases),passed=sum(x['passed'] for x in cases),mode=args.mode,live_wechat_hook=False)
    (run/'results.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=run.relative_to(ROOT).as_posix(),passed=d['passed'],total=d['total'],failures=[(c['case'],c.get('error')) for c in cases if not c['passed']])))
    return int(d['passed']!=d['total'])
if __name__=='__main__':raise SystemExit(main())
