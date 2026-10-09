"""Self-owned x64 unwind probe. Never executes the synthetic instruction bytes.

Only a child created by this script calls the Windows function-table/unwind APIs.
All code-shaped bytes, stacks and contexts are in that child's PAGE_READWRITE
allocation. No DLL injection, code patch, debugger, thread suspension or PID input.
An unsuccessful recovery is preserved as exit 1, not relabelled as a pass.
"""
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import uuid

PREFIX = bytes.fromhex('5541565657')  # push rbp/r14/rsi/rdi; five bytes
PUSHES = [(1, 'rbp'), (3, 'r14'), (4, 'rsi'), (5, 'rdi')]
REG_OFFSETS = {'rbp':160, 'r14':232, 'rsi':168, 'rdi':176}
ORIGINAL = {name:0x10001000 + i * 0x100 for i,name in enumerate(REG_OFFSETS)}
RETURN_PC = 0x12345000  # fictional, never executed
HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[1] / 'data/resident-receive-design-20261009'


class RuntimeFunction(c.Structure):
    _fields_ = [('BeginAddress',c.c_uint32), ('EndAddress',c.c_uint32), ('UnwindData',c.c_uint32)]


def worker(tail, metadata):
    assert os.name == 'nt' and c.sizeof(c.c_void_p) == 8
    k = c.WinDLL('kernel32', use_last_error=True)
    k.SetErrorMode(0x8003)
    k.VirtualAlloc.argtypes = [c.c_void_p,c.c_size_t,c.c_uint32,c.c_uint32]
    k.VirtualAlloc.restype = c.c_void_p
    k.VirtualFree.argtypes = [c.c_void_p,c.c_size_t,c.c_uint32]
    k.VirtualFree.restype = c.c_int
    k.RtlAddFunctionTable.argtypes = [c.POINTER(RuntimeFunction),c.c_uint32,c.c_uint64]
    k.RtlAddFunctionTable.restype = c.c_ubyte
    k.RtlDeleteFunctionTable.argtypes = [c.POINTER(RuntimeFunction)]
    k.RtlDeleteFunctionTable.restype = c.c_ubyte
    k.RtlLookupFunctionEntry.argtypes = [c.c_uint64,c.POINTER(c.c_uint64),c.c_void_p]
    k.RtlLookupFunctionEntry.restype = c.POINTER(RuntimeFunction)
    k.RtlVirtualUnwind.argtypes = [c.c_uint32,c.c_uint64,c.c_uint64,c.POINTER(RuntimeFunction),
                                   c.c_void_p,c.POINTER(c.c_void_p),c.POINTER(c.c_uint64),c.c_void_p]
    k.RtlVirtualUnwind.restype = c.c_void_p
    base = k.VirtualAlloc(None,4096,0x3000,0x04)  # RW, never made executable
    assert base, 'own_allocation_failed'
    code_offset, unwind_offset = 0x100, 0x200
    tails = {'indirect':bytes.fromhex('ff250d000000'), 'nop':b'\x90' * 6,
             'register':b'\x49\xbb' + struct.pack('<Q',base + 0x300) + b'\x41\xff\xe3',
             'register_w':b'\x49\xbb' + struct.pack('<Q',base + 0x300) + b'\x49\xff\xe3'}
    code = PREFIX + tails[tail]
    # The indirect destination pointer is at offset 24: (5 + 6) + 13.
    c.memmove(base + code_offset, code, len(code))
    c.c_uint64.from_address(base + code_offset + 24).value = base + 0x300
    c.memmove(base + 0x300, b'\x90' * 16, 16)
    codes = bytes.fromhex('0570046003e00150')  # four UWOP_PUSH_NONVOL, descending offsets
    if metadata == 'omit_rbp':
        codes = codes[:-2]
    # Experimental contrast: the trampoline's transfer remains part of its
    # prologue, so it must not be mistaken for an epilogue restoring no pushes.
    prologue_size = len(code) if metadata == 'full_prolog' else len(PREFIX)
    unwind = bytes([1,prologue_size,len(codes)//2,0]) + codes
    if len(unwind) % 4:
        unwind += b'\0' * (4 - len(unwind) % 4)
    c.memmove(base + unwind_offset, unwind, len(unwind))
    entry = RuntimeFunction(code_offset,code_offset + len(code),unwind_offset)
    registered = deleted = freed = False
    cases = []
    registration_lookup_absent_after_delete = None
    try:
        lookup_base = c.c_uint64()
        assert not k.RtlLookupFunctionEntry(base + code_offset,c.byref(lookup_base),None)
        if metadata != 'none':
            registered = bool(k.RtlAddFunctionTable(c.byref(entry),1,base))
            assert registered, 'registration_failed'
        pcs = (0,1,3,4,5,15) if tail.startswith('register') else (0,1,3,4,5)
        for pc_offset in pcs:
            # Fictitious caller frame: all reads stay inside this owned allocation.
            entry_rsp = base + 0xc00
            c.memset(base + 0x800,0,0x600)
            c.c_uint64.from_address(entry_rsp).value = RETURN_PC
            rsp = entry_rsp
            pushed = []
            for end,name in PUSHES:
                if end <= pc_offset:
                    rsp -= 8
                    c.c_uint64.from_address(rsp).value = ORIGINAL[name]
                    pushed.append(name)
            storage = c.create_string_buffer(1232 + 15)
            context = (c.addressof(storage) + 15) & ~15
            c.c_uint32.from_address(context + 48).value = 0x10000b
            c.c_uint64.from_address(context + 152).value = rsp
            c.c_uint64.from_address(context + 248).value = base + code_offset + pc_offset
            for name,offset in REG_OFFSETS.items():
                c.c_uint64.from_address(context + offset).value = ORIGINAL[name]
            if tail.startswith('register') and pc_offset == 15:
                c.c_uint64.from_address(context + 208).value = base + 0x300  # R11 after mov
            # Push instructions preserve registers; the artificial context does too.
            lookup_base = c.c_uint64()
            found = k.RtlLookupFunctionEntry(base + code_offset + pc_offset,c.byref(lookup_base),None)
            called = False
            if found:
                assert lookup_base.value == base and found.contents.BeginAddress == code_offset
                handler_data = c.c_void_p()
                establisher = c.c_uint64()
                k.RtlVirtualUnwind(0,base,base + code_offset + pc_offset,found,context,
                                   c.byref(handler_data),c.byref(establisher),None)
                called = True
            else:
                # Documented no-table leaf fallback MODEL, not a RtlVirtualUnwind call.
                c.c_uint64.from_address(context + 248).value = c.c_uint64.from_address(rsp).value
                c.c_uint64.from_address(context + 152).value = rsp + 8
            actual_rsp = c.c_uint64.from_address(context + 152).value
            actual_pc = c.c_uint64.from_address(context + 248).value
            registers_ok = all(c.c_uint64.from_address(context + offset).value == ORIGINAL[name]
                               for name,offset in REG_OFFSETS.items())
            cases.append(dict(pc_offset=pc_offset,push_count=len(pushed),table_found=bool(found),
                native_unwind_called=called,leaf_fallback_model=not called,
                return_pc_matches=actual_pc == RETURN_PC,
                stack_pointer_matches=actual_rsp == entry_rsp + 8,
                stack_pointer_error_bytes=actual_rsp - (entry_rsp + 8),registers_match=registers_ok,
                recovered=actual_pc == RETURN_PC and actual_rsp == entry_rsp + 8 and registers_ok))
    finally:
        if registered:
            deleted = bool(k.RtlDeleteFunctionTable(c.byref(entry)))
            assert deleted, 'function_table_delete_failed'
            lookup_base = c.c_uint64()
            registration_lookup_absent_after_delete = not bool(k.RtlLookupFunctionEntry(base + code_offset,c.byref(lookup_base),None))
            assert registration_lookup_absent_after_delete
        freed = bool(k.VirtualFree(base,0,0x8000))
        assert freed, 'own_allocation_free_failed'
    # Do not emit an allocation address embedded in the register-jump immediate.
    code_pattern = PREFIX + tails[tail][:2] + b'\0' * 8 + tails[tail][-3:] if tail.startswith('register') else code
    return dict(tail=tail,metadata=metadata,prefix_hex=PREFIX.hex(),code_hex=code_pattern.hex(),
        code_immediate_redacted=tail.startswith('register'),
        unwind_info_hex=unwind.hex(),registered=registered,deleted=deleted,freed=freed,
        lookup_absent_after_delete=registration_lookup_absent_after_delete,cases=cases,
        native_unwind_calls=sum(x['native_unwind_called'] for x in cases),
        leaf_fallback_models=sum(x['leaf_fallback_model'] for x in cases),
        successful_recovery=sum(x['recovered'] for x in cases),
        generated_bytes_executed=False,executable_memory_allocated=False,hook_installed=False,
        register_context_applied_to_thread=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tail', choices=('indirect','nop','register','register_w'), default='indirect')
    ap.add_argument('--metadata',choices=('exact','full_prolog','omit_rbp','none'),default='exact')
    ap.add_argument('--worker',action='store_true')
    args = ap.parse_args()
    if args.worker:
        print(json.dumps(worker(args.tail,args.metadata)))
        return 0
    command = [sys.executable,str(Path(__file__).resolve()),'--worker','--tail',args.tail,'--metadata',args.metadata]
    run = subprocess.run(command,capture_output=True,text=True,timeout=20,
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    result = dict(tail=args.tail,metadata=args.metadata,child_exit=run.returncode,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if run.returncode == 0:
        result['observation'] = json.loads(run.stdout)
        result['all_recovered'] = all(x['recovered'] for x in result['observation']['cases'])
    else:
        result['all_recovered'] = False
        result['child_error'] = run.stderr  # own fixture only; no user data is accessed
    CACHE.mkdir(parents=True,exist_ok=True)
    name = 'unwind-' + uuid.uuid4().hex[:12] + '.json'
    (CACHE / name).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(run=name,**result)))
    return 0 if result['all_recovered'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
