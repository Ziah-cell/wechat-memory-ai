"""Fixture-only raw Win32 debugger contrast, main-thread execute slot only.

Not a message collector or replacement production observer. Does not load DbgEng,
patch instructions or inject a DLL. Used to distinguish engine behavior from the
OS debug-register lifetime. Requires a sibling fixture with the four-byte stub.
"""
import argparse
import ctypes as c
import json
import struct
import sys
import threading
import time

from receive_probe_observer import ProcessIdentity

U32, PTR = c.c_uint32, c.c_void_p


class DebugEvent(c.Structure):
    # x64 EXCEPTION_DEBUG_INFO is the largest union member: 160 bytes, align 8.
    _fields_ = [("code", U32), ("pid", U32), ("tid", U32), ("data", c.c_uint64 * 20)]


def emit(**data):
    print(json.dumps(data), flush=True)


class NativeDebugger:
    def __init__(self, pid, tid, address):
        if c.sizeof(PTR) != 8 or c.sizeof(DebugEvent) != 176 or DebugEvent.data.offset != 16:
            raise RuntimeError("AMD64 ABI required")
        self.identity = ProcessIdentity(pid)
        self.pid, self.tid, self.address = pid, tid, address
        self.k = c.WinDLL("kernel32", use_last_error=True)
        bindings = {
            "OpenThread": ([U32, c.c_int, U32], PTR),
            "OpenProcess": ([U32, c.c_int, U32], PTR),
            "GetProcessIdOfThread": ([PTR], U32),
            "ReadProcessMemory": ([PTR, PTR, PTR, c.c_size_t, c.POINTER(c.c_size_t)], c.c_int),
            "CloseHandle": ([PTR], c.c_int),
            "DebugActiveProcess": ([U32], c.c_int),
            "DebugActiveProcessStop": ([U32], c.c_int),
            "DebugSetProcessKillOnExit": ([c.c_int], c.c_int),
            "WaitForDebugEvent": ([c.POINTER(DebugEvent), U32], c.c_int),
            "ContinueDebugEvent": ([U32, U32, U32], c.c_int),
            "GetThreadContext": ([PTR, PTR], c.c_int),
            "SetThreadContext": ([PTR, PTR], c.c_int),
            "SuspendThread": ([PTR], U32), "ResumeThread": ([PTR], U32),
        }
        for name, (args, result) in bindings.items():
            getattr(self.k, name).argtypes = args
            getattr(self.k, name).restype = result
        self.thread = self.k.OpenThread(0x81a, False, tid)
        self.attached = False
        self.pending = None
        self.armed = False
        self.hits = 0
        self.debug_handles = set()
        self.debug_threads = {}
        if not self.thread or self.k.GetProcessIdOfThread(self.thread) != pid:
            raise RuntimeError("not own fixture thread")
        handle = self.k.OpenProcess(0x1010, False, pid)
        if not handle:
            raise c.WinError(c.get_last_error())
        try:
            buf, used = c.create_string_buffer(4), c.c_size_t()
            self.ok(self.k.ReadProcessMemory(handle, address, buf, 4, c.byref(used)))
            if used.value != 4 or buf.raw != b"\x48\x89\xd0\xc3":
                raise RuntimeError("not fixture stub")
        finally:
            self.k.CloseHandle(handle)

    def ok(self, result):
        if not result:
            raise c.WinError(c.get_last_error())

    def context(self, change):
        # Called only while all threads are debug-stopped, or after our own
        # SuspendThread. The debugger only changes its main-thread slot and RF.
        storage = c.create_string_buffer(1247)
        aligned = (c.addressof(storage) + 15) & ~15
        c.c_uint32.from_address(aligned + 48).value = 0x100011
        self.ok(self.k.GetThreadContext(self.thread, aligned))
        dr0 = c.c_uint64.from_address(aligned + 72)
        dr6 = c.c_uint64.from_address(aligned + 104)
        dr7 = c.c_uint64.from_address(aligned + 112)
        flags = c.c_uint32.from_address(aligned + 68)
        if change == "arm":
            if dr7.value & 0xff:
                raise RuntimeError("fixture already has enabled debug slots")
            dr0.value = self.address
            dr7.value = (dr7.value & ~0xf0003) | 1
            dr6.value = 0
        elif change == "resume_own":
            if dr0.value != self.address or not dr7.value & 1:
                raise RuntimeError("owned slot lost")
            flags.value |= 0x10000  # RF lets the faulting instruction run once.
            dr6.value = 0
        elif change == "clear":
            if dr0.value != self.address:
                raise RuntimeError("refuse clearing unknown debug slot")
            dr7.value &= ~3
        else:
            raise ValueError(change)
        self.ok(self.k.SetThreadContext(self.thread, aligned))

    def wait(self, ms=50):
        event = DebugEvent()
        if not self.k.WaitForDebugEvent(c.byref(event), ms):
            if c.get_last_error() in (121, 258):
                return None
            raise c.WinError(c.get_last_error())
        if event.pid != self.pid:
            raise RuntimeError("unexpected debug process")
        self.pending = event
        return event

    def process_event(self, event):
        data = bytes(event.data)
        status = 0x10002
        if event.code in (3, 6):
            file_handle = struct.unpack_from("<Q", data)[0]
            if file_handle:
                self.k.CloseHandle(file_handle)
        if event.code == 3:
            ph, th = struct.unpack_from("<QQ", data, 8)
            self.debug_handles.add(ph)
            self.debug_threads[event.tid] = th
        elif event.code == 2:
            self.debug_threads[event.tid] = struct.unpack_from("<Q", data)[0]
        elif event.code == 4:
            self.debug_threads.pop(event.tid, None)  # system closes on Continue
        elif event.code == 5:
            self.debug_handles.clear()
            self.debug_threads.clear()
        elif event.code == 1:
            code = struct.unpack_from("<I", data)[0]
            address = struct.unpack_from("<Q", data, 16)[0]
            if code == 0x80000003 and not self.armed:
                self.context("arm")
                self.armed = True
            elif code == 0x80000004 and event.tid == self.tid and address == self.address:
                self.context("resume_own")
                self.hits += 1
            else:
                status = 0x80010001  # preserve unrelated exception behavior
        self.ok(self.k.ContinueDebugEvent(event.pid, event.tid, status))
        self.pending = None

    def cleanup(self):
        if self.identity.exited():
            return "target_exited"
        prior = self.k.SuspendThread(self.thread)
        if prior == 0xffffffff:
            raise c.WinError(c.get_last_error())
        try:
            # Our main thread cannot enter the fixture function during this
            # normal cleanup. Drain already queued events before clearing.
            until = time.monotonic() + 1
            while time.monotonic() < until:
                event = self.pending or self.wait(0)
                if event is None:
                    break
                self.process_event(event)
            if self.armed:
                self.context("clear")
            if self.attached:
                self.ok(self.k.DebugActiveProcessStop(self.pid))
                self.attached = False
        finally:
            if self.k.ResumeThread(self.thread) == 0xffffffff:
                raise c.WinError(c.get_last_error())
        return "detached"

    def run(self):
        self.ok(self.k.DebugActiveProcess(self.pid))
        self.attached = True
        self.ok(self.k.DebugSetProcessKillOnExit(False))
        cancelled = threading.Event()
        def controls():
            for line in sys.stdin:
                if line.strip() == "cancel":
                    cancelled.set()
                    return
        threading.Thread(target=controls, daemon=True).start()
        deadline = time.monotonic() + 6
        announced = False
        try:
            while time.monotonic() < deadline and not cancelled.is_set() and self.hits < 200:
                event = self.wait()
                if event is not None:
                    self.process_event(event)
                    if event.code == 5:
                        break
                if self.armed and not announced:
                    emit(kind="armed", fixture_only=True, raw_win32=True)
                    announced = True
            cleanup = self.cleanup()
            emit(kind="result", cleanup=cleanup, hits=self.hits, fixture_only=True,
                 raw_win32=True, stop_reason="cancelled" if cancelled.is_set() else "budget_or_exit")
        finally:
            if not self.attached:
                for handle in self.debug_handles | set(self.debug_threads.values()):
                    self.k.CloseHandle(handle)
            self.k.CloseHandle(self.thread)
            self.identity.close()
        return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture-pid", type=int, required=True)
    p.add_argument("--fixture-tid", type=int, required=True)
    p.add_argument("--fixture-address", type=int, required=True)
    a = p.parse_args()
    return NativeDebugger(a.fixture_pid, a.fixture_tid, a.fixture_address).run()


if __name__ == "__main__":
    raise SystemExit(main())
