"""Fictional durable inbox, NOT a message sender or an adapter for real WeChat.

Atomicity covers inbox rows, sequence cursor and STOP in ONE SQLite database.
The native publisher never calls this module or waits for this process.
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / 'AGENTS.md').exists() and (p / 'docs/experiments').is_dir())
CACHE = ROOT / 'data/target-lifetime-20261012'


class Rejected(Exception):
    pass


def epoch_value(epoch):
    if not isinstance(epoch, str) or re.fullmatch('[0-9a-f]{32}', epoch) is None:
        raise Rejected('invalid_epoch')


def batch_value(records):
    if not isinstance(records, list) or not 1 <= len(records) <= 8:
        raise Rejected('invalid_batch')
    previous = 0
    result = []
    for record in records:
        if not isinstance(record, dict) or set(record) != {'seq', 'generation', 'id', 'a', 'b', 'c'}:
            raise Rejected('invalid_batch')
        if any(type(v) is not int or not 0 <= v < 2**63 for v in record.values()):
            raise Rejected('invalid_batch')
        seq, ident = record['seq'], record['id']
        if not previous < seq < 2**62 or not 1 <= ident <= 1000000:
            raise Rejected('invalid_batch')
        if record['generation'] != (seq - 1) // 8 + 1:
            raise Rejected('invalid_generation')
        if (record['a'], record['b'], record['c']) != (ident ^ 0xa5a5a5a5, ident + 7, ident * 3):
            raise Rejected('invalid_batch')
        previous = seq
        result.append((seq, json.dumps(record, sort_keys=True, separators=(',', ':'))))
    return result


class Ledger:
    def __init__(self, database):
        path = Path(database).resolve()
        if not path.is_relative_to(CACHE.resolve()) or path.name != 'ledger.sqlite3':
            raise Rejected('fixture_path_only')
        # Fixed tested runtime is 3.53.1. Do not use versions with the WAL-reset bug.
        if sqlite3.sqlite_version_info < (3, 51, 3):
            raise Rejected('sqlite_version')
        path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not path.exists()
        self.db = sqlite3.connect(path, timeout=0, isolation_level=None)
        try:
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.execute('PRAGMA synchronous=FULL')
            if fresh:
                self.db.execute('PRAGMA journal_mode=WAL')
                self.db.executescript('''
                    BEGIN IMMEDIATE;
                    CREATE TABLE fixture_padding(data BLOB);
                    CREATE TABLE sessions(epoch TEXT PRIMARY KEY, state TEXT NOT NULL,
                                          last_seq INTEGER NOT NULL, stop_op INTEGER);
                    CREATE TABLE control(id INTEGER PRIMARY KEY CHECK(id=1), epoch TEXT);
                    INSERT INTO control VALUES(1, NULL);
                    CREATE TABLE operations(id INTEGER PRIMARY KEY AUTOINCREMENT,
                                            kind TEXT NOT NULL, epoch TEXT NOT NULL);
                    CREATE TABLE inbox(epoch TEXT NOT NULL REFERENCES sessions(epoch),
                                       seq INTEGER NOT NULL, payload TEXT NOT NULL,
                                       commit_op INTEGER NOT NULL REFERENCES operations(id),
                                       PRIMARY KEY(epoch,seq));
                    PRAGMA user_version=1;
                    COMMIT;
                ''')
            if self.db.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise Rejected('schema')
            if self.db.execute('PRAGMA journal_mode').fetchone()[0] != 'wal':
                raise Rejected('journal_mode')
        except BaseException:
            self.db.close()
            raise

    def transaction(self, action, checkpoint=None):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            result = action()
            if checkpoint:
                checkpoint('before_commit')
            self.db.execute('COMMIT')
        except BaseException:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise
        # A crash here loses the ACK, but cannot roll back the completed commit.
        if checkpoint:
            checkpoint('after_commit')
        return result

    def operation(self, kind, epoch):
        return self.db.execute('INSERT INTO operations(kind,epoch) VALUES(?,?)',
                               (kind, epoch)).lastrowid

    def begin(self, epoch):
        epoch_value(epoch)

        def work():
            if self.db.execute('SELECT 1 FROM sessions WHERE epoch=?', (epoch,)).fetchone():
                raise Rejected('epoch_used')
            if self.db.execute('SELECT epoch FROM control WHERE id=1').fetchone()[0] is not None:
                raise Rejected('active_epoch')
            self.db.execute('INSERT INTO sessions VALUES(?,"active",0,NULL)', (epoch,))
            self.db.execute('UPDATE control SET epoch=? WHERE id=1', (epoch,))
            return dict(epoch=epoch, begin_op=self.operation('begin', epoch))

        return self.transaction(work)

    def accept(self, epoch, records, checkpoint=None):
        epoch_value(epoch)
        batch = batch_value(records)

        def work():
            row = self.db.execute('SELECT state,last_seq FROM sessions WHERE epoch=?', (epoch,)).fetchone()
            current = self.db.execute('SELECT epoch FROM control WHERE id=1').fetchone()[0]
            if row is None or row[0] != 'active' or current != epoch:
                raise Rejected('closed')
            last, added, duplicates, commit_op = row[1], 0, 0, None
            if getattr(self, 'limited', False):
                self.db.execute('INSERT INTO fixture_padding VALUES(zeroblob(1048576))')
            for seq, payload in batch:
                existing = self.db.execute('SELECT payload FROM inbox WHERE epoch=? AND seq=?',
                                           (epoch, seq)).fetchone()
                if existing:
                    if existing[0] != payload:
                        raise Rejected('conflict')
                    duplicates += 1
                    continue
                if seq != last + 1:
                    raise Rejected('gap')
                if commit_op is None:
                    commit_op = self.operation('accept', epoch)
                self.db.execute('INSERT INTO inbox VALUES(?,?,?,?)', (epoch, seq, payload, commit_op))
                added += 1
                last = seq
            self.db.execute('UPDATE sessions SET last_seq=? WHERE epoch=?', (last, epoch))
            return dict(added=added, duplicates=duplicates, last_seq=last, commit_op=commit_op)

        result = self.transaction(work, checkpoint)
        seq = batch[-1][0]
        result['ack'] = dict(epoch=epoch, seq=seq, generation=(seq-1)//8+1)
        return result

    def stop(self, epoch, checkpoint=None):
        epoch_value(epoch)

        def work():
            row = self.db.execute('SELECT state,stop_op FROM sessions WHERE epoch=?', (epoch,)).fetchone()
            if row is None:
                raise Rejected('unknown_epoch')
            if row[0] == 'closed':
                return dict(stop_op=row[1])
            marker = self.operation('stop', epoch)
            self.db.execute('UPDATE sessions SET state="closed",stop_op=? WHERE epoch=?', (marker, epoch))
            self.db.execute('UPDATE control SET epoch=NULL WHERE id=1 AND epoch=?', (epoch,))
            return dict(stop_op=marker)

        return self.transaction(work, checkpoint)

    def snapshot(self):
        self.db.execute('BEGIN')
        try:
            sessions = [dict(zip(('epoch', 'state', 'last_seq', 'stop_op'), row))
                        for row in self.db.execute('SELECT * FROM sessions ORDER BY epoch')]
            records = [dict(epoch=e, seq=s, payload=json.loads(p), commit_op=c)
                       for e,s,p,c in self.db.execute('SELECT * FROM inbox ORDER BY epoch,seq')]
            operations = [dict(zip(('id', 'kind', 'epoch'), row))
                          for row in self.db.execute('SELECT * FROM operations ORDER BY id')]
            integrity = self.db.execute('PRAGMA integrity_check').fetchone()[0]
            return dict(sessions=sessions, records=records, operations=operations, integrity=integrity)
        finally:
            self.db.execute('ROLLBACK')


def emit(value):
    print(json.dumps(value, separators=(',', ':')), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True, type=Path)
    args = parser.parse_args()
    try:
        ledger = Ledger(args.database)
    except (Rejected, sqlite3.Error) as exc:
        emit(dict(event='error', reason=str(exc)))
        return 1
    emit(dict(event='ready', sqlite=sqlite3.sqlite_version, journal_mode='wal',
              synchronous=ledger.db.execute('PRAGMA synchronous').fetchone()[0]))
    try:
        for line in sys.stdin:
            if line.strip() == 'quit':
                break
            try:
                req = json.loads(line)
                if not isinstance(req, dict):
                    raise Rejected('protocol')
                requested = req.get('checkpoint')
                if requested not in (None, 'before_commit', 'after_commit'):
                    raise Rejected('checkpoint')

                def checkpoint(stage):
                    if requested == stage:
                        emit(dict(event='checkpoint', stage=stage))
                        if sys.stdin.readline().strip() != 'resume':
                            raise Rejected('checkpoint_cancelled')

                op = req['op']
                if op == 'begin':
                    result = ledger.begin(req['epoch'])
                elif op == 'accept':
                    result = ledger.accept(req['epoch'], req['records'], checkpoint)
                elif op == 'stop':
                    result = ledger.stop(req['epoch'], checkpoint)
                elif op == 'limit_pages':
                    pages = ledger.db.execute('PRAGMA page_count').fetchone()[0]
                    ledger.db.execute(f'PRAGMA max_page_count={pages}')
                    ledger.limited = True
                    result = dict(pages=pages)
                elif op == 'unlimit_pages':
                    ledger.db.execute('PRAGMA max_page_count=1073741823')
                    ledger.limited = False
                    result = {}
                elif op == 'snapshot':
                    result = ledger.snapshot()
                else:
                    raise Rejected('operation')
                emit(dict(event='result', ok=True, **result))
            except Rejected as exc:
                emit(dict(event='result', ok=False, reason=str(exc)))
            except sqlite3.Error as exc:
                code = getattr(exc, 'sqlite_errorcode', 0)
                reason = 'busy' if code & 255 in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) else 'storage_error'
                emit(dict(event='result', ok=False, reason=reason, sqlite_code=code))
            except (KeyError, TypeError, ValueError) as exc:
                emit(dict(event='result', ok=False, reason='protocol', kind=type(exc).__name__))
    finally:
        ledger.db.close()
    emit(dict(event='bye'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
