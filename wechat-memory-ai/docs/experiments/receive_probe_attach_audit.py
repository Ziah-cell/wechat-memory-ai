"""Diagnose initial-break classification in OWN fixtures; optional narrow candidate.

The optional race holds the observed ntdll break-in thread with one counted
SuspendThread, allows an application breakpoint first, then balances that hold
after detaching. Never a live adapter; no pause-budget certification in this test.
"""
import argparse
import ctypes as c
import struct
import sys
import receive_probe_lifecycle as lifecycle
import receive_probe_timing as timing

RACE=False
STRICT=False

class AttachAudit(lifecycle.LifecycleDebugger):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        # Local addresses are observation labels for identical sibling Python
        # fixtures on this host. They are not remote module identity proof.
        self.breakpoint=c.cast(self.n.DbgBreakPoint,c.c_void_p).value
        self.breakin=c.cast(self.n.DbgUiRemoteBreakin,c.c_void_p).value
        self.starts={};self.held=None;self.held_released=False;self.audits=[]

    def process_event(self,event):
        data=bytes(event.data)
        holding=False
        if event.code==2:
            start=struct.unpack_from('<Q',data,16)[0];self.starts[event.tid]=start
            if RACE and timing.TRACE.role=='owner' and start==self.breakin and not self.initial_break_seen:
                if self.held is not None:raise RuntimeError('duplicate_breakin_thread')
                handle=self.add_thread(event.tid)
                prior=self.k.SuspendThread(handle)
                if prior==0xffffffff:raise c.WinError(c.get_last_error())
                self.held=handle;holding=True
                if prior!=0:raise RuntimeError('unexpected_breakin_suspend_count')
        if event.code==4:self.starts.pop(event.tid,None)
        audit=None
        if event.code==1 and struct.unpack_from('<I',data)[0]==0x80000003:
            address=struct.unpack_from('<Q',data,16)[0]
            first=struct.unpack_from('<I',data,152)[0]
            before=self.initial_break_seen
            audit=dict(kind='breakpoint_audit',fixture_only=True,previous_initial_seen=before,
                first_chance=first,main_thread=event.tid==self.tid,
                address_is_local_dbg_breakpoint=address==self.breakpoint,
                start_is_local_dbg_breakin=self.starts.get(event.tid)==self.breakin,
                candidate_match=not before and first==1 and address==self.breakpoint and
                                self.starts.get(event.tid)==self.breakin)
        # Experimental same-host candidate only. Temporarily bypass the old
        # catch-all first-breakpoint branch so a non-candidate is forwarded by
        # its normal exception path; do not announce attachment readiness.
        reject=bool(STRICT and audit and not audit['previous_initial_seen'] and not audit['candidate_match'])
        if reject:self.initial_break_seen=True
        try:super().process_event(event)
        finally:
            if reject:self.initial_break_seen=False
        if holding:timing.original.emit(kind='attach_hold',fixture_only=True)
        if audit:
            audit['legacy_consumed_as_initial']=not audit['previous_initial_seen'] and self.initial_break_seen
            self.audits.append(audit);timing.original.emit(**audit)
            if RACE and not STRICT and self.held is not None and audit['main_thread']:
                self.stop_reason='attach_audit_complete';self.record=None

    def cleanup(self,*args,**kwargs):
        try:return super().cleanup(*args,**kwargs)
        finally:
            if self.held is not None:
                target_exited=self.identity.exited()
                prior=1 if target_exited else self.k.ResumeThread(self.held)
                self.held=None
                if prior!=1:raise RuntimeError('breakin_hold_not_balanced')
                self.held_released=True
                timing.original.emit(kind='attach_hold_released',fixture_only=True,target_exited=target_exited)

def result_for(debugger,cleanup):
    result=lifecycle.result_for(debugger,cleanup)
    result['attach_audits']=debugger.audits
    result['controlled_hold_released']=debugger.held_released
    result['pause_budget_certified']=False
    return result

def main():
    global RACE,STRICT
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--attach-race',action='store_true')
    parser.add_argument('--strict-attach',action='store_true')
    args,remaining=parser.parse_known_args();RACE=args.attach_race;STRICT=args.strict_attach
    sys.argv=[sys.argv[0]]+remaining
    timing.TimedDebugger=AttachAudit;timing.original.result_for=result_for
    return timing.main()

if __name__=='__main__':raise SystemExit(main())
