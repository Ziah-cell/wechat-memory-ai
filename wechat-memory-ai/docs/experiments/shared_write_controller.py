"""Nested fixture launcher; the outer observer never owns target stdin."""
import argparse,ctypes,json,os,sys
from pathlib import Path
from autonomous_relay import created
from target_lifetime_controller import FileChild
def emit(x):print(json.dumps(x),flush=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--exe',required=True);ap.add_argument('--folder',required=True);a=ap.parse_args()
 folder=Path(a.folder);cfg=json.loads((folder/'config.json').read_text(encoding='utf-8'))
 k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=ctypes.c_void_p;k.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.c_void_p]*4)]
 ts=[ctypes.c_ulonglong() for _ in range(4)];assert k.GetProcessTimes(k.GetCurrentProcess(),*[ctypes.byref(t) for t in ts])
 target=FileChild([a.exe,'target',cfg['mapping'],cfg['epoch'],'owned',str(os.getpid()),str(ts[0].value),cfg['lease']],folder/'target.jsonl')
 ready=target.get();assert ready['event']=='ready',ready
 assert target.send(f"write_config {cfg['point']} {cfg['input']} {cfg['kind']} {cfg['mode']}")['event']=='configured'
 args=[sys.executable,'-u',str(Path(__file__).with_name('shared_write_relay.py')),'--exe',a.exe]
 for key in ['mapping','epoch','lease']:args+=['--'+key,cfg[key]]
 args+=['--target-pid',str(ready['pid']),'--target-created',str(ready['created']),'--database',str(folder/'ledger.sqlite3'),'--journal',str(folder/'relay-journal.jsonl')]
 relay=FileChild(args,folder/'relay.jsonl');r=relay.get();assert r['event']=='ready',r
 r['helpers']['relay']=dict(pid=relay.p.pid,created=created(relay));emit(dict(event='prepared',target=ready,helpers=r['helpers']))
 assert sys.stdin.readline().strip()=='start';assert relay.send('start')['event']=='started'
 assert target.send(f"work {cfg['count']} {cfg['delay']}")['event']=='started';emit(dict(event='armed'))
 for line in sys.stdin:
  if line.strip()=='quit':emit(dict(event='bye'));break
 for p in [target,relay]:
  if not p.p.stdin.closed:p.p.stdin.close()
 return 0
if __name__=='__main__':raise SystemExit(main())
