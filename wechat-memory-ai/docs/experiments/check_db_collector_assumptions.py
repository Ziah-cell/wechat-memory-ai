"""Discardable feasibility probes, NOT a WeChat collector or admission layer.

Own rule projections from wechatauto-replica fbfb026; never imports that package.
All rows, identities, pages and callbacks are fictional. SQLite is :memory: only.
Expected outcomes: sequence loss, partial-shard loss, ambiguous history/identity,
uncommitted-looking page visibility, and incomplete stop are counterexamples.
Passing confirms these limitations, NOT compatibility, a fix, or live readiness.
"""
import io
import itertools
import json
import queue
import sqlite3
import sys
import threading
import unittest


ATTEMPTS = []


def boundary(event, args):
    forbidden = event.startswith(('subprocess.', 'socket.', 'ctypes.'))
    forbidden |= event in ('os.system', 'os.startfile', 'os.posix_spawn')
    forbidden |= event == 'sqlite3.connect' and args[0] != ':memory:'
    if forbidden:
        ATTEMPTS.append(event)
        raise AssertionError('offline probe boundary: ' + event)


sys.addaudithook(boundary)


def scalar_page(shards, since, limit=200):
    """db.py 1738/1986 rule projection, including swallowed query errors."""
    rows = []
    for shard, conn in shards:
        try:
            rows.extend((r[0], shard, r[1], r[2]) for r in conn.execute(
                'SELECT sort_seq, local_id, server_id FROM msgs '
                'WHERE sort_seq > ? ORDER BY sort_seq, local_id LIMIT ?',
                (since, limit)))
        except sqlite3.DatabaseError:
            continue
    return sorted(rows, key=lambda r: r[0])[:limit]


def frozen_scan(shards, limit):
    """Own experiment: per-shard pair cursor ONLY within a frozen snapshot.

    There is no production path, account inference, history decision or callback.
    Exhaust all shards before returning; an error exposes no partial result.
    """
    result = []
    for shard, conn in shards:
        cursor = None
        while True:
            if cursor is None:
                rows = conn.execute(
                    'SELECT sort_seq, local_id, server_id FROM msgs '
                    'ORDER BY sort_seq, local_id LIMIT ?', (limit,)).fetchall()
            else:
                rows = conn.execute(
                    'SELECT sort_seq, local_id, server_id FROM msgs '
                    'WHERE (sort_seq, local_id) > (?, ?) '
                    'ORDER BY sort_seq, local_id LIMIT ?', (*cursor, limit)).fetchall()
            if not rows:
                break
            result.extend((seq, shard, local, server) for seq, local, server in rows)
            cursor = rows[-1][:2]
    return sorted(result)


def public_projection(raw, names):
    """Plain-text branch of db.py 2007; no upstream execution."""
    sid = raw['real_sender_id']
    return dict(local_id=raw['local_id'], type='文本', sender_id=sid,
                sender_username=names.get(sid, '') if sid and sid != 2 else '',
                create_time=raw['create_time'], content=raw['message_content'],
                sort_seq=raw['sort_seq'])


def wrapper_role(row, account):
    """wx.py 265/280 decision; sender_username does not participate."""
    sid = row['sender_id']
    return 'self' if sid == 2 or bool(account and str(sid) == account) else 'friend'


class CollectorCounterexamples(unittest.TestCase):
    def db(self, rows=()):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.execute('CREATE TABLE msgs(sort_seq INTEGER NOT NULL, '
                     'local_id INTEGER PRIMARY KEY, server_id INTEGER NOT NULL)')
        conn.executemany('INSERT INTO msgs VALUES(?,?,?)', rows)
        conn.commit()
        return conn

    def raw(self, sender=7):
        return dict(local_id=1, server_id=9001, real_sender_id=sender,
                    create_time=100, message_content='fictional', sort_seq=10,
                    local_type=1, source='', packed_info_data=b'',
                    compress_content=b'', shard='shard-a')

    def test_01_same_seq_201st_row_is_lost(self):
        conn = self.db((10, n, 1000 + n) for n in range(1, 202))
        first = scalar_page([('a', conn)], 0)
        self.assertEqual(len(first), 200)
        self.assertEqual(scalar_page([('a', conn)], first[-1][0]), [])
        self.assertEqual(conn.execute('SELECT count(*) FROM msgs').fetchone()[0], 201)

    def test_02_cross_shard_tie_is_lost(self):
        shards = [('a', self.db([(10, 1, 1)])), ('b', self.db([(10, 1, 2)]))]
        first = scalar_page(shards, 0, 1)
        self.assertEqual(len(first), 1)
        self.assertEqual(scalar_page(shards, first[-1][0], 1), [])
        self.assertEqual(len(frozen_scan(shards, 1)), 2)

    def test_03_frozen_pair_paging_matches_independent_full_sort(self):
        # Exhaustive small datasets: 81 sequence assignments x 3 page sizes.
        for seqs in itertools.product(range(3), repeat=4):
            a = [(seqs[0], 1, 1), (seqs[1], 2, 2)]
            b = [(seqs[2], 1, 3), (seqs[3], 2, 4)]
            shards = [('b', self.db(b)), ('a', self.db(a))]
            oracle = sorted([(s, 'a', i, v) for s, i, v in a] +
                            [(s, 'b', i, v) for s, i, v in b])
            for limit in (1, 2, 3):
                with self.subTest(seqs=seqs, limit=limit):
                    self.assertEqual(frozen_scan(shards, limit), oracle)

    def test_04_pair_cursor_does_not_solve_late_lower_insert(self):
        conn = self.db([(10, 1, 1), (20, 2, 2)])
        initial = frozen_scan([('a', conn)], 1)
        cursor = (initial[-1][0], initial[-1][2])
        conn.execute('INSERT INTO msgs VALUES(15,3,3)')
        tail = conn.execute('SELECT * FROM msgs WHERE (sort_seq,local_id)>(?,?)',
                            cursor).fetchall()
        self.assertEqual(tail, [])
        self.assertEqual(len(frozen_scan([('a', conn)], 1)), 3)

    def test_05_silent_shard_failure_then_recovery_loses_row(self):
        good, broken = self.db([(20, 1, 1)]), self.db()
        broken.execute('DROP TABLE msgs')
        partial = scalar_page([('a', good), ('b', broken)], 0)
        self.assertEqual([r[0] for r in partial], [20])
        recovered = self.db([(10, 1, 2)])
        self.assertEqual(scalar_page([('a', good), ('b', recovered)], 20), [])

    def test_06_frozen_scan_error_exposes_no_partial_return(self):
        good, broken = self.db([(20, 1, 1)]), self.db()
        broken.execute('DROP TABLE msgs')
        observed = []
        with self.assertRaises(sqlite3.DatabaseError):
            observed.extend(frozen_scan([('a', good), ('b', broken)], 1))
        self.assertEqual(observed, [])

    def test_07_projection_discards_server_and_shard_identity(self):
        a, b = self.raw(), self.raw()
        b.update(server_id=9002, shard='shard-b')
        self.assertNotEqual(a, b)
        self.assertEqual(public_projection(a, {}), public_projection(b, {}))

    def test_08_peer_rowid_two_is_misclassified_self(self):
        row = public_projection(self.raw(2), {2: 'fiction-peer'})
        self.assertEqual(row['sender_username'], '')
        self.assertEqual(wrapper_role(row, 'fiction-self'), 'self')

    def test_09_self_rowid_one_is_misclassified_friend(self):
        row = public_projection(self.raw(1), {1: 'fiction-self'})
        self.assertEqual(row['sender_username'], 'fiction-self')
        self.assertEqual(wrapper_role(row, 'fiction-self'), 'friend')

    def test_10_unknown_sender_is_also_classified_friend(self):
        row = public_projection(self.raw(77), {})
        self.assertEqual(row['sender_username'], '')
        self.assertEqual(wrapper_role(row, 'fiction-self'), 'friend')

    def test_11_persisted_watermark_includes_downtime_history(self):
        conn = self.db([(10, 1, 1), (20, 2, 2)])
        # All rows predate this observation session. Existing watermark wins.
        watermark = 10
        self.assertEqual([r[0] for r in scalar_page([('a', conn)], watermark)], [20])
        fresh_baseline = conn.execute('SELECT max(sort_seq) FROM msgs').fetchone()[0]
        self.assertEqual(scalar_page([('a', conn)], fresh_baseline), [])

    def test_12_fresh_baseline_cannot_distinguish_later_history(self):
        live, history = self.db(), self.db()
        # Different hypothetical origins outside the schema, same observations.
        # This does not prove source/packed_info_data semantics in actual WeChat.
        for conn in (live, history):
            conn.execute('INSERT INTO msgs VALUES(50,1,1001)')
        self.assertEqual(frozen_scan([('a', live)], 1), frozen_scan([('a', history)], 1))
        raw_live, raw_delayed_history = self.raw(), self.raw()
        self.assertEqual(raw_live, raw_delayed_history)

    def test_13_quick_check_cannot_certify_freshness(self):
        old, new = self.db([(10, 1, 1)]), self.db([(10, 1, 1), (20, 2, 2)])
        for conn in (old, new):
            self.assertEqual(conn.execute('PRAGMA quick_check').fetchall(), [('ok',)])
        self.assertNotEqual(frozen_scan([('a', old)], 1), frozen_scan([('a', new)], 1))

    def test_14_uncommitted_page_projection_can_pass_quick_check(self):
        # Synthetic plaintext page/frame model, not WCDB decryption or a real WAL.
        conn = self.db([(10, 1, 1)])
        before = conn.serialize()
        conn.execute('UPDATE msgs SET server_id=2')
        conn.commit()
        after = conn.serialize()
        page_size = int.from_bytes(before[16:18], 'big')
        if page_size == 1:
            page_size = 65536
        self.assertEqual(len(before), len(after))
        root = conn.execute("SELECT rootpage FROM sqlite_master WHERE name='msgs'").fetchone()[0]
        offset = (root - 1) * page_size
        # Frame zero marks a committed original page; next frame has commit size 0.
        frames = [(root, len(before) // page_size, before[offset:offset + page_size]),
                  (root, 0, after[offset:offset + page_size])]
        lax, committed = bytearray(before), bytearray(before)
        for pgno, commit_size, page in frames:
            start = (pgno - 1) * page_size
            lax[start:start + page_size] = page
            if commit_size:
                committed[:] = lax
        bad, good = self.db(), self.db()
        bad.deserialize(bytes(lax))
        good.deserialize(bytes(committed))
        self.assertEqual(bad.execute('PRAGMA quick_check').fetchall(), [('ok',)])
        self.assertEqual(bad.execute('SELECT server_id FROM msgs').fetchone(), (2,))
        self.assertEqual(good.execute('SELECT server_id FROM msgs').fetchone(), (1,))

    def test_15_local_id_requires_shard_scope(self):
        rows = frozen_scan([('a', self.db([(10, 1, 1)])),
                            ('b', self.db([(20, 1, 2)]))], 1)
        self.assertEqual(len({r[2] for r in rows}), 1)
        self.assertEqual(len({(r[1], r[2]) for r in rows}), 2)

    def test_16_tail_sentinel_allows_preceding_callbacks(self):
        q, stop, calls = queue.Queue(), object(), []
        for task in ('queued-a', 'queued-b', stop):
            q.put(task)
        self.assertEqual(q.maxsize, 0)
        while True:
            task = q.get_nowait()
            if task is stop:
                break
            calls.append(task)
        self.assertEqual(calls, ['queued-a', 'queued-b'])

    def test_17_timed_join_returns_while_own_worker_is_alive(self):
        entered, release = threading.Event(), threading.Event()
        def worker():
            entered.set()
            release.wait(3)
        thread = threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertIsNone(thread.join(timeout=0))
            self.assertTrue(thread.is_alive())
        finally:
            release.set()
            thread.join(timeout=1)
        self.assertFalse(thread.is_alive())

    def test_18_callback_group_retry_duplicates_effect_and_advances_failed_row(self):
        effects, outcomes = [], []
        def first():
            effects.append('fictional-effect')
        def second():
            raise ValueError('fictional-failure')
        for attempt in range(2):
            try:
                for callback in (first, second):
                    callback()
            except ValueError:
                outcomes.append(False)
        # db.py 3000 commits even when callbacks exhausted their retries.
        watermark = max(0, 10)
        self.assertEqual((effects, outcomes, watermark),
                         (['fictional-effect'] * 2, [False, False], 10))


if __name__ == '__main__':
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CollectorCounterexamples)
    names = [test.id().split('.')[-1] for test in suite]
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    summary = dict(scope='own synthetic rule projections; no upstream or product execution',
                   python=sys.version.split()[0], sqlite=sqlite3.sqlite_version,
                   tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   frozen_paging_comparisons=243, boundary_attempts=ATTEMPTS,
                   passed=result.wasSuccessful() and not ATTEMPTS,
                   cases=names, log=output.getvalue())
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    raise SystemExit(0 if summary['passed'] else 1)
