"""Durable receipt states and conservative call reservations, never restored backward."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import sqlite3
import time


class Operations:
    def __init__(self, store):
        self.db = store.guard
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS events (
                event_key TEXT PRIMARY KEY, session TEXT NOT NULL, status TEXT NOT NULL,
                updated_ns INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS usage (
                day TEXT PRIMARY KEY, calls INTEGER NOT NULL, estimate TEXT NOT NULL);
        ''')

    def recover(self):
        with self.db:
            self.db.execute("UPDATE events SET status='unknown' WHERE status='sending'")
            self.db.execute("UPDATE events SET status='interrupted' WHERE status IN ('processing','prepared')")

    def status(self, key):
        row = self.db.execute('SELECT status FROM events WHERE event_key=?', (key,)).fetchone()
        return row[0] if row else None

    def claim(self, key, session):
        with self.db:
            result = self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?)',
                                     (key, session, 'processing', time.time_ns()))
        return result.rowcount == 1

    def update(self, key, status):
        allowed = {'processing','prepared','sending','dry_run','simulated','model_failed','budget_blocked',
                   'identity_blocked','unknown','rejected','paused','stopped','interrupted'}
        if status not in allowed:
            raise ValueError('invalid_event_state')
        with self.db:
            self.db.execute('UPDATE events SET status=?,updated_ns=? WHERE event_key=?',
                            (status, time.time_ns(), key))

    def unresolved(self):
        return [dict(row) for row in self.db.execute("SELECT event_key,status FROM events WHERE status='unknown'")]

    def resolve(self, key, outcome):
        if outcome not in ('sent','not_sent'):
            raise ValueError('invalid_review_outcome')
        with self.db:
            changed = self.db.execute("UPDATE events SET status=? WHERE event_key=? AND status='unknown'",
                                      ('reviewed_'+outcome, key)).rowcount
        return changed == 1 # resolution never enqueues or re-sends the old message

    def reserve(self, limits):
        tz = timezone(timedelta(hours=8)) if limits.timezone == 'Asia/Shanghai' else timezone.utc
        day = datetime.now(tz).date().isoformat()
        with self.db:
            row = self.db.execute('SELECT calls,estimate FROM usage WHERE day=?', (day,)).fetchone()
            calls, amount = (row[0], Decimal(row[1])) if row else (0, Decimal('0'))
            if calls >= limits.daily_calls:
                return 'call_limit'
            if amount + limits.per_call_estimate > limits.daily_estimate:
                return 'cost_limit'
            # Retain this reservation even after timeout/failure; billing may already have occurred.
            self.db.execute('INSERT OR REPLACE INTO usage VALUES (?,?,?)',
                            (day, calls+1, str(amount + limits.per_call_estimate)))
        return ''
