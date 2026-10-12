"""Owned thread death must abandon the capture channel without claiming unwind."""
import argparse,json,queue,shutil,sys,time,traceback,uuid,hashlib,os
from pathlib import Path
from types import SimpleNamespace
from test_resident_publisher import Child
from autonomous_relay import Journal,created
R=Path(__file__).resolve().parents[2];D=R/'docs/experiments';C=R/'data/writer-abandon-20261012';EXE=C/'writer_abandon_fixture.exe'
CASES=[*[f'kill_{i}' for i in range(11)],'release_3','release_8']
SOURCES=['writer_abandon_fixture.c','writer_abandon_hook.inc','writer_abandon_schedule.inc','writer_abandon_protocol.h','writer_abandon_ledger.py','test_writer_abandon.py',
 'shared_write_sites.S','capture_copy_site.S','executed_trampoline_fixture.c','trampoline_register_caller.S','target_lifetime_ledger.py','session_target_binding.py','test_resident_publisher.py','autonomous_relay.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8',newline='\n')
def run_case(name,mode,folder):
 folder.mkdir();j=Journal(folder/'journal.jsonl');children=[];o=dict(case=name,mode=mode,passed=False);start=time.perf_counter();action,stage=name.split('_');stage=int(stage)
 cfg=dict(epoch=uuid.uuid4().hex,mapping='Local\\VXOwnPublisher-'+uuid.uuid4().hex,lease=uuid.uuid4().hex,stage=stage,action=action);save(folder/'config.json',cfg)
 def spawn(role,exe,args):
  c=Child(exe,args,j);children.append((role,c));r=c.get();assert r['event']=='ready',r;return c,r
 def ask(c,**r):return c.send(json.dumps(r,separators=(',',':')))
 def end(c):
  out=[c.send('quit')]
  while out[-1].get('event')!='bye':out.append(c.get())
  c.wait();return out
 try:
  t,tr=spawn('target',EXE,['target',cfg['mapping'],cfg['epoch'],'owned',str(os.getpid()),str(created(SimpleNamespace(p=SimpleNamespace(_handle=-1)))),cfg['lease']])
  b,br=spawn('bridge',EXE,['bridge',cfg['mapping'],cfg['epoch'],str(tr['pid']),str(tr['created']),cfg['lease']]);assert br['read_only']
  l,lr=spawn('ledger',sys.executable,['-u',str(D/'writer_abandon_ledger.py'),'--database',str(folder/'ledger.sqlite3')]);assert lr['synchronous']==2
  assert ask(l,op='begin',epoch=cfg['epoch'],target=dict(pid=tr['pid'],created=tr['created']))['ok']
  def commit(records):
   assert ask(l,op='observe',epoch=cfg['epoch'],records=records)['ok'];r=ask(l,op='accept',epoch=cfg['epoch'],records=records);assert r['ok'];return r
  assert t.send('call 7 32')['published']==7;o['receipt7']=commit(b.send('read')['records']);o['ack7']=b.send(f"ack {cfg['epoch']} 7 1");assert o['ack7']['ok']
  assert t.send('call 1 32')['published']==8;o['receipt8']=commit(b.send('read')['records'])
  o['paused']=t.send(f'dead_start {stage} {mode}');o['alive_probe']=t.send('dead_probe')
  if stage<10:o['alive_ack']=b.send(f"ack {cfg['epoch']} 8 1")
  o['before_read']=b.send('read')
  if stage==7 and o['before_read']['records']:o['observed9']=ask(l,op='observe',epoch=cfg['epoch'],records=o['before_read']['records'])
  o['after']=t.send('dead_kill' if action=='kill' else 'dead_release')
  o['ack_after']=[b.send(f"ack {cfg['epoch']} 8 1") for _ in range(3 if action=='kill' else 1)]
  o['detected']=t.send('dead_probe');o['after_read']=b.send('read')
  if action=='release' and stage==3:
   o['receipt9']=commit(o['after_read']['records']);o['ack9']=b.send(f"ack {cfg['epoch']} 9 2")
  o['live_reconcile']=ask(l,op='reconcile',epoch=cfg['epoch']);o['live_snapshot']=ask(l,op='snapshot')
  if action=='kill':o['continued']=t.send('call 3 32')
  o['bridge_end']=end(b);o['target_end']=end(t);o['ending']=ask(l,op='reconcile',epoch=cfg['epoch']);o['snapshot']=ask(l,op='snapshot');o['ledger_end']=end(l)
  # Fail behavior assertions only after real termination/cleanup has been recorded.
  assert o['alive_probe']['wait']==258 and not o['alive_probe']['exit_known'] and o['alive_probe']['state']!=7,o['alive_probe']
  if stage<10:assert o['alive_ack']==dict(event='ack',ok=False,acked=7,reason='busy'),o['alive_ack']
  assert o['after']['wait']==0 and o['after']['exit_known'] and o['after']['exit']==(73 if action=='kill' else 0),o['after']
  point=3 if stage>=8 else stage
  partial=dict(stamp=2 if point==0 else 18 if point==7 else 17,seq=1 if point<2 else 9,
   words=[9 if point>2 else 1,9^0xa5a5a5a5 if point>3 else 1^0xa5a5a5a5,16 if point>4 else 8,27 if point>5 else 3])
  assert {k:o['paused'][k] for k in partial}==partial,(o['paused'],partial)
  assert o['paused']['published']==(9 if stage==7 else 8) and o['paused']['paused_depth']==1 and o['paused']['paused_armed']==(stage not in (7,10)),o['paused']
  w=next(x for x in o['target_end'] if x['event']=='write_status');status=next(x for x in o['target_end'] if x['event']=='status')
  assert w['seen']==(stage>=8) and w['control_protection']==4 and w['record_protection']==(2 if stage>=8 else 4),w
  if stage>=8:assert w['code']==0xc0000005 and w['operation']==1 and w['site']==0 and w['address_offset']==24,w
  assert status['errors']==0 and status['depth']==0,status
  assert next(x for x in o['target_end'] if x['event']=='write_site')==dict(event='write_site',span=3,bytes=[72,135,17])
  if action=='kill':
   assert o['after']['returned']==o['after']['hook_finally']==o['after']['worker_finally']==0,o['after']
   assert o['after']['publisher_finally']==(stage>=9),o['after']
   gate=0 if stage==10 else 1
   assert o['after']['gate']==gate and o['detected']['gate']==gate and o['detected']['state']==7 and o['detected']['abandoned'],o['detected']
   assert all(a==dict(event='ack',ok=False,acked=7,reason='abandoned') for a in o['ack_after']),o['ack_after']
   assert o['after_read']==dict(event='read',reason='inactive',records=[]),o['after_read']
   assert o['continued']['original']==12 and o['continued']['published']==(9 if stage==7 else 8) and o['continued']['state']==7 and o['continued']['gate']==gate,o['continued']
  else:
   assert o['after']['returned']==o['after']['publisher_finally']==o['after']['hook_finally']==o['after']['worker_finally']==1 and o['after']['gate']==0,o['after']
   assert not o['detected']['abandoned'] and o['ack_after'][0]['ok'],o['detected']
  cleanup=next(x for x in o['target_end'] if x['event']=='dead_cleanup')
  assert cleanup['claimed_cooperative']==(action=='release') and cleanup['worker_finally']==(action=='release'),cleanup
  assert o['live_reconcile'].get('reason')=='target_alive' and not o['live_reconcile']['ok'],o['live_reconcile']
  assert o['live_snapshot']['sessions'][0]['state']=='active' and not o['live_snapshot']['endings'],o['live_snapshot']
  wanted=9 if action=='release' and stage==3 else 8;snap=o['snapshot'];ending=o['ending']
  assert snap['integrity']=='ok' and snap['active'] is None and len(snap['inbox'])==wanted and snap['sessions'][0]['state']=='ended',snap
  assert ending['ok'] and ending['tail_unknown'] and ending['proof']['reason']=='same_process_signaled' and ending['discarded_observed']==(stage==7),ending
  assert [r['seq'] for r in snap['inbox']]==list(range(1,wanted+1))
  bye=o['target_end'][-1];assert all(v is True for k,v in bye.items() if k!='event'),bye
  o['passed']=True
 except Exception as exc:o['error']=repr(exc);o['traceback']=traceback.format_exc()
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
    try:j.append(dict(action='unread',pid=c.p.pid,line=c.lines.get_nowait()))
    except queue.Empty:break
   for f in (c.p.stdin,c.p.stdout):
    if not f.closed:f.close()
  o['processes']=[dict(role=role,pid=c.p.pid,exit=c.p.returncode) for role,c in children];j.file.close();o['seconds']=time.perf_counter()-start
  o['files']={p.name:sha(p) for p in folder.iterdir() if p.is_file()};save(folder/'result.json',o)
 return o
def main():
 a=argparse.ArgumentParser();a.add_argument('--case',choices=CASES,action='append');a.add_argument('--repeat',type=int,default=1);a.add_argument('--mode',choices=['exact','skip_abandon','unlock_dead','assume_dead','false_cleanup'],default='exact');x=a.parse_args();assert 1<=x.repeat<=3
 d=C/('run-'+uuid.uuid4().hex[:12]);d.mkdir()
 for p in [*[D/n for n in SOURCES],EXE,C/'build.json']:shutil.copyfile(p,d/p.name)
 hashes={p.name:sha(p) for p in d.iterdir()};build=load(C/'build.json');assert sha(EXE)==build['exe_sha256']
 for n,h in build['source_hashes'].items():assert sha(D/n)==h,n
 results=[]
 for repeat in range(x.repeat):
  for case in x.case or CASES:
   r=run_case(case,x.mode,d/f'{repeat}-{case}');results.append(r);print(json.dumps(dict(run=d.name,case=case,passed=r['passed'],error=r.get('error'))),flush=True)
 save(d/'results.json',dict(mode=x.mode,passed=all(r['passed'] for r in results),source_hashes=hashes,results=results));return int(not all(r['passed'] for r in results))
if __name__=='__main__':raise SystemExit(main())
