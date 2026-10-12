"""Real AV phase barriers with independent ACK service, reader and ledger."""
import argparse,hashlib,json,queue,shutil,sys,time,traceback,uuid
from pathlib import Path
from types import SimpleNamespace
from test_resident_publisher import Child
from autonomous_relay import Journal,created
R=Path(__file__).resolve().parents[2];C=R/'data/write-interleave-20261012';D=R/'docs/experiments';EXE=C/'write_interleave_fixture.exe'
KINDS=['fresh','prepared','prechecked','unarmed','wrong_destination']
CASES=[f'{k}_{p}' for k in KINDS for p in (range(7) if k in KINDS[:3] else [0,3,6])]
SOURCES=['write_interleave_fixture.c','write_interleave_hook.inc','write_interleave_schedule.inc','write_interleave_ledger.py','test_write_interleave.py',
 'shared_write_protocol.h','shared_write_sites.S','capture_copy_site.S','executed_trampoline_fixture.c','trampoline_register_caller.S',
 'target_lifetime_ledger.py','session_target_binding.py','test_resident_publisher.py','autonomous_relay.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def partial(p):
 v=dict(stamp=2,seq=1,words=[1,1^0xa5a5a5a5,8,3])
 if p>0:v['stamp']=17
 if p>1:v['seq']=9
 for i,n in enumerate([9,9^0xa5a5a5a5,16,27]):
  if p>i+2:v['words'][i]=n
 return v
def run_case(name,mode,folder):
 folder.mkdir();journal=Journal(folder/'journal.jsonl');children=[];o=dict(case=name,mode=mode,passed=False);start=time.perf_counter()
 kind,point=name.rsplit('_',1);kind=KINDS.index(kind);point=int(point)
 cfg=dict(epoch=uuid.uuid4().hex,mapping='Local\\VXOwnPublisher-'+uuid.uuid4().hex,lease=uuid.uuid4().hex,kind=kind,point=point);save(folder/'config.json',cfg)
 def spawn(role,exe,args):
  c=Child(exe,args,journal);children.append((role,c));r=c.get();assert r['event']=='ready',r;return c,r
 def ask(c,req):return c.send(json.dumps(req,separators=(',',':')))
 def end(c):
  result=[c.send('quit')]
  while result[-1].get('event')!='bye':result.append(c.get())
  c.wait();return result
 try:
  import os
  target,tr=spawn('target',EXE,['target',cfg['mapping'],cfg['epoch'],'owned',str(os.getpid()),str(created(SimpleNamespace(p=SimpleNamespace(_handle=-1)))),cfg['lease']])
  bridge,br=spawn('bridge',EXE,['bridge',cfg['mapping'],cfg['epoch'],str(tr['pid']),str(tr['created']),cfg['lease']]);assert br['read_only']
  ledger,lr=spawn('ledger',sys.executable,['-u',str(D/'write_interleave_ledger.py'),'--database',str(folder/'ledger.sqlite3')]);assert lr['synchronous']==2
  o['binding']=tr;assert ask(ledger,dict(op='begin',epoch=cfg['epoch'],target=dict(pid=tr['pid'],created=tr['created'])))['ok']
  def commit_read():
   records=bridge.send('read')['records'];assert records
   assert ask(ledger,dict(op='observe',epoch=cfg['epoch'],records=records))['ok']
   receipt=ask(ledger,dict(op='accept',epoch=cfg['epoch'],records=records));assert receipt['ok'];return receipt
  assert target.send('call 7 32')['published']==7
  o['receipt7']=commit_read();o['ack7']=bridge.send(f"ack {cfg['epoch']} 7 1");assert o['ack7']['ok']
  assert target.send('call 1 32')['published']==8;o['receipt8']=commit_read()
  o['cursor_begin']=bridge.send('cursor_begin')
  o['filter']=target.send(f'iw_start {kind} {point} {mode}')
  o['filter_read']=bridge.send('read');o['filter_ack']=bridge.send(f"ack {cfg['epoch']} 8 1")
  o['split_begin']=bridge.send('split_begin')
  if kind>=3:o['probe']=target.send('iw_probe')
  o['unwind']=target.send('iw_next');o['unwind_ack']=bridge.send(f"ack {cfg['epoch']} 8 1");o['split_end']=bridge.send('split_end')
  o['unlock']=target.send('iw_next');o['cursor_end']=bridge.send('cursor_end');o['unlock_ack']=bridge.send(f"ack {cfg['epoch']} 8 1")
  if kind<3:o['second']=target.send('iw_second')
  o['final']=target.send('iw_finish');o['final_read']=bridge.send('read')
  o['bridge_end']=end(bridge);o['target_end']=end(target)
  o['ending']=ask(ledger,dict(op='reconcile',epoch=cfg['epoch']));assert o['ending']['ok']
  o['snapshot']=ask(ledger,dict(op='snapshot'));o['ledger_end']=end(ledger)
  # All processes have cleanly exited before behavior assertions, including negatives.
  for phase,expected_state,expected_gate,armed in [('filter',1,1,1),('unwind',6,1,1),('unlock',6,0,0)]:
   s=o[phase];assert (s['state'],s['gate'],s['published'],s['acked'],s['phase_armed'],s['phase_depth'])==(expected_state,expected_gate,8,7,armed,1),(phase,s)
   assert {k:s[k] for k in ['stamp','seq','words']}==partial(point),(phase,s,partial(point))
  for a in ['filter_ack','unwind_ack']:assert o[a]==dict(event='ack',ok=False,acked=7,reason='busy'),(a,o[a])
  assert o['unlock_ack']==dict(event='ack',ok=True,acked=8,reason='ok'),o['unlock_ack']
  assert o['filter_read']['reason']=='ok' and [r['seq'] for r in o['filter_read']['records']]==[8]
  for read in ['split_end','cursor_end','final_read']:assert o[read]==dict(event='read',reason='inactive',records=[]),(read,o[read])
  f=o['final'];a,b,c=f['threads'];assert (f['state'],f['gate'],f['published'],f['acked'],f['errors'])==(6,0,8,8,0),f
  assert f['original']==(10 if kind<3 else 9),f
  assert a['seen']==a['handled']==a['armed']==a['match']==a['depth']==a['gate']==a['returned']==a['clear']==1,a
  assert a['code']==0xc0000005 and a['operation']==1 and a['site']==0 and a['offset']==[0,8,16,24,32,40,0][point] and a['writes']==point+1,a
  if kind<3:assert b['tid']!=a['tid'] and b['seen']==b['writes']==0 and b['returned']==b['clear']==1 and b['acquired']==(kind==2),b
  else:assert c['code']==0xc0000005 and c['tid']!=a['tid'] and c['seen']==c['propagated']==c['clear']==1 and c['handled']==c['match']==c['returned']==0 and c['armed']==(kind==4) and c['operation']==c['depth']==c['gate']==1 and c['offset']==a['offset'] and c['site']==0,c
  bye=o['target_end'][-1];assert all(v is True for k,v in bye.items() if k!='event'),bye
  site=next(x for x in o['target_end'] if x['event']=='write_site');assert site==dict(event='write_site',span=3,bytes=[72,135,17]),site
  snap=o['snapshot'];assert snap['integrity']=='ok' and snap['active'] is None and len(snap['inbox'])==8 and snap['sessions'][0]['state']=='ended',snap
  assert [r['seq'] for r in snap['inbox']]==list(range(1,9)) and o['ending']['tail_unknown'] and o['ending']['proof']['reason']=='same_process_signaled',o['ending']
  o['passed']=True
 except Exception as e:o['error']=repr(e);o['traceback']=traceback.format_exc()
 finally:
  for role,c in reversed(children):
   if c.p.poll() is None:
    o['passed']=False;o.setdefault('early_cleanup',[]).append(role)
    try:end(c)
    except Exception as exc:
     o.setdefault('cleanup_errors',[]).append(repr(exc))
     if c.p.poll() is None:c.kill()
   c.reader.join(timeout=1)
   while True:
    try:journal.append(dict(action='unread',pid=c.p.pid,line=c.lines.get_nowait()))
    except queue.Empty:break
   for f in (c.p.stdin,c.p.stdout):
    if not f.closed:f.close()
  o['processes']=[dict(role=role,pid=c.p.pid,exit=c.p.returncode) for role,c in children]
  journal.file.close();o['seconds']=time.perf_counter()-start;o['files']={p.name:sha(p) for p in folder.iterdir() if p.is_file()};save(folder/'result.json',o)
 return o
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',choices=CASES,action='append');ap.add_argument('--repeat',type=int,default=1);ap.add_argument('--mode',choices=['exact','late_stop','skip_recheck','shared_arm'],default='exact');a=ap.parse_args();assert 1<=a.repeat<=3
 run=C/('run-'+uuid.uuid4().hex[:12]);run.mkdir()
 for p in [*[D/n for n in SOURCES],EXE,C/'build.json']:shutil.copyfile(p,run/p.name)
 hashes={p.name:sha(p) for p in run.iterdir()};build=load(C/'build.json');assert sha(EXE)==build['exe_sha256']
 for n,h in build['source_hashes'].items():assert sha(D/n)==h,n
 out=[]
 for repeat in range(a.repeat):
  for case in a.case or CASES:
   r=run_case(case,a.mode,run/f'{repeat}-{case}');out.append(r);print(json.dumps(dict(run=run.name,case=case,passed=r['passed'],error=r.get('error'))),flush=True)
 save(run/'results.json',dict(mode=a.mode,passed=all(r['passed'] for r in out),source_hashes=hashes,results=out));return 0 if all(r['passed'] for r in out) else 1
if __name__=='__main__':raise SystemExit(main())
