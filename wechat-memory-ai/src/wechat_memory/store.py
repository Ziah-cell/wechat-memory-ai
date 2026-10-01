"""Bounded conversation content with an independent, replayable privacy journal."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import json
import secrets
import sqlite3
import time
import uuid


def digest(text):
    return sha256(text.encode('utf-8')).hexdigest()


def connect(path):
    con = sqlite3.connect(str(path), timeout=5)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA secure_delete=ON')
    con.execute('PRAGMA journal_mode=DELETE')
    con.execute('PRAGMA synchronous=FULL')
    return con


class Store:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if (self.root / 'state.sqlite3').exists() and not (self.root / 'guard.sqlite3').exists():
            raise ValueError('guard_missing: use the latest guard before opening existing content')
        self.db = connect(self.root / 'state.sqlite3')
        self.guard = connect(self.root / 'guard.sqlite3')
        self.closed = False
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY, session TEXT NOT NULL, key TEXT NOT NULL,
                keyhash TEXT NOT NULL, value TEXT NOT NULL, kind TEXT NOT NULL,
                certainty TEXT NOT NULL, status TEXT NOT NULL, source_ref TEXT NOT NULL,
                created_ns INTEGER NOT NULL, updated_ns INTEGER NOT NULL,
                UNIQUE(session,keyhash));
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY, session TEXT NOT NULL, source_ref TEXT NOT NULL,
                role TEXT NOT NULL, content TEXT NOT NULL, created_ns INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS turns_session ON turns(session,id);
            CREATE TABLE IF NOT EXISTS summaries (
                session TEXT PRIMARY KEY, content TEXT NOT NULL, sources TEXT NOT NULL);
        ''')
        self.guard.executescript('''
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS erasures (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL,
                keyhash TEXT, cutoff_ns INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS confirmations (
                session TEXT PRIMARY KEY, token_hash TEXT NOT NULL, expires REAL NOT NULL);
        ''')
        with self.guard:
            self.guard.execute("INSERT OR IGNORE INTO meta VALUES ('lineage', ?)", (uuid.uuid4().hex,))
            self.guard.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', '1')")
        self.lineage = self.guard.execute("SELECT value FROM meta WHERE key='lineage'").fetchone()[0]
        existing = self.db.execute("SELECT value FROM meta WHERE key='lineage'").fetchone()
        if existing and existing[0] != self.lineage:
            self.close()
            raise ValueError('guard_lineage_mismatch')
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO meta VALUES ('lineage', ?)", (self.lineage,))
            self.db.execute("INSERT OR IGNORE INTO meta VALUES ('applied_seq', '0')")
            self.db.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', '1')")
        maximum = max(self.db.execute('SELECT COALESCE(MAX(updated_ns),0) FROM memories').fetchone()[0],
                      self.db.execute('SELECT COALESCE(MAX(created_ns),0) FROM turns').fetchone()[0],
                      self.guard.execute('SELECT COALESCE(MAX(cutoff_ns),0) FROM erasures').fetchone()[0])
        with self.guard:
            self.guard.execute("INSERT OR IGNORE INTO meta VALUES ('clock', ?)", (str(maximum),))
        self.sync_privacy()

    def close(self):
        if not self.closed:
            self.db.close()
            self.guard.close()
            self.closed = True

    def privacy_seq(self):
        return self.guard.execute('SELECT COALESCE(MAX(seq),0) FROM erasures').fetchone()[0]

    def tick(self):
        # One durable ordering for both content and erasures; wall-clock rollback is harmless.
        with self.guard:
            last = int(self.guard.execute("SELECT value FROM meta WHERE key='clock'").fetchone()[0])
            stamp = max(time.time_ns(), last + 1)
            self.guard.execute("UPDATE meta SET value=? WHERE key='clock'", (str(stamp),))
        return stamp

    def record_erasure(self, session, keyhash):
        cutoff = self.tick()
        with self.guard:
            self.guard.execute('INSERT INTO erasures(session,keyhash,cutoff_ns) VALUES (?,?,?)',
                               (session, keyhash, cutoff))
        return cutoff

    def sync_privacy(self):
        applied = int(self.db.execute("SELECT value FROM meta WHERE key='applied_seq'").fetchone()[0])
        if applied > self.privacy_seq():
            raise ValueError('guard_older_than_content')
        rows = self.guard.execute('SELECT * FROM erasures WHERE seq>? ORDER BY seq', (applied,)).fetchall()
        with self.db:
            for row in rows:
                if row['keyhash'] is None:
                    self.db.execute('DELETE FROM memories WHERE session=? AND updated_ns<=?',
                                    (row['session'], row['cutoff_ns']))
                else:
                    self.db.execute('DELETE FROM memories WHERE session=? AND keyhash=? AND updated_ns<=?',
                                    (row['session'], row['keyhash'], row['cutoff_ns']))
                # Conservative purge avoids facts echoed by an assistant or an old summary.
                self.db.execute('DELETE FROM turns WHERE session=? AND created_ns<=?',
                                (row['session'], row['cutoff_ns']))
                self.db.execute('DELETE FROM summaries WHERE session=?', (row['session'],))
                self.db.execute("UPDATE meta SET value=? WHERE key='applied_seq'", (str(row['seq']),))

    def memories(self, session):
        self.sync_privacy()
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM memories WHERE session=? AND status='active' ORDER BY created_ns,id", (session,))]

    def remember(self, session, key, value, kind, source_ref):
        if kind not in ('preference', 'event') or not key.strip() or len(key) > 40 or not value.strip() or len(value) > 500:
            raise ValueError('invalid_memory')
        rows = self.memories(session)
        previous = next((r for r in rows if r['key'] == key), None)
        if not previous and len(rows) >= 100:
            raise ValueError('memory_limit')
        now = self.tick()
        ident = previous['id'] if previous else uuid.uuid4().hex[:12]
        created = previous['created_ns'] if previous else now
        if previous:
            self.record_erasure(session, digest(key))
            self.sync_privacy()
            now = self.tick()
        with self.db:
            self.db.execute('''INSERT OR REPLACE INTO memories
                (id,session,key,keyhash,value,kind,certainty,status,source_ref,created_ns,updated_ns)
                VALUES (?,?,?,?,?,?,'explicit','active',?,?,?)''',
                (ident, session, key, digest(key), value, kind, source_ref, created, now))
        return next(r for r in self.memories(session) if r['id'] == ident)

    def forget(self, session, ident):
        row = next((r for r in self.memories(session) if r['id'] == ident), None)
        if not row:
            return False
        self.record_erasure(session, row['keyhash'])
        self.sync_privacy()
        return True

    def issue_clear_token(self, session, ttl=60):
        token = secrets.token_hex(4)
        with self.guard:
            self.guard.execute('INSERT OR REPLACE INTO confirmations VALUES (?,?,?)',
                               (session, digest(token), time.time() + ttl))
        return token

    def confirm_clear(self, session, token):
        row = self.guard.execute('SELECT * FROM confirmations WHERE session=?', (session,)).fetchone()
        if not row or row['expires'] < time.time() or not secrets.compare_digest(row['token_hash'], digest(token)):
            return False
        # Erasure is durable first; even a crash after this line will purge on next open.
        self.record_erasure(session, None)
        with self.guard:
            self.guard.execute('DELETE FROM confirmations WHERE session=?', (session,))
        self.sync_privacy()
        return True

    def add_turn(self, session, source_ref, role, content):
        if role not in ('user', 'assistant'):
            raise ValueError('invalid_role')
        with self.db:
            self.db.execute('INSERT INTO turns(session,source_ref,role,content,created_ns) VALUES (?,?,?,?,?)',
                            (session, source_ref, role, content, self.tick()))

    def history(self, session):
        self.sync_privacy()
        return [dict(r) for r in self.db.execute('SELECT * FROM turns WHERE session=? ORDER BY id', (session,))]

    def summary(self, session):
        self.sync_privacy()
        row = self.db.execute('SELECT content FROM summaries WHERE session=?', (session,)).fetchone()
        return row[0] if row else ''

    def summary_sources(self, session):
        row = self.db.execute('SELECT sources FROM summaries WHERE session=?', (session,)).fetchone()
        return json.loads(row[0]) if row else []

    def compact(self, session, keep, summary_chars):
        rows = self.history(session)
        old = rows[:-keep] if keep else rows
        if not old:
            return
        snippets = [self.summary(session)] + [f"[{r['role']}:{r['source_ref'][:12]}] {r['content'][:160]}" for r in old]
        content = '\n'.join(snippets)[-summary_chars:]
        sources = (self.summary_sources(session) + [r['source_ref'] for r in old])[-32:]
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO summaries VALUES (?,?,?)',
                            (session, content, json.dumps(sources)))
            self.db.execute('DELETE FROM turns WHERE session=? AND id<=?', (session, old[-1]['id']))

    def retrieve(self, session, query, limit=12):
        def grams(text):
            text = text.casefold()
            return {text[i:i+2] for i in range(max(0, len(text)-1))}
        q = grams(query)
        scored = []
        for row in self.memories(session):
            score = len(q & grams(row['key'] + row['value']))
            if row['kind'] == 'preference':
                score += 100
            if score:
                scored.append((score, row['updated_ns'], row))
        return [r for _, _, r in sorted(scored, key=lambda v: (v[0], v[1]), reverse=True)[:limit]]
