"""Experimental external DbgEng observer. Currently SELF-OWNED FIXTURES ONLY.

No WeChat launch mode is present. COM slots/signatures were checked against the
Microsoft WinSDK header pinned in data/bounded-receive-native-20261009.
Only the engine changes debugger state. No WriteVirtual/Execute/injection API.
"""
import argparse
import ctypes as c
import json
import os
import pathlib
import secrets
import struct
import sys
import threading
import time
import uuid

from check_receive_probe_layout import project, Rejected, MARKER

U32 = c.c_uint32
U64 = c.c_uint64
PTR = c.c_void_p
HR = c.c_int32

# Checked against every preceding STDMETHOD and STDMETHODV in the SDK header.
SLOTS = {
    "IDebugClient": {"QueryInterface": 0, "Release": 2, "AttachProcess": 12,
                     "GetProcessOptions": 15, "SetProcessOptions": 18, "DetachProcesses": 25,
                     "SetEventCallbacks": 46},
    "IDebugControl": {"Release": 2, "SetInterrupt": 4, "GetDebuggeeType": 34,
                      "GetExecutionStatus": 49, "SetExecutionStatus": 50,
                      "AddEngineOptions": 54,
                      "AddBreakpoint": 72, "RemoveBreakpoint": 73, "WaitForEvent": 93,
                      "GetLastEventInformation": 94},
    "IDebugDataSpaces": {"Release": 2, "ReadVirtualUncached": 6},
    "IDebugRegisters": {"Release": 2, "GetIndexByName": 5, "GetValue": 6},
    "IDebugBreakpoint": {"AddFlags": 7, "SetOffset": 11, "SetDataParameters": 13},
}


class ProbeError(Exception):
    def __init__(self, stage, hr=None):
        self.stage = stage
        self.hr = None if hr is None else hr & 0xffffffff
        super().__init__(stage)


def checked(hr, stage):
    if hr < 0:
        raise ProbeError(stage, hr)
    return hr


def guid(text):
    return (c.c_ubyte * 16).from_buffer_copy(uuid.UUID(text).bytes_le)


class Com:
    def __init__(self, pointer, interface):
        self.interface = interface
        self.pointer = pointer if isinstance(pointer, PTR) else PTR(pointer)
        if not self.pointer.value:
            raise ProbeError("null_interface")
        self.keep = []

    def call(self, method, types, *args):
        slot = SLOTS[self.interface][method]
        table = c.cast(self.pointer, c.POINTER(c.POINTER(PTR))).contents
        function = c.WINFUNCTYPE(HR, PTR, *types)(table[slot])
        return function(self.pointer, *args)

    def query(self, iid, interface):
        result = PTR()
        checked(self.call("QueryInterface", [PTR, c.POINTER(PTR)], guid(iid), c.byref(result)), "query_interface")
        return Com(result, interface)

    def release(self):
        if self.pointer.value:
            self.call("Release", [])
            self.pointer = PTR()


class ProcessIdentity:
    """Limited handle to exactly the selected fixture; no memory reads."""
    def __init__(self, pid):
        self.k = c.WinDLL("kernel32", use_last_error=True)
        self.k.OpenProcess.argtypes = [U32, c.c_int, U32]
        self.k.OpenProcess.restype = PTR
        self.k.CloseHandle.argtypes = [PTR]
        self.k.GetExitCodeProcess.argtypes = [PTR, c.POINTER(U32)]
        self.k.QueryFullProcessImageNameW.argtypes = [PTR, U32, c.c_wchar_p, c.POINTER(U32)]
        self.handle = self.k.OpenProcess(0x101000, False, pid)  # query-limited + synchronize
        if not self.handle:
            raise ProbeError("fixture_open_failed")
        try:
            size = U32(32768)
            name = c.create_unicode_buffer(size.value)
            if not self.k.QueryFullProcessImageNameW(self.handle, 0, name, c.byref(size)):
                raise ProbeError("fixture_image_query_failed")
            if pathlib.Path(name.value).resolve() != pathlib.Path(sys.executable).resolve():
                raise ProbeError("not_fixture_python")
            # Native PROCESS_BASIC_INFORMATION: PID and parent PID are ULONG_PTR.
            class PBI(c.Structure):
                _fields_ = [("exit", HR), ("peb", PTR), ("affinity", U64),
                            ("priority", HR), ("pid", U64), ("parent", U64)]
            n = c.WinDLL("ntdll")
            n.NtQueryInformationProcess.argtypes = [PTR, U32, PTR, U32, c.POINTER(U32)]
            n.NtQueryInformationProcess.restype = HR
            value = PBI()
            used = U32()
            checked(n.NtQueryInformationProcess(self.handle, 0, c.byref(value), c.sizeof(value), c.byref(used)), "fixture_parent_query")
            if value.pid != pid or value.parent != os.getppid() or pid == os.getpid():
                raise ProbeError("not_sibling_fixture")
        except BaseException:
            self.close()
            raise

    def exited(self):
        value = U32()
        if not self.k.GetExitCodeProcess(self.handle, c.byref(value)):
            raise ProbeError("fixture_exit_query_failed")
        return value.value != 259

    def close(self):
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None


class EventCallbacks:
    """Callbacks only request an event-loop stop; no target reads or logging."""
    def __init__(self):
        self.refs = 1
        self.last_stop = None
        self.stops = 0
        self.functions = []
        def add(result, types, body):
            self.functions.append(c.WINFUNCTYPE(result, PTR, *types)(body))
        def query(this, iid, out):
            if c.string_at(iid, 16) in (bytes(guid("00000000-0000-0000-c000-000000000046")),
                                        bytes(guid("337be28b-5036-4d72-b6bf-c45fbb9f2eaa"))):
                out[0] = c.addressof(self.object)
                self.refs += 1
                return 0
            out[0] = None
            return -2147467262
        def addref(this):
            self.refs += 1
            return self.refs
        def release(this):
            self.refs -= 1
            return self.refs
        def mask(this, out):
            out[0] = 0x23  # breakpoint, exception, exit process; finish attach first
            return 0
        def stop(*args):
            self.stops += 1
            self.last_stop = time.monotonic()
            return 6
        def ignore(*args):
            return 0
        add(HR, [PTR, c.POINTER(PTR)], query)
        add(U32, [], addref)
        add(U32, [], release)
        add(HR, [c.POINTER(U32)], mask)
        add(HR, [PTR], stop)
        add(HR, [PTR, U32], stop)
        add(HR, [U64, U64, U64], ignore)
        add(HR, [U32], ignore)
        add(HR, [U64, U64, U64, U32, PTR, PTR, U32, U32, U64, U64, U64], ignore)
        add(HR, [U32], stop)
        add(HR, [U64, U64, U32, PTR, PTR, U32, U32], ignore)
        add(HR, [PTR, U64], ignore)
        add(HR, [U32, U32], ignore)
        add(HR, [U32], ignore)
        for _ in range(3):
            add(HR, [U32, U64], ignore)
        self.table = (PTR * len(self.functions))(*(c.cast(f, PTR).value for f in self.functions))
        self.object = (PTR * 1)(c.addressof(self.table))


class Engine:
    def __init__(self):
        if c.sizeof(PTR) != 8:
            raise ProbeError("x64_required")
        self.lib = c.WinDLL(r"C:\Windows\System32\dbgeng.dll", winmode=0x800)
        self.lib.DebugCreate.argtypes = [PTR, c.POINTER(PTR)]
        self.lib.DebugCreate.restype = HR
        result = PTR()
        checked(self.lib.DebugCreate(guid("27fe5639-8407-4f47-8364-ee118fb08ac8"), c.byref(result)), "debug_create")
        self.client = Com(result, "IDebugClient")
        self.control = self.client.query("5182e668-105e-416e-ad92-24ef800424ba", "IDebugControl")
        self.spaces = self.client.query("88f7dfab-3ea7-4c3a-aefb-c4e8106173aa", "IDebugDataSpaces")
        self.registers = self.client.query("ce289126-9e84-45a7-937e-67bb18691493", "IDebugRegisters")
        self.attached = False
        self.breakpoint = None
        self.rdx_index = None
        self.wait_counts = {}
        self.pending_own_breakpoint = False
        self.at_event = False
        self.cleanup_steps = []
        checked(self.control.call("AddEngineOptions", [U32], 0x48d028), "engine_options")
        self.callbacks = EventCallbacks()
        checked(self.client.call("SetEventCallbacks", [PTR], c.addressof(self.callbacks.object)), "set_event_callbacks")

    def attach(self, pid):
        # This installed engine rejects process options before a live session.
        # The pending-attach/crash interval requires its own fixture test.
        checked(self.client.call("AttachProcess", [U64, U32, U32], 0, pid, 0), "attach")
        self.attached = True  # includes pending attachment, must clean up on failure
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            hr = self.wait()
            if hr == 0:
                checked(self.client.call("SetProcessOptions", [U32], 3), "only_this_process_option")
                options = U32()
                checked(self.client.call("GetProcessOptions", [c.POINTER(U32)], c.byref(options)), "get_process_options")
                if options.value & 3 != 3:
                    raise ProbeError("detach_on_exit_not_set")
                kind, extra = self.event()
                if kind == 2 and len(extra) >= 4 and struct.unpack_from("<I", extra)[0] == 0x80000003:
                    return  # initial debugger break, before installing our breakpoint
                if kind == 0x10:
                    self.resume()
                    continue
                raise ProbeError("unexpected_attach_event")
        raise ProbeError("attach_deadline")

    def wait(self):
        hr = self.control.call("WaitForEvent", [U32, U32], 0, 250)
        self.at_event = hr == 0
        self.pending_own_breakpoint = False
        key = hex(hr & 0xffffffff)
        self.wait_counts[key] = self.wait_counts.get(key, 0) + 1
        if hr < 0 and (hr & 0xffffffff) not in (0x8000000a, 0x8000ffff):
            raise ProbeError("wait_failed", hr)
        return hr

    def resume(self, status=1):
        checked(self.control.call("SetExecutionStatus", [U32], status), "resume")

    def event(self):
        kind, process, thread, used, description_used = [U32() for _ in range(5)]
        extra = c.create_string_buffer(256)
        checked(self.control.call("GetLastEventInformation", [c.POINTER(U32), c.POINTER(U32), c.POINTER(U32), PTR, U32,
                                      c.POINTER(U32), PTR, U32, c.POINTER(U32)],
                                  c.byref(kind), c.byref(process), c.byref(thread), extra, len(extra),
                                  c.byref(used), None, 0, c.byref(description_used)), "event_info")
        self.pending_own_breakpoint = kind.value == 1
        return kind.value, bytes(extra.raw[:used.value])

    def arm(self, address):
        # Fixture signature check; the target memory read is exactly four bytes.
        if self.read(address, 4) != b"\x48\x89\xd0\xc3":
            raise ProbeError("fixture_signature_mismatch")
        result = PTR()
        checked(self.control.call("AddBreakpoint", [U32, U32, c.POINTER(PTR)], 1, 0xffffffff, c.byref(result)), "add_breakpoint")
        self.breakpoint = Com(result, "IDebugBreakpoint")
        checked(self.breakpoint.call("SetOffset", [U64], address), "breakpoint_offset")
        checked(self.breakpoint.call("SetDataParameters", [U32, U32], 1, 4), "breakpoint_parameters")
        checked(self.breakpoint.call("AddFlags", [U32], 4), "breakpoint_enable")
        index = U32()
        checked(self.registers.call("GetIndexByName", [c.c_char_p, c.POINTER(U32)], b"rdx", c.byref(index)), "rdx_lookup")
        self.rdx_index = index.value

    def rdx(self):
        value = c.create_string_buffer(32)
        checked(self.registers.call("GetValue", [U32, PTR], self.rdx_index, value), "rdx_read")
        if struct.unpack_from("<I", value.raw, 28)[0] != 4:  # DEBUG_VALUE_INT64
            raise ProbeError("rdx_type")
        return struct.unpack_from("<Q", value.raw)[0]

    def read(self, address, size):
        if size <= 0 or size > 512:
            raise ProbeError("read_budget")
        value = c.create_string_buffer(size)
        actual = U32()
        checked(self.spaces.call("ReadVirtualUncached", [U64, PTR, U32, c.POINTER(U32)], address, value, size, c.byref(actual)), "read_virtual")
        if actual.value != size:
            raise ProbeError("short_read")
        return value.raw

    def interrupt_exit(self):
        return self.control.call("SetInterrupt", [U32], 2)  # documented callable from any thread

    def detach(self):
        failed = False
        cleanup_break = False
        if self.attached:
            status = U32()
            hr = self.control.call("GetExecutionStatus", [c.POINTER(U32)], c.byref(status))
            self.cleanup_steps.append({"api": "status", "hr": hex(hr & 0xffffffff), "value": status.value})
            # This engine reports logical BREAK even after a timed-out wait when
            # target context remains unavailable. Require a real S_OK event.
            if hr == 0 and not self.at_event and status.value != 7:
                # After finite WaitForEvent timeout this engine retains logical
                # BREAK. Mark GO before ACTIVE so the engine requests a real
                # target break instead of merely registering a user interrupt.
                self.resume()
                hr = self.control.call("SetInterrupt", [U32], 0)  # ACTIVE, cleanup must access context
                self.cleanup_steps.append({"api": "interrupt_active", "hr": hex(hr & 0xffffffff)})
                until = time.monotonic() + 1
                while hr >= 0 and time.monotonic() < until:
                    hr = self.wait()
                    if hr == 0:
                        kind, extra = self.event()
                        cleanup_break = kind == 2 and len(extra) >= 4 and struct.unpack_from("<I", extra)[0] == 0x80000003
                        break
                else:
                    failed = True
        if self.breakpoint:
            hr = self.control.call("RemoveBreakpoint", [PTR], self.breakpoint.pointer)
            self.cleanup_steps.append({"api": "remove_breakpoint", "hr": hex(hr & 0xffffffff)})
            if hr < 0:
                failed = True
            self.breakpoint = None  # RemoveBreakpoint owns deletion, not Release
        # Removing a hardware breakpoint does not consume its pending single-step
        # exception. Continue that OWN event as handled before detaching.
        if self.attached and (self.pending_own_breakpoint or cleanup_break) and not failed:
            try:
                self.resume(2)
                self.wait()
            except ProbeError:
                failed = True
        if self.attached:
            hr = self.client.call("DetachProcesses", [])
            self.cleanup_steps.append({"api": "detach", "hr": hex(hr & 0xffffffff)})
            if hr < 0:
                failed = True
            else:
                self.attached = False
        return "cleanup_unknown" if failed else "detached"

    def release(self):
        for value in [self.registers, self.spaces, self.control, self.client]:
            value.release()

    def diagnostics(self):
        status, kind, qualifier = U32(), U32(), U32()
        a = self.control.call("GetExecutionStatus", [c.POINTER(U32)], c.byref(status))
        b = self.control.call("GetDebuggeeType", [c.POINTER(U32), c.POINTER(U32)], c.byref(kind), c.byref(qualifier))
        return {"wait_hresult_counts": dict(self.wait_counts), "callback_stops": self.callbacks.stops,
                "status_hr": hex(a & 0xffffffff), "status": status.value,
                "type_hr": hex(b & 0xffffffff), "type": kind.value, "qualifier": qualifier.value}


def observe_fixture(pid, address, duration, max_hits):
    identity = ProcessIdentity(pid)
    engine = None
    cancelled = threading.Event()
    finished = threading.Event()
    control_lock = threading.Lock()
    result = {"kind": "result", "stop_reason": "not_started", "hits": 0,
              "record": None, "cleanup": "not_attached", "fixture_only": True}
    try:
        engine = Engine()
        engine.attach(pid)
        engine.arm(address)
        deadline = time.monotonic() + duration
        def control_input():
            for line in sys.stdin:
                if line.strip() == "cancel":
                    with control_lock:
                        if not finished.is_set():
                            cancelled.set()
                            engine.interrupt_exit()
                    return
        threading.Thread(target=control_input, daemon=True).start()
        key = secrets.token_bytes(32)
        engine.resume()
        print(json.dumps({"kind": "armed", "fixture_only": True}), flush=True)
        paused_total = 0
        while True:
            if identity.exited():
                result["stop_reason"] = "target_exited"
                break
            if cancelled.is_set():
                result["stop_reason"] = "cancelled"
                break
            if time.monotonic() >= deadline:
                result["stop_reason"] = "deadline"
                break
            hr = engine.wait()
            if hr != 0:
                continue
            started = engine.callbacks.last_stop or time.monotonic()
            kind, extra = engine.event()
            if kind == 1:
                result["hits"] += 1
                try:
                    record = project(engine.read, engine.rdx(), marker=MARKER, key=key)
                except Rejected:
                    result["stop_reason"] = "layout_rejected"
                    break
                if time.monotonic() - started > 0.1 or paused_total + time.monotonic() - started > 1:
                    result["stop_reason"] = "pause_budget"
                    break
                if record:
                    result["record"] = record
                    result["stop_reason"] = "marker_match"
                    break
                if result["hits"] >= max_hits:
                    result["stop_reason"] = "hit_budget"
                    break
            elif kind == 0x20:
                result["stop_reason"] = "target_exited"
                break
            elapsed = time.monotonic() - started
            paused_total += elapsed
            if elapsed > 0.1 or paused_total > 1:
                result["stop_reason"] = "pause_budget"
                break
            # Never claim unrelated exceptions handled by the observer.
            engine.resume(3 if kind == 2 else 1)
    except ProbeError as error:
        result["stop_reason"] = error.stage
        result["hresult"] = error.hr
    finally:
        with control_lock:
            finished.set()
        if engine:
            result["fixture_diagnostics"] = engine.diagnostics()
            try:
                result["cleanup"] = engine.detach()
            except ProbeError as error:
                result["cleanup"] = "cleanup_unknown"
                result["cleanup_error"] = error.stage
            result["cleanup_api"] = engine.cleanup_steps
            if result["cleanup"] == "detached":
                engine.release()
        identity.close()
    print(json.dumps(result), flush=True)
    if result["cleanup"] == "cleanup_unknown":
        # Keep owner alive: a forced exit is NOT a recovery method for real apps.
        while True:
            time.sleep(1)
    return 0 if result["stop_reason"] in {
        "marker_match", "cancelled", "deadline", "hit_budget", "layout_rejected",
        "target_exited", "pause_budget",
    } else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-pid", type=int, required=True)
    parser.add_argument("--fixture-address", type=int, required=True)
    parser.add_argument("--duration", type=float, default=3)
    parser.add_argument("--max-hits", type=int, default=200)
    args = parser.parse_args()
    if not 0 < args.duration <= 120 or not 0 < args.max_hits <= 200:
        parser.error("budget out of range")
    try:
        return observe_fixture(args.fixture_pid, args.fixture_address, args.duration, args.max_hits)
    except ProbeError as error:
        print(json.dumps({"kind": "result", "stop_reason": error.stage, "hresult": error.hr,
                          "cleanup": "not_attached", "fixture_only": True}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
