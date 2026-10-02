from pathlib import Path
import tempfile
import time
import unittest

from wechat_memory.adapters import Event, MockAdapter
from wechat_memory.audit import Audit
from wechat_memory.config import Config
from wechat_memory.engine import Engine
from wechat_memory.memory import MemoryService
from wechat_memory.store import Store


RECALL = '我平时最喜欢喝什么？'
STATUS = '刚才那条饮品偏好你还记着吗？说清楚是否已经删除。'


class CountingModel:
    def __init__(self):
        self.calls = []

    def complete(self, messages, cancel_check=None):
        self.calls.append(messages)
        return '这是离线推荐样例。'


class MemoryRecallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = Config(peer_id='mock:recall', data_dir=self.root)
        self.store = Store(self.root)
        self.addCleanup(lambda: self.store.close())
        self.audit = Audit(self.root / 'logs')
        self.addCleanup(self.audit.close)
        self.adapter = MockAdapter(self.config.peer_id)
        self.model = CountingModel()
        self.serial = 0
        self.make_engine()

    def make_engine(self):
        self.memory = MemoryService(self.store)
        self.engine = Engine(self.config, self.store, self.adapter, self.model, self.audit)
        self.session = self.engine.session

    def reopen(self):
        self.store.close()
        self.store = Store(self.root)
        self.make_engine()

    def process(self, text):
        self.serial += 1
        result = self.engine.process(Event(
            id=f'recall-{self.serial}', peer_id=self.config.peer_id,
            conversation_id=self.config.peer_id, text=text, timestamp=time.time()))
        self.assertEqual(result.status, 'dry_run')
        self.assertEqual(self.adapter.sent, [])
        return result.reply

    def test_original_unknown_recall_and_status_never_call_model(self):
        self.assertEqual(self.process(RECALL), '这点我现在不太确定。')
        self.assertEqual(self.process(STATUS), '目前没有保存这项饮品偏好。')
        self.assertEqual(self.model.calls, [])
        self.assertEqual(self.store.memories(self.session), [])

    def test_assistant_history_and_summary_do_not_become_preference(self):
        self.store.add_turn(self.session, 'invented-1', 'assistant', '你之前提过喜欢喝冰美式。')
        self.store.compact(self.session, 0, 700)
        self.store.add_turn(self.session, 'invented-2', 'assistant', '你最爱喝冰美式。')
        self.assertEqual(self.process(RECALL), '这点我现在不太确定。')
        self.assertEqual(self.model.calls, [])
        self.assertEqual(self.store.memories(self.session), [])

    def test_single_explicit_preference_uses_value_without_claiming_favorite(self):
        for n, key in enumerate(('饮品偏好', '饮料偏好', '饮品喜好', '饮料喜好')):
            session = f'alias-{n}'
            self.store.remember(session, key, '热柠檬水', 'preference', 'explicit-source')
            reply = self.memory.handle(session, RECALL, 'query')
            self.assertEqual(reply, '你说过的饮品偏好是：热柠檬水。')
        self.store.remember(self.session, '饮品偏好', '热柠檬水', 'preference', 'explicit-source')
        self.assertEqual(self.process(STATUS), '目前保存的饮品偏好是：热柠檬水。')
        self.assertEqual(self.model.calls, [])

    def test_unrelated_event_inactive_or_nonexplicit_records_do_not_answer(self):
        self.store.remember(self.session, '兴趣', '画画', 'preference', 's1')
        self.store.remember(self.session, '饮品偏好', '热柠檬水', 'event', 's2')
        inactive = self.store.remember(self.session, '饮料偏好', '温乌龙茶', 'preference', 's3')
        inferred = self.store.remember(self.session, '饮品喜好', '冰美式', 'preference', 's4')
        with self.store.db:
            self.store.db.execute("UPDATE memories SET status='inactive' WHERE id=?", (inactive['id'],))
            self.store.db.execute("UPDATE memories SET certainty='inferred' WHERE id=?", (inferred['id'],))
        self.assertEqual(self.process(RECALL), '这点我现在不太确定。')
        self.assertEqual(self.process(STATUS), '目前没有保存这项饮品偏好。')
        self.assertEqual(self.model.calls, [])

    def test_multiple_related_records_do_not_choose_or_merge_values(self):
        self.store.remember(self.session, '饮品偏好', '热柠檬水', 'preference', 's1')
        self.store.remember(self.session, '饮料偏好', '温乌龙茶', 'preference', 's2')
        for text in (RECALL, STATUS):
            reply = self.process(text)
            self.assertEqual(reply, '保存了多条饮品偏好，我不能确定你指的是哪一条。')
        self.assertEqual(self.model.calls, [])

    def test_status_reports_current_record_without_assuming_deleted_referent(self):
        deleted = self.store.remember(self.session, '饮品偏好', '热柠檬水', 'preference', 's1')
        self.store.remember(self.session, '饮料偏好', '温乌龙茶', 'preference', 's2')
        self.store.forget(self.session, deleted['id'])
        self.assertEqual(self.process(STATUS), '目前保存的饮品偏好是：温乌龙茶。')
        self.assertEqual(self.model.calls, [])

    def test_correction_uses_only_new_value_before_and_after_restart(self):
        self.process('/记住 preference 饮品偏好=热柠檬水')
        row = self.store.memories(self.session)[0]
        self.process('/纠正 ' + row['id'] + '=温乌龙茶')
        self.assertEqual(self.process(RECALL), '你说过的饮品偏好是：温乌龙茶。')
        self.reopen()
        self.assertEqual(self.process(RECALL), '你说过的饮品偏好是：温乌龙茶。')
        self.assertNotIn('热柠檬水', self.store.summary(self.session))
        self.assertEqual(self.model.calls, [])

    def test_forgetting_stays_unknown_after_restart_without_claiming_deletion(self):
        self.process('/记住 preference 饮品偏好=热柠檬水')
        row = self.store.memories(self.session)[0]
        self.process('/忘记 ' + row['id'])
        for restart in (False, True):
            if restart:
                self.reopen()
            self.assertEqual(self.process(RECALL), '这点我现在不太确定。')
            self.assertEqual(self.process(STATUS), '目前没有保存这项饮品偏好。')
            self.assertEqual(self.store.memories(self.session), [])
        self.assertEqual(self.model.calls, [])

    def test_recommendations_continue_to_model(self):
        self.store.remember(self.session, '饮品偏好', '热柠檬水', 'preference', 's1')
        for text in ('下午想喝点东西，帮我挑一杯吧。', '照我的口味，下午喝点什么好？',
                     '我喜欢喝什么样的饮料比较好？', '你记得我的饮品偏好吗？顺便推荐一家店。'):
            with self.subTest(text=text):
                before = len(self.model.calls)
                self.assertIsNone(self.memory.handle(self.session, text, 'query'))
                self.assertEqual(self.process(text), '这是离线推荐样例。')
                self.assertEqual(len(self.model.calls), before + 1)

    def test_other_topics_quotes_and_hypotheticals_are_not_swallowed(self):
        for text in ('我最喜欢哪本书？', '请翻译“我平时最喜欢喝什么？”',
                     '假如我问你喜欢喝什么，你会怎么回答？',
                     '我平时最喜欢喝什么？解释一下这句话的语法。'):
            with self.subTest(text=text):
                self.assertIsNone(self.memory.handle(self.session, text, 'query'))

    def test_recall_is_session_isolated_and_does_not_mutate_memory_or_history(self):
        self.store.remember('other', '饮品偏好', '冰美式', 'preference', 's1')
        before_state = list(self.store.db.iterdump())
        before_guard = list(self.store.guard.iterdump())
        self.assertEqual(self.memory.handle(self.session, RECALL, 'query'), '这点我现在不太确定。')
        self.assertEqual(self.memory.handle(self.session, STATUS, 'query'), '目前没有保存这项饮品偏好。')
        self.assertEqual(list(self.store.db.iterdump()), before_state)
        self.assertEqual(list(self.store.guard.iterdump()), before_guard)

    def test_common_explicit_forms_and_terminal_punctuation(self):
        for text in ('我喜欢喝什么', '我最喜欢喝什么?', '你还记得我平时喜欢喝什么吗？',
                     '我的饮料偏好是什么。', '  我的饮品偏好是什么？  '):
            with self.subTest(text=text):
                self.assertEqual(self.memory.handle(self.session, text, 'query'), '这点我现在不太确定。')
        for text in ('你还记得我的饮品偏好吗？', '你还保存着我的饮料偏好吗？',
                     '我的饮品偏好还保存着吗？', '我的饮料偏好已经删除了吗？',
                     '刚才那条饮品偏好你还记着吗？'):
            with self.subTest(text=text):
                self.assertEqual(self.memory.handle(self.session, text, 'query'), '目前没有保存这项饮品偏好。')
