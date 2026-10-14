"""Geometry diagnostics must explain rejection without changing message eligibility."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory import live_read
from wechat_memory.preflight import PreflightSession
from test_preflight import row, snapshot


DETAILS = ('image_missing', 'scale_invalid', 'list_size_invalid', 'row_width_below_minimum',
           'row_height_below_minimum', 'list_outside_frame', 'row_outside_list',
           'row_left_misaligned', 'row_right_misaligned')


def detailed(token, text='PRIVATE', detail='row_outside_list'):
    return dict(row(token, text, 'unknown'), reason='geometry_invalid', geometry_reason=detail)


class JointGeometryTests(unittest.TestCase):
    def valid(self, raw):
        try:
            return live_read.validate_visual_text_snapshot(raw)
        except live_read.ReadError:
            self.fail('Valid fixed geometry detail rejected')

    def test_fixed_details_normalize_to_the_existing_observation_contract(self):
        for detail in DETAILS:
            with self.subTest(detail=detail):
                raw = snapshot(detailed('a', detail=detail))
                before = copy.deepcopy(raw)
                self.assertEqual(self.valid(raw), live_read.validate_visual_text_snapshot(snapshot(row('a', 'PRIVATE', 'unknown'))))
                self.assertEqual(raw, before)
        for direction, reason, kind in (('incoming_candidate', 'incoming_evidence', 'text'),
                                        ('self_candidate', 'self_evidence', 'text'),
                                        ('unknown', 'not_text', 'other'),
                                        ('unknown', 'avatar_inconclusive', 'text')):
            raw = snapshot(dict(row('a', 'PRIVATE', direction, kind), reason=reason, geometry_reason=None))
            self.valid(raw)

    def test_detail_requires_matching_geometry_reason_and_fixed_string(self):
        invalid = [dict(detailed('a'), geometry_reason=value) for value in (None, '', 'PRIVATE_DETAIL', 1, True, [], {})]
        invalid += [dict(detailed('a'), reason='incoming_evidence', direction='incoming_candidate'),
                    dict(detailed('a'), reason='not_text', kind='other'),
                    dict(detailed('a'), reason='avatar_inconclusive')]
        no_reason = detailed('a')
        del no_reason['reason']
        invalid.append(no_reason)
        for value in invalid:
            with self.subTest(fields=value):
                session = live_read.VisualOccurrenceSession()
                with self.assertRaises(live_read.ReadError):
                    session.accept(snapshot(value))
                self.assertEqual(session.report()['status'], 'stopped')
                self.assertNotIn('PRIVATE', json.dumps(session.report()))

    def test_detailed_unknown_marker_remains_terminal_with_zero_delivery(self):
        for detail in DETAILS:
            session = PreflightSession()
            baseline = [row('a'), row('b')]
            session.accept(snapshot(*baseline))
            raw = snapshot(*baseline, detailed('m', session.challenge_text, detail))
            self.valid(raw)
            with self.assertRaisesRegex(live_read.ReadError, '^read_session_stopped$'):
                session.accept(raw)
            self.assertEqual(session.report()['stop_reason'], 'preflight_marker_ambiguous')
            self.assertFalse(session.report()['marker_boundary_observed'])
            self.assertEqual(session.report()['post_marker_incoming_candidates'], 0)

    def test_detail_change_does_not_replay_a_consumed_unknown_occurrence(self):
        session = live_read.VisualOccurrenceSession()
        baseline = [row('a'), row('b')]
        session.accept(snapshot(*baseline))
        raw = snapshot(*baseline, detailed('c'))
        self.valid(raw)
        observed = session.accept(raw)
        self.assertEqual([(item.text, item.direction) for item in observed], [('PRIVATE', 'unknown')])
        self.assertNotIn('geometry_reason', vars(observed[0]))
        raw['rows'][-1]['geometry_reason'] = 'row_height_below_minimum'
        self.assertEqual(session.accept(raw), [])
        raw['rows'][-1].update(direction='incoming_candidate', reason='incoming_evidence', geometry_reason=None)
        self.assertEqual(session.accept(raw), [])
        self.assertNotIn('PRIVATE', json.dumps(session.report()))

    def test_native_boundary_preserves_detail_without_retry_or_timing_leak(self):
        raw = snapshot(detailed('a'))
        self.valid(raw)
        binding = {key:raw[key] for key in ('process','started','window','root','list_token')}
        native = live_read.NativeReader('fixture.exe', expected_binding=binding)
        native.executable = Path('never-executed.exe')
        response = subprocess.CompletedProcess([], 0, json.dumps(raw).encode(), b'')
        with patch.object(live_read.subprocess, 'run', return_value=response):
            observed = native.read(visual_text=True)
        self.assertEqual(observed, raw)
        self.assertEqual(native.diagnostics['child_calls'], 1)
        self.assertEqual(native.snapshot_change_retries, 0)
        self.assertNotIn('PRIVATE', json.dumps(native.diagnostics))
        self.assertNotIn('row_outside_list', json.dumps(native.diagnostics))

    @unittest.skipUnless(os.name == 'nt', 'Windows compiler required')
    def test_pure_geometry_gates_keep_boundaries_and_report_first_failure(self):
        # Calls only scalar/Rectangle logic and Analyze(null), never a bitmap,
        # window, PrintWindow, UIA or the previously excluded native fixtures.
        root = Path(__file__).resolve().parents[1]
        framework = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319'
        expected = dict(normal='valid', missing='image_missing', nan='scale_invalid', infinite='scale_invalid',
                        small_scale='scale_invalid', large_scale='scale_invalid', empty_list='list_size_invalid',
                        narrow='row_width_below_minimum', short='row_height_below_minimum', list_outside='list_outside_frame',
                        row_above='row_outside_list', row_below='row_outside_list', left_gap='row_left_misaligned',
                        right_gap='row_right_misaligned', aligned_boundary='valid', scaled_minimum='valid',
                        scaled_short='row_height_below_minimum', scaled_narrow='row_width_below_minimum',
                        min_scale='valid', max_scale='valid', null_analysis='unknown/geometry_invalid/image_missing')
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory)/'geometry.exe'
            command = [str(framework/'csc.exe'), '/nologo', '/target:exe', '/out:'+str(exe),
                       '/reference:'+str(framework/'System.Drawing.dll'),
                       str(root/'src/wechat_memory/visual_direction.cs'), str(root/'tests/fixtures/geometry_contract.cs')]
            compiled = subprocess.run(command, capture_output=True, timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(compiled.returncode, 0, compiled.stdout.decode(errors='replace'))
            done = subprocess.run([str(exe)], capture_output=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))
            self.assertEqual(dict(line.split('=',1) for line in done.stdout.decode().splitlines()), expected)
