"""Fixture-only lifecycle and bounded-read matrix; no user app selection."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import time
import uuid
from test_receive_probe_native import Child,HERE
from compare_receive_probe_methods import close_child

MODES=('main_match','new_thread','delayed_match','layout_main','layout_thread','deadline',
       'cancel_idle','cancel_parallel','hit_budget','thread_churn','owner_main_pending',
       'owner_thread_pending','owner_context_thread','owner_parallel','guardian_parallel',
       'owner_cleanup_frozen','owner_cleanup_detached','owner_thread_armed','owner_foreign',
       'owner_foreign_breakpoint','owner_fatal','normal_fatal','target_exit','pause_budget',
       'owner_attached','owner_main_armed','owner_thread_exit','owner_before_hit','owner_after_hit','normal_breakpoint','cancel_collision','cancel_rapid',
       'owner_cleanup_cleared','owner_cleanup_thawed','owner_rapid','guardian_rapid')
FAULTS={'owner_main_pending':'received','owner_thread_pending':'received',
        'owner_context_thread':'context','owner_cleanup_frozen':'cleanup_frozen',
        'owner_cleanup_detached':'cleanup_detached','owner_thread_armed':'thread_armed',
        'owner_foreign':'foreign','owner_foreign_breakpoint':'foreign_breakpoint',
        'owner_fatal':'fatal','pause_budget':'slow_read','owner_attached':'attached',
        'owner_main_armed':'main_armed','owner_thread_exit':'thread_exit',
        'owner_cleanup_cleared':'cleanup_cleared','owner_cleanup_thawed':'cleanup_thawed'}
EARLY=('owner_attached','owner_main_armed')
RAPID=('cancel_rapid','owner_cleanup_cleared','owner_cleanup_thawed','owner_rapid','guardian_rapid')

def run_case(mode):
    fixture=Child('receive_probe_parallel_fixture.py');owner=guardian=None
    r={'mode':mode,'passed':False,'fixture_only':True};stage='setup'
    try:
        info=fixture.event('ready')
        args=['--fixture-pid',str(info['pid']),'--fixture-tid',str(info['main_tid']),
              '--fixture-address',str(info['address'])]
        options=['--duration','0.35' if mode=='deadline' else '3']
        if mode in FAULTS:options+=['--fault',FAULTS[mode]]
        if mode=='hit_budget':options+=['--max-hits','2']
        owner=Child('receive_probe_guarded.py','--role','owner',*args,*options)
        owner.event('owner_ready')
        guardian=Child('receive_probe_guarded.py','--role','guardian',*args,'--owner-pid',str(owner.process.pid))
        ready=guardian.event('guardian_ready')
        owner.send(json.dumps({'debug_handle':ready['remote_handle'],'guardian_pid':guardian.process.pid}))
        if mode in EARLY:r['fault_boundary']=owner.event('fault_boundary')['stage']
        else:owner.event('armed');fixture.send('ping');fixture.event('pong')
        stage='trigger'
        command=None
        if mode in ('main_match','delayed_match','owner_cleanup_frozen','owner_cleanup_detached','pause_budget'):
            if mode=='delayed_match':time.sleep(0.15)
            command='hit'
        elif mode in ('new_thread','thread_churn'):command='thread:hit'
        elif mode=='layout_main':command='bad'
        elif mode=='layout_thread':command='thread:bad'
        elif mode=='owner_main_pending':command='miss'
        elif mode in ('owner_thread_pending','owner_context_thread','owner_thread_armed','owner_thread_exit'):command='thread:miss'
        elif mode in ('owner_foreign','owner_foreign_breakpoint'):command='breakpoint' if mode.endswith('breakpoint') else 'exception'
        elif mode in ('owner_fatal','normal_fatal'):command='fatal'
        elif mode=='normal_breakpoint':command='breakpoint'
        elif mode=='target_exit':command='exit'
        elif mode.endswith('parallel'):command='parallel_burst'
        elif mode=='cancel_collision':command='parallel_ready_burst'
        elif mode in RAPID:command='parallel_rapid'
        if mode=='thread_churn':
            for _ in range(4):fixture.send('thread:miss');fixture.event('called')
        if mode=='hit_budget':
            fixture.send('thread:miss');fixture.event('called');command='thread:miss'
        if mode=='owner_after_hit':fixture.send('miss');fixture.event('called')
        if command:fixture.send(command)
        if mode.endswith('parallel') or mode=='cancel_collision' or mode in RAPID:fixture.event('burst_started')
        if mode in ('cancel_idle','cancel_parallel','cancel_collision','cancel_rapid','owner_cleanup_cleared','owner_cleanup_thawed'):owner.send('cancel')
        killed=None
        if mode.startswith('owner_'):
            if mode in FAULTS and mode not in EARLY:r['fault_boundary']=owner.event('fault_boundary')['stage']
            killed=owner;r['killed_role']='owner'
        elif mode in ('guardian_parallel','guardian_rapid'):killed=guardian;r['killed_role']='guardian'
        if killed:
            assert killed.process.poll() is None
            killed.process.kill();killed.process.wait(timeout=3)
            if mode in EARLY or mode in ('owner_before_hit','owner_after_hit'):fixture.send('miss')
        stage='cleanup';survivor=guardian if killed is owner else owner
        r['result']=survivor.event('result',timeout=4)
        assert r['result']['cleanup'] in ('detached','already_detached','target_exited')
        assert survivor.process.wait(timeout=3)==0
        if killed is None:
            r['guardian_result']=guardian.event('result',timeout=4)
            assert r['guardian_result']['cleanup'] in ('detached','already_detached','target_exited')
            assert guardian.process.wait(timeout=3)==0
        if mode in ('owner_fatal','normal_fatal','owner_foreign_breakpoint','normal_breakpoint'):
            stage='fatal_exit';r['native_exit']=fixture.process.wait(timeout=3)
            assert r['native_exit']==(0x80000003 if 'breakpoint' in mode else 0xc000001d)
        elif mode=='target_exit':assert fixture.process.wait(timeout=3)==0
        else:
            stage='fresh_calls'
            if mode.endswith('parallel') or mode=='cancel_collision' or mode in RAPID:
                done=fixture.event('burst_done',timeout=3)
                assert done['workers_completed']==3 and done['calls']>=3
                r['burst_calls']=done['calls']
            if mode=='owner_foreign':
                fixture.event('exception_caught',timeout=2);r['unrelated_exception_reached_target']=True
            fixture.send('ping');fixture.event('pong')
            fixture.send('thread:miss');fixture.event('called')
            fixture.send('miss');fixture.event('called')
            a=fixture.event('heartbeat')['tick'];b=fixture.event('heartbeat')['tick'];assert b>a
            r['recovered']=True
        stage='semantics'
        if mode in ('main_match','new_thread','delayed_match','thread_churn'):
            assert r['result']['stop_reason']=='marker_match'
            assert r['result']['hits']==(5 if mode=='thread_churn' else 1)
            record=r['result']['record'];assert record['marker_match']
            assert record['origin']==record['direction']=='unknown'
            assert record['read_bytes']<=512 and record['read_calls']<=12
            if mode in ('new_thread','thread_churn'):assert r['result']['thread_hits']==r['result']['hits']
        expected={'layout_main':'layout_rejected','layout_thread':'layout_rejected','deadline':'deadline',
                  'cancel_idle':'cancelled','cancel_parallel':'cancelled','hit_budget':'hit_budget',
                  'pause_budget':'pause_budget','guardian_parallel':'cancelled','guardian_rapid':'cancelled','cancel_collision':'cancelled','cancel_rapid':'cancelled'}
        if mode in expected:assert r['result']['stop_reason']==expected[mode]
        if mode=='hit_budget':assert r['result']['hits']==2
        if mode in ('owner_thread_pending','owner_context_thread','owner_foreign'):assert r['result']['replayed']==1
        for child in (owner,guardian):
            output='\n'.join(child.lines)
            assert not any(x in output for x in ('VXPROBE:','fixture-A','fixture-B'))
            assert not child.errors
        assert not fixture.errors;r['passed']=True
    except (AssertionError,OSError,subprocess.TimeoutExpired) as e:
        r['failure_type']=type(e).__name__;r['failure_stage']=stage
    finally:
        r['fixture_exit_before_teardown']=fixture.process.poll()
        for child,name in ((owner,'owner'),(guardian,'guardian')):
            if child:
                if child.process.poll() is None:child.process.kill();child.process.wait(timeout=3)
                events=[json.loads(s) for s in child.lines if s.startswith('{')]
                for e in events:e.pop('remote_handle',None)
                r[name+'_events']=events;r[name+'_error_tail']=child.errors[-2:]
                r[name+'_exit']=child.process.returncode;close_child(child)
        fixture.close_fixture();r['fixture_exit_after_teardown']=fixture.process.returncode
        r['fixture_error_tail']=fixture.errors[-2:]
        r['fixture_single_step_errors']=sum('exception: single step' in s for s in fixture.errors)
        r['fixture_error_diagnostics']=fixture.errors[-24:]
        r['fixture_diagnostics']=[json.loads(s) for s in fixture.lines if s.startswith('{') and json.loads(s).get('kind') in ('worker_fault','burst_summary')]
    return r

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=MODES)
    p.add_argument('--repeat',type=int,default=1);args=p.parse_args()
    if not 1<=args.repeat<=5:p.error('repeat must be 1..5')
    cache=HERE.parents[1]/'data/bounded-receive-guarded-20261009';cache.mkdir(exist_ok=True)
    paths=[pathlib.Path(__file__)]+[HERE/n for n in ('receive_probe_parallel_fixture.py',
        'receive_probe_transfer.py','receive_probe_win32.py','check_receive_probe_layout.py',
        'test_receive_probe_native.py','probe_fixture_freeze.py','receive_probe_variants.py',
        'receive_probe_observer.py','compare_receive_probe_methods.py','receive_probe_guarded.py')]
    r={'source_hashes':{s.relative_to(HERE.parents[1]).as_posix():hashlib.sha256(s.read_bytes()).hexdigest() for s in paths},'cases':[]}
    output=cache/('matrix-'+uuid.uuid4().hex[:12]+'.json');print(json.dumps({'output':str(output)}),flush=True)
    for mode in [args.mode] if args.mode else MODES:
        for repeat in range(args.repeat):
            case=run_case(mode);case['repeat']=repeat;r['cases'].append(case)
            output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:case.get(k) for k in ('mode','passed','failure_stage','result')}),flush=True)
    return 0 if all(c['passed'] for c in r['cases']) else 1

if __name__=='__main__':raise SystemExit(main())
