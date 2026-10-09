"""Compare crash behavior in self-owned fixtures; no real-app launch mode.

Results distinguish a killed controller from a killed debugger owner. Continuous
fixture calls are autonomous; the parent never makes them wait for cleanup.
This experiment intentionally retains failures and exits nonzero if any remain.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import time
import uuid

from test_receive_probe_native import Child, HERE
from diagnose_receive_probe_crash import FixtureThread


def close_child(child):
    for stream in (child.process.stdin, child.process.stdout, child.process.stderr):
        stream.close()


def run_case(mode, repeat):
    started = time.monotonic()
    fixture = Child("receive_probe_fixture.py")
    observer = controller = thread = None
    result = {"mode": mode, "repeat": repeat, "recovered": False,
              "fixture_only": True, "snapshots": []}
    try:
        info = fixture.event("ready")
        thread = FixtureThread(fixture, info)
        result['snapshots'].append(thread.snapshot("baseline", info['address']))
        if mode != "baseline_busy":
            args = ["--fixture-pid", str(info['pid']), "--fixture-address", str(info['address'])]
            if mode.startswith("raw_"):
                observer = Child("receive_probe_win32.py", *args, "--fixture-tid", str(info['main_tid']))
            elif mode.startswith("broker_"):
                controller = Child("receive_probe_variants.py", "--mode", "controller")
                controller.event("controller_ready")
                observer = Child("receive_probe_variants.py", "--mode", "broker", *args,
                                 "--controller-pid", str(controller.process.pid))
            else:
                observer = Child("receive_probe_variants.py", "--mode", "one_shot", *args)
            observer.event("armed")
            # Proves the main thread made progress AFTER arming, unlike an old
            # heartbeat already queued before the debugger attached.
            fixture.send("ping")
            fixture.event("pong")
            result["post_arm_main_thread_progress"] = True
        busy = mode.endswith("busy")
        if busy:
            fixture.send("burst")
            fixture.event("burst_started")
        elif mode.endswith("after_hit") or mode.endswith("normal"):
            fixture.send("miss")
            fixture.event("called")
            if mode.startswith("raw_"):
                fixture.send("miss")
                fixture.event("called")  # RF path must handle repeated executions
        if observer:
            if mode.endswith("normal"):
                observer.send("cancel")
                result["observer_result"] = observer.event("result")
                result["observer_exit"] = observer.process.wait(timeout=3)
            else:
                victim = controller if mode.startswith("broker_front_") else observer
                assert victim.process.poll() is None, "owner already exited before crash injection"
                result['killed_role'] = 'controller' if victim is controller else 'debugger_owner'
                crash_at = time.monotonic()
                victim.process.kill()  # exactly the child just created by this harness
                result['killed_child_exit'] = victim.process.wait(timeout=3)
                if victim is controller:
                    result["observer_result"] = observer.event("result")
                    result["observer_exit"] = observer.process.wait(timeout=3)
                    assert result["observer_result"]["stop_reason"] == "cancelled"
                    assert result["observer_result"]["cleanup"] == "detached"
                result['exit_or_cleanup_ms'] = round((time.monotonic()-crash_at)*1000, 3)
        if busy:
            result['burst_calls'] = fixture.event("burst_done", timeout=3)['calls']
        else:
            result['snapshots'].append(thread.snapshot("after_exit_or_cleanup", info['address']))
        fixture.send("miss")
        fixture.event("called", timeout=3)
        a = fixture.event("heartbeat", timeout=3)['tick']
        b = fixture.event("heartbeat", timeout=3)['tick']
        result['recovered'] = b > a
    except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
        result['failure_type'] = type(error).__name__
        # Error tails below are from our synthetic child only; no app errors read.
    finally:
        result['fixture_exit_before_teardown'] = fixture.process.poll()
        result['fixture_error_tail'] = fixture.errors[-1:]
        if thread:
            thread.close()
        if controller:
            if controller.process.poll() is None:
                controller.process.kill()
                controller.process.wait(timeout=3)
            close_child(controller)
        if observer:
            if observer.process.poll() is None:
                observer.send('cancel')
                try:
                    observer.process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    observer.process.kill()
                    observer.process.wait(timeout=3)
            result['observer_events'] = [json.loads(s) for s in observer.lines if s.startswith('{')]
            result['observer_error_tail'] = observer.errors[-2:]
            result['observer_exit_after_teardown'] = observer.process.returncode
            close_child(observer)
        fixture.close_fixture()
        result['fixture_exit_after_teardown'] = fixture.process.returncode
        result['seconds'] = round(time.monotonic()-started, 3)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--method', choices=('one_shot', 'broker', 'raw'))
    args = p.parse_args()
    cases = [('baseline_busy', 1), ('one_shot_normal', 1), ('one_shot_before_hit', 3),
             ('one_shot_after_hit', 3), ('one_shot_busy', 3),
             ('broker_front_before_hit', 3), ('broker_front_busy', 3), ('broker_owner_busy', 3),
             ('raw_normal', 1), ('raw_before_hit', 3), ('raw_after_hit', 3), ('raw_busy', 3)]
    if args.smoke:
        cases = [('baseline_busy', 1), ('one_shot_normal', 1), ('raw_normal', 1)]
    if args.method:
        cases = [(name, count) for name, count in cases if name.startswith(args.method)]
    cache = HERE.parents[1]/'data/bounded-receive-methods-20261009'
    cache.mkdir(exist_ok=True)
    output = cache / ('run-' + uuid.uuid4().hex[:12] + '.json')
    result = {'fixture_only': True, 'wechat_gate': 'not qualified by this comparison',
              'cases': [], 'selected_cases': cases,
              'source_hashes': {p.relative_to(HERE.parents[1]).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (pathlib.Path(__file__), HERE/'receive_probe_win32.py',
                            HERE/'receive_probe_variants.py', HERE/'receive_probe_fixture.py',
                            HERE/'receive_probe_observer.py', HERE/'diagnose_receive_probe_crash.py',
                            HERE/'test_receive_probe_native.py')}}
    print(json.dumps({'output': str(output)}), flush=True)
    for mode, repeats in cases:
        for repeat in range(repeats):
            case = run_case(mode, repeat)
            result['cases'].append(case)
            output.write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps({k: case.get(k) for k in ('mode', 'repeat', 'recovered', 'burst_calls',
                              'fixture_exit_before_teardown', 'fixture_error_tail', 'observer_error_tail')}), flush=True)
    return 0 if all(c['recovered'] for c in result['cases']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
