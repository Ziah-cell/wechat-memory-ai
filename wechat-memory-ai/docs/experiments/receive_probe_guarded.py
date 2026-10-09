"""Research-only guarded collector for this repository's fictional fixtures.

No WeChat entry point. Uses third-party Native API declarations, not a stable
Microsoft contract. All identity, code and memory operations target sibling
fixtures. The old observers remain intact as versioned research comparisons.
"""
import argparse
import ctypes as c
import json
import secrets
import struct
import sys
import threading
import time

from check_receive_probe_layout import MARKER, Rejected, project
from receive_probe_observer import ProcessIdentity
from receive_probe_win32 import NativeDebugger, PTR, U32, emit
from receive_probe_transfer import DebugObject
from probe_fixture_freeze import StateFreeze


class GuardedDebugger(NativeDebugger):
    def __init__(self, pid, tid, address, fault=None):
        super().__init__(pid, tid, address)
        self.process = self.k.OpenProcess(0xe10, False, pid)  # query, read, state change
        if not self.process:
            raise c.WinError(c.get_last_error())
        self.n = c.WinDLL('ntdll', use_last_error=True)
        self.n.NtGetNextThread.argtypes = [PTR,PTR,U32,U32,U32,c.POINTER(PTR)]
        self.n.NtGetNextThread.restype = c.c_int32
        self.k.GetThreadId.argtypes = [PTR]; self.k.GetThreadId.restype = U32
        self.k.WaitForSingleObject.argtypes = [PTR,U32]; self.k.WaitForSingleObject.restype = U32
        self.k.CheckRemoteDebuggerPresent.argtypes = [PTR,c.POINTER(c.c_int)]
        self.k.CheckRemoteDebuggerPresent.restype = c.c_int
        self.threads = {}
        self.cleaning = False
        self.initial_break_seen = False
        self.record = None
        self.stop_reason = None
        self.key = secrets.token_bytes(32)
        self.fault = fault
        self.thread_hits = 0
        self.created = self.exited_threads = self.replayed = 0
        self.later_threads = set()
        self.max_read_bytes = self.max_read_calls = 0
        self.read_bytes = self.read_calls = 0
        self.pause_total = self.pause_max = 0.0
        self.cleanup_registers = []
        self.drained = 0
        self.cleanup_ms = 0
        self.pending_steps = set()
        self.drained_after_thaw = 0
        self.resume_registers = []

    def pause(self, stage):
        if self.fault == stage:
            emit(kind='fault_boundary', stage=stage, fixture_only=True)
            time.sleep(8)  # only harness-owned process is terminated here

    def add_thread(self, tid):
        if tid in self.threads:
            return self.threads[tid]
        if len(self.threads) >= 64:
            raise RuntimeError('thread_budget')
        handle = self.k.OpenThread(0x10081a, False, tid)
        if not handle:
            raise c.WinError(c.get_last_error())
        if self.k.GetProcessIdOfThread(handle) != self.pid:
            self.k.CloseHandle(handle)
            raise RuntimeError('wrong_thread_process')
        self.threads[tid] = handle
        return handle

    def discover_threads(self):
        # Scoped to this exact process handle; no system-wide thread snapshot.
        previous = None
        try:
            for _ in range(65):
                result = PTR()
                status = self.n.NtGetNextThread(self.process, previous, 0x10081a, 0, 0, c.byref(result))
                if status & 0xffffffff == 0x8000001a:
                    return
                StateFreeze.check(status)
                if previous:
                    self.k.CloseHandle(previous)
                previous = result.value
                tid = self.k.GetThreadId(previous)
                if not tid or self.k.GetProcessIdOfThread(previous) != self.pid:
                    raise RuntimeError('thread_enumeration_identity')
                self.add_thread(tid)
            raise RuntimeError('thread_budget')
        finally:
            if previous:
                self.k.CloseHandle(previous)

    def registers(self, tid, change=None):
        handle = self.add_thread(tid)
        storage = c.create_string_buffer(1247)
        aligned = (c.addressof(storage)+15) & ~15
        c.c_uint32.from_address(aligned+48).value = 0x100013
        self.ok(self.k.GetThreadContext(handle, aligned))
        dr0 = c.c_uint64.from_address(aligned+72)
        dr6 = c.c_uint64.from_address(aligned+104)
        dr7 = c.c_uint64.from_address(aligned+112)
        flags = c.c_uint32.from_address(aligned+68)
        own = dr0.value == self.address and dr7.value & 0xf00ff == 1
        rdx = c.c_uint64.from_address(aligned+136).value
        if change == 'arm':
            if dr7.value & 0xff and not own:
                raise RuntimeError('foreign_enabled_slot')
            dr0.value = self.address
            dr7.value = dr7.value & ~0xf0003 | 1
            dr6.value = 0
        elif change == 'resume':
            if self.cleaning:
                self.resume_registers.append({'address_matches':dr0.value==self.address,
                    'dr7':hex(dr7.value),'dr6_b0':bool(dr6.value & 1),
                    'at_entry':c.c_uint64.from_address(aligned+248).value==self.address,
                    'pending':tid in self.pending_steps})
            # Called only for a delivered single-step event at the exact owned
            # fixture instruction. Windows can zero disabled debug registers
            # when publishing an already-raised exception.
            cleared_own = self.cleaning and not dr7.value & 0xff
            if not own and not cleared_own:
                raise RuntimeError('own_slot_missing')
            flags.value |= 0x10000
            dr6.value = 0
        elif change == 'clear':
            self.cleanup_registers.append({'enabled':bool(dr7.value & 0xff),'own':own,
                'dr6_b0':bool(dr6.value & 1),'at_entry':c.c_uint64.from_address(aligned+248).value==self.address,
                'resume_flag':bool(flags.value & 0x10000)})
            # A hardware fault can precede event publication while frozen.
            # Leave this owned slot armed until the ACTUAL event is delivered:
            # disabling it now can erase the only recoverable register evidence.
            if own and dr6.value & 1 and c.c_uint64.from_address(aligned+248).value==self.address:
                self.pending_steps.add(tid)
                return rdx
            if dr7.value & 0xff:
                if not own:
                    raise RuntimeError('foreign_enabled_slot')
                dr7.value &= ~3
        elif change == 'assert_clear':
            if dr7.value & 0xff:
                raise RuntimeError('enabled_slot_after_detach')
        if change in ('arm','resume','clear'):
            self.ok(self.k.SetThreadContext(handle, aligned))
        return rdx

    def read(self, address, size):
        # The projector checks address/length and 512-byte/12-call limits first.
        self.read_bytes += size; self.read_calls += 1
        if self.read_bytes > 512 or self.read_calls > 12:
            raise Rejected('read_budget')
        buf = c.create_string_buffer(size); used = c.c_size_t()
        self.ok(self.k.ReadProcessMemory(self.process,address,buf,size,c.byref(used)))
        return buf.raw[:used.value]

    def process_event(self, event):
        started = time.perf_counter()
        data = bytes(event.data)
        status = 0x10002
        if event.code in (3,6):
            file_handle = struct.unpack_from('<Q',data)[0]
            if file_handle:self.k.CloseHandle(file_handle)
        if event.code == 3:
            ph,th = struct.unpack_from('<QQ',data,8)
            self.debug_handles.add(ph); self.debug_threads[event.tid] = th
        elif event.code == 2:
            self.debug_threads[event.tid] = struct.unpack_from('<Q',data)[0]
            self.created += 1
            if self.initial_break_seen:self.later_threads.add(event.tid)
        if event.code in (2,3):
            self.add_thread(event.tid)
            if self.cleaning:self.registers(event.tid,'clear')
            else:
                self.registers(event.tid,'arm')
                if event.tid == self.tid:self.pause('main_armed')
                elif self.initial_break_seen:self.pause('thread_armed')
        elif event.code == 4:
            if event.tid in self.later_threads:self.pause('thread_exit')
            self.later_threads.discard(event.tid)
            self.debug_threads.pop(event.tid,None)
            h=self.threads.pop(event.tid,None)
            if h:self.k.CloseHandle(h)
            self.exited_threads += 1
        elif event.code == 5:
            self.debug_handles.clear(); self.debug_threads.clear()
            self.stop_reason = 'target_exited'
        elif event.code == 1:
            code = struct.unpack_from('<I',data)[0]
            address = struct.unpack_from('<Q',data,16)[0]
            if code == 0x80000003 and not self.initial_break_seen:
                self.initial_break_seen = True
            elif code == 0x80000004 and address == self.address:
                self.pause('received')
                rdx = self.registers(event.tid)
                if not self.cleaning:
                    self.hits += 1
                    self.thread_hits += event.tid != self.tid
                    self.read_bytes = self.read_calls = 0
                    try:
                        if self.fault == 'slow_read':time.sleep(0.15)
                        record = project(self.read,rdx,marker=MARKER,key=self.key)
                        if record:
                            self.record = record
                            self.stop_reason = 'marker_match'
                    except Rejected:
                        self.stop_reason = 'layout_rejected'
                    self.max_read_bytes = max(self.max_read_bytes,self.read_bytes)
                    self.max_read_calls = max(self.max_read_calls,self.read_calls)
                self.registers(event.tid,'resume')
                if self.cleaning:self.registers(event.tid,'clear')
                self.pending_steps.discard(event.tid)
                self.pause('context')
            else:
                status = 0x80010001
                self.pause('foreign' if code == 0xe1234567 else 'fatal' if code == 0xc000001d else
                           'foreign_breakpoint' if code == 0x80000003 else '')
        self.ok(self.k.ContinueDebugEvent(event.pid,event.tid,status))
        self.pending = None
        elapsed = time.perf_counter()-started
        self.pause_total += elapsed; self.pause_max = max(self.pause_max,elapsed)
        if not self.cleaning and (elapsed>0.1 or self.pause_total>1):
            self.stop_reason = 'pause_budget'; self.record = None

    def has_debugger(self):
        present=c.c_int()
        self.ok(self.k.CheckRemoteDebuggerPresent(self.process,c.byref(present)))
        return bool(present.value)

    def recover_received(self):
        if self.wait(0) is not None:return
        self.discover_threads()
        for tid,handle in list(self.threads.items()):
            if self.k.WaitForSingleObject(handle,0)==0:continue
            if not self.k.ContinueDebugEvent(self.pid,tid,0x40010001):
                if c.get_last_error()!=87:raise c.WinError(c.get_last_error())
                continue
            event=self.wait(500)
            if event is None or event.tid!=tid:
                raise RuntimeError('event_replay_missing')
            self.replayed+=1
            return

    def cleanup(self, recovery=False):
        if self.identity.exited():return 'target_exited'
        self.cleaning=True
        # A guardian did not initiate attachment. Never consume a recovered
        # application breakpoint as if it were its own initial attach stop.
        if recovery:self.initial_break_seen=True
        self.attached=self.has_debugger()
        if recovery and self.attached:self.recover_received()
        freeze=StateFreeze(self.process)
        started=time.perf_counter()
        try:
            freeze.suspend()
            self.pause('cleanup_frozen')
            until=time.monotonic()+1
            while self.attached:
                event=self.pending or self.wait(0)
                if event is None:break
                self.process_event(event)
                self.drained+=1
                if time.monotonic()>until:raise RuntimeError('cleanup_event_budget')
            self.discover_threads()
            for tid,handle in list(self.threads.items()):
                if self.k.WaitForSingleObject(handle,0)==0:continue
                self.registers(tid,'clear' if self.attached else 'assert_clear')
            self.pause('cleanup_cleared')
            freeze.close()
            self.pause('cleanup_thawed')
            until=time.monotonic()+1
            while self.pending_steps:
                event=self.wait(50)
                if event:
                    self.process_event(event)
                    self.drained_after_thaw+=1
                if time.monotonic()>until:
                    raise RuntimeError('pending_step_not_delivered')
            if self.attached:
                self.ok(self.k.DebugActiveProcessStop(self.pid))
                self.attached=False
                result='detached'
            else:result='already_detached'
            self.pause('cleanup_detached')
            return result
        finally:
            freeze.close()  # kernel also releases this suspension on owner death
            self.cleanup_ms=round((time.perf_counter()-started)*1000,3)

    def release(self):
        for handle in set(self.threads.values())|self.debug_handles|set(self.debug_threads.values()):
            self.k.CloseHandle(handle)
        self.k.CloseHandle(self.thread);self.k.CloseHandle(self.process);self.identity.close()


def result_for(debugger, cleanup):
    return dict(kind='result',fixture_only=True,cleanup=cleanup,hits=debugger.hits,
                thread_hits=debugger.thread_hits,record=debugger.record,stop_reason=debugger.stop_reason,
                replayed=debugger.replayed,created=debugger.created,exited_threads=debugger.exited_threads,
                max_read_bytes=debugger.max_read_bytes,max_read_calls=debugger.max_read_calls,
                cleanup_registers=debugger.cleanup_registers,drained=debugger.drained,
                cleanup_ms=debugger.cleanup_ms,
                drained_after_thaw=debugger.drained_after_thaw,
                resume_registers=debugger.resume_registers,
                max_event_processing_ms=round(debugger.pause_max*1000,3),
                total_event_processing_ms=round(debugger.pause_total*1000,3))


def owner(args):
    emit(kind='owner_ready',fixture_only=True)
    setup=json.loads(sys.stdin.readline())
    connection=DebugObject(); connection.bind(setup['debug_handle'])
    guardian_identity=ProcessIdentity(setup['guardian_pid'])
    debugger=GuardedDebugger(args.fixture_pid,args.fixture_tid,args.fixture_address,args.fault)
    cancelled=threading.Event()
    def stdin_control():
        for line in sys.stdin:
            if line.strip()=='cancel':cancelled.set();return
    threading.Thread(target=stdin_control,daemon=True).start()
    try:
        debugger.ok(debugger.k.DebugActiveProcess(debugger.pid));debugger.attached=True
        debugger.pause('attached')
        debugger.ok(debugger.k.DebugSetProcessKillOnExit(False))
        deadline=time.monotonic()+args.duration
        announced=False
        while not debugger.stop_reason:
            # Check the retained process handle on every event-loop iteration.
            # A periodic helper can miss a guardian loss for hundreds of fast
            # calls before its next scheduling interval.
            if cancelled.is_set() or guardian_identity.exited():debugger.stop_reason='cancelled';break
            if time.monotonic()>=deadline:debugger.stop_reason='deadline';break
            event=debugger.wait(50)
            if event:debugger.process_event(event)
            if debugger.initial_break_seen and not announced:
                emit(kind='armed',fixture_only=True);announced=True
            if debugger.hits>=args.max_hits and not debugger.stop_reason:debugger.stop_reason='hit_budget'
        cleanup=debugger.cleanup()
        emit(**result_for(debugger,cleanup))
    except (OSError,RuntimeError) as e:
        emit(**result_for(debugger,'unknown'),error_type=type(e).__name__,error_code=getattr(e,'winerror',None),
             error_stage=str(e) if isinstance(e,RuntimeError) else None,pending_step_count=len(debugger.pending_steps))
        # Preserve debug object on unknown cleanup until parent inspects/tears
        # down these fixtures. Never use forced teardown as live recovery.
        while True:time.sleep(1)
    finally:
        guardian_identity.close();debugger.release();connection.close()
    return 0


def guardian(args):
    identity=ProcessIdentity(args.owner_pid)
    debugger=GuardedDebugger(args.fixture_pid,args.fixture_tid,args.fixture_address)
    connection=DebugObject()
    try:
        connection.create()
        emit(kind='guardian_ready',remote_handle=connection.duplicate_to(args.owner_pid),fixture_only=True)
        deadline=time.monotonic()+args.duration+5
        while time.monotonic()<deadline:
            if identity.exited():break
            time.sleep(0.02)
        else:raise RuntimeError('owner_did_not_exit')
        time.sleep(args.recovery_delay)
        cleanup=debugger.cleanup(recovery=True)
        emit(**result_for(debugger,cleanup))
        return 0
    except (OSError,RuntimeError) as e:
        emit(**result_for(debugger,'unknown'),error_type=type(e).__name__,error_code=getattr(e,'winerror',None),
             error_stage=str(e) if isinstance(e,RuntimeError) else None,pending_step_count=len(debugger.pending_steps))
        while True:time.sleep(1)
    finally:
        debugger.release();connection.close();identity.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--role',choices=('owner','guardian'),required=True)
    p.add_argument('--fixture-pid',type=int,required=True)
    p.add_argument('--fixture-tid',type=int,required=True)
    p.add_argument('--fixture-address',type=int,required=True)
    p.add_argument('--owner-pid',type=int)
    p.add_argument('--duration',type=float,default=3)
    p.add_argument('--max-hits',type=int,default=200)
    p.add_argument('--recovery-delay',type=float,default=0.2)
    p.add_argument('--fault',choices=('received','context','thread_armed','thread_exit','main_armed','attached','cleanup_frozen','cleanup_cleared','cleanup_thawed','cleanup_detached','foreign','foreign_breakpoint','fatal','slow_read'))
    a=p.parse_args()
    if not 0<a.duration<=120 or not 1<=a.max_hits<=200 or not 0<=a.recovery_delay<=0.5:p.error('budget')
    if a.role=='guardian' and a.owner_pid is None:p.error('owner pid required')
    return owner(a) if a.role=='owner' else guardian(a)


if __name__=='__main__':raise SystemExit(main())
