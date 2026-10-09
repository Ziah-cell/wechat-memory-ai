"""Instrument the preserved guarded fixture collector; never a live-app CLI.

Trace timestamps surround APIs, including time OUTSIDE process_event(). This
adds measurement overhead. It does not measure exact kernel suspension onset.
"""
import argparse
import ctypes as c
import json
import pathlib
import struct
import sys
import time
import receive_probe_guarded as original
from receive_pause_bounds import assess

TRACE=None
CASE='normal'
ENFORCE=False
JOURNAL=None

class Recorder:
    def __init__(self,role):
        self.role=role;self.seq=0;self.records=[]
        self.file=JOURNAL.with_suffix('.'+role+'.jsonl').open('x',encoding='utf-8') if JOURNAL else None
        self.log('role_start')
    def log(self,op,**values):
        self.seq+=1
        if self.seq>4096:raise RuntimeError('trace_budget')
        record=dict(kind='timing_trace',role=self.role,seq=self.seq,op=op,ns=time.perf_counter_ns(),**values)
        self.records.append(record)
        if self.file:
            self.file.write(json.dumps(record)+'\n');self.file.flush()
        original.emit(**record)

def owner_history():
    if JOURNAL is None:raise RuntimeError('timing_history_missing')
    path=JOURNAL.with_suffix('.owner.jsonl')
    if path.stat().st_size>2_000_000:raise RuntimeError('timing_history_budget')
    raw=path.read_bytes()
    if not raw.endswith(b'\n'):raise RuntimeError('timing_history_truncated')
    try:text=raw.decode('utf-8')
    except UnicodeError:raise RuntimeError('timing_history_invalid') from None
    try:records=[json.loads(s) for s in text.splitlines()]
    except ValueError:raise RuntimeError('timing_history_invalid') from None
    if not records or len(records)>4096:raise RuntimeError('timing_history_budget')
    allowed={'kind','role','seq','op','ns','tid','status','success','error','timeout_ms','event_code','has_event','exception_code'}
    operations={'role_start','role_end','attach_begin','attach_end','detach_begin','detach_end',
                'wait_begin','wait_end','continue_begin','continue_end','freeze_begin','freeze_active',
                'thaw_begin','thaw_end','cleanup_begin','cleanup_end'}
    previous=0
    for i,record in enumerate(records,1):
        if not isinstance(record,dict) or set(record)-allowed:
            raise RuntimeError('timing_history_schema')
        if record.get('role')!='owner' or record.get('seq')!=i or record.get('kind')!='timing_trace':
            raise RuntimeError('timing_history_sequence')
        if record.get('op') not in operations or type(record.get('ns')) is not int or record['ns']<previous:
            raise RuntimeError('timing_history_clock')
        previous=record['ns']
        for key in ('tid','status','error','timeout_ms','event_code','exception_code'):
            if key in record and type(record[key]) is not int:raise RuntimeError('timing_history_schema')
        for key in ('success','has_event'):
            if key in record and type(record[key]) is not bool:raise RuntimeError('timing_history_schema')
        op=record['op']
        required={'continue_begin':('tid','status'),'continue_end':('tid','status','success'),
                  'attach_end':('success',),'detach_end':('success',),'wait_end':('has_event',)}.get(op,())
        if any(key not in record for key in required):raise RuntimeError('timing_history_schema')
        if op=='wait_end' and record['has_event'] and not {'tid','event_code'}<=set(record):
            raise RuntimeError('timing_history_schema')
    if records[0]['op']!='role_start':raise RuntimeError('timing_history_schema')
    return records

BaseFreeze=original.StateFreeze
class TimedFreeze(BaseFreeze):
    def suspend(self):
        TRACE.log('freeze_begin')
        super().suspend()
        TRACE.log('freeze_active')
        if TRACE.role=='owner' and CASE=='cleanup':time.sleep(0.15)
    def close(self):
        if self.handle.value:
            TRACE.log('thaw_begin')
            super().close()
            TRACE.log('thaw_end')

class TimedDebugger(original.GuardedDebugger):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.queue_delay_done=False
        self.history=[];self.history_unknown=False
        for name,op in (('DebugActiveProcess','attach'),('DebugActiveProcessStop','detach'),
                        ('ContinueDebugEvent','continue')):
            fn=getattr(self.k,name)
            def wrapped(*values,_fn=fn,_op=op):
                fields={'tid':int(values[1]),'status':int(values[2])} if _op=='continue' else {}
                TRACE.log(_op+'_begin',**fields)
                result=_fn(*values);error=c.get_last_error()
                TRACE.log(_op+'_end',success=bool(result),error=0 if result else error,**fields)
                if _op=='attach' and result and CASE=='attach':time.sleep(0.15)
                c.set_last_error(error)
                return result
            setattr(self.k,name,wrapped)
    def wait(self,ms=50):
        if TRACE.role=='owner' and CASE=='queued' and self.hits>=1 and not self.queue_delay_done:
            self.queue_delay_done=True
            original.emit(kind='timing_boundary',stage='before_wait',fixture_only=True)
            time.sleep(0.18)
        TRACE.log('wait_begin',timeout_ms=ms)
        event=super().wait(min(ms,5) if CASE=='total' else ms)
        fields={'event_code':int(event.code),'tid':int(event.tid)} if event else {}
        if event and event.code==1:
            fields['exception_code']=struct.unpack_from('<I',bytes(event.data))[0]
        TRACE.log('wait_end',has_event=event is not None,**fields)
        return event
    def process_event(self,event):
        own=(event.code==1 and struct.unpack_from('<I',bytes(event.data))[0]==0x80000004 and
             struct.unpack_from('<Q',bytes(event.data),16)[0]==self.address)
        if own and not self.cleaning:
            if CASE=='received':time.sleep(0.15)
            elif CASE in ('cumulative','total'):time.sleep(0.06)
        result=super().process_event(event)
        if not self.cleaning:self.check_budget()
        return result
    def check_budget(self):
        if ENFORCE:
            bounds=assess(self.history+TRACE.records)
            if self.history_unknown or bounds['errors'] or bounds['unclosed_intervals']:
                self.stop_reason='pause_timing_unknown';self.record=None
            elif bounds['upper_max_ms']>100 or bounds['upper_total_ms']>1000:
                self.stop_reason='pause_budget_upper';self.record=None
    def cleanup(self,*args,**kwargs):
        # Original guardian calls this only after its retained owner identity
        # reports exit. A partial final journal record is rejected, not guessed.
        if kwargs.get('recovery'):
            try:self.history=owner_history()
            except (OSError,RuntimeError):self.history_unknown=True
        TRACE.log('cleanup_begin')
        try:return super().cleanup(*args,**kwargs)
        finally:
            TRACE.log('cleanup_end')
            self.check_budget()

def main():
    global TRACE,CASE,ENFORCE,JOURNAL
    p=argparse.ArgumentParser(add_help=False)
    p.add_argument('--timing-case',choices=('normal','idle','new_thread','queued','received','attach','cleanup','cumulative','total','owner_crash'),default='normal')
    p.add_argument('--enforce-timing',action='store_true')
    p.add_argument('--timing-journal',type=pathlib.Path)
    a,remaining=p.parse_known_args();CASE=a.timing_case;ENFORCE=a.enforce_timing
    if a.timing_journal:
        cache=pathlib.Path(__file__).resolve().parents[2]/'data/bounded-receive-timing-20261009'
        JOURNAL=a.timing_journal.resolve()
        if JOURNAL.parent!=cache.resolve() or not JOURNAL.name.startswith('journal-'):
            p.error('journal must be a fresh fixture-cache path')
    role=remaining[remaining.index('--role')+1]
    TRACE=Recorder(role)
    original.GuardedDebugger=TimedDebugger;original.StateFreeze=TimedFreeze
    sys.argv=[sys.argv[0]]+remaining
    try:return original.main()
    finally:
        TRACE.log('role_end')
        if TRACE.file:TRACE.file.close()

if __name__=='__main__':raise SystemExit(main())
