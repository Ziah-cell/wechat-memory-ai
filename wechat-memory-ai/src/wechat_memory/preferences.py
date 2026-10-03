"""Finite whole-sentence preference intents; no inference from arbitrary prose."""
from dataclasses import dataclass, field
import re


SLOT_KEYS = {
    '饮品偏好': ('饮品偏好', '饮料偏好', '饮品喜好', '饮料喜好'),
    '咖啡加糖': ('咖啡加糖',),
    '回复长度': ('回复长度',),
}
_NAMES = {
    '饮品偏好': r'(?:饮品偏好|饮料偏好|饮品喜好|饮料喜好)',
    '咖啡加糖': r'咖啡加糖(?:偏好)?',
    '回复长度': r'回复长度(?:偏好)?',
}
_VALUES = {
    '饮品偏好': {value: value for value in (
        '茶', '热柠檬水', '温乌龙茶', '乌龙茶', '绿茶', '红茶',
        '白开水', '咖啡', '美式咖啡', '冰美式', '拿铁')},
    '咖啡加糖': {'不加糖': '不加糖', '无糖': '不加糖', '少糖': '少糖',
             '少加糖': '少糖', '正常糖': '正常糖', '正常加糖': '正常糖'},
    '回复长度': {'简短': '简短', '详细': '详细'},
}
_VALUE_PATTERNS = {
    slot: '(?:' + '|'.join(re.escape(value) for value in values) + ')'
    for slot, values in _VALUES.items()
}
_END = r'[。.!！]?'
_QUERY_END = r'[？?。.]?'
_OBSERVATIONS = (
    ('饮品偏好', re.compile(r'我(?:平时)?(?:最)?喜欢喝(?P<value>' + _VALUE_PATTERNS['饮品偏好'] + ')' + _END)),
    ('咖啡加糖', re.compile(r'我(?:平时)?喝咖啡(?P<value>' + _VALUE_PATTERNS['咖啡加糖'] + ')' + _END)),
    ('回复长度', re.compile(r'以后回复我(?P<value>简短|详细)(?:一点)?' + _END)),
    ('回复长度', re.compile(r'我喜欢(?P<value>简短|详细)的回复' + _END)),
)


@dataclass(frozen=True)
class PreferenceIntent:
    action: str
    slot: str = ''
    value: str = field(default='', repr=False)


def parse_preference(text):
    """Only exact supported text is actionable; surrounding quotes are not stripped."""
    text = text.strip()
    for slot, pattern in _OBSERVATIONS:
        match = pattern.fullmatch(text)
        if match:
            return PreferenceIntent('observe', slot, _VALUES[slot][match['value']])
    for slot, name in _NAMES.items():
        match = re.fullmatch(r'(?:请)?(?:把)?我的' + name + r'改成(?P<value>' +
                             _VALUE_PATTERNS[slot] + ')' + _END, text)
        if match:
            return PreferenceIntent('set', slot, _VALUES[slot][match['value']])
        if re.fullmatch(r'(?:请)?(?:忘记|删除|别再记)(?:我的)?' + name + _END, text):
            return PreferenceIntent('forget', slot)
        if re.fullmatch(r'我的' + name + r'是什么' + _QUERY_END, text):
            return PreferenceIntent('recall', slot)
        if re.fullmatch(r'(?:你(?:还)?记得我的' + name + r'吗|我的' + name +
                        r'(?:已经)?删除了吗)' + _QUERY_END, text):
            return PreferenceIntent('status', slot)
    if re.fullmatch(r'我喝咖啡怎么加糖' + _QUERY_END, text):
        return PreferenceIntent('recall', '咖啡加糖')
    if re.fullmatch(r'我喜欢你回复多长' + _QUERY_END, text):
        return PreferenceIntent('recall', '回复长度')
    if re.fullmatch(r'(?:请)?(?:忘记|删除|别再记)(?:这个|这条|刚才那条)(?:偏好|记忆)?' + _END, text):
        return PreferenceIntent('clarify')
    all_values = '(?:' + '|'.join(_VALUE_PATTERNS.values()) + ')'
    if re.fullmatch(r'(?:请)?(?:把)?(?:这个|这条|刚才那条)(?:偏好|记忆)改成' + all_values + _END, text):
        return PreferenceIntent('clarify')
    return None
