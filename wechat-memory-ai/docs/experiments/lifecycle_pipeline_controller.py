"""Nested launcher: target/relay output is files, never outer-observer pipes."""
import argparse,ctypes,json,os,sys
from pathlib import Path
from autonomous_relay import created
from target_lifetime_controller import FileChild

def emit(x):print(json.dumps(x),flush=True)
def main():
 ap=argparse.ArgumentParser()
 for arg in ['exe','folder','case','mode']:ap.add_argument('--'+arg,required=True)
 a=ap.parse_args();folder=Path(a.folder);cfg=json.loads((folder/'config.json').read_text());serial=0
 k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=ctypes.c_void_p;k.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.c_void_p]*4)]
 times=[ctypes.c_ulonglong() for _ in range(4)];assert k.GetProcessTimes(k.GetCurrentProcess(),*[ctypes.byref(x) for x in times])
 target=FileChild([a.exe,'target',cfg['mapping'],cfg['epoch'],'owned',str(os.getpid()),str(times[0].value),cfg['lease']],folder/'target.jsonl')
 ready=target.get();assert ready['event']=='ready',ready
 def launch(point=None):
  nonlocal serial
  args=[sys.executable,'-u',str(Path(__file__).with_name('lifecycle_pipeline_relay.py')),'--exe',a.exe]
  for key in ['mapping','epoch','lease']:args+=['--'+key,cfg[key]]
  args+=['--target-pid',str(ready['pid']),'--target-created',str(ready['created']),'--database',str(folder/'ledger.sqlite3'),
    '--journal',str(folder/f'relay-{serial}-journal.jsonl'),'--mode','storage_full' if a.case=='storage_full' else a.mode]
  if point:args+=['--checkpoint',point]
  relay=FileChild(args,folder/f'relay-{serial}.jsonl');serial+=1;r=relay.get();assert r['event']=='ready',r
  r['helpers']['relay']=dict(pid=relay.p.pid,created=created(relay));return relay,r['helpers']
 point='before_commit' if a.case in ('receiver_before','relay_before','all_before') else 'after_commit' if a.case in ('receiver_after','relay_after','all_after') else None
 relay,info=launch(point);emit(dict(event='prepared',target=ready,helpers=info))
 assert sys.stdin.readline().strip()=='start'
 assert relay.send('start')['event']=='started'
 assert target.send(f"work {cfg['count']} {cfg['delay']}")['event']=='started'
 checkpoint=relay.get() if point else None
 if checkpoint:assert checkpoint['event']=='checkpoint',checkpoint
 emit(dict(event='armed',checkpoint=checkpoint))
 for line in sys.stdin:
  command=line.strip()
  if command=='resume':relay.p.stdin.write('resume\n');relay.p.stdin.flush();emit(dict(event='resumed'))
  elif command=='restart':
   assert relay.p.poll() is not None,'old relay still live'
   relay,info=launch();assert relay.send('start')['event']=='started';emit(dict(event='restarted',helpers=info))
  elif command=='exit':os._exit(0)
  elif command=='quit':emit(dict(event='bye'));break
 for p in [relay,target]:
  if not p.p.stdin.closed:p.p.stdin.close()
 return 0
if __name__=='__main__':raise SystemExit(main())
