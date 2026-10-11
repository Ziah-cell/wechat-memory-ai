"""Autonomous fictional consumer/COMMIT/ACK loop. No real application adapter."""
import argparse,ctypes,json,queue,sys,threading,time
from pathlib import Path
from test_resident_publisher import Child


class Journal(list):
    def __init__(self,path):
        super().__init__();self.file=path.open('x',encoding='utf-8')
    def append(self,item):
        item=dict(item,at_ns=time.perf_counter_ns())
        self.file.write(json.dumps(item,separators=(',',':'))+'\n');self.file.flush()
        super().append(item)


def emit(value):print(json.dumps(value,separators=(',',':')),flush=True)
def good(value):
    if value.get('ok') is not True:raise RuntimeError(value)
    return value
def created(p):
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.c_void_p]*4)]
    times=[ctypes.c_ulonglong() for _ in range(4)]
    if not k.GetProcessTimes(int(p.p._handle),*[ctypes.byref(t) for t in times]):raise ctypes.WinError(ctypes.get_last_error())
    return times[0].value


def main():
    ap=argparse.ArgumentParser()
    for arg in ['exe','mapping','epoch','target-pid','target-created','database','journal','count']:ap.add_argument('--'+arg,required=True)
    ap.add_argument('--checkpoint',choices=['before_read','before_commit','after_commit','before_ack'])
    ap.add_argument('--mode',choices=['exact','early_ack'],default='exact')
    a=ap.parse_args();commands=queue.Queue();journal=Journal(Path(a.journal));children=[];status=0
    def input_pump():
        for line in sys.stdin:commands.put(line.strip())
        commands.put('stop')
    threading.Thread(target=input_pump,daemon=True).start()
    def pause(stage,batch_size):
        journal.append(dict(action='relay_checkpoint',stage=stage,batch_size=batch_size))
        emit(dict(event='checkpoint',stage=stage,batch_size=batch_size))
        if commands.get(timeout=20)!='resume':raise RuntimeError('checkpoint cancelled')
    def spawn(exe,args):
        p=Child(exe,args,journal);children.append(p);return p
    def cmd(p,op,**kw):return p.send(json.dumps(dict(op=op,**kw)))
    def send_ack(receipt):
        ack=receipt['ack'];line=f"ack {ack['epoch']} {ack['seq']} {ack['generation']}"
        response=bridge.send(line)
        if not response.get('ok') and response.get('reason') not in ('busy','stale'):raise RuntimeError(response)
        return response
    try:
        bridge=spawn(a.exe,['bridge',a.mapping,a.epoch,a.target_pid,a.target_created]);bready=bridge.get()
        if bready.get('event')!='ready' or not bready.get('read_only'):raise RuntimeError(bready)
        ledger=spawn(sys.executable,['-u',str(Path(__file__).with_name('autonomous_relay_ledger.py')),'--database',a.database]);lready=ledger.get()
        if lready.get('synchronous')!=2:raise RuntimeError(lready)
        snap=good(cmd(ledger,'snapshot'))
        active=[s for s in snap['sessions'] if s['state']=='active']
        if not active:good(cmd(ledger,'begin',epoch=a.epoch))
        elif len(active)!=1 or active[0]['epoch']!=a.epoch:raise RuntimeError('active epoch mismatch')
        emit(dict(event='ready',bridge=dict(pid=bridge.p.pid,created=bready['created']),ledger=dict(pid=ledger.p.pid,created=created(ledger))))
        if commands.get(timeout=20)!='start':raise RuntimeError('start required')
        emit(dict(event='started'));checkpoint=a.checkpoint;last_seq=0
        if checkpoint=='before_read':pause(checkpoint,0);checkpoint=None
        while True:
            try:
                if commands.get_nowait() in ('stop','quit'):break
            except queue.Empty:pass
            result=bridge.send('read')
            if result.get('reason')=='changed':continue
            if result.get('reason')!='ok':raise RuntimeError(result)
            batch=result['records']
            if not batch:time.sleep(.002);continue
            if a.mode=='early_ack':
                # Deliberately wrong control: proves trusting an authorized relay
                # does not prove that its ACK followed a durable commit.
                seq=batch[-1]['seq'];send_ack(dict(ack=dict(epoch=a.epoch,seq=seq,generation=(seq-1)//8+1)))
            point=checkpoint if checkpoint in ('before_commit','after_commit') else None
            kw=dict(checkpoint=point) if point else {}
            receipt=cmd(ledger,'accept',epoch=a.epoch,records=batch,**kw)
            if point:
                if receipt!=dict(event='checkpoint',stage=point):raise RuntimeError(receipt)
                pause(point,len(batch));receipt=ledger.send('resume');checkpoint=None
            if not receipt.get('ok'):
                if receipt.get('reason')=='busy':time.sleep(.002);continue
                raise RuntimeError(receipt)
            if checkpoint=='before_ack':pause(checkpoint,len(batch));checkpoint=None
            acked=send_ack(receipt)
            if not acked.get('ok') and acked.get('acked',0)<receipt['ack']['seq']:continue
            last_seq=receipt['last_seq']
            journal.append(dict(action='relay_committed_acked',last_seq=last_seq,ack=receipt['ack']))
            if last_seq>=int(a.count):break
        emit(dict(event='done',last_seq=last_seq))
    except Exception as exc:
        status=1;journal.append(dict(action='relay_error',error=repr(exc)));emit(dict(event='error',reason=repr(exc)))
    finally:
        for p in reversed(children):
            try:
                if p.p.poll() is not None:p.wait(None)
                p.cleanup()
            except Exception as exc:
                status=1;journal.append(dict(action='cleanup_error',error=repr(exc)))
                if p.p.poll() is None:p.kill()
        journal.file.close()
    return status


if __name__=='__main__':raise SystemExit(main())
