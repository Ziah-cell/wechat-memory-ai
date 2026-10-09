"""Both debugger roles lost: recovery acceptance, never expected-failure masking.

Only creates/kills its own fixture and debugger children. Kills are consecutive
requests, not an atomic OS operation. No surviving helper clears debug slots.
"""
import argparse
import ctypes as c
import hashlib
import json
import pathlib
import subprocess
import time
import uuid
from test_receive_probe_native import Child,HERE
from test_receive_probe_timing_lifecycle import parse_events
from compare_receive_probe_methods import close_child
from diagnose_receive_probe_crash import FixtureThread

MODES=('baseline','normal_detach','attached','idle','pending','parallel',
       'frozen','cleared','thawed','detached')
FAULTS={'attached':'attached','pending':'received','frozen':'cleanup_frozen',
        'cleared':'cleanup_cleared','thawed':'cleanup_thawed','detached':'cleanup_detached'}

def run_case(mode):
    fixture=Child('receive_probe_lifecycle_fixture.py');owner=guardian=thread=None
    r=dict(mode=mode,passed=False,recovered=False,fixture_only=True);stage='setup'
    journal=HERE.parents[1]/'data/bounded-receive-timing-20261009'/('journal-'+uuid.uuid4().hex)
    try:
        info=fixture.event('ready')
        thread=FixtureThread(fixture,info)
        if mode!='baseline':
            args=['--fixture-pid',str(info['pid']),'--fixture-tid',str(info['main_tid']),
                  '--fixture-address',str(info['address']),'--enforce-timing','--timing-journal',str(journal)]
            options=['--duration','3']
            if mode in FAULTS:options+=['--fault',FAULTS[mode]]
            owner=Child('receive_probe_lifecycle.py','--role','owner',*args,*options)
            owner.event('owner_ready')
            guardian=Child('receive_probe_lifecycle.py','--role','guardian',*args,'--owner-pid',str(owner.process.pid))
            ready=guardian.event('guardian_ready')
            owner.send(json.dumps(dict(debug_handle=ready['remote_handle'],guardian_pid=guardian.process.pid)))
            if mode=='attached':owner.event('fault_boundary')
            else:
                owner.event('armed');fixture.send('ping');fixture.event('pong')
            stage='trigger'
            if mode in ('normal_detach','frozen','cleared','thawed','detached'):fixture.send('hit')
            elif mode=='pending':fixture.send('miss')
            elif mode=='parallel':fixture.send('parallel_rapid');fixture.event('burst_started')
            if mode in FAULTS and mode!='attached':
                r['fault_boundary']=owner.event('fault_boundary')['stage']
            if mode=='normal_detach':
                r['owner_result']=owner.event('result');assert owner.process.wait(timeout=3)==0
                r['guardian_result']=guardian.event('result');assert guardian.process.wait(timeout=3)==0
            else:
                stage='dual_exit'
                assert owner.process.poll() is None and guardian.process.poll() is None
                first=time.perf_counter_ns();owner.process.kill()
                second=time.perf_counter_ns();guardian.process.kill()
                owner.process.wait(timeout=3);guardian.process.wait(timeout=3)
                r['kill_request_gap_ms']=round((second-first)/1e6,6)
                r['both_confirmed_exited']=True
                r['kill_order']=['owner','guardian']
        stage='post_exit_state'
        if fixture.process.poll() is None:
            # Exactly the retained child PID; query only, no attachment or repair.
            k=c.WinDLL('kernel32',use_last_error=True)
            k.OpenProcess.argtypes=[c.c_uint32,c.c_int,c.c_uint32];k.OpenProcess.restype=c.c_void_p
            k.CheckRemoteDebuggerPresent.argtypes=[c.c_void_p,c.POINTER(c.c_int)]
            k.CloseHandle.argtypes=[c.c_void_p]
            handle=k.OpenProcess(0x400,False,fixture.process.pid)
            if not handle:raise c.WinError(c.get_last_error())
            try:
                present=c.c_int()
                if not k.CheckRemoteDebuggerPresent(handle,c.byref(present)):raise c.WinError(c.get_last_error())
                r['debugger_present_after_roles_exit']=bool(present.value)
            finally:k.CloseHandle(handle)
        if mode!='parallel' and fixture.process.poll() is None:
            state=thread.snapshot('after_both_exit',info['address'])
            r['register_state']={k:state[k] for k in ('prior_suspend_count','resume_prior_count',
                'trap_flag','dr0_is_fixture_function','enabled_slots_mask')}
        stage='fresh_calls'
        if mode=='parallel':
            done=fixture.event('burst_done',timeout=3)
            r['burst']=done;assert done['workers_completed']==3
        fixture.send('ping');fixture.event('pong',timeout=3)
        fixture.send('miss');fixture.event('called',timeout=3)
        fixture.send('thread:miss');fixture.event('called',timeout=3)
        a=fixture.event('heartbeat',timeout=3)['tick'];b=fixture.event('heartbeat',timeout=3)['tick']
        assert b>a and not fixture.errors
        r['recovered']=True
        if 'register_state' in r:assert r['register_state']['enabled_slots_mask']==0
        r['passed']=True
    except (AssertionError,OSError,RuntimeError,subprocess.TimeoutExpired) as error:
        r['failure_stage']=stage;r['failure_type']=type(error).__name__
    finally:
        if thread:thread.close()
        r['fixture_exit_before_teardown']=fixture.process.poll()
        for child,role in ((owner,'owner'),(guardian,'guardian')):
            if child:
                if child.process.poll() is None:child.process.kill();child.process.wait(timeout=3)
                events,invalid=parse_events(child.lines)
                r[role+'_results']=[x for x in events if x.get('kind')=='result']
                r[role+'_invalid_lines']=invalid;r[role+'_stderr']=child.errors[-3:]
                r[role+'_exit']=child.process.returncode;close_child(child)
        fixture.close_fixture()
        r['fixture_exit_after_teardown']=fixture.process.returncode
        r['fixture_stderr']=fixture.errors[-8:]
        events,invalid=parse_events(fixture.lines)
        r['fixture_invalid_lines']=invalid
        r['worker_faults']=[x for x in events if x.get('kind') in ('worker_fault','burst_summary')]
        r['journal_files']=[dict(path=p.relative_to(HERE.parents[1]).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                            for p in journal.parent.glob(journal.name+'.*.jsonl')]
    return r

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=MODES);parser.add_argument('--repeat',type=int,default=1)
    args=parser.parse_args()
    if not 1<=args.repeat<=3:parser.error('repeat1..3')
    root=HERE.parents[1];cache=root/'data/bounded-receive-fault-boundaries-20261009';cache.mkdir(exist_ok=True)
    old=json.loads((root/'docs/evidence/501-bounded-receive-lifecycle-validation.json').read_text())
    paths=[root/p for p in old['source_hashes']]+[pathlib.Path(__file__)]
    result=dict(source_hashes={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},cases=[])
    output=cache/('dual-'+uuid.uuid4().hex[:12]+'.json');print(json.dumps(dict(output=str(output))),flush=True)
    for mode in [args.mode] if args.mode else MODES:
        for repeat in range(args.repeat):
            case=run_case(mode);case['repeat']=repeat;result['cases'].append(case)
            output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:case.get(k) for k in ('mode','passed','failure_stage','register_state','fixture_exit_before_teardown','kill_request_gap_ms')}),flush=True)
    return 0 if all(c['passed'] for c in result['cases']) else 1

if __name__=='__main__':raise SystemExit(main())
