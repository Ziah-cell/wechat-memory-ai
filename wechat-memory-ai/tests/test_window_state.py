"""Metadata-only diagnostics must not become message or reply evidence."""
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from wechat_memory import live_read
from test_bound_reader import binding


def state(**changes):
    raw = dict(binding(), status='window_state_snapshot', minimized=True,
               list_bounds_usable=False, list_scroll_pattern=False, rows=3,
               text_rows=2, offscreen_text_rows=2, bounded_text_rows=0,
               text_pattern_rows=0, child_text_rows=0)
    raw.update(changes)
    return raw


class WindowStateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(live_read, 'window_state_report', None)),
                        'metadata-only window state diagnostic is not implemented')

    def test_fixed_report_omits_binding_and_never_claims_minimized_support(self):
        report = live_read.window_state_report(state())
        self.assertTrue(report['minimized'])
        self.assertEqual(report['text_rows'], 2)
        self.assertEqual(report['offscreen_text_rows'], 2)
        self.assertFalse(report['message_text_read'])
        self.assertFalse(report['minimized_reply_supported'])
        self.assertFalse(report['model_called'])
        self.assertNotIn('wxid_', json.dumps(report))
        self.assertNotIn('list_token', json.dumps(report))

    def test_malformed_counts_flags_and_extra_fields_are_rejected(self):
        changes = [{'rows':True},{'text_rows':4},{'rows':257},{'rows':-1},
                   {'offscreen_text_rows':3},{'bounded_text_rows':3},{'text_pattern_rows':3},
                   {'child_text_rows':3},{'minimized':1},{'list_bounds_usable':None},
                   {'list_scroll_pattern':[]},{'text':'PRIVATE'},{'status':'snapshot'}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(live_read.ReadError):
                live_read.window_state_report(state(**change))

    def test_diagnostic_cannot_enter_message_sessions(self):
        for session in (live_read.ReadSession(), live_read.VisualOccurrenceSession()):
            with self.assertRaises(live_read.ReadError):
                session.accept(state())

    def test_reader_requires_existing_binding_before_any_native_call(self):
        reader = live_read.NativeReader('fixture.exe')
        self.assertTrue(callable(getattr(reader,'read_window_state',None)))
        with patch.object(live_read.subprocess, 'run', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(live_read.ReadError, '^window_binding_unavailable$'):
                reader.read_window_state()

    def test_bound_diagnostic_uses_private_stdin_and_retains_binding(self):
        raw = state()
        reader = live_read.NativeReader('fixture.exe', expected_binding=binding())
        reader.executable = Path('never-executed.exe')
        done = subprocess.CompletedProcess([],0,json.dumps(raw).encode('utf-8'),b'')
        with patch.object(live_read.subprocess, 'run', return_value=done) as run:
            self.assertEqual(reader.read_window_state(), raw)
        self.assertEqual(run.call_args.args[0][-1], '--window-state')
        self.assertEqual(json.loads(run.call_args.kwargs['input']), binding())
        self.assertEqual(reader.binding, binding())

    def test_changed_binding_and_bad_diagnostic_do_not_replace_target(self):
        for raw, reason in ((state(window=99),'window_or_list_changed'),
                            (state(text='PRIVATE'),'native_reader_unavailable')):
            reader = live_read.NativeReader('fixture.exe', expected_binding=binding())
            reader.executable = Path('never-executed.exe')
            done = subprocess.CompletedProcess([],0,json.dumps(raw).encode('utf-8'),b'')
            with patch.object(live_read.subprocess, 'run', return_value=done):
                with self.assertRaisesRegex(live_read.ReadError, '^'+reason+'$'):
                    reader.read_window_state()
            self.assertEqual(reader.binding, binding())
