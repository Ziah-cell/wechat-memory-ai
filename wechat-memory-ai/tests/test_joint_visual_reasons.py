"""Same-frame reason metadata must not weaken admission or escape reports."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from wechat_memory import live_read
from wechat_memory.preflight import PreflightSession
from test_preflight import row, snapshot


REASONS = {
    'geometry_invalid': 'unknown', 'background_unsupported': 'unknown',
    'edges_inconsistent': 'unknown', 'avatar_inconclusive': 'unknown',
    'foreground_evidence_absent': 'unknown', 'incoming_bubble_unconfirmed': 'unknown',
    'incoming_green_conflict': 'unknown', 'self_bubble_unconfirmed': 'unknown',
    'incoming_evidence': 'incoming_candidate', 'self_evidence': 'self_candidate',
    'not_text': 'unknown',
}


def explained(token, text='PRIVATE', direction='incoming_candidate', reason='incoming_evidence', kind='text'):
    return dict(row(token, text, direction, kind), reason=reason)


class JointVisualReasonTests(unittest.TestCase):
    def accept_valid(self, raw):
        try:
            return live_read.validate_visual_text_snapshot(raw)
        except live_read.ReadError:
            self.fail('Valid same-frame reason metadata was rejected')

    def test_reason_metadata_preserves_legacy_observation_values_and_input(self):
        legacy = snapshot(row('a'), row('b', direction='unknown'))
        current = snapshot(explained('a'), explained('b', direction='unknown', reason='geometry_invalid'))
        before = copy.deepcopy(current)
        self.assertEqual(self.accept_valid(current), live_read.validate_visual_text_snapshot(legacy))
        self.assertEqual(current, before)

    def test_reason_direction_and_row_kind_must_agree_for_every_fixed_reason(self):
        for reason, expected in REASONS.items():
            for direction in ('incoming_candidate', 'self_candidate', 'unknown'):
                for kind in ('text', 'other'):
                    with self.subTest(reason=reason, direction=direction, kind=kind):
                        raw = snapshot(explained('a', direction=direction, reason=reason, kind=kind))
                        valid = direction == expected and ((kind == 'other') == (reason == 'not_text'))
                        if valid:
                            self.assertEqual(self.accept_valid(raw)[1][0][-1], direction)
                        else:
                            with self.assertRaisesRegex(live_read.ReadError, '^invalid_snapshot$'):
                                live_read.validate_visual_text_snapshot(raw)

    def test_untrusted_reason_or_extra_diagnostic_fields_remain_terminal_and_sanitized(self):
        for change in ({'reason': 'PRIVATE_REASON'}, {'reason': None}, {'reason': []},
                       {'reason': True}, {'pixels': 'PRIVATE_PIXELS'}):
            session = live_read.VisualOccurrenceSession()
            raw = snapshot(explained('a'))
            raw['rows'][0].update(change)
            with self.assertRaises(live_read.ReadError):
                session.accept(raw)
            self.assertEqual(session.report()['status'], 'stopped')
            self.assertNotIn('PRIVATE', json.dumps(session.report()))
            with self.assertRaises(live_read.ReadError):
                session.accept(snapshot(row('a')))

    def test_explained_unknown_marker_still_stops_without_admission(self):
        session = PreflightSession()
        baseline = [row('a'), row('b')]
        session.accept(snapshot(*baseline))
        marker = explained('m', session.challenge_text, 'unknown', 'incoming_bubble_unconfirmed')
        self.accept_valid(snapshot(*baseline, marker))
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot(*baseline, marker))
        report = session.report()
        self.assertEqual(report['stop_reason'], 'preflight_marker_ambiguous')
        self.assertFalse(report['marker_boundary_observed'])
        self.assertEqual(report['post_marker_incoming_candidates'], 0)
        self.assertEqual(report['preflight_state'], 'closed')

    def test_explained_rows_keep_self_filtering_incoming_delivery_and_zero_repeats(self):
        session = PreflightSession()
        rows = [row('a'), row('b')]
        session.accept(snapshot(*rows))
        rows.append(explained('m', session.challenge_text))
        self.accept_valid(snapshot(*rows))
        self.assertEqual(session.accept(snapshot(*rows)), [])
        rows.append(explained('self', 'PRIVATE_SELF', 'self_candidate', 'self_evidence'))
        self.assertEqual(session.accept(snapshot(*rows)), [])
        rows.append(explained('incoming', 'PRIVATE_INCOMING'))
        result = session.accept(snapshot(*rows))
        self.assertEqual([(item.text, item.direction) for item in result],
                         [('PRIVATE_INCOMING', 'incoming_candidate')])
        self.assertEqual(session.accept(snapshot(*rows)), [])
        report = session.report()
        self.assertEqual(report['filtered_self_texts'], 1)
        self.assertEqual(report['post_marker_incoming_candidates'], 1)
        self.assertNotIn('PRIVATE', json.dumps(report))
        self.assertNotIn('reason', vars(result[0]))

    def test_native_reader_preserves_same_frame_reason_but_not_in_public_timing_report(self):
        raw = snapshot(explained('a', 'PRIVATE_BODY', 'unknown', 'geometry_invalid'))
        self.accept_valid(raw)
        reader = live_read.NativeReader('fixture.exe')
        reader.executable = Path('never-executed.exe')
        done = subprocess.CompletedProcess([], 0, json.dumps(raw).encode(), b'')
        with patch.object(live_read.subprocess, 'run', return_value=done):
            observed = reader.read(visual_text=True)
        self.assertEqual(observed['rows'][0]['reason'], 'geometry_invalid')
        self.assertEqual(observed['rows'][0]['text'], 'PRIVATE_BODY')
        self.assertNotIn('PRIVATE', json.dumps(reader.diagnostics))


if __name__ == '__main__':
    unittest.main()
