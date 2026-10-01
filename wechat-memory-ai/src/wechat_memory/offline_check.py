"""Repeatable synthetic callback rehearsal, with temporary data and a fake model."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
import json
import tempfile
import time

from .adapters import Event, MockAdapter
from .audit import Audit
from .callback_inbox import CallbackInbox
from .config import Config
from .engine import Engine
from .models import FakeModel
from .store import Store


def run_check():
    report = dict(status='failed', source='synthetic_callbacks', network_enabled=False,
                  real_wechat_verified=False, real_send_supported=False, checks={})
    checks = report['checks']
    try:
        with tempfile.TemporaryDirectory(prefix='wechat-offline-check-') as directory, ExitStack() as stack:
            config = Config(peer_id='mock:offline-check', data_dir=Path(directory))
            store = Store(config.data_dir)
            stack.callback(store.close)
            audit = Audit(config.data_dir/'logs')
            stack.callback(audit.close)
            adapter = MockAdapter(config.peer_id)
            engine = Engine(config, store, adapter, FakeModel(), audit)
            inbox = CallbackInbox(capacity=8)
            stack.callback(inbox.close)
            def make(ident, **changes):
                values = dict(id=ident, peer_id=config.peer_id, conversation_id=config.peer_id,
                              text='虚构重复文本', timestamp=time.time())
                values.update(changes)
                return Event(**values)
            first, second = make('fixture-1'), make('fixture-2')
            items = [first, second, first, make('self', is_self=True), make('history', timestamp=0),
                     make('stranger', peer_id='mock:stranger', display_name='虚构同名')]
            callback = inbox.begin()
            with ThreadPoolExecutor(max_workers=1) as pool:
                queued = list(pool.map(callback, items))
            checks['callbacks_enqueue_without_processing'] = (
                queued == ['queued']*len(items) and not store.history(engine.session))
            outcomes = []
            inbox.consume(lambda event: outcomes.append(engine.process(event).status))
            checks['same_text_with_distinct_ids_preserved'] = outcomes[:2] == ['dry_run', 'dry_run']
            checks['duplicate_filtered'] = outcomes[2] == 'duplicate'
            checks['self_history_other_peer_filtered'] = outcomes[3:] == ['rejected']*3
            checks['no_sends'] = not adapter.sent
            store.close()
            store = Store(config.data_dir)
            stack.callback(store.close)
            engine = Engine(config, store, adapter, FakeModel(), audit)
            checks['restart_dedup'] = engine.process(first).status == 'duplicate'
            callback(make('discarded'))
            inbox.suspend('window_changed')
            inbox.begin()
            checks['old_callback_revoked'] = callback(make('stale')) == 'stale_callback'
            checks['old_backlog_discarded'] = inbox.consume(lambda _: None) == 0
            callback = inbox.begin()
            for index in range(8):
                callback(make(f'overflow-{index}'))
            checks['overflow_stops_and_discards'] = (
                callback(make('overflow-trigger')) == 'overflow'
                and inbox.status() == {'state': 'overflow', 'pending': 0})
            inbox.close()
            checks['closed_callbacks_rejected'] = callback(make('after-close')) == 'stale_callback'
        # Temporary content, guard database and logs have been removed here.
        report['status'] = 'passed' if checks and all(checks.values()) else 'failed'
    except Exception:
        # No external exceptions, content, paths or credentials enter the report.
        report['status'] = 'failed'
    return report


def main():
    report = run_check()
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
