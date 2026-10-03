"""Explicit commands, finite direct self-statements and bounded local recall."""
import re

from .preferences import SLOT_KEYS, parse_preference


SENSITIVE = re.compile(r'密码|口令|密钥|令牌|身份证|银行卡|手机号|病历|诊断|性取向|宗教|账户余额|'
                       r'password|api[ _-]?key|secret|token|sk-[A-Za-z0-9]|\b1[3-9]\d{9}\b|\b\d{16,19}\b', re.I)

# Whole questions only: recommendations, quotations and mixed requests stay outside
# this deliberately narrow recall path. Missing records never imply a past deletion.
_DRINK_KEYS = SLOT_KEYS['饮品偏好']
_DRINK_RECALL = re.compile(
    r'(?:我(?:平时)?(?:最)?喜欢喝什么|你(?:还)?记得我(?:平时)?(?:最)?喜欢喝什么吗|'
    r'我的(?:饮品|饮料)偏好是什么)[？?。.]?')
_DRINK_STATUS = re.compile(
    r'(?:你(?:还)?(?:记得|记着|保存着?)我的(?:饮品|饮料)偏好吗|'
    r'我的(?:饮品|饮料)偏好(?:还(?:保存着|记着)吗|(?:已经)?删除了吗)|'
    r'(?:刚才那条|那条|这条)(?:饮品|饮料)偏好你还记着吗'
    r'(?:[？?，,]\s*说清楚是否已经删除)?)[？?。.]?')


def sensitive(text):
    return bool(SENSITIVE.search(text))


class MemoryService:
    def __init__(self, store):
        self.store = store

    def handle(self, session, text, source):
        text = text.strip()
        if text == '你记住了什么' or re.fullmatch(r'/记忆(?: \d+)?', text):
            page = int(text.split()[-1]) if text.split()[-1].isdigit() else 1
            rows = self.store.memories(session)
            if not rows:
                return '目前没有保存长期记忆。'
            if page < 1:
                return '页码从 1 开始。'
            selected = rows[(page-1)*5:page*5]
            lines = [f"{r['id']} [{r['kind']}] {r['key']}={r['value'][:100]}" for r in selected]
            return '\n'.join(lines) + f'\n第 {page} 页；用 /记忆 页码 翻页，/纠正 ID=新内容 或 /忘记 ID。'
        if text == '/清空记忆':
            token = self.store.issue_clear_token(session)
            return f'将清空本会话长期记忆、历史与摘要。60 秒内输入 /确认清空 {token}；原微信与旧备份不会被删除。'
        if text.startswith('/确认清空 '):
            ok = self.store.confirm_clear(session, text.split(' ', 1)[1])
            return '已清空本地记忆、历史与摘要。请保留最新 guard.sqlite3，旧备份未被销毁。' if ok else '确认码无效或已过期，未清空。'
        if text.startswith('/忘记 '):
            ok = self.store.forget(session, text.split(' ', 1)[1])
            return '已删除该记忆，并清理此前会话历史与摘要；其他记忆保留。' if ok else '未找到本会话的记忆 ID。'
        if text.startswith('/纠正 '):
            ident, sep, value = text[4:].partition('=')
            if not sep or not value.strip():
                return '格式：/纠正 ID=新内容'
            if sensitive(value):
                return '这可能包含敏感信息，本版不写入长期记忆。'
            row = next((r for r in self.store.memories(session) if r['id'] == ident.strip()), None)
            if not row:
                return '未找到本会话的记忆 ID。'
            return self._save(session, [(row['kind'], row['key'], value.strip())], source)
        nickname = re.fullmatch(r'以后不要叫[^，,]+[，,]\s*改叫([^，,。]+)[。]?', text)
        if nickname:
            return self._save(session, [('preference', '称呼', nickname.group(1).strip())], source)
        recall = self._recall_drink(session, text)
        if recall is not None:
            return recall
        natural = self._handle_preference(session, text, source)
        if natural is not None:
            return natural
        if not (text.startswith('记住') or text.startswith('/记住')):
            return None
        if sensitive(text):
            return '这可能包含敏感信息，本版不写入长期记忆。'
        explicit = re.fullmatch(r'/记住 (preference|event) ([^=\n]+)=(.+)', text, re.S)
        if explicit:
            return self._save(session, [tuple(p.strip() for p in explicit.groups())], source)
        body = re.sub(r'^记住[：:]\s*', '', text)
        items = []
        for part in re.split('[，,；;]', body):
            part = part.strip().rstrip('。')
            name = re.fullmatch(r'称呼我为(.+)', part)
            if name:
                items.append(('preference', '称呼', name.group(1)))
            elif part in ('回复尽量简短', '回复简短'):
                items.append(('preference', '回复长度', '简短'))
            elif '=' in part:
                key, value = part.split('=', 1)
                items.append(('preference', key.strip(), value.strip()))
            else:
                return '请明确记忆内容，例如：记住：称呼我为小禾，回复尽量简短；或 /记住 event 考试=下周复习。'
        return self._save(session, items, source)

    def observe(self, session, text, source, *, check_only=False):
        """Recognize one direct statement; a successful observation still gets a model reply."""
        intent = parse_preference(text)
        if intent is None or intent.action != 'observe':
            return None
        if sensitive(text):
            return '这可能包含敏感信息，本版不写入长期记忆。'
        return self._write_preference(session, intent.slot, intent.value, source, check_only=check_only)

    def _slot_state(self, session, slot):
        all_rows = self.store.memories(session)
        rows = [row for row in all_rows if row['key'] in SLOT_KEYS[slot]]
        if len(rows) > 1:
            return all_rows, None, '这项偏好有多条记录，请先查看并明确要修改哪一条。'
        row = rows[0] if rows else None
        if row and (row['kind'] != 'preference' or row['certainty'] != 'explicit'):
            return all_rows, None, '这项记录不是明确偏好，请先查看并指定要修改的记录。'
        return all_rows, row, None

    def _write_preference(self, session, slot, value, source, *, check_only=False):
        all_rows, row, error = self._slot_state(session, slot)
        if error:
            return error
        if row is None and len(all_rows) >= 100:
            return '长期记忆已达 100 条，请先删除不用的条目。'
        if not check_only and (row is None or row['value'] != value):
            self.store.remember(session, row['key'] if row else slot, value, 'preference', source)
        return None

    def _handle_preference(self, session, text, source):
        intent = parse_preference(text)
        if intent is None or intent.action == 'observe':
            return None
        if sensitive(text):
            return '这可能包含敏感信息，本版不写入长期记忆。'
        if intent.action == 'clarify':
            return '你指的是哪项偏好？请说清饮品偏好、咖啡加糖或回复长度。'
        if intent.action == 'set':
            error = self._write_preference(session, intent.slot, intent.value, source)
            return error or '好，' + intent.slot + '记为' + intent.value + '。'
        _, row, error = self._slot_state(session, intent.slot)
        if error:
            return error
        if intent.action == 'forget':
            if row is None:
                return '目前没有保存这项偏好。'
            self.store.forget(session, row['id'])
            return '已删除这项偏好，并清理此前会话历史与摘要。'
        if row is None:
            return '目前没有保存这项偏好。' if intent.action == 'status' else '这点我现在不太确定。'
        prefix = '目前保存的' if intent.action == 'status' else '你说过的'
        return prefix + intent.slot + '是：' + row['value'] + '。'

    def _recall_drink(self, session, text):
        status = _DRINK_STATUS.fullmatch(text) is not None
        if not status and _DRINK_RECALL.fullmatch(text) is None:
            return None
        rows = [row for row in self.store.memories(session)
                if row['session'] == session and row['status'] == 'active'
                and row['kind'] == 'preference' and row['certainty'] == 'explicit'
                and row['key'] in _DRINK_KEYS]
        if not rows:
            return '目前没有保存这项饮品偏好。' if status else '这点我现在不太确定。'
        if len(rows) > 1:
            return '保存了多条饮品偏好，我不能确定你指的是哪一条。'
        prefix = '目前保存的' if status else '你说过的'
        return prefix + '饮品偏好是：' + rows[0]['value'] + '。'

    def _save(self, session, items, source):
        if any(sensitive(key + '=' + value) for _, key, value in items):
            return '这可能包含敏感信息，本版不写入长期记忆。'
        if not items or any(not key or len(key) > 40 or not value or len(value) > 500 for _, key, value in items):
            return '记忆键需 1–40 字，内容需 1–500 字。'
        existing = {r['key'] for r in self.store.memories(session)}
        if len(existing | {key for _, key, _ in items}) > 100:
            return '长期记忆已达 100 条，请先删除不用的条目。'
        for kind, key, value in items:
            self.store.remember(session, key, value, kind, source)
        return '已记住：' + '；'.join(key for _, key, _ in items) + '。可用 /记忆 查看和修改。'
