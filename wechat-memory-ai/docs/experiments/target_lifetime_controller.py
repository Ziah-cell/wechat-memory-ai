"""Nested launch controller. It alone holds target/relay stdin writers.

Target and relay stdout go directly to exclusive evidence files. The outer
observer receives identities, never a duplicated target stdin handle.
"""
import argparse,ctypes,json,os,subprocess,sys,time
from pathlib import Path
from autonomous_relay import created

def emit(x):print(json.dumps(x),flush=True)

class FileChild:
 def __init__(self,args,path):
  self.file=path.open('x',encoding='utf-8');self.read=path.open(encoding='utf-8')
  self.p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=self.file,stderr=self.file,text=True,bufsize=1,close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW)
  path.with_suffix('.process.json').write_text(json.dumps(dict(pid=self.p.pid,created=created(self))),encoding='utf-8')
 def get(self):
  deadline=time.monotonic()+15;pending=''
  while time.monotonic()<deadline:
   line=self.read.readline()
   pending+=line
   # An unbuffered native printf may reach the regular file in several writes.
   # Only a newline completes the record; a partial JSON fragment is not failure.
   if pending.endswith('\n'):return json.loads(pending)
   if self.p.poll() is not None:raise RuntimeError(('child_exit',self.p.pid,self.p.returncode))
   time.sleep(.005)
  raise TimeoutError(self.p.pid)
 def send(self,line):
  self.p.stdin.write(line+'\n');self.p.stdin.flush();return self.get()

def main():
 ap=argparse.ArgumentParser()
 for arg in ['exe','folder','case','mode']:ap.add_argument('--'+arg,required=True)
 a=ap.parse_args();folder=Path(a.folder);cfg=json.loads((folder/'config.json').read_text())
 k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=ctypes.c_void_p
 k.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.c_void_p]*4)]
 times=[ctypes.c_ulonglong() for _ in range(4)];assert k.GetProcessTimes(k.GetCurrentProcess(),*[ctypes.byref(x) for x in times])
 target=FileChild([a.exe,'target',cfg['mapping'],cfg['epoch'],a.mode,str(os.getpid()),str(times[0].value)],folder/'target.jsonl')
 ready=target.get();assert ready['event']=='ready',ready
 relay=None;info={}
 if a.case in ('before_commit','after_commit','all_before','all_after','acked'):
  args=[sys.executable,'-u',str(Path(__file__).with_name('target_lifetime_relay.py')),
    '--exe',a.exe,'--mapping',cfg['mapping'],'--epoch',cfg['epoch'],'--target-pid',str(ready['pid']),
    '--target-created',str(ready['created']),'--database',str(folder/'ledger.sqlite3'),
    '--journal',str(folder/'relay-journal.jsonl'),'--count','8']
  if a.case!='acked':args+=['--checkpoint','after_commit' if a.case in ('after_commit','all_after') else 'before_commit']
  relay=FileChild(args,folder/'relay.jsonl');info=relay.get();assert info['event']=='ready',info
  assert target.send(f"bind {info['bridge']['pid']} {info['bridge']['created']}")['ok'] is True
  info['relay']=dict(pid=relay.p.pid,created=created(relay))
 emit(dict(event='prepared',target=ready,helpers=info))
 assert sys.stdin.readline().strip()=='start'
 if a.case=='bootstrap_eof':target.p.stdin.close();emit(dict(event='armed',count=0))
 else:
  if a.case=='acked':assert target.send('call 8 32')['original']==8
  if relay:assert relay.send('start')['event']=='started'
  assert target.send(f"work {cfg['count']} {cfg['delay']}")['event']=='started'
  checkpoint=relay.get() if relay else None
  if checkpoint:assert checkpoint['event']==('done' if a.case=='acked' else 'checkpoint'),checkpoint
  emit(dict(event='armed',checkpoint=checkpoint,count=cfg['count']))
 for line in sys.stdin:
  command=line.strip()
  if command=='eof':
   if not target.p.stdin.closed:target.p.stdin.close()
   emit(dict(event='eof_sent'))
  elif command=='exit':os._exit(0)
  elif command=='quit':break
 # Only reached after the observer has already seen target exit in positive cases.
 if not target.p.stdin.closed:target.p.stdin.close()
 if relay and not relay.p.stdin.closed:relay.p.stdin.close()
 return 0

if __name__=='__main__':raise SystemExit(main())
