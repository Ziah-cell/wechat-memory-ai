"""Fictional session terminal barrier against real owned native processes."""
import argparse,hashlib,json,queue,shutil,sqlite3,subprocess,sys,time,traceback,uuid
from pathlib import Path
from test_resident_publisher import Child
R=Path(__file__).resolve().parents[2];C=R/'data/session-reconcile-20261012'
EXE=C/'target_lifetime_fixture.exe';LEDGER=Path(__file__).with_name('session_reconcile_ledger.py')
CASES=['live_refusal','unknown_tail','observed_discard','commit_ack_lost','terminal_replay','old_epoch',
 'close_before_crash','close_after_crash','busy','storage_full','accept_race','close_race',
 'binding_reject','unknown_probe','absent_restart','conflicting_replay','recovery_restart','recovery_live']
SOURCES=['test_session_reconcile.py','session_reconcile_ledger.py','session_target_binding.py','session_reconcile_recovery.py',
 'test_resident_publisher.py','target_lifetime_ledger.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
def good(x):assert x.get('ok') is True,x;return x
def bad(x,reason):assert x.get('ok') is False and x.get('reason')==reason,x;return x

def case(name,mode,folder):
 folder.mkdir();db=folder/'ledger.sqlite3';log=[];children=[];targets=[];blocker=None
 out=dict(case=name,mode=mode,passed=False,observations=log);start=time.perf_counter()
 def spawn(exe,args,role):
  p=Child(exe,args,log);p.role=role;children.append(p);return p
 def cmd(p,op,**kw):return p.send(json.dumps(dict(op=op,**kw)))
 def receiver(selected=None):
  p=spawn(sys.executable,['-u',str(LEDGER),'--database',str(db),'--mode',selected or mode],'ledger')
  r=p.get();assert r['event']=='ready' and r['synchronous']==2,r;return p
 def target():
  ep=uuid.uuid4().hex;mapping='Local\\VXOwnPublisher-'+uuid.uuid4().hex
  p=spawn(EXE,['target',mapping,ep],'target');r=p.get();assert r['event']=='ready'
  b=spawn(EXE,['bridge',mapping,ep,str(r['pid']),str(r['created'])],'bridge');br=b.get();assert br['read_only'] is True
  good(p.send(f"bind {br['pid']} {br['created']}"))
  x=dict(target=p,bridge=b,epoch=ep,binding=dict(pid=r['pid'],created=r['created']));targets.append(x);return x
 def stop(x,kill=False,drop=False):
  if x['bridge'].p.poll() is None:x['bridge'].send('quit');x['bridge'].wait()
  if x['target'].p.poll() is None:
   if kill:x['target'].kill();out.setdefault('forced_targets',[]).append(x['binding'])
   else:
    p=x['target'];events=[p.send('quit'),p.get(),p.get()]
    assert events[0]['event']=='work_finished' and events[-1]['event']=='bye',events
    assert all(v is True for k,v in events[-1].items() if k!='event'),events[-1]
    p.wait();out.setdefault('target_cleanups',[]).append(events[-1])
  if drop:
   x['target'].p._handle.Close();x['bridge'].p._handle.Close()
 def publish(x,n=8):
  s=x['target'].send(f'call {n} 32');assert s['published']==n,s
  r=x['bridge'].send('read');assert r['reason']=='ok' and len(r['records'])==n,r;return r['records']
 def acknowledge(x,r):
  a=r['ack'];good(x['bridge'].send(f"ack {a['epoch']} {a['seq']} {a['generation']}"))
 def close(p,x,**kw):return cmd(p,'reconcile',epoch=x['epoch'],**kw)
 try:
  assert EXE.exists() and LEDGER.exists() and LEDGER.with_name('session_target_binding.py').exists(),'session reconciliation implementation missing'
  q=receiver();x=target();ep=x['epoch']
  if name=='binding_reject':bad(cmd(q,'begin',epoch=ep,target=dict(pid=x['binding']['pid'],created=x['binding']['created']+1)),'binding_mismatch')
  good(cmd(q,'begin',epoch=ep,target=x['binding']))
  batch=publish(x)
  if name=='live_refusal':bad(close(q,x),'target_alive');assert good(cmd(q,'snapshot'))['sessions'][0]['state']=='active';stop(x)
  elif name in ('unknown_tail','binding_reject'):stop(x)
  elif name=='observed_discard':
   good(cmd(q,'observe',epoch=ep,records=batch));good(cmd(q,'accept',epoch=ep,records=batch[:3]));stop(x,kill=True)
  elif name=='commit_ack_lost':
   assert cmd(q,'accept',epoch=ep,records=batch,checkpoint='after_commit')==dict(event='checkpoint',stage='after_commit')
   q.kill();q=receiver();r=good(cmd(q,'accept',epoch=ep,records=batch));assert r['added']==0 and r['duplicates']==8,r
   acknowledge(x,r);stop(x)
  elif name in ('terminal_replay','old_epoch','conflicting_replay'):
   good(cmd(q,'accept',epoch=ep,records=batch));stop(x)
  elif name in ('close_before_crash','close_after_crash'):
   good(cmd(q,'observe',epoch=ep,records=batch));good(cmd(q,'accept',epoch=ep,records=batch[:3]));stop(x)
   point='before_commit' if name=='close_before_crash' else 'after_commit'
   assert close(q,x,checkpoint=point)==dict(event='checkpoint',stage=point)
   q.kill();q=receiver();snap=good(cmd(q,'snapshot'));out['after_crash']=snap
   assert snap['sessions'][0]['state']==('active' if point=='before_commit' else 'ended'),snap
   assert len(snap['endings'])==(0 if point=='before_commit' else 1),snap
  elif name=='busy':
   stop(x);blocker=sqlite3.connect(db,timeout=0);blocker.execute('BEGIN IMMEDIATE')
   bad(close(q,x),'busy');blocker.rollback();blocker.close();blocker=None
  elif name=='storage_full':
   stop(x);good(cmd(q,'limit_pages'));r=bad(close(q,x),'storage_error');assert r['sqlite_code']&255==sqlite3.SQLITE_FULL,r
   snap=good(cmd(q,'snapshot'));assert snap['sessions'][0]['state']=='active' and not snap['endings'],snap
   good(cmd(q,'unlimit_pages'))
  elif name=='accept_race':
   assert cmd(q,'accept',epoch=ep,records=batch,checkpoint='before_commit')==dict(event='checkpoint',stage='before_commit')
   stop(x);other=receiver();bad(close(other,x),'busy');good(q.send('resume'));q=other
  elif name=='close_race':
   stop(x);assert close(q,x,checkpoint='before_commit')==dict(event='checkpoint',stage='before_commit')
   other=receiver();bad(cmd(other,'accept',epoch=ep,records=batch),'busy');good(q.send('resume'));q=other
  elif name=='unknown_probe':
   stop(x);q.cleanup();q=receiver('probe_unknown');bad(close(q,x),'binding_unknown')
   assert good(cmd(q,'snapshot'))['sessions'][0]['state']=='active';q.cleanup();q=receiver()
  elif name=='absent_restart':
   stop(x,drop=True);q.cleanup();q=receiver()
  elif name in ('recovery_restart','recovery_live'):
   good(cmd(q,'observe',epoch=ep,records=batch));good(cmd(q,'accept',epoch=ep,records=batch[:3]))
   q.kill()
   if name=='recovery_restart':stop(x,drop=True)
   recovery=spawn(sys.executable,['-u',str(LEDGER.with_name('session_reconcile_recovery.py')),'--database',str(db)],'recovery')
   result=recovery.get();recovery.wait();out['recovery']=result
   assert result['outcome']==('ended' if name=='recovery_restart' else 'deferred'),result
   if name=='recovery_restart':
    again=spawn(sys.executable,['-u',str(LEDGER.with_name('session_reconcile_recovery.py')),'--database',str(db)],'recovery')
    assert again.get()==dict(event='recovery',outcome='no_active_session');again.wait()
   if name=='recovery_live':assert result['reason']=='target_alive';stop(x)
   q=receiver()
  terminal=good(close(q,x));out['terminal']=terminal
  assert terminal['state']=='ended' and terminal['tail_unknown'] is True,terminal
  assert terminal['committed_last_seq']==(3 if name in ('observed_discard','close_before_crash','close_after_crash','recovery_restart','recovery_live') else 8 if name in ('commit_ack_lost','terminal_replay','old_epoch','conflicting_replay','accept_race') else 0),terminal
  expected_discard=5 if name in ('observed_discard','close_before_crash','close_after_crash','recovery_restart','recovery_live') else 0
  assert terminal['discarded_observed']==expected_discard,terminal
  if expected_discard:assert (terminal['discarded_from'],terminal['discarded_to'])==(4,8),terminal
  assert good(close(q,x))==terminal,'terminal reconciliation must be idempotent'
  bad(cmd(q,'accept',epoch=ep,records=batch),'closed')
  if name in ('terminal_replay','conflicting_replay'):
   replay=good(cmd(q,'replay',epoch=ep,records=batch));assert replay['duplicates']==8 and replay['ack'] is None and replay['read_only'] is True,replay
   altered=[dict(v) for v in batch];altered[0].update(id=33,a=33^0xa5a5a5a5,b=40,c=99)
   bad(cmd(q,'replay',epoch=ep,records=altered),'conflict')
  elif name=='observed_discard':bad(cmd(q,'replay',epoch=ep,records=batch),'not_committed')
  if name=='old_epoch':
   y=target();good(cmd(q,'begin',epoch=y['epoch'],target=y['binding']))
   bad(cmd(q,'begin',epoch=ep,target=y['binding']),'epoch_used')
   bad(cmd(q,'accept',epoch=ep,records=batch),'closed')
   snap=good(cmd(q,'snapshot'));assert snap['active']==y['epoch'],snap
   stop(y);good(close(q,y))
  out['snapshot']=good(cmd(q,'snapshot'));assert out['snapshot']['active'] is None
  assert all(s['state']=='ended' for s in out['snapshot']['sessions'])
  out['passed']=True
 except Exception as exc:out['error']=repr(exc);out['traceback']=traceback.format_exc()
 finally:
  if blocker:blocker.rollback();blocker.close()
  for x in targets:
   try:stop(x)
   except Exception as exc:out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(exc))
  for p in reversed(children):
   try:
    if p.p.poll() is None:p.cleanup()
    else:p.wait(None)
   except Exception as exc:
    out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(exc))
    if p.p.poll() is None:p.kill()
   if not p.p.stdin.closed:p.p.stdin.close()
   p.reader.join(timeout=1)
   while True:
    try:log.append(dict(action='unread',pid=p.p.pid,line=p.lines.get_nowait()))
    except queue.Empty:break
   if not p.p.stdout.closed:p.p.stdout.close()
  out['processes']=[dict(pid=p.p.pid,role=p.role,exit=p.p.returncode) for p in children]
  out['seconds']=time.perf_counter()-start
  out['files']={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
  save(folder/'result.json',out)
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',action='append',choices=CASES);ap.add_argument('--repeat',type=int,default=1)
 ap.add_argument('--mode',default='exact',choices=['exact','assume_dead','accept_terminal','zero_tail','skip_replay_match']);a=ap.parse_args()
 assert 1<=a.repeat<=3
 run=C/('run-'+uuid.uuid4().hex[:12]);run.mkdir(parents=True);hashes={}
 for p in [*[Path(__file__).with_name(n) for n in SOURCES],EXE]:
  if p.exists():shutil.copyfile(p,run/p.name);hashes[p.name]=sha(p)
 cases=[]
 for i,n in enumerate((a.case or CASES)*a.repeat):
  x=case(n,a.mode,run/f'{i:03d}-{n}');cases.append(x)
  save(run/'results.json',dict(source_hashes=hashes,cases=cases,total=len(cases),passed=sum(x['passed'] for x in cases),mode=a.mode))
  print(json.dumps(dict(run=run.name,case=n,passed=x['passed'],error=x.get('error'),cleanup_errors=x.get('cleanup_errors'))),flush=True)
 return int(not all(x['passed'] for x in cases))
if __name__=='__main__':raise SystemExit(main())
