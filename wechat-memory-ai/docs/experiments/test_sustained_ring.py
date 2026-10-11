"""Own Windows processes and fictional rows only. Each run is immutable evidence."""
import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import time
import traceback
import uuid
from pathlib import Path
from test_resident_publisher import Child

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data/sustained-ring-20261011'
EXE = CACHE / 'sustained_ring_fixture.exe'
LEDGER = Path(__file__).with_name('sustained_ring_ledger.py')
CASES = ['multilap', 'ack_loss', 'stale_epoch', 'stale_generation', 'stale_sequence',
         'future_ack', 'consumer_loss', 'before_commit', 'after_commit', 'db_busy',
         'db_full', 'capacity', 'torn_copy', 'ledger_reject', 'stop', 'target_loss', 'original_fault',
         'reentrant_original_fault'] + ['reuse_' + p for p in
         ['gate_enter', 'gate_partial', 'gate_precommit', 'gate_postcommit']]
SOURCES = ['sustained_ring_fixture.c', 'sustained_ring_protocol.h',
           'sustained_ring_ledger.py', 'capture_copy_site.S',
           'executed_trampoline_fixture.c', 'trampoline_register_caller.S',
           'test_resident_publisher.py']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def good(r):
    assert r.get('ok') is True, r
    return r


def run_case(name, mode, run, index):
    folder = run / f'{index:03d}-{name}'
    folder.mkdir()
    db = folder / 'ledger.sqlite3'
    log, children = [], []
    epoch = uuid.uuid4().hex
    mapping = 'Local\\VXOwnPublisher-' + uuid.uuid4().hex
    out = dict(case=name, mode=mode, passed=False, observations=log,
               database=db.relative_to(ROOT).as_posix())
    target = ledger = consumer = blocker = None
    race_open = False
    started = time.perf_counter()

    def spawn(exe, args):
        p = Child(exe, args, log)
        children.append(p)
        return p

    def command(p, op, **kw):
        return p.send(json.dumps(dict(op=op, **kw)))

    def new_ledger():
        p = spawn(sys.executable, ['-u', str(LEDGER), '--database', str(db)])
        r = p.get()
        assert r['event'] == 'ready' and r['synchronous'] == 2, r
        return p

    def new_consumer():
        p = spawn(EXE, ['consumer', mapping, epoch] + ([mode] if mode == 'skip_stamp' else []))
        assert p.get()['read_only'] is True
        return p

    def read(ids):
        batch = consumer.send('read')
        assert batch['reason'] == 'ok', batch
        assert [r['id'] for r in batch['records']] == list(ids), batch
        for r in batch['records']:
            i = r['id']
            assert (r['a'], r['b'], r['c']) == (i ^ 0xa5a5a5a5, i + 7, i * 3), r
            assert r['generation'] == (r['seq'] - 1) // 8 + 1, r
        return batch['records']

    def accept(batch, **kw):
        return command(ledger, 'accept', epoch=epoch, records=batch, **kw)

    def ack(receipt, **kw):
        a = dict(receipt['ack'], **kw)
        return target.send(f"ack {a['epoch']} {a['seq']} {a['generation']}")

    def flow(start, count=8):
        state = target.send(f'call {count} 32')
        batch = read(range(start, start + count))
        receipt = good(accept(batch))
        good(ack(receipt))
        return state, batch, receipt

    try:
        assert EXE.exists() and LEDGER.exists(), 'new sustained ring implementation missing'
        target = spawn(EXE, ['target', mapping, epoch] + ([mode] if mode not in ('exact', 'skip_stamp') else []))
        r = target.get()
        assert r['registered_entries'] == 3 and r['lock_free'] and r['mapping_bytes'] == 4096, r
        ledger = new_ledger()
        good(command(ledger, 'begin', epoch=epoch))
        consumer = new_consumer()
        expected_rows = 0
        if name == 'multilap':
            for start in range(1, 257, 8):
                state, batch, receipt = flow(start)
                assert state['state'] == 1 and receipt['added'] == 8
                assert [r['seq'] for r in batch] == list(range(start, start + 8))
            expected_rows = 256
        elif name in ('ack_loss', 'consumer_loss', 'before_commit', 'after_commit', 'db_busy', 'db_full'):
            target.send('call 8 32')
            batch = read(range(1, 9))
            if name == 'consumer_loss':
                consumer.kill()
                state = target.send('call 10000 32')
                assert state['original'] == 10008 and state['state'] == 4 and state['published'] == 8, state
                consumer = new_consumer()
                assert read(range(1, 9)) == batch
            if name in ('before_commit', 'after_commit'):
                point = accept(batch, checkpoint=name)
                assert point == dict(event='checkpoint', stage=name), point
                ledger.kill()
                state = target.send('call 10000 32')
                assert state['original'] == 10008 and state['published'] == 8 and state['state'] == 4, state
                ledger = new_ledger()
                snap = good(command(ledger, 'snapshot'))
                assert len(snap['records']) == (8 if name == 'after_commit' else 0), snap
            elif name == 'db_busy':
                blocker = sqlite3.connect(db, timeout=0)
                blocker.execute('BEGIN IMMEDIATE')
                result = accept(batch)
                assert result['ok'] is False and result['reason'] == 'busy', result
                # Original calls still return while the durable writer holds its lock.
                state = target.send('call 10000 32')
                assert state['original'] == 10008 and state['published'] == 8 and state['state'] == 4, state
                blocker.rollback(); blocker.close(); blocker = None
            elif name == 'db_full':
                good(command(ledger, 'limit_pages'))
                result = accept(batch)
                assert result['ok'] is False and result['sqlite_code'] == sqlite3.SQLITE_FULL, result
                assert good(command(ledger, 'snapshot'))['records'] == []
                assert target.send('status')['acked'] == 0
                good(command(ledger, 'unlimit_pages'))
            receipt = good(accept(batch))
            if name in ('ack_loss', 'after_commit'):
                again = good(accept(batch))
                assert again['added'] == 0 and again['duplicates'] == 8, again
                assert target.send('status')['acked'] == 0
                receipt = again
            good(ack(receipt))
            expected_rows = 8
            if name not in ('db_busy', 'consumer_loss', 'before_commit', 'after_commit'):
                flow(9)
                expected_rows = 16
        elif name in ('stale_epoch', 'stale_generation', 'stale_sequence', 'future_ack'):
            _, _, old = flow(1)
            target.send('call 8 32')
            batch = read(range(9, 17))
            receipt = good(accept(batch))
            before = target.send('status')
            changes = {'stale_epoch': dict(epoch='0' * 32),
                       'stale_generation': dict(generation=1),
                       'stale_sequence': dict(seq=8, generation=1),
                       'future_ack': dict(seq=24, generation=3)}[name]
            rejected = ack(receipt, **changes)
            after = target.send('status')
            assert rejected['ok'] is False and after['acked'] == before['acked'] == 8, (rejected, after)
            good(ack(receipt))
            flow(17)
            expected_rows = 24
        elif name == 'capacity':
            target.send('call 8 32')
            first = read(range(1, 9))
            state = target.send('call 10000 32')
            out['full_state'] = state
            after = consumer.send('read'); out['full_batch'] = after
            assert state['original'] == 10008 and state['published'] == 8 and state['acked'] == 0, state
            assert state['state'] == 4 and state['gap'] == 10000, state
            assert after['records'] == first, after
            good(ack(good(accept(first))))
            assert target.send('call 2 32')['published'] == 8
            expected_rows = 8
        elif name == 'torn_copy':
            target.send('call 8 32')
            batch = read(range(1, 9))
            assert consumer.send('split')['event'] == 'split'
            good(ack(good(accept(batch))))
            target.send('call 8 32')
            result = consumer.send('finish'); out['mixed_copy'] = result
            assert result['reason'] == 'changed' and result['records'] == [], result
            good(ack(good(accept(read(range(9, 17))))))
            expected_rows = 16
        elif name == 'ledger_reject':
            target.send('call 8 32')
            batch = read(range(1, 9))
            bad = [dict(batch[0], generation=2)]
            result = accept(bad)
            assert result['ok'] is False and result['reason'] == 'invalid_generation', result
            result = accept(batch[1:])
            assert result['ok'] is False and result['reason'] == 'gap', result
            assert good(command(ledger, 'snapshot'))['records'] == []
            receipt = good(accept(batch))
            bad = [dict(batch[0], id=42, a=42 ^ 0xa5a5a5a5, b=49, c=126)]
            result = accept(bad)
            assert result['ok'] is False and result['reason'] == 'conflict', result
            assert target.send('status')['acked'] == 0
            good(ack(receipt))
            expected_rows = 8
        elif name == 'stop':
            target.send('call 8 32')
            batch = read(range(1, 9))
            receipt = good(accept(batch))
            good(command(ledger, 'stop', epoch=epoch))
            target.send('stop')
            assert accept(batch)['ok'] is False
            good(ack(receipt))  # Earlier commit remains valid, but cannot restart capture.
            assert target.send('call 5 32')['published'] == 8
            expected_rows = 8
        elif name == 'target_loss':
            target.send('call 8 32')
            target.kill()
            result = consumer.send('read')
            assert result['reason'] == 'target_dead' and not result['records'], result
        elif name in ('original_fault', 'reentrant_original_fault'):
            first = target.send('scenario ' + name)
            assert first['original_exceptions'] == 1 and first['depth'] == first['published'] == 0, first
            target.send('scenario normal')
            ident = 1 if name == 'original_fault' else 2
            good(ack(good(accept(read([ident])))))
            expected_rows = 1
        elif name.startswith('reuse_'):
            flow(1)
            first = target.send('race ' + name[6:] + '_prechecked')
            race_open = True
            out['race_window'] = first
            window = consumer.send('read'); out['window_batch'] = window
            if window['records']:
                out['window_commit'] = good(accept(window['records']))
            later = target.send('resume'); race_open = False
            out['race_end'] = later
            post = int(name == 'reuse_gate_postcommit')
            assert first['window_state'] == 6 and first['window_gate'] == 0, first
            assert first['second_gate_acquired'] == 1 and first['published'] == 8 + post, first
            assert window['reason'] == 'inactive' and window['records'] == [], window
            assert later['depth'] == later['gate'] == later['errors'] == 0 and later['capture_faults'] == 1, later
            assert later['tls_workers'] == later['tls_depth_zero'] == 2 and later['tls_distinct'], later
            assert target.send('call 2 32')['original'] == 12
            expected_rows = 8
        snap = good(command(ledger, 'snapshot')); out['snapshot'] = snap
        assert len(snap['records']) == expected_rows and snap['integrity'] == 'ok', snap
        assert [r['seq'] for r in snap['records']] == list(range(1, expected_rows + 1)), snap
        out['expected_rows'] = expected_rows
        if target.p.poll() is None:
            state = target.send('status'); out['final_state'] = state
            assert state['errors'] == state['gate'] == state['depth'] == 0, state
            assert state['acked'] <= len(snap['records']) and state['published'] - state['acked'] <= 8, state
            assert state['gap'] == state['original'] - state['published'], state
        out['passed'] = True
    except Exception as exc:
        out.update(error=repr(exc), traceback=traceback.format_exc())
    finally:
        if blocker:
            blocker.rollback(); blocker.close()
        if ledger and ledger.p.poll() is None:
            try:
                out['stop_result'] = command(ledger, 'stop', epoch=epoch)
            except Exception as exc:
                out.setdefault('cleanup_errors', []).append(repr(exc)); out['passed'] = False
        for child in reversed(children):
            try:
                if child is target and child.p.poll() is None:
                    if race_open:
                        child.send('resume')
                    result = child.send('quit'); out['target_cleanup'] = result
                    assert all(result.get(k) is True for k in ['prefix_restored', 'table_deleted', 'lookups_absent', 'freed', 'mapping_closed', 'guard_freed']), result
                    child.wait()
                child.cleanup()
            except Exception as exc:
                out['passed'] = False
                out.setdefault('cleanup_errors', []).append(repr(exc))
                if child.p.poll() is None:
                    child.kill()
        out['all_children_exited'] = all(p.p.poll() is not None for p in children)
        out['passed'] &= out['all_children_exited']
        out['database_files'] = {p.name: sha(p) for p in folder.glob('ledger.sqlite3*')}
        out['seconds'] = time.perf_counter() - started
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', action='append', choices=CASES)
    ap.add_argument('--mode', default='exact', choices=['exact', 'overwrite', 'skip_epoch', 'skip_generation', 'skip_stamp', 'late_stop', 'skip_recheck'])
    ap.add_argument('--repeat', type=int, default=1)
    args = ap.parse_args()
    assert 1 <= args.repeat <= 3
    run = CACHE / ('run-' + uuid.uuid4().hex[:12]); run.mkdir(parents=True)
    hashes = {}
    for p in [Path(__file__), *[Path(__file__).with_name(n) for n in SOURCES], EXE, CACHE / 'build.json']:
        if p.exists():
            shutil.copyfile(p, run / p.name); hashes[p.name] = sha(p)
    if EXE.exists():
        build = json.loads((CACHE / 'build.json').read_text())
        assert sha(EXE) == build['exe_sha256']
        for n, h in build['source_hashes'].items():
            assert sha(Path(__file__).with_name(n)) == h, n
    cases = [run_case(n, args.mode, run, i) for i, n in enumerate((args.case or CASES) * args.repeat)]
    result = dict(source_hashes=hashes, cases=cases, total=len(cases), passed=sum(c['passed'] for c in cases), mode=args.mode)
    (run / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(run=run.relative_to(ROOT).as_posix(), passed=result['passed'], total=result['total'], failures=[(c['case'], c.get('error')) for c in cases if not c['passed']])))
    return int(result['passed'] != result['total'])


if __name__ == '__main__':
    raise SystemExit(main())
