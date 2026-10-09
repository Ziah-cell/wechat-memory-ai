"""Attach-break audit variant of the self-owned x64 fixture. Never opens another process.

Creates a four-byte function in its OWN address space to exercise an external
debugger. All message bytes, addresses and endpoint labels here are fictional.
"""
import ctypes as c
import json
import os
import queue
import struct
import sys
import threading
import time

_output_lock = threading.Lock()


def emit(value):
    with _output_lock:
        print(json.dumps(value), flush=True)


MARKER = b"VXPROBE:" + b"0123456789abcdef" * 2


def main():
    assert c.sizeof(c.c_void_p) == 8
    k = c.WinDLL("kernel32", use_last_error=True)
    k.SetErrorMode(0x8003)  # own process only; no crash dialog for deliberate fixture failures
    k.VirtualAlloc.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.c_uint32]
    k.VirtualAlloc.restype = c.c_void_p
    k.VirtualProtect.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.POINTER(c.c_uint32)]
    k.VirtualFree.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
    k.GetCurrentProcess.restype = c.c_void_p
    k.FlushInstructionCache.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
    address = k.VirtualAlloc(None, 4096, 0x3000, 4)
    assert address
    c.memmove(address, b"\x48\x89\xd0\xc3", 4)  # mov rax, rdx; ret
    c.memmove(address + 16, b"\x0f\x0b\xc3", 3)  # UD2 on a native thread for exception propagation
    old = c.c_uint32()
    assert k.VirtualProtect(address, 4096, 0x20, c.byref(old))
    assert k.FlushInstructionCache(k.GetCurrentProcess(), address, 19)
    function = c.WINFUNCTYPE(c.c_uint64, c.c_void_p, c.c_void_p)(address)
    buffers = []

    def allocate(value):
        buf = c.create_string_buffer(value, len(value))
        buffers.append(buf)
        return c.addressof(buf)

    def nested(value):
        if len(value) <= 15:
            desc = value.ljust(16, b"\0") + struct.pack("<QQ", len(value), 15)
        else:
            desc = struct.pack("<QQQQ", allocate(value), 0, len(value), len(value))
        return allocate(struct.pack("<QQ", 0, allocate(desc)))

    def raw(value, bad=False):
        header = bytearray(0x58)
        struct.pack_into("<I", header, 0x14, 1)
        for offset, value in [(8, b"fixture-A"), (0x18, b"fixture-B"), (0x20, value)]:
            struct.pack_into("<Q", header, offset, nested(value))
        struct.pack_into("<Q", header, 0x50, 12345)
        if bad:
            struct.pack_into("<Q", header, 0x20, 0)
        return allocate(bytes(header))

    samples = {"hit": raw(MARKER), "miss": raw(b"X" * 40), "bad": raw(MARKER, True)}
    commands = queue.Queue()
    def input_thread():
        for line in sys.stdin:
            commands.put(line.strip())
        commands.put("exit")
    threading.Thread(target=input_thread, daemon=True).start()
    emit({"kind": "ready", "pid": os.getpid(), "main_tid": threading.get_native_id(),
          "address": address, "signature": "4889d0c3"})
    count = 0
    heartbeat = 0
    try:
        while True:
            try:
                command = commands.get(timeout=0.05)
            except queue.Empty:
                command = ""
            if command == "exit":
                emit({"kind": "exit", "calls": count})
                break
            if command:
                if command in ('parallel_burst','parallel_ready_burst','parallel_rapid'):
                    counts=[]
                    started=threading.Event()
                    notice=threading.Lock()
                    barrier=threading.Barrier(3) if command!='parallel_burst' else None
                    def burst_worker():
                        if barrier:barrier.wait()
                        until=time.monotonic()+1
                        calls=0
                        while time.monotonic()<until:
                            try:
                                value=function(None,samples['miss'])
                                if value!=samples['miss']:
                                    emit({'kind':'worker_fault','reason':'unexpected_return'})
                                assert value==samples['miss']
                            except OSError as error:
                                emit({'kind':'worker_fault','reason':'single_step' if 'single step' in str(error) else 'native_error'})
                                raise
                            calls+=1
                            with notice:
                                if not started.is_set():
                                    started.set();emit({'kind':'burst_started'})
                            time.sleep(0 if command=='parallel_rapid' else 0.001)
                        counts.append(calls)
                    workers=[threading.Thread(target=burst_worker) for _ in range(3)]
                    for t in workers:t.start()
                    for t in workers:t.join()
                    emit({'kind':'burst_summary','workers_completed':len(counts),'counts':counts})
                    assert len(counts)==3 and min(counts)>0
                    count+=sum(counts)
                    emit({'kind':'burst_done','calls':sum(counts),'workers_completed':len(counts)})
                    continue
                if command == "ping":
                    emit({"kind": "pong"})
                    continue
                if command == "burst":
                    # Autonomous calls continue while the harness kills a worker
                    # or debugger; no wait-for-repair handshake and no catch.
                    until = time.monotonic() + 1
                    burst_calls = 0
                    while time.monotonic() < until:
                        assert function(None, samples["miss"]) == samples["miss"]
                        burst_calls += 1
                        if burst_calls == 1:
                            emit({"kind": "burst_started"})
                        time.sleep(0.001)
                    count += burst_calls
                    emit({"kind": "burst_done", "calls": burst_calls})
                    continue
                if command == "fatal":
                    k.CreateThread.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p,
                                               c.c_uint32, c.POINTER(c.c_uint32)]
                    k.CreateThread.restype = c.c_void_p
                    tid = c.c_uint32()
                    handle = k.CreateThread(None, 0, address + 16, None, 0, c.byref(tid))
                    assert handle
                    k.CloseHandle.argtypes = [c.c_void_p]
                    k.CloseHandle(handle)
                    continue
                if command == "ntdll_breakpoint":
                    c.WinDLL("ntdll").DbgBreakPoint()
                    emit({"kind":"application_breakpoint_returned"})
                    continue
                if command in ("exception", "breakpoint"):
                    k.RaiseException.argtypes = [c.c_uint32, c.c_uint32, c.c_uint32, c.c_void_p]
                    try:
                        k.RaiseException(0x80000003 if command == 'breakpoint' else 0xe1234567, 0, 0, None)
                    except OSError:
                        emit({"kind": "exception_caught"})
                    continue
                new_thread = command.startswith("thread:")
                name = command.split(":")[-1]
                if name in samples:
                    def invoke():
                        assert function(None, samples[name]) == samples[name]
                    if new_thread:
                        t = threading.Thread(target=invoke)
                        t.start()
                        t.join()
                    else:
                        invoke()
                    count += 1
                    emit({"kind": "called", "calls": count, "new_thread": new_thread})
            heartbeat += 1
            emit({"kind": "heartbeat", "tick": heartbeat})
    finally:
        k.VirtualFree(address, 0, 0x8000)


if __name__ == "__main__":
    main()
