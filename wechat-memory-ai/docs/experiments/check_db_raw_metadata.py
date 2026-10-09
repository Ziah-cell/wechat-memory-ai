"""Synthetic raw-lookup counterexamples for pinned wechatauto fbfb026.

No upstream/product imports, files, real database, model, or WeChat operations.
These projections demonstrate why local_id re-fetch cannot repair lost identity.
They do not determine the actual meaning of source/packed_info_data in WeChat.
"""
import io
import json
import sqlite3
import sys
import unittest


ATTEMPTS = []


def boundary(event, args):
    forbidden = event.startswith(('socket.', 'subprocess.', 'ctypes.'))
    forbidden |= event in ('os.system', 'os.startfile', 'os.posix_spawn')
    forbidden |= event == 'sqlite3.connect' and args[0] != ':memory:'
    if forbidden:
        ATTEMPTS.append(event)
        raise AssertionError('offline boundary: ' + event)


sys.addaudithook(boundary)


def raw_lookup(shards, local_id, local_type=None):
    """Own rule projection of db.py 1923-1965, without an upstream import."""
    rows = []
    for conn in shards:
        sql = 'SELECT * FROM msgs WHERE local_id=?'
        params = [local_id]
        if local_type is not None:
            sql += ' AND local_type=?'
            params.append(local_type)
        rows.extend(dict(row) for row in conn.execute(sql, params))
    rows.sort(key=lambda row: row['sort_seq'], reverse=True)
    return rows[0] if rows else None


class RawMetadataCounterexamples(unittest.TestCase):
    def shard(self, server, seq, label):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE msgs(local_id INTEGER, local_type INTEGER, '
                     'server_id INTEGER, sort_seq INTEGER, source TEXT, packed_info_data BLOB)')
        conn.execute('INSERT INTO msgs VALUES(1,1,?,?,?,?)',
                     (server, seq, label, label.encode()))
        return conn

    def test_newer_other_shard_replaces_original_metadata(self):
        original = self.shard(1001, 10, 'fictional-a')
        unrelated = self.shard(2001, 20, 'fictional-b')
        got = raw_lookup([original, unrelated], 1)
        self.assertEqual((got['server_id'], got['source'], got['packed_info_data']),
                         (2001, 'fictional-b', b'fictional-b'))
        self.assertNotEqual(got['server_id'], 1001)

    def test_type_filter_still_cannot_bind_same_type_collision(self):
        original = self.shard(1001, 10, 'fictional-a')
        unrelated = self.shard(2001, 20, 'fictional-b')
        self.assertEqual(raw_lookup([original, unrelated], 1, 1)['server_id'], 2001)

    def test_equal_seq_selection_depends_on_shard_iteration(self):
        a, b = self.shard(1001, 10, 'fictional-a'), self.shard(2001, 10, 'fictional-b')
        first = raw_lookup([a, b], 1, 1)
        reversed_order = raw_lookup([b, a], 1, 1)
        self.assertNotEqual(first['server_id'], reversed_order['server_id'])
        # A stable scan order still supplies no link to the original listener row.
        self.assertEqual({first['server_id'], reversed_order['server_id']}, {1001, 2001})


if __name__ == '__main__':
    log = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RawMetadataCounterexamples)
    cases = [test.id().split('.')[-1] for test in suite]
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    passed = result.wasSuccessful() and not ATTEMPTS
    print(json.dumps(dict(scope='synthetic memory SQLite rule projections only',
                          python=sys.version.split()[0], sqlite=sqlite3.sqlite_version,
                          tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                          cases=cases, boundary_attempts=ATTEMPTS, passed=passed, log=log.getvalue()), indent=2))
    raise SystemExit(0 if passed else 1)
