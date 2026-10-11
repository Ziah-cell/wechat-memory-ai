"""Real nested-controller loss; observer owns no target control handle.

Every attempted run gets a new archive, including failures. Failed fixtures may
be terminated to contain the experiment, but that makes the case fail.
"""
import argparse,ctypes,hashlib,json,queue,shutil,sqlite3,subprocess,sys,time,traceback,uuid
from pathlib import Path
from test_resident_publisher import Child
from test_autonomous_relay import K,bind_handle
K.GetTickCount64.restype=ctypes.c_ulonglong

R=Path(__file__).resolve().parents[2];C=R/'data/target-lifetime-20261012'
EXE=C/'target_lifetime_fixture.exe'
CASES=['kill','exit','eof','alive','bootstrap_eof','before_commit','after_commit','all_before','all_after','acked']
SOURCES=['test_target_lifetime.py','target_lifetime_fixture.c','target_lifetime_controller.py','target_lifetime_relay.py','target_lifetime_ledger.py',
 'autonomous_relay_hook.inc','sustained_ring_protocol.h','executed_trampoline_fixture.c','capture_copy_site.S','trampoline_register_caller.S',
 'test_resident_publisher.py','test_autonomous_relay.py','autonomous_relay.py']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def run_case(name,mode,folder):
 folder.mkdir();logs=[];handles=[];controller=None
 cfg=dict(epoch=uuid.uuid4().hex,mapping='Local\\VXOwnPublisher-'+uuid.uuid4().hex,count=128,delay=20)
 write(folder/'config.json',cfg)
 out=dict(case=name,mode=mode,passed=False,observations=logs);start=time.perf_counter()
 def bind(role,info):
  h=bind_handle(info['pid'],info['created']);handles.append(dict(role=role,pid=info['pid'],created=info['created'],handle=h))
 def waited(g,timeout):
  assert K.WaitForSingleObject(g['handle'],timeout)==0,(g['role'],'still_alive')
  code=ctypes.c_ulong();assert K.GetExitCodeProcess(g['handle'],ctypes.byref(code))
  g['exit']=code.value;g['observed_exit_ns']=time.perf_counter_ns()
  return code.value
 try:
  assert EXE.exists(),'target lifetime implementation missing'
  controller=Child(sys.executable,['-u',str(Path(__file__).with_name('target_lifetime_controller.py')),
    '--exe',str(EXE),'--folder',str(folder),'--case',name,'--mode',mode],logs)
  ready=controller.get();out['prepared']=ready;assert ready['event']=='prepared',ready
  bind('target',ready['target'])
  for role in ('relay','bridge','ledger'):
   if role in ready['helpers']:bind(role,ready['helpers'][role])
  out['armed']=controller.send('start');assert out['armed']['event']=='armed',out['armed']
  # Target must still be alive before the controlled loss; retain its identity handle.
  if name!='bootstrap_eof':assert K.WaitForSingleObject(handles[0]['handle'],0)==258
  out['fault_at_ns']=time.perf_counter_ns()
  if name in ('kill','before_commit','after_commit','all_before','all_after','acked'):
   if name.startswith('all_'):
    # Kill every external worker first, request controller termination last.
    # No order/simultaneity guarantee is claimed; all handles are creation-bound.
    for g in handles[1:]:assert K.TerminateProcess(g['handle'],1)
   controller.kill()
  elif name=='exit':
   controller.p.stdin.write('exit\n');controller.p.stdin.flush();controller.wait()
  elif name=='eof':assert controller.send('eof')==dict(event='eof_sent')
  for g in handles[1:]:waited(g,12000)
  out['helpers_exited_at_ns']=time.perf_counter_ns()
  out['helpers_exited_tick_ms']=K.GetTickCount64()
  # No commands, close notifications, or reaping signals go to the target here.
  target_exit=waited(handles[0],18000)
  out['target_events']=events=rows(folder/'target.jsonl')
  finish_index=next(i for i,x in enumerate(events) if x.get('event')=='work_finished')
  final=events[finish_index+1];out['final']=final
  bye=next(x for x in events if x.get('event')=='bye');out['cleanup']=bye
  expected=0 if name=='bootstrap_eof' else cfg['count']+(8 if name=='acked' else 0)
  assert final['original']==expected,('premature_original_stop',final,expected)
  assert final['hook_returns']==expected and final['errors']==0 and final['depth']==0,final
  assert final['gate']==0,final
  assert all(bye.get(k) is True for k in ['prefix_restored','table_deleted','lookups_absent','freed','mapping_closed','guard_freed','threads_joined']),bye
  assert target_exit==0,target_exit
  if name in ('kill','exit','before_commit','after_commit','all_before','all_after','acked'):
   lost_index=next(i for i,x in enumerate(events) if x.get('event')=='controller_lost')
   lost=next(x for x in events[lost_index+1:] if x.get('event')=='status');out['at_controller_loss']=lost
   assert lost['original']<expected and final['original']>lost['original'],(lost,final)
   assert any(x.get('event')=='progress' and x['tick_ms']>out['helpers_exited_tick_ms'] for x in events),'no original progress after external workers exited'
  if name in ('eof','alive','bootstrap_eof'):
   assert controller.p.poll() is None,'controller must remain alive through target exit'
   assert not any(x.get('event')=='controller_lost' for x in events)
  if name!='bootstrap_eof':
   assert final['state']==4 and final['gap']==final['original']-final['published'],final
   assert final['published']==(16 if name=='acked' else 8),final
   assert final['acked']==(8 if name=='acked' else 0),final
  if (folder/'ledger.sqlite3').exists():
   # Database is inspected only after every writer has exited. This is recovery
   # observation, not an external stop or cleanup that can make target exit.
   db=sqlite3.connect('file:'+str(folder/'ledger.sqlite3').replace('\\','/')+'?mode=ro',uri=True)
   snapshot=dict(integrity=db.execute('PRAGMA integrity_check').fetchone()[0],rows=db.execute('SELECT count(*) FROM inbox').fetchone()[0],sessions=db.execute('SELECT state,last_seq,stop_op FROM sessions').fetchall())
   db.close();out['database']=snapshot
   expected_rows=8 if name=='acked' else out['armed']['checkpoint']['batch_size'] if name in ('after_commit','all_after') else 0
   assert snapshot['integrity']=='ok' and snapshot['rows']==expected_rows,(snapshot,expected_rows)
   # Application session remains active after process loss; do not invent STOP.
   assert all(s[0]=='active' and s[2] is None for s in snapshot['sessions']),snapshot
  out['passed']=True
 except Exception as exc:out['error']=repr(exc);out['traceback']=traceback.format_exc()
 finally:
  for g in handles:
   if K.WaitForSingleObject(g['handle'],0)!=0:
    # Containment only on failure, never counted as autonomous cleanup.
    out['passed']=False;out.setdefault('containment',[]).append(g['role']);K.TerminateProcess(g['handle'],91)
   try:waited(g,8000)
   except Exception as exc:out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(exc))
   K.CloseHandle(g['handle']);g.pop('handle')
  if controller:
   if controller.p.poll() is None:
    controller.p.stdin.write('quit\n');controller.p.stdin.flush()
    try:controller.wait()
    except Exception as exc:out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(exc));controller.kill()
   out['controller_exit']=controller.p.returncode
   controller.reader.join(timeout=1)
   while True:
    try:logs.append(dict(action='unread_controller_output',line=controller.lines.get_nowait()))
    except queue.Empty:break
   if not controller.p.stdin.closed:controller.p.stdin.close()
   controller.p.stdout.close()
  out['processes']=handles
  out['target_events']=rows(folder/'target.jsonl')
  out['seconds']=time.perf_counter()-start
  out['files']={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
  write(folder/'result.json',out)
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',choices=CASES,action='append');ap.add_argument('--repeat',type=int,default=1)
 ap.add_argument('--mode',choices=['owned','legacy_eof','stop_on_loss','keep_table'],default='owned');a=ap.parse_args()
 assert 1<=a.repeat<=3
 run=C/('run-'+uuid.uuid4().hex[:12]);run.mkdir(parents=True);hashes={}
 for p in [*[Path(__file__).with_name(n) for n in SOURCES],EXE,C/'build.json']:
  if p.exists():shutil.copyfile(p,run/p.name);hashes[p.name]=sha(p)
 if EXE.exists():
  b=json.loads((C/'build.json').read_text());assert sha(EXE)==b['exe_sha256']
  for n,h in b['source_hashes'].items():assert sha(Path(__file__).with_name(n))==h,n
 cases=[]
 for i,n in enumerate((a.case or CASES)*a.repeat):
  x=run_case(n,a.mode,run/f'{i:03d}-{n}');cases.append(x)
  print(json.dumps(dict(case=n,passed=x['passed'],error=x.get('error'),run=run.name)),flush=True)
  write(run/'results.json',dict(source_hashes=hashes,cases=cases,total=len(cases),passed=sum(x['passed'] for x in cases),mode=a.mode))
 return int(not all(x['passed'] for x in cases))
if __name__=='__main__':raise SystemExit(main())
