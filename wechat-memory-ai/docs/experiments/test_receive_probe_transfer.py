"""Fault-injection comparison for pre-retained debug objects; fixtures only."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import time
import uuid

from test_receive_probe_native import Child, HERE
from compare_receive_probe_methods import close_child

MODES = ('owner_before_hit','owner_after_hit','owner_busy','owner_pending',
         'owner_context','owner_continued','owner_foreign','owner_fatal','guardian_busy',
         'owner_attached','owner_arm_before','owner_arm_written','normal_budget')
STAGES = {'owner_pending':'received','owner_context':'context',
          'owner_continued':'continued','owner_foreign':'foreign','owner_fatal':'fatal',
          'owner_attached':'attached','owner_arm_before':'arm_before','owner_arm_written':'arm_written'}
EARLY = ('owner_attached','owner_arm_before','owner_arm_written')


def run_case(mode, repeat, replay=False):
    f = Child('receive_probe_fixture.py')
    o = g = None
    result = {'mode': mode, 'repeat': repeat, 'replay': replay, 'recovered': False, 'fixture_only': True}
    try:
        info = f.event('ready')
        args = ['--fixture-pid', str(info['pid']), '--fixture-tid', str(info['main_tid']),
                '--fixture-address', str(info['address'])]
        extra = ['--pause-stage', STAGES[mode]] if mode in STAGES else []
        o = Child('receive_probe_transfer.py', '--role', 'owner', *args, *extra)
        o.event('owner_ready')
        g = Child('receive_probe_transfer.py', '--role', 'guardian', *args,
                  '--owner-pid', str(o.process.pid), *(['--replay'] if replay else []))
        ready = g.event('guardian_ready')
        result['created_before_attach'] = ready['created_before_attach']
        o.send(json.dumps({'debug_handle': ready['remote_handle'], 'guardian_pid': g.process.pid}))
        if mode in EARLY:
            result['fault_boundary'] = o.event('fault_boundary')['stage']
        else:
            o.event('armed')
            f.send('ping'); f.event('pong')
        if mode == 'owner_after_hit':
            f.send('miss'); f.event('called')
        elif mode.endswith('busy') or mode == 'normal_budget':
            f.send('burst'); f.event('burst_started')
        elif mode in STAGES and mode not in EARLY:
            f.send({'owner_foreign':'exception','owner_fatal':'fatal'}.get(mode,'miss'))
            result['fault_boundary'] = o.event('fault_boundary')['stage']
        victim = g if mode == 'guardian_busy' else o
        if mode == 'normal_budget':
            result['owner_normal_result'] = o.event('result', timeout=4)
            assert result['owner_normal_result']['cleanup'] == 'detached'
            assert o.process.wait(timeout=3) == 0
        else:
            assert victim.process.poll() is None
            victim.process.kill()
            victim.process.wait(timeout=3)
        if mode in ('owner_before_hit', 'owner_after_hit') or mode in EARLY:
            # Demand the next call now, before the deliberately delayed guardian
            # cleanup. This is not the old manual repair-before-call contrast.
            f.send('miss')
        survivor = o if victim is g else g
        result['recovery_result'] = survivor.event('result', timeout=4)
        result['survivor_exit'] = survivor.process.wait(timeout=3)
        assert result['recovery_result']['cleanup'] in ('detached','already_detached')
        if result['recovery_result']['cleanup'] == 'already_detached':
            assert any(json.loads(s).get('kind') == 'already_clean' and
                       json.loads(s).get('debugger_present') is False and
                       json.loads(s).get('enabled_slots') == 0 for s in survivor.lines if s.startswith('{'))
        assert result['survivor_exit'] == 0
        if mode == 'owner_fatal':
            result['native_exit_code'] = f.process.wait(timeout=3)
            result['expected_native_exit_preserved'] = result['native_exit_code'] == 0xc000001d
            result['passed'] = result['expected_native_exit_preserved']
            return result
        if mode.endswith('busy') or mode == 'normal_budget':
            result['burst_calls'] = f.event('burst_done', timeout=3)['calls']
        elif mode == 'owner_foreign':
            f.event('exception_caught', timeout=3)
            result['unrelated_exception_reached_target'] = True
        else:
            f.event('called', timeout=3)
        f.send('miss'); f.event('called', timeout=3)
        a=f.event('heartbeat',timeout=3)['tick']; b=f.event('heartbeat',timeout=3)['tick']
        result['recovered'] = b>a
        result['passed'] = result['recovered']
    except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
        result['failure_type'] = type(error).__name__
    finally:
        result['fixture_exit_before_teardown'] = f.process.poll()
        result['fixture_error_tail'] = f.errors[-1:]
        # Kill only our own surviving debugger children during failed-test cleanup.
        for child,name in ((o,'owner'),(g,'guardian')):
            if child:
                if child.process.poll() is None:
                    child.process.kill(); child.process.wait(timeout=3)
                result[name+'_events']=[json.loads(s) for s in child.lines if s.startswith('{')]
                # Local duplicated handle values are setup details, not evidence.
                for e in result[name+'_events']: e.pop('remote_handle',None)
                result[name+'_error_tail']=child.errors[-2:]
                result[name+'_exit']=child.process.returncode
                close_child(child)
        f.close_fixture()
        result['fixture_exit_after_teardown']=f.process.returncode
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--mode', choices=MODES)
    p.add_argument('--repeat', type=int, default=3)
    p.add_argument('--replay', action='store_true')
    a=p.parse_args()
    if not 1 <= a.repeat <= 20:
        p.error('--repeat must be 1..20')
    modes=[('owner_after_hit',1)] if a.smoke else [(n,a.repeat) for n in MODES]
    if a.mode:
        modes=[(a.mode,a.repeat)]
    cache=HERE.parents[1]/'data/bounded-receive-transfer-20261009'
    cache.mkdir(exist_ok=True)
    output=cache/('run-'+uuid.uuid4().hex[:12]+'.json')
    sources=[pathlib.Path(__file__),HERE/'receive_probe_transfer.py',HERE/'receive_probe_win32.py',
             HERE/'receive_probe_variants.py',HERE/'receive_probe_fixture.py',HERE/'test_receive_probe_native.py',
             HERE/'compare_receive_probe_methods.py',HERE/'receive_probe_observer.py']
    r={'fixture_only':True,'selected_modes':modes,'cases':[],
       'source_hashes':{f.relative_to(HERE.parents[1]).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sources}}
    print(json.dumps({'output':str(output)}),flush=True)
    for mode,count in modes:
        for repeat in range(count):
            c=run_case(mode,repeat,a.replay);r['cases'].append(c)
            output.write_text(json.dumps(r,indent=2),encoding='utf-8')
            print(json.dumps({k:c.get(k) for k in ('mode','repeat','recovered','passed','recovery_result',
                 'fixture_error_tail','owner_error_tail','guardian_error_tail')}),flush=True)
    return 0 if all(c.get('passed',False) for c in r['cases']) else 1


if __name__=='__main__':
    raise SystemExit(main())
