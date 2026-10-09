"""Own-process Windows fixture only. Every invocation preserves raw observations."""
import argparse
import hashlib
import json
import queue
import shutil
import subprocess
import threading
import time
import traceback
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data/resident-publisher-20261010'
SOURCE = Path(__file__).with_name('resident_publisher_fixture.c')
ACTIVE, STOPPED, EXITING, FULL, BUSY, INVALID = range(1, 7)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Child:
    def __init__(self, exe, args, log):
        self.log, self.lines = log, queue.Queue()
        self.p = subprocess.Popen([str(exe), *args], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, bufsize=1,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        log.append(dict(action='spawn', args=args, pid=self.p.pid))
        self.reader = threading.Thread(target=self.pump, daemon=True)
        self.reader.start()

    def pump(self):
        for line in self.p.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def get(self):
        line = self.lines.get(timeout=8)
        self.log.append(dict(action='receive', pid=self.p.pid, line=line))
        if line is None:
            raise AssertionError(f'Unexpected EOF, exit={self.p.poll()}')
        return json.loads(line)

    def send(self, command):
        self.log.append(dict(action='send', pid=self.p.pid, command=command))
        self.p.stdin.write(command + '\n')
        self.p.stdin.flush()
        return self.get()

    def wait(self, expected=0):
        code = self.p.wait(timeout=8)
        self.log.append(dict(action='exit', pid=self.p.pid, code=code))
        if expected is not None:
            assert code == expected, code
        self.reader.join(timeout=1)
        return code

    def kill(self):
        self.log.append(dict(action='kill_own_child', pid=self.p.pid))
        self.p.kill()
        return self.wait(None)

    def cleanup(self):
        if self.p.poll() is None:
            try:
                self.send('quit')
                self.wait()
            except Exception:
                self.kill()
                raise
        for f in (self.p.stdin, self.p.stdout):
            f.close()


def records(result, ids):
    assert result['event'] == 'read' and result['reason'] == 'ok', result
    assert [r['id'] for r in result['records']] == ids, result
    for r in result['records']:
        assert (r['seq'], r['a'], r['b'], r['c']) == (
            r['id'], r['id'] ^ 0xa5a5a5a5, r['id'] + 7, r['id'] * 3), r


def rejected(result, reason):
    assert result['event'] == 'read' and result['reason'] == reason, result
    assert result['records'] == [], result


def status(t, count, state=None, published=None):
    r = t.send('status')
    assert r['original'] == count and r['errors'] == 0, r
    if state is not None:
        assert r['state'] == state, r
    if published is not None:
        assert r['published'] == published, r
    return r


def run_case(name, exe):
    log, children = [], []
    mapping = 'Local\\VXOwnPublisher-' + uuid.uuid4().hex
    epoch = uuid.uuid4().hex

    def spawn(role, ep=epoch):
        c = Child(exe, [role, mapping, ep], log)
        children.append(c)
        return c

    def consumer():
        c = spawn('consumer')
        r = c.get()
        assert r['event'] == 'ready' and r['read_only'] is True, r
        assert r['target_pid'] == t.p.pid, r
        return c

    started = time.perf_counter()
    outcome = dict(case=name, passed=False, observations=log)
    try:
        t = spawn('target')
        ready = t.get()
        assert ready['event'] == 'ready' and ready['capacity'] == 8, ready
        assert ready['lock_free'] is True, ready
        if name == 'normal_dedup_full':
            c = consumer()
            t.send('call 4 32')
            records(c.send('read'), list(range(1, 5)))
            records(c.send('read'), [])
            t.send('call 3 32')
            records(c.send('read'), [5, 6, 7])
            t.send('call 2 32')
            status(t, 9, FULL, 8)
            rejected(c.send('read'), 'inactive')
            t.send('call 1000 32')
            status(t, 1009, FULL, 8)
        elif name in ('consumer_stalled', 'consumer_killed', 'consumer_copy_killed', 'consumer_closed'):
            c = consumer()
            if name == 'consumer_copy_killed':
                t.send('call 2 32')
                assert c.send('copy')['count'] == 2
            before = t.send('status')['original']
            assert t.send('workers 1 100 2')['event'] == 'started'
            # The worker is autonomous; no call/cleanup command gates its next call.
            time.sleep(0.03)
            mid = t.send('status')['original']
            assert before < mid < before + 100, mid
            if name in ('consumer_killed', 'consumer_copy_killed'):
                assert c.kill() != 0
            elif name == 'consumer_closed':
                assert c.send('quit')['event'] == 'bye'
                c.wait()
            result = t.send('join')
            assert result['original'] == before + 100 and result['original'] > mid
            status(t, before + 100, FULL, 8)
            if name == 'consumer_stalled':
                rejected(c.send('read'), 'inactive')
        elif name == 'consumer_killed_before_calls':
            c = consumer()
            assert c.kill() != 0
            t.send('call 10000 32')
            status(t, 10000, FULL, 8)
        elif name == 'all_consumers_killed':
            c, d = consumer(), consumer()
            t.send('workers 1 100 2')
            time.sleep(0.03)
            mid = t.send('status')['original']
            assert 0 < mid < 100, mid
            assert c.kill() != 0 and d.kill() != 0
            t.send('join')
            status(t, 100, FULL, 8)
        elif name == 'consumer_restart_replays_same_epoch':
            c = consumer()
            t.send('call 3 32')
            records(c.send('read'), [1, 2, 3])
            c.send('quit')
            c.wait()
            d = consumer()
            # This is an observed limitation, not exactly-once delivery acceptance.
            records(d.send('read'), [1, 2, 3])
            outcome['limitation_observed'] = 'same_epoch_reconnect_replays_without_downstream_checkpoint'
        elif name in ('stop_empty', 'stop_backlog', 'stop_between_copy_commit'):
            c = consumer()
            n = 0 if name == 'stop_empty' else 3
            t.send(f'call {n} 32')
            if name == 'stop_between_copy_commit':
                assert c.send('copy')['count'] == n
            t.send('stop')
            rejected(c.send('commit' if name == 'stop_between_copy_commit' else 'read'), 'inactive')
            t.send('call 1000 32')
            status(t, n + 1000, STOPPED, n)
        elif name == 'accepted_before_stop_is_not_retracted':
            c = consumer()
            t.send('call 1 32')
            accepted = c.send('read')
            t.send('stop')
            records(accepted, [1])  # Explicitly demonstrates the limited acceptance boundary.
            rejected(c.send('read'), 'inactive')
            outcome['limitation_observed'] = 'accepted_output_cannot_be_retracted_by_publisher_stop'
        elif name in ('target_exit_with_view', 'target_killed_between_copy_commit'):
            c = consumer()
            t.send('call 3 32')
            assert c.send('copy')['count'] == 3
            if name == 'target_exit_with_view':
                assert t.send('quit')['event'] == 'bye'
                t.wait()
            else:
                assert t.kill() != 0
            rejected(c.send('commit'), 'target_dead')
            # Existing consumer holds the mapping alive; a new target must refuse it.
            duplicate = spawn('target', uuid.uuid4().hex)
            assert duplicate.get()['reason'] == 'mapping_exists'
            duplicate.wait(10)
            c.send('quit')
            c.wait()
            fresh = spawn('target', uuid.uuid4().hex)
            assert fresh.get()['event'] == 'ready'
            fresh.send('call 1 32')
            status(fresh, 1, ACTIVE, 1)
        elif name == 'epoch_mismatch':
            c = spawn('consumer', uuid.uuid4().hex)
            assert c.get()['reason'] == 'binding'
            c.wait(11)
            t.send('call 1 32')
            status(t, 1, ACTIVE, 1)
        elif name == 'mapping_collision_preserves_data':
            t.send('call 2 32')
            d = spawn('target', uuid.uuid4().hex)
            assert d.get()['reason'] == 'mapping_exists'
            d.wait(10)
            c = consumer()
            records(c.send('read'), [1, 2])
            status(t, 2, ACTIVE, 2)
        elif name == 'invalid_length':
            c = consumer()
            t.send('call 1 33')
            t.send('call 1000 32')
            status(t, 1001, INVALID, 0)
            rejected(c.send('read'), 'inactive')
        elif name == 'publisher_busy':
            t.send('busy')
            t.send('call 1000 32')
            status(t, 1001, BUSY, 0)
        elif name == 'parallel_publishers':
            c = consumer()
            t.send('workers 4 50000 0')
            t.send('join')
            s = status(t, 200000)
            assert s['state'] in (FULL, BUSY) and 0 <= s['published'] <= 8, s
            rejected(c.send('read'), 'inactive')
        elif name == 'stop_during_autonomous_calls':
            c = consumer()
            t.send('workers 1 100 3')
            t.send('stop')
            t.send('join')
            status(t, 100, STOPPED)
            rejected(c.send('read'), 'inactive')
        else:
            raise ValueError(name)
        outcome['passed'] = True
    except Exception as e:
        outcome['error'] = repr(e)
        outcome['traceback'] = traceback.format_exc()
    finally:
        for c in reversed(children):
            try:
                c.cleanup()
            except Exception as e:
                outcome['passed'] = False
                outcome.setdefault('cleanup_errors', []).append(repr(e))
        outcome['all_children_exited'] = all(c.p.poll() is not None for c in children)
        outcome['passed'] &= outcome['all_children_exited']
        outcome['seconds'] = round(time.perf_counter() - started, 6)
    return outcome


CASES = ['normal_dedup_full', 'consumer_stalled', 'consumer_killed',
         'consumer_copy_killed', 'consumer_closed', 'consumer_killed_before_calls',
         'stop_empty', 'stop_backlog', 'stop_between_copy_commit',
         'accepted_before_stop_is_not_retracted', 'target_exit_with_view',
         'target_killed_between_copy_commit', 'epoch_mismatch',
         'mapping_collision_preserves_data', 'invalid_length', 'publisher_busy',
         'parallel_publishers', 'stop_during_autonomous_calls']
CASES += ['all_consumers_killed', 'consumer_restart_replays_same_epoch']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--exe', type=Path, default=CACHE / 'resident_publisher_fixture.exe')
    p.add_argument('--case', action='append', choices=CASES)
    p.add_argument('--repeat', type=int, default=1)
    args = p.parse_args()
    assert 1 <= args.repeat <= 10
    run = CACHE / ('run-' + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    versions = {}
    for f in (Path(__file__), SOURCE, args.exe, CACHE / 'build.json'):
        if f.exists():
            shutil.copyfile(f, run / f.name)
            versions[f.name] = sha(f)
    if args.exe.exists():
        build = json.loads((CACHE / 'build.json').read_text(encoding='utf-8'))
        assert build['exit'] == 0 and build['source_sha256'] == sha(SOURCE)
        assert build['exe_sha256'] == sha(args.exe), 'Executable does not match saved build'
    results = [run_case(c, args.exe) for _ in range(args.repeat) for c in (args.case or CASES)]
    outcome = dict(source_hashes=versions, cases=results,
                   passed=sum(r['passed'] for r in results), total=len(results),
                   target='self-owned fictional native processes', hook_installed=False,
                   command_arguments=vars(args) | {'exe': str(args.exe)})
    (run / 'results.json').write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(run=str(run.relative_to(ROOT)), passed=outcome['passed'], total=len(results),
                          failures=[(r['case'], r.get('error', r.get('cleanup_errors'))) for r in results if not r['passed']])))
    return 0 if outcome['passed'] == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
