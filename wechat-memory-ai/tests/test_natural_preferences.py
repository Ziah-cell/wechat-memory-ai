from pathlib import Path
import tempfile
import unittest

from wechat_memory.backup import backup_store, restore_backup
from wechat_memory.memory import MemoryService
from wechat_memory.store import Store


class NaturalPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'data')
        self.addCleanup(lambda: self.store.close())
        self.memory = MemoryService(self.store)

    def reopen(self):
        self.store.close()
        self.store = Store(self.root / 'data')
        self.memory = MemoryService(self.store)

    def snapshot(self):
        return list(self.store.db.iterdump()), list(self.store.guard.iterdump())

    def test_stable_statements_store_three_explicit_slots_with_provenance(self):
        cases = (
            ('我平时喜欢喝热柠檬水。', '饮品偏好', '热柠檬水'),
            ('我喝咖啡不加糖。', '咖啡加糖', '不加糖'),
            ('以后回复我简短一点。', '回复长度', '简短'),
        )
        for n, (text, key, value) in enumerate(cases):
            with self.subTest(key=key):
                self.assertIsNone(self.memory.handle('s', text, f'm{n}'))
                self.assertIsNone(self.memory.observe('s', text, f'm{n}'))
                row = next(r for r in self.store.memories('s') if r['key'] == key)
                self.assertEqual(row['value'], value)
                self.assertEqual(row['source_ref'], f'm{n}')
                self.assertEqual((row['kind'], row['certainty']), ('preference', 'explicit'))
        self.reopen()
        self.assertEqual(len(self.store.memories('s')), 3)

    def test_temporary_hypothetical_quoted_negative_and_mixed_text_does_not_write(self):
        texts = (
            '我今天喜欢喝茶。', '我今天只想喝茶。', '我平时可能喜欢喝茶。',
            '假如我平时喜欢喝茶。', '如果我喝咖啡不加糖。', '她说我平时喜欢喝茶。',
            '“我平时喜欢喝茶。”', '请翻译：我平时喜欢喝茶。', '我不喜欢喝茶。',
            '我不是喜欢喝茶。', '我平时喜欢喝茶？', '我平时喜欢喝茶，但今天不想喝。',
            '我平时喜欢喝茶。帮我选一杯。', '我平时喜欢喝茶\n帮我选一杯',
            '这次回复我简短一点。', '今天以后回复我简短一点。',
            '我喝咖啡不加糖，但今天例外。', '我平时喜欢喝茶；我喝咖啡少糖。',
            '我平时喜欢喝热柠檬水是假话。', '我平时喜欢喝热柠檬水只是举例。',
            '我平时喜欢喝热柠檬水但最近不喝了。', '今天我喝咖啡不加糖。',
            '以后回复我简短一点，除非我问细节。',
        )
        for text in texts:
            with self.subTest(text=text):
                before = self.snapshot()
                self.assertIsNone(self.memory.observe('s', text, 'message'))
                self.assertEqual(self.snapshot(), before)

    def test_unsupported_values_recommendations_and_management_questions_do_not_write(self):
        for text in ('我平时喜欢喝百香果双拼。', '我喝咖啡超级多糖。',
                     '下午推荐喝什么？', '照我的口味推荐一杯。',
                     '我的饮品偏好改成茶吗？', '忘记我的饮品偏好吗？',
                     '我的饮品偏好改成茶，密码是虚构样例。',
                     '忘记我的饮品偏好，密钥是虚构样例。'):
            with self.subTest(text=text):
                before = self.snapshot()
                self.assertIsNone(self.memory.observe('s', text, 'm'))
                self.assertIsNone(self.memory.handle('s', text, 'm'))
                self.assertEqual(self.snapshot(), before)

    def test_precheck_has_no_writes_then_commit_has_same_success_result(self):
        before = self.snapshot()
        self.assertIsNone(self.memory.observe('s', '我平时喜欢喝茶。', 'm', check_only=True))
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(self.memory.observe('s', '我平时喜欢喝茶。', 'm'))
        self.assertEqual(self.store.memories('s')[0]['value'], '茶')

    def test_same_value_is_idempotent_and_preserves_history_and_source(self):
        self.memory.observe('s', '我平时喜欢喝茶。', 'original')
        self.store.add_turn('s', 'history', 'user', '虚构的旧话题')
        self.store.compact('s', 0, 300)
        before = self.snapshot()
        self.assertIsNone(self.memory.observe('s', '我平时喜欢喝茶。', 'again', check_only=True))
        self.assertIsNone(self.memory.observe('s', '我平时喜欢喝茶。', 'again'))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.store.memories('s')[0]['source_ref'], 'original')

    def test_unique_legacy_alias_updates_original_key_and_erases_old_context(self):
        self.store.remember('s', '饮料喜好', '茶', 'preference', 'old')
        self.store.add_turn('s', 'history', 'assistant', '虚构的旧饮品值')
        self.store.compact('s', 0, 300)
        self.assertIsNone(self.memory.observe('s', '我平时喜欢喝温乌龙茶。', 'new'))
        rows = self.store.memories('s')
        self.assertEqual([(r['key'], r['value'], r['source_ref']) for r in rows],
                         [('饮料喜好', '温乌龙茶', 'new')])
        self.assertEqual(self.store.summary('s'), '')
        self.reopen()
        self.assertEqual(self.memory.handle('s', '我平时最喜欢喝什么？', 'query'),
                         '你说过的饮品偏好是：温乌龙茶。')

    def test_multiple_aliases_block_precheck_commit_correction_and_forgetting(self):
        self.store.remember('s', '饮品偏好', '茶', 'preference', 'one')
        self.store.remember('s', '饮料偏好', '茶', 'preference', 'two')
        before = self.snapshot()
        check = self.memory.observe('s', '我平时喜欢喝温乌龙茶。', 'new', check_only=True)
        self.assertIsInstance(check, str)
        self.assertEqual(self.memory.observe('s', '我平时喜欢喝温乌龙茶。', 'new'), check)
        self.assertIsInstance(self.memory.handle('s', '我的饮品偏好改成温乌龙茶。', 'change'), str)
        self.assertIsInstance(self.memory.handle('s', '忘记我的饮品偏好。', 'forget'), str)
        self.assertEqual(self.snapshot(), before)

    def test_event_or_nonexplicit_slot_conflicts_do_not_get_rewritten_or_forgotten(self):
        for n, (kind, certainty) in enumerate((('event', 'explicit'), ('preference', 'inferred'))):
            session = f's{n}'
            row = self.store.remember(session, '咖啡加糖', '少糖', kind, 'old')
            with self.store.db:
                self.store.db.execute('UPDATE memories SET certainty=? WHERE id=?', (certainty, row['id']))
            before = self.snapshot()
            self.assertIsInstance(self.memory.observe(session, '我喝咖啡不加糖。', 'new', check_only=True), str)
            self.assertIsInstance(self.memory.observe(session, '我喝咖啡不加糖。', 'new'), str)
            self.assertIsInstance(self.memory.handle(session, '我的咖啡加糖偏好改成不加糖。', 'change'), str)
            self.assertIsInstance(self.memory.handle(session, '忘记我的咖啡加糖偏好。', 'forget'), str)
            self.assertEqual(self.snapshot(), before)

    def test_capacity_blocks_new_slot_but_allows_existing_slot_update(self):
        for n in range(99):
            self.store.remember('s', f'fixture-{n}', '虚构值', 'preference', f'm{n}')
        self.store.remember('s', '饮品偏好', '茶', 'preference', 'existing')
        before = self.snapshot()
        check = self.memory.observe('s', '我喝咖啡不加糖。', 'new', check_only=True)
        self.assertIsInstance(check, str)
        self.assertEqual(self.memory.observe('s', '我喝咖啡不加糖。', 'new'), check)
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(self.memory.observe('s', '我平时喜欢喝温乌龙茶。', 'change'))
        self.assertEqual(len(self.store.memories('s')), 100)
        self.assertEqual(next(r['value'] for r in self.store.memories('s') if r['key'] == '饮品偏好'), '温乌龙茶')

    def test_named_natural_management_and_recall_cover_all_three_slots(self):
        cases = (
            ('我的饮品偏好改成温乌龙茶。', '我的饮品偏好是什么？', '饮品偏好', '温乌龙茶'),
            ('我的咖啡加糖偏好改成无糖。', '我喝咖啡怎么加糖？', '咖啡加糖', '不加糖'),
            ('我的回复长度改成详细。', '我喜欢你回复多长？', '回复长度', '详细'),
        )
        for change, query, key, value in cases:
            with self.subTest(key=key):
                self.assertIsInstance(self.memory.handle('s', change, 'change'), str)
                self.assertIn(value, self.memory.handle('s', query, 'query'))
                row = next(r for r in self.store.memories('s') if r['key'] == key)
                self.assertEqual(row['value'], value)
                before = self.snapshot()
                self.assertIsInstance(self.memory.handle('s', change, 'unchanged'), str)
                self.assertEqual(self.snapshot(), before)

    def test_named_forgetting_purges_context_and_stays_forgotten_after_restart(self):
        self.memory.observe('s', '我喝咖啡不加糖。', 'initial')
        self.store.add_turn('s', 'history', 'assistant', '虚构的咖啡偏好内容')
        self.store.compact('s', 0, 300)
        self.assertIsInstance(self.memory.handle('s', '忘记我的咖啡加糖偏好。', 'forget'), str)
        self.assertEqual(self.store.memories('s'), [])
        self.assertEqual(self.store.history('s'), [])
        self.assertEqual(self.store.summary('s'), '')
        self.reopen()
        self.assertEqual(self.memory.handle('s', '我喝咖啡怎么加糖？', 'query'), '这点我现在不太确定。')
        self.assertEqual(self.memory.handle('s', '忘记我的咖啡加糖偏好。', 'again'), '目前没有保存这项偏好。')

    def test_current_guard_blocks_old_backup_after_natural_correction_or_forgetting(self):
        for n, command in enumerate(('我的饮品偏好改成温乌龙茶。', '忘记我的饮品偏好。')):
            session = f'backup-{n}'
            self.memory.observe(session, '我平时喜欢喝热柠檬水。', 'initial')
            backup = self.root / f'backup-{n}.zip'
            backup_store(self.store, backup)
            self.assertIsInstance(self.memory.handle(session, command, 'management'), str)
            self.store.close()
            restore_backup(backup, self.root / 'data')
            self.store = Store(self.root / 'data')
            self.memory = MemoryService(self.store)
            self.assertEqual(self.store.memories(session), [])
            self.assertEqual(self.memory.handle(session, '我平时最喜欢喝什么？', 'query'), '这点我现在不太确定。')

    def test_vague_management_asks_for_slot_without_mutating(self):
        self.memory.observe('s', '我平时喜欢喝茶。', 'initial')
        before = self.snapshot()
        for text in ('忘记这个。', '别再记这个。', '忘记刚才那条。', '把这条偏好改成少糖。'):
            with self.subTest(text=text):
                reply = self.memory.handle('s', text, 'vague')
                self.assertIsInstance(reply, str)
                self.assertIn('哪项偏好', reply)
                self.assertEqual(self.snapshot(), before)

    def test_queries_do_not_promote_assistant_history_or_other_session_values(self):
        self.memory.observe('other', '我喝咖啡不加糖。', 'other')
        self.store.add_turn('s', 'invented', 'assistant', '你喝咖啡少糖，喜欢详细回复。')
        self.store.compact('s', 0, 300)
        for text in ('我喝咖啡怎么加糖？', '我喜欢你回复多长？'):
            self.assertEqual(self.memory.handle('s', text, 'query'), '这点我现在不太确定。')
        self.assertEqual(self.memory.handle('s', '你还记得我的咖啡加糖偏好吗？', 'query'),
                         '目前没有保存这项偏好。')
        self.assertEqual(self.store.memories('s'), [])

    def test_finite_sugar_and_length_forms_normalize_without_general_extraction(self):
        for n, (text, key, expected) in enumerate((
            ('我喝咖啡无糖。', '咖啡加糖', '不加糖'),
            ('我喝咖啡少加糖。', '咖啡加糖', '少糖'),
            ('我喝咖啡正常加糖。', '咖啡加糖', '正常糖'),
            ('我喜欢简短的回复。', '回复长度', '简短'),
            ('以后回复我详细一点。', '回复长度', '详细'),
        )):
            session = f'normalized-{n}'
            self.assertIsNone(self.memory.observe(session, text, 'm'))
            self.assertEqual([(r['key'], r['value']) for r in self.store.memories(session)], [(key, expected)])
