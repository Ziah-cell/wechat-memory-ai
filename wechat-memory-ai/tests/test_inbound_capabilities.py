"""Synthetic metadata only; these tests never inspect a real window."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from wechat_memory import live_read
from test_bound_reader import binding


def sample(**changes):
    raw = dict(binding(), status='inbound_capability_snapshot', minimized=True,
               rows=[dict(token='row1', kind='text', automation_id=True,
                          help_text=False, item_status=False, item_type=False,
                          labeled_by=False, text_pattern=False, has_children=False)],
               distinct_automation_ids=1,
               scroll_nodes=[dict(depth=0, scroll_pattern=False,
                                  vertical_scrollable=None, vertical_scroll_percent=None),
                             dict(depth=1, scroll_pattern=True,
                                  vertical_scrollable=True, vertical_scroll_percent=100.0)])
    raw.update(changes)
    return raw


class InboundCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(live_read.NativeReader, 'read_inbound_capabilities', None)),
                        'bound inbound capability diagnostic is not implemented')
        from wechat_memory.inbound_capabilities import inbound_capability_report
        self.report = inbound_capability_report

    def test_report_is_redacted_and_no_capability_is_an_admission(self):
        report = self.report(sample())
        self.assertEqual(report['status'], 'inbound_capabilities_observed')
        self.assertEqual(report['admission'], 'rejected')
        self.assertEqual(report['rejection_reasons'], [
            'direction_unverified', 'target_identity_unverified',
            'history_boundary_unverified', 'message_identity_unverified'])
        self.assertEqual(report['text_rows'], 1)
        self.assertEqual(report['ancestor_scroll_patterns'], 1)
        for key in ('sender_verified', 'history_boundary_verified', 'message_identity_verified',
                    'model_called', 'memory_written', 'real_send_supported', 'reply_ready',
                    'message_text_read'):
            self.assertIs(report[key], False)
        encoded = json.dumps(report)
        for private in ('ChatSingleWindow', 'row1', 'list_token', '123456', 'process', 'window'):
            self.assertNotIn(private, encoded)

    def test_all_metadata_present_and_bottom_scroll_still_reject(self):
        raw = sample()
        for key in set(raw['rows'][0]) - {'token', 'kind'}:
            raw['rows'][0][key] = True
        report = self.report(raw)
        self.assertEqual(report['admission'], 'rejected')
        self.assertEqual(len(report['rejection_reasons']), 4)
        self.assertEqual(report['help_text_rows'], 1)
        self.assertEqual(report['scroll_nodes'][1]['vertical_scroll_percent'], 100)

    def test_empty_rows_are_valid_but_not_ready(self):
        report = self.report(sample(rows=[], distinct_automation_ids=0))
        self.assertEqual(report['text_rows'], 0)
        self.assertEqual(report['admission'], 'rejected')

    def test_nontext_metadata_does_not_become_text_evidence(self):
        raw = sample()
        raw['rows'].append(dict(raw['rows'][0], token='row2', kind='other', help_text=True))
        report = self.report(raw)
        self.assertEqual(report['rows'], 2)
        self.assertEqual(report['text_rows'], 1)
        self.assertEqual(report['help_text_rows'], 0)

    def test_report_is_independent_from_native_input(self):
        raw = sample()
        report = self.report(raw)
        report['scroll_nodes'][1]['vertical_scroll_percent'] = 0
        self.assertEqual(raw['scroll_nodes'][1]['vertical_scroll_percent'], 100)
        raw['rows'][0]['help_text'] = True
        self.assertEqual(report['help_text_rows'], 0)

    def test_bad_top_level_fields_and_counts_are_rejected(self):
        invalid = [None, [], {}, sample(status='snapshot'), sample(minimized=1),
                   sample(body='PRIVATE'), sample(sender_verified=True),
                   sample(rows=None), sample(rows=[sample()['rows'][0]] * 257),
                   sample(distinct_automation_ids=True), sample(distinct_automation_ids=-1),
                   sample(distinct_automation_ids=2), sample(distinct_automation_ids=0)]
        invalid += [{k:v for k,v in sample().items() if k != missing} for missing in sample()]
        for raw in invalid:
            with self.subTest(raw_type=type(raw).__name__), self.assertRaises(live_read.ReadError):
                self.report(raw)

    def test_bad_rows_are_rejected(self):
        edits = [{'token':''}, {'token':1}, {'token':'x'*257}, {'kind':'incoming'},
                 {'text':'PRIVATE'}, {'help_text':1}, {'has_children':None},
                 {'automation_id':'PRIVATE'}, {'text_pattern':[]}, {'labeled_by':{}},
                 {'item_type':0}, {'item_status':'false'}]
        for change in edits:
            raw = sample()
            raw['rows'][0].update(change)
            with self.subTest(field=next(iter(change))), self.assertRaises(live_read.ReadError):
                self.report(raw)
        raw = sample()
        raw['rows'].append(copy.deepcopy(raw['rows'][0]))
        with self.assertRaises(live_read.ReadError):
            self.report(raw)

    def test_bad_scroll_path_and_values_are_rejected(self):
        edits = [{'depth':True}, {'depth':2}, {'depth':-1}, {'scroll_pattern':1},
                 {'vertical_scrollable':True}, {'vertical_scroll_percent':0}, {'name':'PRIVATE'}]
        for change in edits:
            raw = sample()
            raw['scroll_nodes'][0].update(change)
            with self.subTest(field=next(iter(change))), self.assertRaises(live_read.ReadError):
                self.report(raw)
        for percent in (True, -2, 101, 10**400, float('nan'), float('inf'), '100', None):
            raw = sample()
            raw['scroll_nodes'][1]['vertical_scroll_percent'] = percent
            with self.subTest(percent_type=type(percent).__name__), self.assertRaises(live_read.ReadError):
                self.report(raw)
        for nodes in ([], None, sample()['scroll_nodes'] * 25):
            with self.assertRaises(live_read.ReadError):
                self.report(sample(scroll_nodes=nodes))

    def test_scroll_no_scroll_sentinel_requires_not_scrollable(self):
        raw = sample()
        raw['scroll_nodes'][1].update(vertical_scrollable=False, vertical_scroll_percent=-1)
        self.assertEqual(self.report(raw)['ancestor_scroll_patterns'], 1)
        raw['scroll_nodes'][1]['vertical_scrollable'] = True
        with self.assertRaises(live_read.ReadError):
            self.report(raw)
        raw['scroll_nodes'][1].update(vertical_scrollable=False, vertical_scroll_percent=100)
        with self.assertRaises(live_read.ReadError):
            self.report(raw)

    def test_read_requires_binding_before_subprocess(self):
        reader = live_read.NativeReader('fixture.exe')
        with patch.object(live_read.subprocess, 'run', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(live_read.ReadError, '^window_binding_unavailable$'):
                reader.read_inbound_capabilities()

    def test_bound_read_uses_private_stdin_and_default_timeout(self):
        reader = live_read.NativeReader('fixture.exe', expected_binding=binding())
        reader.executable = Path('never-executed.exe')
        done = subprocess.CompletedProcess([], 0, json.dumps(sample()).encode(), b'')
        with patch.object(live_read.subprocess, 'run', return_value=done) as run:
            raw = reader.read_inbound_capabilities()
        self.assertEqual(raw, sample())
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][-1], '--inbound-capabilities')
        self.assertEqual(json.loads(run.call_args.kwargs['input']), binding())
        self.assertEqual(run.call_args.kwargs['timeout'], 8)

    def test_bad_result_never_rebinds(self):
        for raw, reason in ((sample(window=99), 'window_or_list_changed'),
                            (sample(body='PRIVATE'), 'native_reader_unavailable')):
            reader = live_read.NativeReader('fixture.exe', expected_binding=binding())
            reader.executable = Path('never-executed.exe')
            done = subprocess.CompletedProcess([], 0, json.dumps(raw).encode(), b'')
            with patch.object(live_read.subprocess, 'run', return_value=done):
                with self.assertRaisesRegex(live_read.ReadError, '^'+reason+'$'):
                    reader.read_inbound_capabilities()
            self.assertEqual(reader.binding, binding())

    def test_metadata_change_is_rejected_without_retry(self):
        reader = live_read.NativeReader('fixture.exe', expected_binding=binding())
        raw = dict(status='reader_error', reason='inbound_capabilities_changed')
        done = subprocess.CompletedProcess([], 3, json.dumps(raw).encode(), b'')
        with patch.object(live_read.subprocess, 'run', return_value=done) as run:
            with self.assertRaisesRegex(live_read.ReadError, '^inbound_capabilities_changed$'):
                reader.read_inbound_capabilities()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(reader.binding, binding())

    def test_capabilities_cannot_enter_any_message_session(self):
        for cls in (live_read.ReadSession, live_read.OccurrenceSession,
                    live_read.VisualOccurrenceSession, live_read.SelectionOccurrenceSession,
                    live_read.BackgroundOccurrenceSession):
            with self.subTest(session=cls.__name__), self.assertRaises(live_read.ReadError):
                cls().accept(sample())
