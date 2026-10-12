"""Independent bounded fixture relay. All records and endpoints are fictional.

The startup controller is not an execution dependency after start. A receiver
may restart, but only a successful durable receipt authorizes a native ACK.
"""
import argparse,json,queue,sys,threading,time
from pathlib import Path
from autonomous_relay import Journal,created
from test_resident_publisher import Child
from session_target_binding import probe

def emit(x):print(json.dumps(x,separators=(',',':')),flush=True)
class Deferred(Exception):pass

def main():
 ap=argparse.ArgumentParser()
 for arg in ['exe','mapping','epoch','target-pid','target-created','lease','database','journal']:ap.add_argument('--'+arg,required=True)
 ap.add_argument('--checkpoint',choices=['before_commit','after_commit'])
 ap.add_argument('--mode',choices=['exact','early_ack','omit_terminal','storage_full'],default='exact')
 a=ap.parse_args();journal=Journal(Path(a.journal));children=[];commands=queue.Queue();status=0
 binding=dict(pid=int(a.target_pid),created=int(a.target_created));bridge=ledger=None;restarts=0
 def pump():
  for line in sys.stdin:commands.put(line.strip())
  commands.put('controller_eof')
 threading.Thread(target=pump,daemon=True).start()
 def spawn(exe,args,role):
  p=Child(exe,args,journal);p.role=role;p.reaped=False;children.append(p)
  journal.append(dict(action='identity',role=role,pid=p.p.pid,created=created(p)))
  return p
 def reap(p):
  if not p.reaped:p.wait(None);p.reaped=True
 def cmd(p,op,**kw):return p.send(json.dumps(dict(op=op,**kw)))
 def good(r):
  if not r.get('ok'):raise Deferred(r)
  return r
 def receiver():
  p=spawn(sys.executable,['-u',str(Path(__file__).with_name('shared_write_ledger.py')),'--database',a.database],'ledger')
  r=p.get()
  if r.get('synchronous')!=2:raise Deferred(r)
  snap=good(cmd(p,'snapshot'));sessions=snap['sessions']
  if not sessions:good(cmd(p,'begin',epoch=a.epoch,target=binding))
  elif len(sessions)!=1 or sessions[0]['epoch']!=a.epoch or (sessions[0]['target_pid'],sessions[0]['target_created'])!=(binding['pid'],binding['created']):raise Deferred('session binding mismatch')
  return p
 def alive():return probe(binding['pid'],binding['created'])
 def pause(stage,n):
  journal.append(dict(action='relay_checkpoint',stage=stage,batch_size=n));emit(dict(event='checkpoint',stage=stage,batch_size=n))
  if commands.get(timeout=20)!='resume':raise Deferred('checkpoint cancelled')
 def ack(receipt):
  x=receipt['ack'];r=bridge.send(f"ack {x['epoch']} {x['seq']} {x['generation']}")
  if not r.get('ok') and r.get('reason') not in ('busy','stale'):
   if alive()['state'] not in ('dead','replaced'):raise Deferred(r)
  return r
 try:
  # A dead-target restart must never invent a fresh empty session/database.
  if not Path(a.database).exists() and alive()['state']!='live':raise Deferred('missing_database')
  ledger=receiver();state=alive()
  if state['state']=='unknown':raise Deferred(state)
  if state['state']=='live':
   bridge=spawn(a.exe,['bridge',a.mapping,a.epoch,a.target_pid,a.target_created,a.lease],'bridge');r=bridge.get()
   if r.get('event')!='ready' or not r.get('read_only'):raise Deferred(r)
  emit(dict(event='ready',helpers={p.role:dict(pid=p.p.pid,created=created(p)) for p in children}))
  if commands.get(timeout=20)!='start':raise Deferred('start required')
  emit(dict(event='started'));point=a.checkpoint;deadline=time.monotonic()+12;full=False
  while time.monotonic()<deadline:
   try:
    command=commands.get_nowait()
    journal.append(dict(action='controller_input',command=command))
    if command=='quit':raise Deferred('explicit quit')
   except queue.Empty:pass
   try:
    state=alive()
    if state['state']=='unknown':raise Deferred(state)
    if state['state'] in ('dead','replaced'):
     if a.mode=='omit_terminal':emit(dict(event='terminal',outcome='incorrect_omitted'));break
     r=cmd(ledger,'reconcile',epoch=a.epoch)
     if r.get('reason')=='busy':time.sleep(.005);continue
     good(r);journal.append(dict(action='durable_terminal',detail=r));emit(dict(event='terminal',outcome='ended',detail=r));break
    if bridge is None:raise Deferred('missing live bridge')
    r=bridge.send('read')
    if r.get('reason') in ('changed','inactive','target_dead'):time.sleep(.005);continue
    if r.get('reason')!='ok':raise Deferred(r)
    batch=r['records']
    if not batch:time.sleep(.003);continue
    observed=cmd(ledger,'observe',epoch=a.epoch,records=batch)
    if observed.get('reason') in ('busy','target_dead'):time.sleep(.005);continue
    good(observed)
    if a.mode=='storage_full' and not full:good(cmd(ledger,'limit_pages'));full=True
    if a.mode=='early_ack':
     seq=batch[-1]['seq'];ack(dict(ack=dict(epoch=a.epoch,seq=seq,generation=(seq-1)//8+1)))
    receipt=cmd(ledger,'accept',epoch=a.epoch,records=batch,**(dict(checkpoint=point) if point else {}))
    if point and receipt.get('event')=='checkpoint':
     current=point;point=None;pause(current,len(batch));receipt=ledger.send('resume')
    if receipt.get('reason') in ('busy','target_dead'):time.sleep(.005);continue
    good(receipt);ack(receipt)
   except (BrokenPipeError,AssertionError,OSError) as exc:
    # Receiver death is recoverable only with an observed process exit. Other
    # I/O errors do not establish target death or commit success.
    if ledger.p.poll() is not None:
     reap(ledger);restarts+=1
     if restarts>3:raise Deferred('receiver restart budget')
     journal.append(dict(action='receiver_restart',previous=ledger.p.pid,error=repr(exc)))
     ledger=receiver();continue
    if alive()['state'] in ('dead','replaced'):continue
    raise
  else:raise Deferred('deadline')
 except Deferred as exc:
  status=2;journal.append(dict(action='deferred',reason=repr(exc)));emit(dict(event='deferred',reason=repr(exc)))
 except Exception as exc:
  status=1;journal.append(dict(action='relay_error',reason=repr(exc)));emit(dict(event='error',reason=repr(exc)))
 finally:
  for p in reversed(children):
   try:
    if not p.p.stdin.closed:
     try:p.p.stdin.close()
     except OSError as exc:
      if p.p.poll() is None:raise
      journal.append(dict(action='stdin_close_after_exit',pid=p.p.pid,reason=repr(exc)))
    reap(p)
   except Exception as exc:
    status=1;journal.append(dict(action='cleanup_error',role=p.role,reason=repr(exc)))
    if p.p.poll() is None:p.kill();p.reaped=True
   p.reader.join(timeout=1)
   while True:
    try:journal.append(dict(action='unread',pid=p.p.pid,line=p.lines.get_nowait()))
    except queue.Empty:break
   if not p.p.stdout.closed:p.p.stdout.close()
  journal.file.close()
 return status
if __name__=='__main__':raise SystemExit(main())
