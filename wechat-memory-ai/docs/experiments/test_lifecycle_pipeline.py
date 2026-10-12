"""Real owned-process lifecycle faults; preserve every attempt and raw output."""
import argparse,ctypes,hashlib,json,queue,shutil,sqlite3,sys,time,traceback,uuid
from pathlib import Path
from test_resident_publisher import Child
from test_autonomous_relay import K,bind_handle
R=Path(__file__).resolve().parents[2];C=R/'data/lifecycle-pipeline-20261012';EXE=C/'lifecycle_pipeline_fixture.exe'
CASES=['normal','controller_loss','receiver_before','receiver_after','relay_before','relay_after','all_before','all_after','db_busy','db_deadline','storage_full','terminal_restart','lease']
SOURCES=['lifecycle_pipeline_fixture.c','lifecycle_pipeline_ledger.py','lifecycle_pipeline_relay.py','lifecycle_pipeline_controller.py','test_lifecycle_pipeline.py',
 'session_target_binding.py','target_lifetime_ledger.py','target_lifetime_controller.py','autonomous_relay.py','test_resident_publisher.py','test_autonomous_relay.py',
 'autonomous_relay_hook.inc','sustained_ring_protocol.h','executed_trampoline_fixture.c','capture_copy_site.S','trampoline_register_caller.S']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def ack_order(folder):
 count=duplicates=0
 for p in sorted(folder.glob('relay-*-journal.jsonl')):
  receipts=set()
  for e in rows(p):
   if e['action']=='receive' and e.get('line'):
    r=json.loads(e['line'])
    if r.get('ok') and r.get('ack'):
     a=r['ack'];receipts.add((a['epoch'],a['seq'],a['generation']));duplicates+=r.get('duplicates',0)
   if e['action']=='send' and e['command'].startswith('ack '):
    _,epoch,seq,gen=e['command'].split();assert (epoch,int(seq),int(gen)) in receipts,('ack_before_receipt',p.name,e);count+=1
 return dict(commands=count,duplicates=duplicates)
def run_case(name,mode,folder):
 folder.mkdir();log=[];handles=[];children=[];blocker=None;out=dict(case=name,mode=mode,passed=False,observations=log)
 start=time.perf_counter();cfg=dict(epoch=uuid.uuid4().hex,mapping='Local\\VXOwnPublisher-'+uuid.uuid4().hex,lease=uuid.uuid4().hex,count=64,delay=40);save(folder/'config.json',cfg)
 def spawn(exe,args,role):
  p=Child(exe,args,log);p.role=role;children.append(p);return p
 def bind(role,info):
  g=dict(role=role,pid=info['pid'],created=info['created'],handle=bind_handle(info['pid'],info['created']));handles.append(g);return g
 def helpers(info):return {role:bind(role,x) for role,x in info.items()}
 def wait(g,ms=15000):
  assert K.WaitForSingleObject(g['handle'],ms)==0,(g['role'],'still_alive')
  code=ctypes.c_ulong();assert K.GetExitCodeProcess(g['handle'],ctypes.byref(code));g['exit']=code.value;g['exit_observed_ns']=time.perf_counter_ns();return code.value
 def end(gs):
  for g in gs:
   assert K.WaitForSingleObject(g['handle'],0)==258,(g['role'],'already exited');assert K.TerminateProcess(g['handle'],1)
  for g in gs:wait(g)
 def recovery(target):
  args=['-u',str(Path(__file__).with_name('lifecycle_pipeline_relay.py')),'--exe',str(EXE)]
  for key in ['mapping','epoch','lease']:args+=['--'+key,cfg[key]]
  args+=['--target-pid',str(target['pid']),'--target-created',str(target['created']),'--database',str(folder/'ledger.sqlite3'),'--journal',str(folder/'relay-recovery-journal.jsonl')]
  p=spawn(sys.executable,args,'recovery');r=p.get();assert r['event']=='ready',r;new=helpers(r['helpers'])
  assert p.send('start')['event']=='started';terminal=p.get();assert terminal.get('outcome')=='ended',terminal;p.wait();out['recovery']=terminal
  for g in new.values():assert wait(g)==0
 try:
  if name=='lease':
   K.GetCurrentProcess.restype=ctypes.c_void_p;ts=[ctypes.c_ulonglong() for _ in range(4)];assert K.GetProcessTimes(K.GetCurrentProcess(),*[ctypes.byref(t) for t in ts])
   target=spawn(EXE,['target',cfg['mapping'],cfg['epoch'],'owned_skip_lease' if mode=='skip_lease' else 'owned',str(__import__('os').getpid()),str(ts[0].value),cfg['lease']],'target')
   tr=target.get();assert tr['event']=='ready'
   def bridge(token):return spawn(EXE,['bridge',cfg['mapping'],cfg['epoch'],str(tr['pid']),str(tr['created']),token],'bridge')
   b=bridge(cfg['lease']);assert b.get()['event']=='ready';assert b.send('detach')['event']=='detached'
   live=bridge(cfg['lease']);assert live.get()==dict(event='error',reason='lease_binding',detail=6);live.wait(29)
   b.send('quit');b.wait()
   wrong=bridge('0'*32);assert wrong.get()==dict(event='error',reason='lease_binding',detail=7);wrong.wait(29)
   b=bridge(cfg['lease']);assert b.get()['event']=='ready'
   assert target.send('work 8 0')['event']=='started';events=[]
   while not events or events[-1].get('event')!='bye':events.append(target.get())
   target.wait();b.send('quit');b.wait();out['target_events']=events
   assert events[-2]['original']==8 and all(v is True for k,v in events[-1].items() if k!='event');out['passed']=True
  else:
   controller=spawn(sys.executable,['-u',str(Path(__file__).with_name('lifecycle_pipeline_controller.py')),'--exe',str(EXE),'--folder',str(folder),'--case',name,'--mode',mode],'controller')
   r=controller.get();assert r['event']=='prepared',r;out['prepared']=r;target=bind('target',r['target']);hs=helpers(r['helpers'])
   if name in ('db_busy','db_deadline'):blocker=sqlite3.connect(folder/'ledger.sqlite3',timeout=0);blocker.execute('BEGIN IMMEDIATE')
   armed=controller.send('start');assert armed['event']=='armed',armed;out['armed']=armed
   assert K.WaitForSingleObject(target['handle'],0)==258,'target ended before fault';out['fault_at_ns']=time.perf_counter_ns()
   if name=='controller_loss':controller.kill()
   elif name.startswith('receiver_'):end([hs['ledger']]);assert controller.send('resume')['event']=='resumed'
   elif name.startswith('relay_'):
    end(list(hs.values()));r=controller.send('restart');assert r['event']=='restarted',r;out['restart']=r;hs=helpers(r['helpers'])
   elif name.startswith('all_'):end(list(hs.values()));controller.kill();out['all_external_exited_ns']=time.perf_counter_ns()
   assert wait(target)==0
   events=rows(folder/'target.jsonl');out['target_events']=events
   idx=next(i for i,x in enumerate(events) if x.get('event')=='work_finished');final=events[idx+1];bye=events[idx+2];out['final']=final;out['cleanup']=bye
   assert final['original']==cfg['count'] and final['hook_returns']==cfg['count'] and final['errors']==0 and final['depth']==0 and final['gate']==0,final
   assert all(v is True for k,v in bye.items() if k!='event') and bye['event']=='bye',bye
   assert final['gap']==cfg['count']-final['published'],final
   if name=='controller_loss' or name.startswith('all_'):
    idx=next(i for i,x in enumerate(events) if x.get('event')=='controller_lost');loss=events[idx+1];assert loss['original']<final['original'],(loss,final);out['at_controller_loss']=loss
   if blocker and name!='db_deadline':blocker.rollback();blocker.close();blocker=None;out['lock_released_after_target_exit']=True
   for g in hs.values():wait(g)
   if blocker:blocker.rollback();blocker.close();blocker=None;out['lock_released_after_relay_exit']=True
   if name=='storage_full':
    assert hs['relay']['exit']==2,hs
    deferred=rows(folder/'relay-0.jsonl')[-1];assert deferred['event']=='deferred' and 'storage_error' in deferred['reason'],deferred;out['deferred']=deferred;assert final['acked']==0,final
   elif name=='db_deadline':
    assert hs['relay']['exit']==2,hs
    deferred=rows(folder/'relay-0.jsonl')[-1];assert deferred['event']=='deferred' and 'deadline' in deferred['reason'],deferred;out['deferred']=deferred;assert final['acked']==0,final
   elif not name.startswith('all_'):assert hs['relay']['exit']==0,hs
   if name.startswith('all_') or name in ('storage_full','db_deadline','terminal_restart'):recovery(out['prepared']['target'])
   db=sqlite3.connect((folder/'ledger.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
   snap=dict(integrity=db.execute('PRAGMA integrity_check').fetchone()[0],sessions=[dict(s) for s in db.execute('SELECT * FROM sessions')],endings=[json.loads(s[0]) for s in db.execute('SELECT detail FROM endings')],rows=db.execute('SELECT count(*) FROM inbox').fetchone()[0],active=db.execute('SELECT epoch FROM control').fetchone()[0]);db.close();out['database']=snap
   assert snap['integrity']=='ok' and snap['active'] is None and len(snap['endings'])==1 and snap['sessions'][0]['state']=='ended',snap
   terminal=snap['endings'][0];assert terminal['tail_unknown'] and terminal['committed_last_seq']==snap['rows'] and terminal['discarded_observed']==terminal['observed_hi']-snap['rows'],terminal
   assert final['acked']<=snap['rows']<=final['published'],(final,snap)
   if name in ('normal','controller_loss','terminal_restart'):assert snap['rows']==cfg['count'] and final['acked']==cfg['count'],(final,snap)
   if name in ('all_before','db_busy','db_deadline','storage_full'):assert snap['rows']==0,snap
   if name=='all_after':assert snap['rows']==armed['checkpoint']['batch_size'],snap
   out['ack_order']=ack_order(folder)
   if name in ('receiver_after','relay_after'):assert out['ack_order']['duplicates']>0,out['ack_order']
   out['passed']=True
 except Exception as exc:out['error']=repr(exc);out['traceback']=traceback.format_exc()
 finally:
  if blocker:blocker.rollback();blocker.close()
  for g in handles:
   if K.WaitForSingleObject(g['handle'],0)!=0:out['passed']=False;out.setdefault('containment',[]).append(g['role']);K.TerminateProcess(g['handle'],91)
   try:wait(g,8000)
   except Exception as exc:out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(exc))
   K.CloseHandle(g['handle']);g.pop('handle')
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
  out['processes']=handles+[dict(role=p.role,pid=p.p.pid,exit=p.p.returncode) for p in children]
  if (folder/'target.jsonl').exists():out['target_events']=rows(folder/'target.jsonl')
  out['seconds']=time.perf_counter()-start;out['files']={p.name:sha(p) for p in folder.iterdir() if p.is_file()};save(folder/'result.json',out)
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',choices=CASES,action='append');ap.add_argument('--repeat',type=int,default=1)
 ap.add_argument('--mode',choices=['exact','early_ack','omit_terminal','skip_lease'],default='exact');a=ap.parse_args();assert 1<=a.repeat<=3
 run=C/('run-'+uuid.uuid4().hex[:12]);run.mkdir();hashes={}
 for p in [*[Path(__file__).with_name(n) for n in SOURCES],EXE,C/'build.json']:shutil.copyfile(p,run/p.name);hashes[p.name]=sha(p)
 build=json.loads((C/'build.json').read_text());assert sha(EXE)==build['exe_sha256']
 for n,h in build['source_hashes'].items():assert sha(Path(__file__).with_name(n))==h,n
 cases=[]
 for i,name in enumerate((a.case or CASES)*a.repeat):
  x=run_case(name,a.mode,run/f'{i:03d}-{name}');cases.append(x)
  save(run/'results.json',dict(source_hashes=hashes,cases=cases,total=len(cases),passed=sum(x['passed'] for x in cases),mode=a.mode))
  print(json.dumps(dict(run=run.name,case=name,passed=x['passed'],error=x.get('error'),cleanup_errors=x.get('cleanup_errors'))),flush=True)
 return int(not all(x['passed'] for x in cases))
if __name__=='__main__':raise SystemExit(main())
