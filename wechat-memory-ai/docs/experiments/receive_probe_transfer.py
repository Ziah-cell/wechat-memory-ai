"""Fixture-only pre-retained debug-object transfer experiment.

Native API declarations come from pinned phnt, not a Microsoft API guarantee.
The guardian creates a no-kill debug object BEFORE any attachment and duplicates
it into its sibling owner. Only self-owned fixtures are accepted by identity and
stub checks. No WeChat mode, payload collection, code patches or DLL injection.
"""
import argparse
import ctypes as c
import json
import struct
import sys
import time

from receive_probe_observer import ProcessIdentity
from receive_probe_variants import ControllerLease
from receive_probe_win32 import NativeDebugger, U32, PTR, emit


class DebugObject:
    def __init__(self):
        self.n = c.WinDLL("ntdll", use_last_error=True)
        self.n.NtCreateDebugObject.argtypes = [c.POINTER(PTR), U32, PTR, U32]
        self.n.NtCreateDebugObject.restype = c.c_int32
        self.n.DbgUiSetThreadDebugObject.argtypes = [PTR]
        self.n.DbgUiSetThreadDebugObject.restype = None
        self.n.DbgUiGetThreadDebugObject.argtypes = []
        self.n.DbgUiGetThreadDebugObject.restype = PTR
        self.k = c.WinDLL("kernel32", use_last_error=True)
        self.k.GetCurrentProcess.restype = PTR
        self.k.OpenProcess.argtypes = [U32, c.c_int, U32]
        self.k.OpenProcess.restype = PTR
        self.k.CloseHandle.argtypes = [PTR]
        self.k.DuplicateHandle.argtypes = [PTR, PTR, PTR, c.POINTER(PTR), U32, c.c_int, U32]
        self.k.DuplicateHandle.restype = c.c_int
        self.k.WaitForSingleObject.argtypes = [PTR, U32]
        self.k.WaitForSingleObject.restype = U32
        self.handle = None

    def create(self):
        handle = PTR()
        # DEBUG_ALL_ACCESS, flags=0 (no DEBUG_KILL_ON_CLOSE), no named object.
        status = self.n.NtCreateDebugObject(c.byref(handle), 0x1f000f, None, 0)
        if status < 0:
            raise RuntimeError(f"NtCreateDebugObject failed: {status & 0xffffffff:#x}")
        self.bind(handle.value)

    def bind(self, handle):
        self.handle = handle
        self.n.DbgUiSetThreadDebugObject(handle)
        if self.n.DbgUiGetThreadDebugObject() != handle:
            raise RuntimeError("thread debug-object binding mismatch")

    def duplicate_to(self, pid):
        # Caller also holds ProcessIdentity for this exact sibling. No global
        # handle enumeration or access to unrelated processes is performed.
        destination = self.k.OpenProcess(0x40, False, pid)  # PROCESS_DUP_HANDLE
        if not destination:
            raise c.WinError(c.get_last_error())
        try:
            remote = PTR()
            if not self.k.DuplicateHandle(self.k.GetCurrentProcess(), self.handle,
                                           destination, c.byref(remote), 0, False, 2):
                raise c.WinError(c.get_last_error())
            return remote.value
        finally:
            self.k.CloseHandle(destination)

    def close(self):
        self.n.DbgUiSetThreadDebugObject(None)
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None


class TransferOwner(NativeDebugger):
    def __init__(self, pid, tid, address, pause_stage):
        super().__init__(pid, tid, address)
        self.pause_stage = pause_stage

    def pause(self, stage):
        if self.pause_stage == stage:
            emit(kind="fault_boundary", stage=stage, fixture_only=True)
            time.sleep(8)  # the parent kills only this child at this boundary

    def context(self, change):
        if change == 'arm':
            self.pause('arm_before')
        super().context(change)
        if change == 'arm':
            self.pause('arm_written')
        if change == 'resume_own':
            self.pause('context')

    def run(self):
        original = self.k.DebugActiveProcess
        def attach(pid):
            result = original(pid)
            if result:
                self.pause('attached')
            return result
        self.k.DebugActiveProcess = attach
        return super().run()

    def process_event(self, event):
        code = struct.unpack_from('<I', bytes(event.data))[0] if event.code == 1 else None
        own = (code == 0x80000004 and event.tid == self.tid and
               struct.unpack_from('<Q', bytes(event.data), 16)[0] == self.address)
        # The boundary notice goes only to the test parent, never to guardian.
        if own:
            self.pause('received')
        elif code == 0xe1234567:
            self.pause('foreign')
        elif code == 0xc000001d:
            self.pause('fatal')
        super().process_event(event)
        if own:
            self.pause('continued')


class TransferGuardian(NativeDebugger):
    def has_debugger(self):
        handle = self.k.OpenProcess(0x400, False, self.pid)
        if not handle:
            raise c.WinError(c.get_last_error())
        self.k.CheckRemoteDebuggerPresent.argtypes = [PTR, c.POINTER(c.c_int)]
        self.k.CheckRemoteDebuggerPresent.restype = c.c_int
        try:
            present = c.c_int()
            self.ok(self.k.CheckRemoteDebuggerPresent(handle, c.byref(present)))
            return bool(present.value)
        finally:
            self.k.CloseHandle(handle)

    def slot_state(self):
        # Caller must have stopped the thread. Read only debug registers.
        storage = c.create_string_buffer(1247)
        aligned = (c.addressof(storage) + 15) & ~15
        c.c_uint32.from_address(aligned + 48).value = 0x100010
        self.ok(self.k.GetThreadContext(self.thread, aligned))
        return (c.c_uint64.from_address(aligned + 72).value == self.address,
                c.c_uint64.from_address(aligned + 112).value & 0xff)

    def context(self, change):
        if change == 'clear':
            own, enabled = self.slot_state()
            emit(kind='slot_state', owned_address=own, enabled_slots=enabled, fixture_only=True)
            if not enabled:
                return  # the owner may have died before arming, or after clearing
            if not own or enabled != 1:
                raise RuntimeError('unexpected enabled debug slot')
        super().context(change)

    def cleanup(self):
        if self.attached:
            return super().cleanup()
        prior = self.k.SuspendThread(self.thread)
        if prior == 0xffffffff:
            raise c.WinError(c.get_last_error())
        try:
            _, enabled = self.slot_state()
            if enabled:
                raise RuntimeError('detached fixture still has enabled debug slots')
            emit(kind='already_clean', debugger_present=False, enabled_slots=enabled, fixture_only=True)
            return 'already_detached'
        finally:
            if self.k.ResumeThread(self.thread) == 0xffffffff:
                raise c.WinError(c.get_last_error())

    def recover_received_event(self):
        # A received event is not returned to a second waiter automatically.
        # Request replay; never guess its exception code or mark it handled.
        if self.wait(0) is not None:
            emit(kind="replay_probe", queued_event=True, fixture_only=True)
            return
        if not self.k.ContinueDebugEvent(self.pid, self.tid, 0x40010001):
            error = c.get_last_error()
            emit(kind="replay_probe", replay_requested=False, error_code=error, fixture_only=True)
            if error != 87:  # no matching received event in this fixture object
                raise c.WinError(error)
            return
        event = self.wait(500)
        if event is None or event.tid != self.tid:
            raise RuntimeError("requested event replay was not observed")
        emit(kind="replay_probe", replay_requested=True, event_code=event.code,
             exception_code=hex(struct.unpack_from('<I', bytes(event.data))[0]) if event.code == 1 else None,
             fixture_only=True)
        # self.pending now holds the actual redelivered event. Normal cleanup
        # classifies owned steps, and forwards unrelated exceptions unhandled.


def owner(args):
    emit(kind="owner_ready", fixture_only=True)
    message = json.loads(sys.stdin.readline())
    connection = DebugObject()
    lease = ControllerLease(message['guardian_pid'])
    connection.bind(message['debug_handle'])
    sys.stdin = lease
    try:
        return TransferOwner(args.fixture_pid, args.fixture_tid, args.fixture_address,
                             'received' if args.pause_event else args.pause_stage).run()
    finally:
        lease.close()
        connection.close()


def guardian(args):
    owner_identity = ProcessIdentity(args.owner_pid)
    connection = DebugObject()
    debugger = TransferGuardian(args.fixture_pid, args.fixture_tid, args.fixture_address)
    try:
        connection.create()
        remote = connection.duplicate_to(args.owner_pid)
        emit(kind="guardian_ready", remote_handle=remote, fixture_only=True,
             created_before_attach=True)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = connection.k.WaitForSingleObject(owner_identity.handle, 50)
            if state == 0:
                break
            if state != 258:
                raise RuntimeError("owner wait failed")
        else:
            emit(kind="result", cleanup="not_attempted", reason="owner_still_alive", fixture_only=True)
            return 2
        detected = time.monotonic()
        # Deliberately delayed recovery: autonomous target calls are NOT waiting
        # for the parent to allow them. The shared kernel object must bridge this.
        time.sleep(0.2)
        debugger.armed = True  # request inspection/clear; never arm during recovery
        try:
            debugger.attached = debugger.has_debugger()
            if args.replay and debugger.attached:
                debugger.recover_received_event()
            cleanup = debugger.cleanup()
            emit(kind="result", cleanup=cleanup, recovery_hits=debugger.hits,
                 recovery_ms=round((time.monotonic()-detected)*1000, 3), fixture_only=True)
            return 0 if cleanup in ('detached','already_detached') else 2
        except (OSError, RuntimeError) as error:
            emit(kind="result", cleanup="unknown", error_type=type(error).__name__,
                 error_code=getattr(error, 'winerror', None), fixture_only=True)
            return 2
    finally:
        # All objects/handles here belong to this harness's own processes.
        connection.close()
        owner_identity.close()
        debugger.k.CloseHandle(debugger.thread)
        debugger.identity.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--role', choices=('owner', 'guardian'), required=True)
    p.add_argument('--fixture-pid', type=int, required=True)
    p.add_argument('--fixture-tid', type=int, required=True)
    p.add_argument('--fixture-address', type=int, required=True)
    p.add_argument('--owner-pid', type=int)
    p.add_argument('--pause-event', action='store_true')
    p.add_argument('--pause-stage', choices=('received','context','continued','foreign','fatal',
                                           'attached','arm_before','arm_written'))
    p.add_argument('--replay', action='store_true')
    a = p.parse_args()
    if a.role == 'guardian' and a.owner_pid is None:
        p.error('sibling owner PID required')
    return owner(a) if a.role == 'owner' else guardian(a)


if __name__ == '__main__':
    raise SystemExit(main())
