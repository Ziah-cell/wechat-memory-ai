"""Redacted UIA capability evidence, never a real-message admission token.

Field presence does not establish its meaning. Even all fields present and a
scroll percentage of 100 cannot authenticate a sender or exclude history sync.
"""
from .live_read import ReadError, validate_binding


_IDENTITY = {'process', 'started', 'window', 'root', 'list_token'}
_ROW_FLAGS = {'automation_id', 'help_text', 'item_status', 'item_type',
              'labeled_by', 'text_pattern', 'has_children'}
_SCROLL = {'depth', 'scroll_pattern', 'vertical_scrollable', 'vertical_scroll_percent'}


def inbound_capability_report(raw):
    """Validate the entire private protocol before producing a fixed safe report."""
    if (not isinstance(raw, dict)
            or set(raw) != _IDENTITY | {'status', 'minimized', 'rows',
                                       'distinct_automation_ids', 'scroll_nodes'}
            or raw['status'] != 'inbound_capability_snapshot'):
        raise ReadError('invalid_snapshot')
    validate_binding({key:raw[key] for key in _IDENTITY})
    if (type(raw['minimized']) is not bool or not isinstance(raw['rows'], list)
            or len(raw['rows']) > 256 or type(raw['distinct_automation_ids']) is not int):
        raise ReadError('invalid_snapshot')
    seen = set()
    for row in raw['rows']:
        if (not isinstance(row, dict) or set(row) != _ROW_FLAGS | {'token', 'kind'}
                or not isinstance(row['token'], str) or not 1 <= len(row['token']) <= 256
                or row['token'] in seen or row['kind'] not in ('text', 'other')
                or any(type(row[key]) is not bool for key in _ROW_FLAGS)):
            raise ReadError('invalid_snapshot')
        seen.add(row['token'])
    id_rows = sum(row['automation_id'] for row in raw['rows'])
    distinct = raw['distinct_automation_ids']
    if not (distinct == 0 if id_rows == 0 else 1 <= distinct <= id_rows):
        raise ReadError('invalid_snapshot')
    nodes = raw['scroll_nodes']
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 49:
        raise ReadError('invalid_snapshot')
    for depth, node in enumerate(nodes):
        if (not isinstance(node, dict) or set(node) != _SCROLL
                or type(node['depth']) is not int or node['depth'] != depth
                or type(node['scroll_pattern']) is not bool):
            raise ReadError('invalid_snapshot')
        vertical, percent = node['vertical_scrollable'], node['vertical_scroll_percent']
        if not node['scroll_pattern']:
            if vertical is not None or percent is not None:
                raise ReadError('invalid_snapshot')
        elif (type(vertical) is not bool or type(percent) not in (int, float)
              or not (0 <= percent <= 100 if vertical else percent == -1)):
            raise ReadError('invalid_snapshot')
    texts = [row for row in raw['rows'] if row['kind'] == 'text']
    return dict(
        status='inbound_capabilities_observed', minimized=raw['minimized'],
        rows=len(raw['rows']), text_rows=len(texts),
        **{key+'_rows':sum(row[key] for row in texts) for key in sorted(_ROW_FLAGS)},
        distinct_automation_ids=distinct,
        list_scroll_pattern=nodes[0]['scroll_pattern'],
        ancestor_scroll_patterns=sum(node['scroll_pattern'] for node in nodes[1:]),
        scroll_nodes=[dict(node) for node in nodes],
        admission='rejected', rejection_reasons=[
            'direction_unverified', 'target_identity_unverified',
            'history_boundary_unverified', 'message_identity_unverified'],
        sender_verified=False, history_boundary_verified=False,
        message_identity_verified=False, message_text_read=False,
        model_called=False, memory_written=False, real_send_supported=False, reply_ready=False)
