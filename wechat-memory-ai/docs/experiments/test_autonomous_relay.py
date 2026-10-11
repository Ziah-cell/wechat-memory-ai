"""Owned autonomous target and fictional durable inbox only; preserve every attempt."""
import argparse,ctypes,hashlib,json,shutil,subprocess,sys,time,traceback,uuid
from pathlib import Path
from test_resident_publisher import Child

R=Path(__file__).resolve().parents[2];C=R/'data/autonomous-relay-20261011'
EXE=C/'autonomous_relay_fixture.exe';RELAY=Path(__file__).with_name('autonomous_relay.py');LEDGER=Path(__file__).with_name('autonomous_relay_ledger.py')
CASES=['autonomous','all_helpers_before','all_helpers_after','ack_loss','consumer_loss','db_busy',
       'late_batch','cursor_race','ack_range','peer','packet_target','packet_epoch','live_rebind','binding_pid','binding_creation',
       'ack_gate','publisher_gate','original_fault','reentrant_original_fault','reuse_order','reuse_recheck']
DEPENDENCIES=['autonomous_relay_fixture.c','autonomous_relay_hook.inc','autonomous_relay.py','autonomous_relay_ledger.py',
 'sustained_ring_fixture.c','sustained_ring_protocol.h','executed_trampoline_fixture.c','capture_copy_site.S','trampoline_register_caller.S','test_resident_publisher.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def good(x):assert x.get('ok') is True,x;return x
K=ctypes.WinDLL('kernel32',use_last_error=True)
K.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];K.OpenProcess.restype=ctypes.c_void_p
K.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.c_void_p]*4)]
K.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint];K.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];K.CloseHandle.argtypes=[ctypes.c_void_p]
K.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
def bind_handle(pid,created):
 h=K.OpenProcess(0x100001|0x1000,0,pid);assert h,ctypes.get_last_error()
 times=[ctypes.c_ulonglong() for _ in range(4)]
 assert K.GetProcessTimes(h,*[ctypes.byref(x) for x in times])
 assert times[0].value==created,(pid,created,times[0].value)
 return h

def run_case(name,mode,run,index):
 folder=run/f'{index:03d}-{name}';folder.mkdir();db=folder/'ledger.sqlite3'
 epoch=uuid.uuid4().hex;mapping='Local\\VXOwnPublisher-'+uuid.uuid4().hex
 logs=[];children=[];grands=[];target=bridge=ledger=relay=None;blocker=None;race=False;held=False
 out=dict(case=name,mode=mode,passed=False,observations=logs,database=db.relative_to(R).as_posix());start=time.perf_counter()
 def spawn(exe,args):
  p=Child(exe,args,logs);children.append(p);return p
 def cmd(p,op,**kw):return p.send(json.dumps(dict(op=op,**kw)))
 def new_ledger(begin=False):
  p=spawn(sys.executable,['-u',str(LEDGER),'--database',str(db)]);assert p.get()['synchronous']==2
  if begin:good(cmd(p,'begin',epoch=epoch))
  return p
 def new_bridge(pid=None,created=None):
  p=spawn(EXE,['bridge',mapping,epoch,str(pid or ready['pid']),str(created or ready['created'])]+(['skip_cursor'] if mode=='skip_cursor' else []));return p
 def bind(pinfo):return target.send(f"bind {pinfo['pid']} {pinfo['created']}")
 def ack(receipt,verb='ack',extra=''):
  a=receipt['ack'];return bridge.send(f"{verb} {a['epoch']} {a['seq']} {a['generation']} {extra}".strip())
 def batch():
  x=bridge.send('read');assert x['reason']=='ok',x;return x['records']
 def commit(b):return good(cmd(ledger,'accept',epoch=epoch,records=b))
 def new_relay(count,checkpoint=None):
  args=['-u',str(RELAY),'--exe',str(EXE),'--mapping',mapping,'--epoch',epoch,'--target-pid',str(ready['pid']),'--target-created',str(ready['created']),'--database',str(db),'--journal',str(folder/('relay-'+uuid.uuid4().hex[:8]+'.jsonl')),'--count',str(count)]
  if checkpoint:args+=['--checkpoint',checkpoint]
  if mode=='early_ack':args+=['--mode',mode]
  p=spawn(sys.executable,args);info=p.get();assert info['event']=='ready',info
  for role in ['bridge','ledger']:
   g=info[role];g['role']=role;g['handle']=bind_handle(g['pid'],g['created']);grands.append(g)
  good(bind(info['bridge']));assert p.send('start')==dict(event='started')
  return p,info
 def kill_all(p,info):
  stamps=[]
  for role in ['bridge','ledger']:
   g=next(g for g in grands if g['pid']==info[role]['pid'])
   assert K.TerminateProcess(g['handle'],1)
   stamps.append(time.perf_counter_ns())
  logs.append(dict(action='kill_own_child',pid=p.p.pid))
  assert K.TerminateProcess(int(p.p._handle),1);stamps.append(time.perf_counter_ns())
  p.wait(1)
  for role in ['bridge','ledger']:
   g=next(g for g in grands if g['pid']==info[role]['pid'])
   assert K.WaitForSingleObject(g['handle'],8000)==0
   logs.append(dict(action='grandchild_exit',pid=g['pid'],role=role,code=1,termination_requested=True))
  out['termination_request_span_ns']=max(stamps)-min(stamps)
 try:
  assert EXE.exists() and RELAY.exists() and LEDGER.exists(),'autonomous relay implementation missing'
  args=['target',mapping,epoch]+([mode] if mode not in ('exact','early_ack') else [])
  target=spawn(EXE,args);ready=target.get();out['ready']=ready
  assert ready['registered_entries']==3 and ready['worker_autonomous'] is True
  if name in ('autonomous','all_helpers_before','all_helpers_after','ack_loss','consumer_loss','db_busy'):
   checkpoint={'all_helpers_before':'before_commit','all_helpers_after':'after_commit','ack_loss':'before_ack','consumer_loss':'before_commit','db_busy':'before_read'}.get(name)
   relay,info=new_relay(128 if name=='autonomous' else 8,checkpoint)
   if name=='db_busy':
    assert relay.get()['stage']=='before_read'
    # A separate real SQLite writer holds the transaction while target runs.
    import sqlite3
    blocker=sqlite3.connect(db,timeout=0);blocker.execute('BEGIN IMMEDIATE')
    relay.p.stdin.write('resume\n');relay.p.stdin.flush()
    target.send('work 512 1');state=target.send('join')
    blocker.rollback();blocker.close();blocker=None
    done=relay.get();assert done['event']=='done',done;relay.wait()
   else:
    target.send('work 128 20' if name=='autonomous' else 'work 512 1')
    event=relay.get()
    if name=='autonomous':
     assert event['event']=='done' and event['last_seq']==128,event
     relay.wait();state=target.send('join')
     assert state['state']==1 and state['published']==state['acked']==state['original']==128,state
    else:
     assert event['event']=='checkpoint',event;out['relay_checkpoint']=event
     at=target.send('status');out['checkpoint_target']=at
     if name=='consumer_loss':
      g=next(g for g in grands if g['pid']==info['bridge']['pid']);assert K.TerminateProcess(g['handle'],1)
      assert K.WaitForSingleObject(g['handle'],8000)==0
      logs.append(dict(action='grandchild_exit',pid=g['pid'],role='bridge',code=1,termination_requested=True))
      relay.p.stdin.write('resume\n');relay.p.stdin.flush();error=relay.get();assert error['event']=='error',error
      relay.wait(1)
     else:kill_all(relay,info)
     state=target.send('join');out['after_loss']=state
     assert at['acked']==0 and state['acked']==0,state
     # All successful calls finish without a consumer, ledger or relay ACK.
     assert state['original']==512 and state['published']==8 and state['state']==4 and state['gap']==504,state
     # Native original keeps running after helper termination, not merely before it.
     assert state['original']>at['original'],(at,state)
     recovery=new_ledger();snap=good(cmd(recovery,'snapshot'));recovery.send('quit');recovery.wait()
     out['recovery_before_replay']=snap
     expected=0 if name=='all_helpers_before' else event['batch_size']
     if name!='consumer_loss':assert len(snap['records'])==expected,(name,snap,event)
     relay,info=new_relay(8);done=relay.get();assert done['event']=='done',done;relay.wait()
   out['joined']=state
   if name!='autonomous':assert state['original']==512 and state['published']==8 and state['state']==4,state
   expected_rows=128 if name=='autonomous' else 8
  else:
   ledger=new_ledger(True)
   if name in ('binding_pid','binding_creation'):
    bridge=new_bridge(pid=ready['pid']+1 if name=='binding_pid' else None,created=ready['created']+1 if name=='binding_creation' else None)
    result=bridge.get();assert result['event']=='error' and result['reason']=='expected_target',result
    bridge.wait(11);expected_rows=0
   else:
    bridge=new_bridge();bready=bridge.get();assert bready['read_only'] is True
    good(bind(ready if name=='peer' else bready))
    if name in ('original_fault','reentrant_original_fault'):
     s=target.send('scenario '+name);assert s['original_exceptions']==1 and s['depth']==s['published']==0,s
     target.send('scenario normal');good(ack(commit(batch())));expected_rows=1
    elif name=='live_rebind':
     rejected=bind(ready);assert rejected['ok'] is False and rejected['reason']=='live_peer',rejected
     target.send('call 8 32');good(ack(commit(batch())));expected_rows=8
    elif name=='ack_range':
     target.send('call 8 32');receipt=commit(batch())
     for seq,gen in [(0,1),(9,2),(8,0),(18446744073709551615,1)]:
      rejected=bridge.send(f'ack {epoch} {seq} {gen}')
      assert rejected['ok'] is False and rejected['acked']==0,rejected
     good(ack(receipt));expected_rows=8
    elif name in ('peer','packet_target','packet_epoch'):
     target.send('call 8 32');receipt=commit(batch())
     if name=='packet_target':result=ack(receipt,'ack_as',f"{ready['pid']+1} {ready['created']}")
     elif name=='packet_epoch':
      receipt['ack']['epoch']='0'*32;result=ack(receipt)
     else:result=ack(receipt)
     out['rejected_ack']=result
     assert result['ok'] is False and target.send('status')['acked']==0,result
     expected_rows=8
    elif name in ('late_batch','cursor_race'):
     target.send('call 8 32');old=batch();oldreceipt=commit(old);good(ack(oldreceipt))
     if name=='cursor_race':
      good(bridge.send('cursor_begin'))
     target.send('call 8 32');good(ack(commit(batch())))
     if name=='cursor_race':
      target.send('call 8 32')
      result=bridge.send('cursor_end');out['cursor_race']=result
      assert result['reason']=='changed' and result['records']==[],result
      good(ack(commit(batch())));expected_rows=24
     else:
      replay=commit(old);assert replay['added']==0 and replay['duplicates']==8,replay
      result=ack(replay);assert result['ok'] is False and result['acked']==16,result
      target.send('call 8 32');good(ack(commit(batch())));expected_rows=24
    elif name in ('ack_gate','publisher_gate'):
     target.send('call 4 32');receipt=commit(batch())
     if name=='ack_gate':
      good(target.send('ack_hold'));held=True
      a=receipt['ack'];line=f"ack {a['epoch']} {a['seq']} {a['generation']}"
      logs.append(dict(action='send',pid=bridge.p.pid,command=line));bridge.p.stdin.write(line+'\n');bridge.p.stdin.flush()
      good(target.send('ack_held'))
      state=target.send('call 1 32');out['contention']=state
      good(target.send('ack_release'));held=False;good(bridge.get())
      assert state['original']==5 and state['published']==4 and state['gap']==1 and state['state']==5,state
     else:
      good(target.send('publisher_hold'));held=True
      result=ack(receipt);out['contention']=result
      assert result['ok'] is False and result['reason']=='busy' and result['acked']==0,result
      good(target.send('publisher_release'));held=False;good(ack(receipt))
     expected_rows=4
    elif name in ('reuse_order','reuse_recheck'):
     target.send('call 8 32');good(ack(commit(batch())))
     first=target.send('race gate_partial_prechecked');race=True;out['race_window']=first
     b=bridge.send('read');out['window_batch']=b
     if b['records']:out['window_commit']=commit(b['records'])
     target.send('resume');race=False
     assert first['state']==first['window_state']==6 and first['published']==8 and first['second_gate_acquired']==1,first
     assert not b['records'] and b['reason']=='inactive',b
     expected_rows=8
  ledger=new_ledger();snap=good(cmd(ledger,'snapshot'));out['snapshot']=snap
  assert snap['integrity']=='ok' and len(snap['records'])==expected_rows,snap
  assert [x['seq'] for x in snap['records']]==list(range(1,expected_rows+1)),snap
  out['expected_rows']=expected_rows
  good(cmd(ledger,'stop',epoch=epoch))
  state=target.send('status');out['final_state']=state
  assert state['errors']==state['depth']==state['gate']==0 and state['acked']<=expected_rows,state
  out['transport']=target.send('transport');out['passed']=True
 except Exception as exc:out.update(error=repr(exc),traceback=traceback.format_exc())
 finally:
  if blocker:blocker.rollback();blocker.close()
  # Force-killed relays do not own cleanup; each already-bound child handle is checked.
  for g in grands:
   if K.WaitForSingleObject(g['handle'],0)!=0:
    K.TerminateProcess(g['handle'],1);K.WaitForSingleObject(g['handle'],8000)
    logs.append(dict(action='grandchild_cleanup_kill',pid=g['pid'],role=g['role']))
    out['passed']=False
   code=ctypes.c_ulong();assert K.GetExitCodeProcess(g['handle'],ctypes.byref(code))
   out.setdefault('grandchildren',[]).append(dict(pid=g['pid'],created=g['created'],role=g['role'],exit=code.value))
   K.CloseHandle(g['handle'])
  for p in reversed(children):
   try:
    if p is target and p.p.poll() is None:
     if race:p.send('resume')
     if held:
      p.send('ack_release');p.send('publisher_release')
     out['target_cleanup']=p.send('quit');p.wait()
     assert all(out['target_cleanup'].get(k) is True for k in ['prefix_restored','table_deleted','lookups_absent','freed','mapping_closed','guard_freed','threads_joined'])
    p.cleanup()
   except Exception as exc:
    out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(exc))
    if p.p.poll() is None:p.kill()
  # Close the fictional session even for retained negative controls.
  if db.exists():
   try:
    q=Child(sys.executable,['-u',str(LEDGER),'--database',str(db)],logs);q.get()
    good(cmd(q,'stop',epoch=epoch));q.cleanup()
   except Exception as exc:out['passed']=False;out.setdefault('cleanup_errors',[]).append(repr(exc))
  out['all_direct_children_exited']=all(p.p.poll() is not None for p in children)
  out['database_files']={p.name:sha(p) for p in folder.glob('ledger.sqlite3*')}
  out['seconds']=time.perf_counter()-start
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',action='append',choices=CASES);ap.add_argument('--repeat',type=int,default=1)
 ap.add_argument('--mode',default='exact',choices=['exact','early_ack','skip_peer','skip_target_binding','skip_epoch','skip_cursor','late_stop','skip_recheck'])
 args=ap.parse_args();assert 1<=args.repeat<=3
 run=C/('run-'+uuid.uuid4().hex[:12]);run.mkdir(parents=True);hashes={}
 for p in [Path(__file__),*[Path(__file__).with_name(n) for n in DEPENDENCIES],EXE,C/'build.json']:
  if p.exists():shutil.copyfile(p,run/p.name);hashes[p.name]=sha(p)
 if EXE.exists():
  b=json.loads((C/'build.json').read_text());assert b['exe_sha256']==sha(EXE)
  for n,h in b['source_hashes'].items():assert sha(Path(__file__).with_name(n))==h,n
 cases=[run_case(n,args.mode,run,i) for i,n in enumerate((args.case or CASES)*args.repeat)]
 d=dict(source_hashes=hashes,cases=cases,total=len(cases),passed=sum(x['passed'] for x in cases),mode=args.mode)
 (run/'results.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
 print(json.dumps(dict(run=run.relative_to(R).as_posix(),passed=d['passed'],total=d['total'],failures=[(x['case'],x.get('error'),x.get('cleanup_errors')) for x in cases if not x['passed']])))
 return int(d['passed']!=d['total'])
if __name__=='__main__':raise SystemExit(main())
