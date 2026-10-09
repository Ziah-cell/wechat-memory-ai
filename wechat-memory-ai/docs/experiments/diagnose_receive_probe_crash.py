"""Read debug-register residue ONLY in children this harness creates.

No user-provided PID, process enumeration, reattachment or exception suppression.
Suspend/GetThreadContext/Resume pairs inspect the fixture main thread. One causal
contrast disables the owned hardware slot before allowing the next synthetic call;
this controlled sequencing is not available as a crash guarantee for a live app.
Forced termination is limited to the harness's observer child.
This is a diagnostic matrix, NOT a passing recovery acceptance test.
"""
import ctypes as c
import hashlib
import json
import pathlib
import struct
import sys
import time

from test_receive_probe_native import Child, HERE


class FixtureThread:
    def __init__(self, child, info, allow_disable=False):
        if child.process.poll() is not None or info["pid"] != child.process.pid:
            raise RuntimeError("fixture identity mismatch")
        self.k = c.WinDLL("kernel32", use_last_error=True)
        self.k.OpenThread.argtypes = [c.c_uint32, c.c_int, c.c_uint32]
        self.k.OpenThread.restype = c.c_void_p
        self.k.GetProcessIdOfThread.argtypes = [c.c_void_p]
        self.k.GetProcessIdOfThread.restype = c.c_uint32
        for name in ("SuspendThread", "ResumeThread"):
            getattr(self.k, name).argtypes = [c.c_void_p]
            getattr(self.k, name).restype = c.c_uint32
        self.k.GetThreadContext.argtypes = [c.c_void_p, c.c_void_p]
        self.k.GetThreadContext.restype = c.c_int
        self.k.SetThreadContext.argtypes = [c.c_void_p, c.c_void_p]
        self.k.SetThreadContext.restype = c.c_int
        self.k.CloseHandle.argtypes = [c.c_void_p]
        self.allow_disable = allow_disable
        # QUERY_LIMITED_INFORMATION | GET_CONTEXT | SUSPEND_RESUME.
        # SET_CONTEXT only for the explicitly selected self-owned causal contrast.
        self.handle = self.k.OpenThread(0x080a | (0x10 if allow_disable else 0),
                                        False, info["main_tid"])
        if not self.handle:
            raise c.WinError(c.get_last_error())
        if self.k.GetProcessIdOfThread(self.handle) != child.process.pid:
            self.close()
            raise RuntimeError("thread is not in our fixture child")

    def snapshot(self, stage, address):
        # AMD64 CONTEXT from the pinned Microsoft winnt.h: 1232 bytes, 16-byte
        # alignment; only CONTROL | DEBUG_REGISTERS requested. General registers
        # and vector state are not interpreted or saved.
        storage = c.create_string_buffer(1232 + 15)
        aligned = (c.addressof(storage) + 15) & ~15
        c.c_uint32.from_address(aligned + 48).value = 0x100011
        prior = self.k.SuspendThread(self.handle)
        if prior == 0xffffffff:
            raise c.WinError(c.get_last_error())
        try:
            if not self.k.GetThreadContext(self.handle, aligned):
                raise c.WinError(c.get_last_error())
            raw = c.string_at(aligned, 1232)
        finally:
            resumed = self.k.ResumeThread(self.handle)
            if resumed == 0xffffffff:
                raise c.WinError(c.get_last_error())
        dr = dict(zip(("dr0", "dr1", "dr2", "dr3", "dr6", "dr7"),
                      struct.unpack_from("<6Q", raw, 72)))
        flags = struct.unpack_from("<I", raw, 68)[0]
        return {"stage": stage, "prior_suspend_count": prior,
                "resume_prior_count": resumed,
                "context_flags": hex(struct.unpack_from("<I", raw, 48)[0]),
                "registers": {key: hex(value) for key, value in dr.items()},
                "eflags": hex(flags), "trap_flag": bool(flags & 0x100),
                "dr0_is_fixture_function": dr["dr0"] == address,
                "enabled_slots_mask": dr["dr7"] & 0xff}

    def disable_owned_slot(self, address):
        if not self.allow_disable:
            raise RuntimeError("read-only diagnostic handle")
        storage = c.create_string_buffer(1232 + 15)
        aligned = (c.addressof(storage) + 15) & ~15
        c.c_uint32.from_address(aligned + 48).value = 0x100010  # DEBUG_REGISTERS only
        prior = self.k.SuspendThread(self.handle)
        if prior == 0xffffffff:
            raise c.WinError(c.get_last_error())
        try:
            if not self.k.GetThreadContext(self.handle, aligned):
                raise c.WinError(c.get_last_error())
            dr = struct.unpack_from("<6Q", c.string_at(aligned, 1232), 72)
            if prior != 0 or dr[0] != address or dr[1:4] != (0, 0, 0) or dr[5] & 0xf00ff != 1:
                raise RuntimeError("not the expected single fixture execute breakpoint")
            # Change only DR7's slot-0 enable bits. Preserve the rest of the debug
            # registers; do not touch EFLAGS, RIP, native code or process memory.
            c.c_uint64.from_address(aligned + 112).value = dr[5] & ~3
            if not self.k.SetThreadContext(self.handle, aligned):
                raise c.WinError(c.get_last_error())
        finally:
            resumed = self.k.ResumeThread(self.handle)
            if resumed == 0xffffffff:
                raise c.WinError(c.get_last_error())
        return {"prior_suspend_count": prior, "resume_prior_count": resumed,
                "changed_field": "DR7 slot-0 enable bits only"}

    def close(self):
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None


def run_case(mode, repeat):
    fixture = Child("receive_probe_fixture.py")
    observer = None
    thread = None
    result = {"mode": mode, "repeat": repeat, "snapshots": [], "recovered": False}
    try:
        info = fixture.event("ready")
        thread = FixtureThread(fixture, info, allow_disable=mode == "disable_before_next_call")
        def snapshot(stage):
            result["snapshots"].append(thread.snapshot(stage, info["address"]))
        snapshot("before_attach")
        if mode != "baseline":
            observer = Child("receive_probe_observer.py", "--fixture-pid", str(info["pid"]),
                             "--fixture-address", str(info["address"]), "--duration", "8")
            observer.event("armed")
            if mode in ("normal_detach", "kill_after_hit", "kill_after_settled_hit",
                        "disable_before_next_call"):
                fixture.send("miss")
                fixture.event("called")
                result["call_before_exit"] = True
            if mode == "kill_after_settled_hit":
                # Diagnostic contrast for a transient pending-event hypothesis;
                # this delay is not a recovery fix or an acceptance workaround.
                time.sleep(0.4)
            snapshot("before_observer_exit")
            if mode == "normal_detach":
                observer.send("cancel")
                result["observer_result"] = observer.event("result")
                result["observer_exit"] = observer.process.wait(timeout=4)
            else:
                observer.process.kill()
                result["observer_exit"] = observer.process.wait(timeout=3)
            snapshot("after_observer_exit")
            if mode == "disable_before_next_call":
                result["manual_disable"] = thread.disable_owned_slot(info["address"])
                snapshot("after_controlled_disable")
        fixture.send("miss")
        try:
            fixture.event("called", timeout=3)
            a = fixture.event("heartbeat", timeout=3)["tick"]
            b = fixture.event("heartbeat", timeout=3)["tick"]
            result["recovered"] = b > a
        except AssertionError:
            result["recovery_failed"] = True
        result["fixture_exit_before_teardown"] = fixture.process.poll()
        result["fixture_error_tail"] = fixture.errors[-1:]
    finally:
        if thread:
            thread.close()
        if observer:
            if observer.process.poll() is None:
                observer.send("cancel")
                try:
                    observer.process.wait(timeout=4)
                except Exception:
                    observer.process.kill()  # this harness's child only
                    observer.process.wait(timeout=3)
            for stream in (observer.process.stdin, observer.process.stdout, observer.process.stderr):
                stream.close()
        fixture.close_fixture()
        result["fixture_exit_after_teardown"] = fixture.process.returncode
    return result


def main():
    cache = HERE.parents[1] / "data/bounded-receive-crash-20261009"
    results = []
    modes = (("baseline", 1), ("normal_detach", 1),
             ("kill_before_hit", 3), ("kill_after_hit", 3),
             ("kill_after_settled_hit", 3), ("disable_before_next_call", 3))
    # A narrow invocation avoids re-running completed contrasts while diagnosing.
    if len(sys.argv) == 2 and sys.argv[1] == "--causal-only":
        modes = (("disable_before_next_call", 3),)
    elif len(sys.argv) != 1:
        raise SystemExit("Only --causal-only is supported; no PID input is accepted")
    output_name = "causal-disable.json" if len(sys.argv) == 2 else "register-diagnostics.json"
    for mode, repeats in modes:
        for repeat in range(repeats):
            result = run_case(mode, repeat)
            results.append(result)
            (cache / output_name).write_text(json.dumps({
                "fixture_only": True, "diagnostic_only": True, "cases": results,
                "source_hashes": {str(p.relative_to(HERE.parents[1])).replace("\\", "/"):
                                  hashlib.sha256(p.read_bytes()).hexdigest() for p in (
                                      pathlib.Path(__file__), HERE / "receive_probe_fixture.py",
                                      HERE / "receive_probe_observer.py", HERE / "test_receive_probe_native.py")},
            }, indent=2), encoding="utf-8")
            print(json.dumps({"mode": mode, "repeat": repeat, "recovered": result["recovered"],
                              "snapshots": result["snapshots"],
                              "error": result["fixture_error_tail"]}), flush=True)
    # An execution that records known failures is still failed recovery.
    return 0 if all(r["recovered"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
