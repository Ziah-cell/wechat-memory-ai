from dataclasses import replace
from pathlib import Path
import json
import tempfile
import time
import unittest

from wechat_memory.adapters import Event, Identity, MockAdapter
from wechat_memory.audit import Audit
from wechat_memory.config import Config
from wechat_memory.engine import Engine
from wechat_memory.models import ModelError
from wechat_memory.store import Store


DECLARATION = '我平时喜欢喝热柠檬水。'


class CaptureModel:
    def __init__(self):
        self.calls = []
        self.response = '那下午就来一杯吧。'

    def complete(self, messages, cancel_check=None):
        self.calls.append(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class PreferenceEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = Config(peer_id='mock:owner', data_dir=self.root)
        self.store = Store(self.root)
        self.addCleanup(lambda: self.store.close())
        self.audit = Audit(self.root / 'logs')
        self.addCleanup(self.audit.close)
        self.adapter = MockAdapter(self.config.peer_id)
        self.model = CaptureModel()
        self.serial = 0
        self.make_engine()

    def make_engine(self):
        self.engine = Engine(self.config, self.store, self.adapter, self.model, self.audit)
        self.session = self.engine.session

    def event(self, text=DECLARATION, **changes):
        self.serial += 1
        values = dict(id=f'preference-{self.serial}', peer_id=self.config.peer_id,
                      conversation_id=self.config.peer_id, timestamp=time.time(), text=text)
        values.update(changes)
        return Event(**values)

    def usage(self):
        return self.store.guard.execute('SELECT COALESCE(SUM(calls),0) FROM usage').fetchone()[0]

    def test_declaration_is_grounded_in_same_single_reply_request(self):
        event = self.event()
        result = self.engine.process(event)
        self.assertEqual(result.status, 'dry_run')
        self.assertEqual(result.reply, self.model.response)
        self.assertEqual(self.adapter.sent, [])
        rows = self.store.memories(self.session)
        self.assertEqual([(r['key'], r['value']) for r in rows], [('饮品偏好', '热柠檬水')])
        self.assertEqual(rows[0]['source_ref'], self.engine.event_key(event))
        self.assertEqual(rows[0]['certainty'], 'explicit')
        self.assertEqual(len(self.model.calls), 1)
        context = self.model.calls[0]
        memory = next(m['content'] for m in context if m['content'].startswith('记忆数据 JSON：'))
        self.assertEqual(json.loads(memory.split('：', 1)[1])[0]['value'], '热柠檬水')
        self.assertEqual(context[-1], {'role': 'user', 'content': DECLARATION})
        self.assertEqual(sum(m['content'] == DECLARATION for m in context), 1)
        self.assertEqual(self.usage(), 1)

    def test_filtered_paused_and_identity_blocked_events_do_not_extract(self):
        for changes in (dict(is_self=True), dict(is_group=True), dict(kind='image'),
                        dict(peer_id='mock:other'), dict(conversation_id='mock:other'),
                        dict(timestamp=0)):
            with self.subTest(changes=changes):
                self.assertEqual(self.engine.process(self.event(**changes)).status, 'rejected')
        self.engine.paused = True
        self.assertEqual(self.engine.process(self.event()).status, 'paused')
        self.engine.paused = False
        self.adapter.select(Identity('mock:other', 'mock:other'))
        self.assertEqual(self.engine.process(self.event()).status, 'identity_blocked')
        self.assertEqual(self.store.memories(self.session), [])
        self.assertEqual(self.model.calls, [])
        self.assertEqual(self.usage(), 0)

    def test_budget_blocked_declaration_does_not_extract(self):
        self.config = replace(self.config, limits=replace(self.config.limits, daily_calls=1))
        self.make_engine()
        self.engine.process(self.event('你好。'))
        self.assertEqual(self.engine.process(self.event()).status, 'budget_blocked')
        self.assertEqual(self.store.memories(self.session), [])
        self.assertEqual(len(self.model.calls), 1)

    def test_ambiguous_aliases_clarify_without_model_or_budget(self):
        self.store.remember(self.session, '饮品偏好', '茶', 'preference', 'a')
        self.store.remember(self.session, '饮料偏好', '温乌龙茶', 'preference', 'b')
        before = self.store.memories(self.session)
        result = self.engine.process(self.event())
        self.assertEqual(result.status, 'dry_run')
        self.assertTrue(result.reply)
        self.assertEqual(self.store.memories(self.session), before)
        self.assertEqual(self.model.calls, [])
        self.assertEqual(self.usage(), 0)

    def test_full_memory_clarifies_without_model_or_budget(self):
        for n in range(100):
            self.store.remember(self.session, f'测试偏好{n}', '虚构值', 'preference', f's{n}')
        result = self.engine.process(self.event())
        self.assertEqual(result.status, 'dry_run')
        self.assertTrue(result.reply)
        self.assertEqual(len(self.store.memories(self.session)), 100)
        self.assertEqual(self.model.calls, [])
        self.assertEqual(self.usage(), 0)

    def test_duplicate_does_not_repeat_write_or_request(self):
        event = self.event()
        self.engine.process(event)
        before = self.store.memories(self.session)
        self.assertEqual(len(before), 1)
        self.assertEqual(self.engine.process(event).status, 'duplicate')
        self.assertEqual(self.store.memories(self.session), before)
        self.assertEqual(len(self.model.calls), 1)

    def test_model_failure_keeps_user_fact_and_never_retries(self):
        self.model.response = ModelError('timeout')
        result = self.engine.process(self.event())
        self.assertEqual(result.status, 'model_failed')
        self.assertEqual(result.reply, '')
        self.assertEqual(len(self.model.calls), 1)
        self.assertEqual([r['value'] for r in self.store.memories(self.session)], ['热柠檬水'])
        self.assertEqual(self.adapter.sent, [])

    def test_only_user_declaration_is_observed_not_model_output(self):
        self.model.response = DECLARATION
        self.engine.process(self.event('今天做点什么好？'))
        self.assertEqual(self.store.memories(self.session), [])
        self.engine.process(self.event('我喝咖啡不加糖。'))
        self.assertEqual([(r['key'], r['value']) for r in self.store.memories(self.session)],
                         [('咖啡加糖', '不加糖')])
        self.assertEqual(len(self.model.calls), 2)

    def test_natural_correction_forget_and_recall_are_local(self):
        self.config = replace(self.config, limits=replace(self.config.limits, daily_calls=1))
        self.make_engine()
        self.engine.process(self.event())
        self.assertEqual(len(self.store.memories(self.session)), 1)
        self.engine.process(self.event('我的饮品偏好改成温乌龙茶。'))
        self.assertEqual([r['value'] for r in self.store.memories(self.session)], ['温乌龙茶'])
        self.engine.process(self.event('忘记我的饮品偏好。'))
        result = self.engine.process(self.event('我平时最喜欢喝什么？'))
        self.assertEqual(result.reply, '这点我现在不太确定。')
        self.assertEqual(self.store.memories(self.session), [])
        self.assertEqual(len(self.model.calls), 1)
        self.assertEqual(self.usage(), 1)
        self.assertNotIn('热柠檬水', json.dumps(self.store.history(self.session), ensure_ascii=False))
        self.assertNotIn('温乌龙茶', json.dumps(self.store.history(self.session), ensure_ascii=False))
        self.assertEqual(self.store.summary(self.session), '')

    def test_reply_length_is_saved_without_replacing_the_natural_reply(self):
        result = self.engine.process(self.event('以后回复我简短一点。'))
        self.assertEqual(result.reply, self.model.response)
        self.assertEqual([(r['key'], r['value']) for r in self.store.memories(self.session)],
                         [('回复长度', '简短')])
        self.assertEqual(len(self.model.calls), 1)


if __name__ == '__main__':
    unittest.main()
