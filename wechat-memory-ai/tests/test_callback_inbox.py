"""Synthetic callback transport: no WeChat, network or personal configuration."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
from threading import get_ident
import time
import unittest
from unittest.mock import patch

from wechat_memory.adapters import Event, MockAdapter
from wechat_memory.audit import Audit
from wechat_memory.callback_inbox import CallbackInbox
from wechat_memory.config import Config
from wechat_memory.engine import Engine
from wechat_memory.models import FakeModel
from wechat_memory.offline_check import run_check
from wechat_memory.store import Store


def event(number=1, **changes):
    values = dict(id=f'fixture-{number}', peer_id='mock:owner', conversation_id='mock:owner',
                  text='虚构重复文本', timestamp=time.time())
    values.update(changes)
    return Event(**values)


class InboxTests(unittest.TestCase):
    def test_callbacks_only_enqueue_then_owner_consumes_fifo_without_coalescing(self):
        inbox = CallbackInbox(capacity=4)
        callback = inbox.begin()
        first, second = event(1), event(2)
        with ThreadPoolExecutor(max_workers=1) as pool:
            self.assertEqual(pool.submit(callback, first).result(), 'queued')
            self.assertEqual(pool.submit(callback, second).result(), 'queued')
            self.assertEqual(pool.submit(callback, first).result(), 'queued')
        consumed = []
        inbox.consume(lambda item: consumed.append(item.id))
        self.assertEqual(consumed, [first.id, second.id, first.id])
        self.assertEqual(inbox.status(), {'state': 'accepting', 'pending': 0})

    def test_many_producers_only_owner_runs_consumer(self):
        inbox = CallbackInbox(capacity=128)
        callback, owner = inbox.begin(), get_ident()
        def produce(group):
            return [callback(event(f'{group}-{i}')) for i in range(20)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(produce, range(4)))
        self.assertEqual(results, [['queued']*20]*4)
        consumed = []
        inbox.consume(lambda item: consumed.append((get_ident(), item.id)))
        self.assertEqual(len(consumed), 80)
        self.assertTrue(all(tid == owner for tid, _ in consumed))
        for group in range(4):
            self.assertEqual([ident for _, ident in consumed if ident.startswith(f'fixture-{group}-')],
                             [f'fixture-{group}-{i}' for i in range(20)])

    def test_switch_pause_disconnect_and_restart_invalidate_old_callbacks(self):
        for reason in ('paused', 'window_changed', 'disconnected'):
            inbox = CallbackInbox()
            old = inbox.begin()
            old(event())
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(inbox.suspend, reason).result()
            seen = []
            self.assertEqual(inbox.consume(seen.append), 0)
            new = inbox.begin()
            self.assertEqual(old(event(2)), 'stale_callback')
            self.assertEqual(new(event(3)), 'queued')
            inbox.consume(seen.append)
            self.assertEqual([item.id for item in seen], ['fixture-3'])

    def test_overflow_clears_backlog_and_requires_explicit_new_subscription(self):
        inbox = CallbackInbox(capacity=1)
        old = inbox.begin()
        self.assertEqual(old(event(1)), 'queued')
        self.assertEqual(old(event(2)), 'overflow')
        self.assertEqual(inbox.status(), {'state': 'overflow', 'pending': 0})
        self.assertEqual(old(event(3)), 'stale_callback')
        self.assertEqual(inbox.consume(lambda _: self.fail('must not consume')), 0)
        self.assertEqual(inbox.begin()(event(4)), 'queued')

    def test_close_is_terminal_and_discards_backlog(self):
        inbox = CallbackInbox()
        callback = inbox.begin()
        callback(event())
        inbox.close()
        inbox.suspend('paused')
        self.assertEqual(inbox.status(), {'state': 'closed', 'pending': 0})
        self.assertEqual(callback(event()), 'stale_callback')
        with self.assertRaisesRegex(RuntimeError, '^inbox_closed$'):
            inbox.begin()

    def test_begin_consume_and_invalid_arguments_cannot_corrupt_owner_state(self):
        inbox = CallbackInbox()
        callback = inbox.begin()
        callback(event())
        with ThreadPoolExecutor(max_workers=1) as pool:
            for operation in (inbox.begin, lambda: inbox.consume(lambda _: None)):
                with self.assertRaisesRegex(RuntimeError, '^owner_thread_required$'):
                    pool.submit(operation).result()
        self.assertEqual(inbox.status()['pending'], 1)
        for value in (0, -1, True, 1025):
            with self.assertRaises(ValueError):
                CallbackInbox(capacity=value)
        with self.assertRaises(ValueError):
            inbox.suspend('PRIVATE-EXCEPTION')

    def test_bad_or_oversized_events_are_not_retained_or_logged(self):
        inbox = CallbackInbox()
        callback = inbox.begin()
        for item in (None, {'text': 'PRIVATE'}, event(text='x'*10001),
                     event(id=[]), event(timestamp=10**400), event(is_self=1)):
            self.assertEqual(callback(item), 'invalid_event')
        self.assertEqual(inbox.status()['pending'], 0)
        self.assertNotIn('PRIVATE', repr(inbox))

    def test_consumer_can_invalidate_without_deadlock_and_failure_stops_backlog(self):
        inbox = CallbackInbox()
        callback = inbox.begin()
        callback(event(1)); callback(event(2))
        self.assertEqual(inbox.consume(lambda _: inbox.suspend('window_changed')), 1)
        callback = inbox.begin()
        callback(event(3)); callback(event(4))
        def fail(_):
            raise ValueError('PRIVATE')
        with self.assertRaisesRegex(RuntimeError, '^consumer_failed$'):
            inbox.consume(fail)
        self.assertEqual(inbox.status(), {'state': 'consumer_failed', 'pending': 0})
        self.assertEqual(callback(event(5)), 'stale_callback')

    def test_consume_does_not_cross_subscription_generation_and_honors_limit(self):
        inbox = CallbackInbox()
        callback = inbox.begin()
        callback(event(1))
        seen = []
        def replace_subscription(item):
            seen.append(item.id)
            new = inbox.begin()
            new(event(2))
            new(event(3))
        self.assertEqual(inbox.consume(replace_subscription, limit=2), 1)
        self.assertEqual(seen, ['fixture-1'])
        self.assertEqual(inbox.consume(lambda item: seen.append(item.id), limit=1), 1)
        self.assertEqual(inbox.status()['pending'], 1)
        self.assertEqual(seen, ['fixture-1', 'fixture-2'])

    def test_callback_to_real_sqlite_engine_stays_on_owner_and_dedup_is_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config(peer_id='mock:owner', data_dir=Path(directory))
            store, audit = Store(config.data_dir), Audit(config.data_dir/'logs')
            inbox, adapter = CallbackInbox(), MockAdapter(config.peer_id)
            try:
                engine = Engine(config, store, adapter, FakeModel(), audit)
                items = [event(1), event(2), event(1), event(3, is_self=True), event(4, timestamp=0)]
                callback = inbox.begin()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    self.assertEqual(list(pool.map(callback, items)), ['queued']*5)
                self.assertEqual(store.history(engine.session), [])
                results = []
                inbox.consume(lambda item: results.append(engine.process(item).status))
                self.assertEqual(results, ['dry_run', 'dry_run', 'duplicate', 'rejected', 'rejected'])
                self.assertEqual(adapter.sent, [])
                store.close()
                store = Store(config.data_dir)
                engine = Engine(config, store, adapter, FakeModel(), audit)
                self.assertEqual(engine.process(items[0]).status, 'duplicate')
            finally:
                inbox.close(); audit.close(); store.close()


class OfflineCheckTests(unittest.TestCase):
    def test_report_is_offline_sanitized_and_temp_data_removed(self):
        with tempfile.TemporaryDirectory() as parent:
            with patch('wechat_memory.offline_check.tempfile.tempdir', parent):
                report = run_check()
            self.assertEqual(list(Path(parent).iterdir()), [])
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['source'], 'synthetic_callbacks')
        self.assertFalse(report['network_enabled'])
        self.assertFalse(report['real_wechat_verified'])
        self.assertFalse(report['real_send_supported'])
        self.assertTrue(all(report['checks'].values()))
        self.assertNotIn('虚构重复文本', json.dumps(report, ensure_ascii=False))

    def test_failure_report_does_not_expose_exception_text(self):
        with patch('wechat_memory.offline_check.Store', side_effect=OSError('SECRET')):
            report = run_check()
        self.assertEqual(report['status'], 'failed')
        self.assertNotIn('SECRET', json.dumps(report))
