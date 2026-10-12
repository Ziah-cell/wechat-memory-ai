"""Real owned mapping WRITE AVs, raw partial state and durable delivery checks."""
import argparse,ctypes,hashlib,json,queue,shutil,sqlite3,sys,time,traceback,uuid
from pathlib import Path
from test_resident_publisher import Child
from test_autonomous_relay import K,bind_handle
R=Path(__file__).resolve().parents[2];C=R/'data/shared-write-20261012';EXE=C/'shared_write_fixture.exe'
CASES=['healthy',*[f'first_{n}' for n in range(7)],*[f'reuse_{n}' for n in range(7)],'other_site','other_address','nested_original','controller_loss']
SOURCES=['shared_write_fixture.c','shared_write_hook.inc','shared_write_protocol.h','shared_write_sites.S','shared_write_ledger.py','shared_write_relay.py','shared_write_controller.py','test_shared_write.py',
 'session_target_binding.py','target_lifetime_ledger.py','target_lifetime_controller.py','autonomous_relay.py','test_resident_publisher.py','test_autonomous_relay.py',
 'executed_trampoline_fixture.c','capture_copy_site.S','trampoline_register_caller.S']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()] if p.exists() else []
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8',newline='\n')
def payload(n):return [n,n^0xa5a5a5a5,n+7,n*3]
def partial(point,prior):
 stamp=2 if prior else 0;seq=prior;words=payload(prior) if prior else [0]*4;next_seq=9 if prior else 1;new=payload(next_seq)
 if point>0:stamp=next_seq*2-1
 if point>1:seq=next_seq
 for i in range(4):
  if point>i+2:words[i]=new[i]
 return dict(stamp=stamp,seq=seq,words=words)
def run_case(name,mode,folder):
 folder.mkdir();logs=[];handles=[];controller=None;out=dict(case=name,mode=mode,passed=False,observations=logs);start=time.perf_counter()
 point=int(name.rsplit('_',1)[1]) if name.startswith(('first_','reuse_')) else 6 if name=='controller_loss' else -1 if name in ('healthy','nested_original') else 3
 fault_input=9 if name.startswith('reuse_') or name=='controller_loss' else 1
 kind={'other_site':1,'other_address':2,'nested_original':3}.get(name,0)
 cfg=dict(epoch=uuid.uuid4().hex,mapping='Local\\VXOwnPublisher-'+uuid.uuid4().hex,lease=uuid.uuid4().hex,count=24,delay=40,point=point,input=fault_input,kind=kind,mode=mode);save(folder/'config.json',cfg)
 def bind(role,info):
  g=dict(role=role,pid=info['pid'],created=info['created'],handle=bind_handle(info['pid'],info['created']));handles.append(g);return g
 def wait(g,ms=15000):
  assert K.WaitForSingleObject(g['handle'],ms)==0,(g['role'],'still_alive')
  code=ctypes.c_ulong();assert K.GetExitCodeProcess(g['handle'],ctypes.byref(code));g['exit']=code.value;return code.value
 try:
  controller=Child(sys.executable,['-u',str(Path(__file__).with_name('shared_write_controller.py')),'--exe',str(EXE),'--folder',str(folder)],logs)
  ready=controller.get();assert ready['event']=='prepared',ready;out['prepared']=ready;target=bind('target',ready['target'])
  for role,info in ready['helpers'].items():bind(role,info)
  assert controller.send('start')['event']=='armed';out['started_at_ns']=time.perf_counter_ns()
  if name=='controller_loss':assert K.WaitForSingleObject(target['handle'],0)==258;controller.kill()
  for g in handles:assert wait(g)==0,(g['role'],g['exit'])
  events=rows(folder/'target.jsonl');out['target_events']=events
  status=next(x for x in reversed(events) if x.get('event')=='status');write=next(x for x in events if x.get('event')=='write_status');bye=next(x for x in events if x.get('event')=='bye')
  out.update(final=status,write=write,cleanup=bye)
  code=next(x for x in events if x.get('event')=='write_site');assert code==dict(event='write_site',span=3,bytes=[0x48,0x87,0x11]),code
  assert all(v is True for k,v in bye.items() if k!='event'),bye
  assert status['errors']==0 and status['depth']==0 and status['gate']==0,status
  assert write['depth_clear']==24 and write['armed_clear']==24,write
  expected=23 if name=='nested_original' else 24;assert status['original']==expected and status['hook_returns']==expected,status
  if name=='healthy':
   assert write['seen']==0 and write['outer_caught']==0 and write['work_returns']==24,write;wanted=24
  elif name=='nested_original':
   assert write['seen']==1 and write['handled']==0 and write['outer_caught']==1 and write['work_returns']==23,write
   assert write['operation']==0 and write['site']==2 and status['nested_skips']==1,write;wanted=23
  else:
   assert write['seen']==1 and write['code']==0xc0000005 and write['operation']==1 and write['field']==point,write
   assert write['control_protection']==4 and write['record_protection']==(4 if kind==2 else 2),write
   assert write['site']==(1 if kind==1 else 0),write
   assert write['address_offset']==(-1 if kind==2 else [0,8,16,24,32,40,0][point]),write
   rejected=kind in (1,2)
   assert write['handled']==(0 if rejected else 1) and write['outer_caught']==(1 if rejected else 0) and write['work_returns']==(23 if rejected else 24),write
   assert status['state']==6,status;wanted=8 if fault_input==9 else 0
   expected_partial=partial(point,1 if fault_input==9 else 0)
   assert {k:write[k] for k in expected_partial}==expected_partial,(write,expected_partial)
  assert status['published']==wanted and status['acked']==wanted,status
  if name=='controller_loss':
   loss=next(i for i,x in enumerate(events) if x.get('event')=='controller_lost');assert events[loss+1]['original']<24;out['at_controller_loss']=events[loss+1]
  files=list(folder.glob('ledger.sqlite3*'));before={p.name:sha(p) for p in files}
  # Verification reads a complete copy, never the original database or WAL.
  import tempfile
  with tempfile.TemporaryDirectory(prefix='vx-write-test-') as temp:
   dest=Path(temp)
   for p in files:shutil.copyfile(p,dest/p.name)
   db=sqlite3.connect((dest/'ledger.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
   snap=dict(integrity=db.execute('PRAGMA integrity_check').fetchone()[0],sessions=[dict(x) for x in db.execute('SELECT * FROM sessions')],
    inbox=[dict(x) for x in db.execute('SELECT * FROM inbox ORDER BY seq')],endings=[json.loads(x[0]) for x in db.execute('SELECT detail FROM endings')],active=db.execute('SELECT epoch FROM control').fetchone()[0]);db.close()
  assert before=={p.name:sha(p) for p in files};out['database']=snap
  assert snap['integrity']=='ok' and snap['active'] is None and len(snap['endings'])==1 and snap['sessions'][0]['state']=='ended',snap
  assert len(snap['inbox'])==wanted and snap['endings'][0]['committed_last_seq']==wanted and snap['endings'][0]['tail_unknown'],snap
  assert [json.loads(r['payload'])['id'] for r in snap['inbox']]==list(range(2,25) if name=='nested_original' else range(1,wanted+1)),snap
  receipts=set();acks=0
  for e in rows(folder/'relay-journal.jsonl'):
   if e['action']=='receive' and e.get('line'):
    r=json.loads(e['line'])
    if r.get('ok') and r.get('ack'):
     a=r['ack'];receipts.add((a['epoch'],a['seq'],a['generation']))
    if r.get('event')=='ack' and r.get('ok'):acks+=1
   if e['action']=='send' and e['command'].startswith('ack '):
    _,ep,seq,gen=e['command'].split();assert (ep,int(seq),int(gen)) in receipts,e
  out['successful_acks']=acks;out['passed']=True
 except Exception as exc:out['error']=repr(exc);out['traceback']=traceback.format_exc()
 finally:
  for g in handles:
   if K.WaitForSingleObject(g['handle'],0)!=0:out['passed']=False;out.setdefault('containment',[]).append(g['role']);K.TerminateProcess(g['handle'],91)
   try:wait(g,8000)
   except Exception as exc:out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(exc))
   K.CloseHandle(g['handle']);g.pop('handle')
  if controller:
   try:
    if controller.p.poll() is None:controller.cleanup()
    else:controller.wait(None)
   except Exception as exc:
    out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(exc))
    if controller.p.poll() is None:controller.kill()
   if not controller.p.stdin.closed:controller.p.stdin.close()
   controller.reader.join(timeout=1)
   while True:
    try:logs.append(dict(action='unread',pid=controller.p.pid,line=controller.lines.get_nowait()))
    except queue.Empty:break
   if not controller.p.stdout.closed:controller.p.stdout.close()
   handles.append(dict(role='controller',pid=controller.p.pid,exit=controller.p.returncode))
  out['processes']=handles;out['target_events']=rows(folder/'target.jsonl');out['seconds']=time.perf_counter()-start
  out['files']={p.name:sha(p) for p in folder.iterdir() if p.is_file()};save(folder/'result.json',out)
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',choices=CASES,action='append');ap.add_argument('--repeat',type=int,default=1)
 ap.add_argument('--mode',choices=['exact','old_read_guard','broad','leak_gate','publish_early'],default='exact');a=ap.parse_args();assert 1<=a.repeat<=3
 run=C/('run-'+uuid.uuid4().hex[:12]);run.mkdir();hashes={}
 for p in [*[Path(__file__).with_name(n) for n in SOURCES],EXE,C/'build.json']:shutil.copyfile(p,run/p.name);hashes[p.name]=sha(p)
 build=load(C/'build.json');assert sha(EXE)==build['exe_sha256']
 for n,h in build['source_hashes'].items():assert sha(Path(__file__).with_name(n))==h,n
 cases=[]
 for i,name in enumerate((a.case or CASES)*a.repeat):
  x=run_case(name,a.mode,run/f'{i:03d}-{name}');cases.append(x);save(run/'results.json',dict(source_hashes=hashes,cases=cases,total=len(cases),passed=sum(x['passed'] for x in cases),mode=a.mode))
  print(json.dumps(dict(run=run.name,case=name,passed=x['passed'],error=x.get('error'),cleanup_errors=x.get('cleanup_errors'))),flush=True)
 return int(not all(x['passed'] for x in cases))
if __name__=='__main__':raise SystemExit(main())
