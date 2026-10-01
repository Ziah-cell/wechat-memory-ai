from pathlib import Path
import json
import re
import sqlite3
import tempfile
import unittest
import zipfile

from wechat_memory.store import Store
from wechat_memory.memory import MemoryService
from wechat_memory.backup import BackupError, backup_store, restore_backup


class MemoryTests(unittest.TestCase):
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

    def test_explicit_preferences_survive_restart_with_provenance(self):
        reply = self.memory.handle('s', '记住：称呼我为小禾，回复尽量简短', 'message-1')
        self.assertIn('记住', reply)
        self.reopen()
        rows = self.store.memories('s')
        self.assertEqual({r['key']: r['value'] for r in rows}, {'称呼': '小禾', '回复长度': '简短'})
        for row in rows:
            self.assertEqual(row['source_ref'], 'message-1')
            self.assertEqual(row['certainty'], 'explicit')
            self.assertEqual(row['status'], 'active')
            self.assertGreaterEqual(row['updated_ns'], row['created_ns'])

    def test_preference_change_removes_stale_context(self):
        self.memory.handle('s', '记住：称呼我为小禾', 'm1')
        self.store.add_turn('s', 'm1', 'user', '我的旧称呼是小禾')
        self.store.compact('s', 0, 300)
        self.memory.handle('s', '以后不要叫小禾，改叫阿禾', 'm2')
        self.assertEqual(self.store.memories('s')[0]['value'], '阿禾')
        self.assertNotIn('小禾', self.store.summary('s'))
        self.assertEqual(self.store.history('s'), [])

    def test_temporary_statement_does_not_become_permanent_preference(self):
        self.assertIsNone(self.memory.handle('s', '今天有些累，不想长聊', 'm'))
        self.assertEqual(self.store.memories('s'), [])

    def test_sensitive_information_is_not_saved(self):
        for text in ['记住：密码=secret', '/记住 preference api_key=unit-test-key',
                     '记住：手机号=13800138000', '记住：病历=某诊断']:
            with self.subTest(text=text):
                self.assertIn('敏感', self.memory.handle('s', text, 'm'))
        self.assertEqual(self.store.memories('s'), [])

    def test_view_correct_and_delete_specific_memory(self):
        self.memory.handle('s', '/记住 preference 兴趣=绘画', 'm')
        row = self.store.memories('s')[0]
        self.assertIn(row['id'], self.memory.handle('s', '你记住了什么', 'm2'))
        self.memory.handle('s', f'/纠正 {row["id"]}=编程', 'm3')
        self.assertEqual(self.store.memories('s')[0]['value'], '编程')
        self.memory.handle('s', '/忘记 ' + row['id'], 'm4')
        self.assertEqual(self.store.memories('s'), [])

    def test_retrieval_and_deletion_are_session_isolated(self):
        a = self.store.remember('a', '兴趣', '绘画', 'preference', 'ma')
        self.store.remember('b', '兴趣', '编程', 'preference', 'mb')
        self.assertNotIn('编程', json.dumps(self.store.retrieve('a', '兴趣'), ensure_ascii=False))
        self.assertFalse(self.store.forget('b', a['id']))
        self.assertEqual(len(self.store.memories('a')), 1)

    def test_retrieve_events_by_relevance_and_preserve_type(self):
        self.store.remember('s', '英语考试', '下周复习词汇', 'event', 'm1')
        self.store.remember('s', '运动计划', '周末跑步', 'event', 'm2')
        result = self.store.retrieve('s', '英语考试进度')
        self.assertEqual([r['key'] for r in result], ['英语考试'])
        self.assertEqual(result[0]['kind'], 'event')

    def test_clear_requires_session_bound_expiring_confirmation(self):
        self.store.remember('s', '称呼', '测试用户', 'preference', 'm')
        response = self.memory.handle('s', '/清空记忆', 'm2')
        token = re.search(r'/确认清空 ([a-f0-9]+)', response).group(1)
        self.memory.handle('other', '/确认清空 ' + token, 'm3')
        self.assertEqual(len(self.store.memories('s')), 1)
        self.memory.handle('s', '/确认清空 wrong', 'm4')
        self.assertEqual(len(self.store.memories('s')), 1)
        self.memory.handle('s', '/确认清空 ' + token, 'm5')
        self.assertEqual(self.store.memories('s'), [])
        self.assertIn('无效', self.memory.handle('s', '/确认清空 ' + token, 'm6'))

    def test_expired_clear_token_does_not_clear(self):
        self.store.remember('s', '称呼', '测试', 'preference', 'm')
        token = self.store.issue_clear_token('s', ttl=-1)
        self.assertFalse(self.store.confirm_clear('s', token))
        self.assertEqual(len(self.store.memories('s')), 1)

    def test_forgetting_purges_history_summary_and_survives_restart(self):
        row = self.store.remember('s', '称呼', '仅测试秘密称呼', 'preference', 'm1')
        self.store.add_turn('s', 'm1', 'user', '仅测试秘密称呼')
        self.store.add_turn('s', 'm2', 'assistant', '仅测试秘密称呼你好')
        self.store.compact('s', 1, 100)
        self.assertIn('仅测试秘密称呼', self.store.summary('s'))
        self.store.forget('s', row['id'])
        self.reopen()
        self.assertEqual(self.store.history('s'), [])
        self.assertEqual(self.store.summary('s'), '')
        self.assertEqual(self.store.retrieve('s', '称呼'), [])

    def test_compaction_keeps_bounded_recent_history_and_source_refs(self):
        for n in range(30):
            self.store.add_turn('s', f'm{n}', 'user', f'第{n}次聊天\n内容')
        self.store.compact('s', 6, 150)
        self.assertEqual(len(self.store.history('s')), 6)
        self.assertEqual(self.store.history('s')[-1]['content'], '第29次聊天\n内容')
        self.assertLessEqual(len(self.store.summary('s')), 150)
        self.assertTrue(self.store.summary_sources('s'))

    def test_old_backup_with_current_guard_cannot_revive_deleted_memory(self):
        row = self.store.remember('s', '称呼', '已遗忘称呼', 'preference', 'm')
        self.store.remember('s', '兴趣', '保留绘画', 'preference', 'm2')
        self.store.add_turn('s', 'm', 'user', '已遗忘称呼')
        self.store.compact('s', 0, 300)
        backup = self.root / 'old.zip'
        backup_store(self.store, backup)
        self.store.forget('s', row['id'])
        self.store.close()
        restore_backup(backup, self.root / 'data')
        self.reopen()
        self.assertEqual([r['value'] for r in self.store.memories('s')], ['保留绘画'])
        self.assertNotIn('已遗忘称呼', self.store.summary('s'))
        self.assertEqual(self.store.history('s'), [])

    def test_old_backup_cannot_revive_replaced_preference(self):
        self.store.remember('s', '称呼', '旧称呼', 'preference', 'm')
        backup_store(self.store, self.root / 'old.zip')
        self.store.remember('s', '称呼', '新称呼', 'preference', 'm2')
        self.store.close()
        restore_backup(self.root / 'old.zip', self.root / 'data')
        self.reopen()
        self.assertEqual(self.store.memories('s'), []) # newer value was not in the old backup

    def test_restore_without_matching_guard_is_rejected(self):
        backup_store(self.store, self.root / 'old.zip')
        with self.assertRaises(BackupError):
            restore_backup(self.root / 'old.zip', self.root / 'new')
        other = Store(self.root / 'other')
        other.close()
        with self.assertRaises(BackupError):
            restore_backup(self.root / 'old.zip', self.root / 'other')

    def test_restore_on_new_machine_with_latest_guard(self):
        self.store.remember('s', '兴趣', '绘画', 'preference', 'm')
        backup_store(self.store, self.root / 'backup.zip')
        self.store.close()
        restore_backup(self.root / 'backup.zip', self.root / 'migrated', self.root / 'data' / 'guard.sqlite3')
        other = Store(self.root / 'migrated')
        try:
            self.assertEqual(other.memories('s')[0]['value'], '绘画')
        finally:
            other.close()

    def test_incomplete_forget_replays_before_any_read(self):
        self.store.remember('s', '称呼', '需清除', 'preference', 'm')
        self.store.record_erasure('s', None)
        self.reopen()
        self.assertEqual(self.store.memories('s'), [])

    def test_malformed_backup_leaves_existing_content_intact(self):
        self.store.remember('s', '称呼', '保留', 'preference', 'm')
        path = self.root / 'bad.zip'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('../../escape', 'bad')
        with self.assertRaises(BackupError):
            restore_backup(path, self.root / 'data')
        self.assertEqual(self.store.memories('s')[0]['value'], '保留')
