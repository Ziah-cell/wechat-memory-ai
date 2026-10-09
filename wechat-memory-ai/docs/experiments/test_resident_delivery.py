"""Real own-process native reader -> fictional SQLite inbox crash/stop tests."""
import argparse
import hashlib
import json
import shutil
import sys
import time
import traceback
import uuid
from pathlib import Path
from test_resident_publisher import Child

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data/resident-delivery-20261010'
NATIVE = ROOT / 'data/resident-publisher-20261010/resident_publisher_fixture.exe'
SOURCE = Path(__file__).with_name('resident_delivery_ledger.py')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fixture_record(seq, ident=None):
    ident = seq if ident is None else ident
    return dict(seq=seq, id=ident, a=ident ^ 0xa5a5a5a5, b=ident + 7, c=ident * 3)


def ok(result, **expected):
    assert result['ok'] is True, result
    for key, value in expected.items():
        assert result[key] == value, result
    return result


def denied(result, reason):
    assert result['ok'] is False and result['reason'] == reason, result


def run_case(name, run, source):
    folder = run / (name + '-' + uuid.uuid4().hex[:8])
    folder.mkdir()
    db = folder / 'ledger.sqlite3'
    log, children = [], []
    epoch = uuid.uuid4().hex
    mapping = 'Local\\VXOwnPublisher-' + uuid.uuid4().hex

    def spawn(exe, args):
        c = Child(exe, args, log)
        children.append(c)
        return c

    def ledger():
        p = spawn(sys.executable, ['-u', str(source), '--database', str(db)])
        r = p.get()
        assert r['event'] == 'ready' and r['journal_mode'] == 'wal' and r['synchronous'] == 2, r
        return p

    def cmd(p, operation, **kwargs):
        return p.send(json.dumps(dict(op=operation, **kwargs)))

    def accept(p, recs, ep=epoch, **kwargs):
        return cmd(p, 'accept', epoch=ep, records=recs, **kwargs)

    def snapshot(p, count, seq, closed=False):
        x = ok(cmd(p, 'snapshot'))
        assert len(x['records']) == count, x
        session = next(s for s in x['sessions'] if s['epoch'] == epoch)
        assert session['last_seq'] == seq and session['state'] == ('closed' if closed else 'active'), x
        assert x['integrity'] == 'ok', x
        return x

    start = time.perf_counter()
    out = dict(case=name, passed=False, observations=log, database=db.relative_to(ROOT).as_posix())
    try:
        p = ledger()
        ok(cmd(p, 'begin', epoch=epoch))
        if name in ('native_reconnect_dedup', 'pending_native_after_stop', 'ledger_busy_target_continues'):
            t = spawn(NATIVE, ['target', mapping, epoch])
            assert t.get()['event'] == 'ready'
            c = spawn(NATIVE, ['consumer', mapping, epoch])
            assert c.get()['read_only'] is True
            t.send('call 3 32')
            batch = c.send('read')['records']
            assert [r['seq'] for r in batch] == [1, 2, 3]
            if name == 'native_reconnect_dedup':
                ok(accept(p, batch), added=3, duplicates=0)
                c.send('quit'); c.wait()
                p.send('quit'); p.wait()
                c = spawn(NATIVE, ['consumer', mapping, epoch])
                assert c.get()['event'] == 'ready'
                p = ledger()
                replay = c.send('read')['records']
                assert replay == batch
                ok(accept(p, replay), added=0, duplicates=3)
                t.send('call 1 32')
                ok(accept(p, c.send('read')['records']), added=1)
                snapshot(p, 4, 4)
            elif name == 'pending_native_after_stop':
                mark = ok(cmd(p, 'stop', epoch=epoch))['stop_op']
                denied(accept(p, batch), 'closed')
                t.send('call 1 32')
                denied(accept(p, c.send('read')['records']), 'closed')
                s = snapshot(p, 0, 0, True)
                assert s['operations'][-1]['id'] == mark
                assert t.send('status')['original'] == 4
            else:
                q = ledger()
                held = accept(p, batch, checkpoint='before_commit')
                assert held['stage'] == 'before_commit'
                t.send('workers 1 100 2')
                denied(cmd(q, 'stop', epoch=epoch), 'busy')
                assert p.kill() != 0
                mark = ok(cmd(q, 'stop', epoch=epoch))['stop_op']
                assert t.send('join')['original'] == 103
                denied(accept(q, batch), 'closed')
                assert snapshot(q, 0, 0, True)['operations'][-1]['id'] == mark
        elif name.startswith('accept_crash_'):
            stage = name.removeprefix('accept_crash_')
            assert accept(p, [fixture_record(1), fixture_record(2)], checkpoint=stage)['stage'] == stage
            assert p.kill() != 0
            p = ledger()
            committed = stage == 'after_commit'
            snapshot(p, 2 if committed else 0, 2 if committed else 0)
            ok(accept(p, [fixture_record(1), fixture_record(2)]), added=0 if committed else 2,
               duplicates=2 if committed else 0)
            snapshot(p, 2, 2)
        elif name.startswith('stop_crash_'):
            stage = name.removeprefix('stop_crash_')
            assert cmd(p, 'stop', epoch=epoch, checkpoint=stage)['stage'] == stage
            assert p.kill() != 0
            p = ledger()
            committed = stage == 'after_commit'
            snapshot(p, 0, 0, committed)
            if committed:
                denied(accept(p, [fixture_record(1)]), 'closed')
            else:
                ok(accept(p, [fixture_record(1)]), added=1)
            first = ok(cmd(p, 'stop', epoch=epoch))['stop_op']
            second = ok(cmd(p, 'stop', epoch=epoch))['stop_op']
            assert first == second
        elif name in ('accept_holds_stop', 'stop_holds_accept'):
            q = ledger()
            if name == 'accept_holds_stop':
                assert accept(p, [fixture_record(1)], checkpoint='before_commit')['stage'] == 'before_commit'
                denied(cmd(q, 'stop', epoch=epoch), 'busy')
                ok(p.send('resume'), added=1)
                mark = ok(cmd(q, 'stop', epoch=epoch))['stop_op']
                denied(accept(p, [fixture_record(2)]), 'closed')
                s = snapshot(q, 1, 1, True)
                assert all(r['commit_op'] < mark for r in s['records'])
            else:
                assert cmd(p, 'stop', epoch=epoch, checkpoint='before_commit')['stage'] == 'before_commit'
                denied(accept(q, [fixture_record(1)]), 'busy')
                ok(p.send('resume'))
                denied(accept(q, [fixture_record(1)]), 'closed')
                snapshot(q, 0, 0, True)
        elif name in ('accept_ack_after_stop', 'duplicate_writer_race'):
            q = ledger()
            stage = 'after_commit' if name == 'accept_ack_after_stop' else 'before_commit'
            assert accept(p, [fixture_record(1)], checkpoint=stage)['stage'] == stage
            if name == 'accept_ack_after_stop':
                marker = ok(cmd(q, 'stop', epoch=epoch))['stop_op']
                ok(p.send('resume'), added=1)  # Late ACK describes a commit BEFORE STOP.
                denied(accept(p, [fixture_record(1)]), 'closed')
                assert snapshot(q, 1, 1, True)['records'][0]['commit_op'] < marker
                out['boundary_observed'] = 'old_commit_ack_may_arrive_after_stop_ack; no_later_inbox_insert'
            else:
                denied(accept(q, [fixture_record(1)]), 'busy')
                ok(p.send('resume'), added=1)
                ok(accept(q, [fixture_record(1)]), added=0, duplicates=1)
                snapshot(q, 1, 1)
        elif name == 'malformed_protocol':
            denied(p.send('[]'), 'protocol')
            ok(accept(p, [fixture_record(1)]), added=1)
            snapshot(p, 1, 1)
        elif name == 'closed_reopen_and_epoch_switch':
            ok(accept(p, [fixture_record(1)]), added=1)
            ok(cmd(p, 'stop', epoch=epoch))
            p.send('quit'); p.wait(); p = ledger()
            denied(cmd(p, 'begin', epoch=epoch), 'epoch_used')
            fresh = uuid.uuid4().hex
            ok(cmd(p, 'begin', epoch=fresh))
            denied(accept(p, [fixture_record(2)]), 'closed')
            ok(accept(p, [fixture_record(1)], ep=fresh), added=1)
            ok(cmd(p, 'stop', epoch=epoch))  # Late old STOP must not close the new epoch.
            ok(accept(p, [fixture_record(2)], ep=fresh), added=1)
            snapshot(p, 3, 1, True)
        elif name in ('gap_rolls_back_batch', 'payload_conflict', 'malformed_batch', 'new_epoch_while_active'):
            ok(accept(p, [fixture_record(1)]), added=1)
            if name == 'gap_rolls_back_batch':
                denied(accept(p, [fixture_record(2), fixture_record(4)]), 'gap')
            elif name == 'payload_conflict':
                denied(accept(p, [fixture_record(1, 99), fixture_record(2)]), 'conflict')
            elif name == 'malformed_batch':
                denied(accept(p, [fixture_record(2), fixture_record(3) | {'id': True}]), 'invalid_batch')
            else:
                denied(cmd(p, 'begin', epoch=uuid.uuid4().hex), 'active_epoch')
            snapshot(p, 1, 1)
            ok(accept(p, [fixture_record(2)]), added=1)
            snapshot(p, 2, 2)
        else:
            raise ValueError(name)
        out['passed'] = True
    except Exception as e:
        out.update(error=repr(e), traceback=traceback.format_exc())
    finally:
        for child in reversed(children):
            try:
                child.cleanup()
            except Exception as e:
                out['passed'] = False
                out.setdefault('cleanup_errors', []).append(repr(e))
        out['all_children_exited'] = all(c.p.poll() is not None for c in children)
        out['passed'] &= out['all_children_exited']
        out['seconds'] = time.perf_counter() - start
        out['database_files'] = {f.name:sha(f) for f in folder.glob('ledger.sqlite3*')}
    return out


CASES = ['native_reconnect_dedup', 'pending_native_after_stop', 'ledger_busy_target_continues',
         'accept_crash_before_commit', 'accept_crash_after_commit',
         'stop_crash_before_commit', 'stop_crash_after_commit',
         'accept_holds_stop', 'stop_holds_accept', 'closed_reopen_and_epoch_switch',
         'gap_rolls_back_batch', 'payload_conflict', 'malformed_batch', 'new_epoch_while_active']
CASES += ['accept_ack_after_stop', 'duplicate_writer_race', 'malformed_protocol']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', type=Path, default=SOURCE)
    parser.add_argument('--case', action='append', choices=CASES)
    parser.add_argument('--repeat', type=int, default=1)
    args = parser.parse_args()
    assert 1 <= args.repeat <= 3
    assert sha(NATIVE) == '9c5225def798ea77507dce2643282479869c35fb5e49cc7841a50512b4e41307'
    run = CACHE / ('run-' + uuid.uuid4().hex[:12]); run.mkdir(parents=True)
    hashes = {}
    for f in (Path(__file__), args.ledger, Path(__file__).with_name('test_resident_publisher.py')):
        if f.exists():
            shutil.copyfile(f, run / f.name); hashes[f.name] = sha(f)
    cases = [run_case(c, run, args.ledger.resolve()) for _ in range(args.repeat) for c in (args.case or CASES)]
    result = dict(source_hashes=hashes, native_exe_sha256=sha(NATIVE), cases=cases,
                  passed=sum(c['passed'] for c in cases), total=len(cases),
                  external_effect='fictional SQLite inbox only; no real message delivery',
                  ledger_source=str(args.ledger), python=sys.version)
    (run / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(run=run.relative_to(ROOT).as_posix(), passed=result['passed'], total=len(cases),
                         failures=[(c['case'], c.get('error')) for c in cases if not c['passed']])))
    return int(result['passed'] != result['total'])


if __name__ == '__main__':
    raise SystemExit(main())
