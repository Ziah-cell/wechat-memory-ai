"""Keep the first accepted unknown reason without replaying or exposing messages."""
import copy
import json
import unittest

from wechat_memory.live_read import ReadError, VisualOccurrenceSession
import test_live_source as source_fixtures
from test_preflight import row, snapshot


def explained(token, text='PRIVATE_BODY', direction='unknown',
              reason='geometry_invalid', geometry='row_outside_list', kind='text'):
    return dict(row(token, text, direction, kind), reason=reason, geometry_reason=geometry)


class ObservationDiagnosticsTests(unittest.TestCase):
    def diagnostics(self, owner):
        method = getattr(owner, 'diagnostics', None)
        self.assertTrue(callable(method), 'A separate sanitized diagnostics snapshot is required')
        return method()

    def test_baselines_repaints_and_direction_upgrades_never_count_as_new_observations(self):
        session = VisualOccurrenceSession()
        session.accept(snapshot())
        rows = [row('a'), row('b')]
        session.accept(snapshot(*rows))
        rows.append(explained('u', reason='avatar_inconclusive', geometry=None))
        session.accept(snapshot(*rows))
        rows[-1]['reason'] = 'edges_inconsistent'
        self.assertEqual(session.accept(snapshot(*rows)), [])
        rows[-1].update(direction='self_candidate', reason='self_evidence')
        self.assertEqual(session.accept(snapshot(*rows)), [])
        report = self.diagnostics(session)
        self.assertEqual((report['snapshots'], report['observed_texts']), (5, 1))
        self.assertEqual(report['reason_counts']['avatar_inconclusive'], 1)
        self.assertEqual(sum(report['reason_counts'].values()), 1)
        self.assertEqual(report['first_unknown_batch']['snapshot'], 3)
        self.assertEqual(report['latest_unknown_batch']['snapshot'], 3)

    def test_equal_text_on_different_rows_keeps_exact_append_alignment_through_eviction(self):
        session = VisualOccurrenceSession()
        rows = [explained('a', 'SAME_PRIVATE', 'incoming_candidate', 'incoming_evidence', None),
                explained('b', 'SAME_PRIVATE', 'incoming_candidate', 'incoming_evidence', None)]
        session.accept(snapshot(*rows))
        rows += [explained('c', 'SAME_PRIVATE', 'self_candidate', 'self_evidence', None),
                 explained('d', 'SAME_PRIVATE'),
                 explained('e', 'PRIVATE_TIME', 'unknown', 'not_text', None, 'other'),
                 explained('f', '   ')]
        before = copy.deepcopy(rows)
        result = session.accept(snapshot(*rows))
        self.assertEqual([item.direction for item in result], ['self_candidate', 'unknown'])
        self.assertEqual(rows, before)
        rows = rows[1:] + [explained('g', 'SAME_PRIVATE', 'incoming_candidate', 'incoming_evidence', None)]
        self.assertEqual(len(session.accept(snapshot(*rows))), 1)
        report = self.diagnostics(session)
        self.assertEqual(report['observed_texts'], 3)
        self.assertEqual(sum(report['reason_counts'].values()), 3)
        for name in ('self_evidence', 'incoming_evidence', 'geometry_invalid'):
            self.assertEqual(report['reason_counts'][name], 1)
        self.assertEqual(report['geometry_reason_counts']['row_outside_list'], 1)
        self.assertEqual(report['first_unknown_batch']['unknown_texts'], 1)

    def test_legacy_missing_metadata_is_explicit_and_not_invented_as_geometry(self):
        session = VisualOccurrenceSession()
        rows = [row('a'), row('b')]
        session.accept(snapshot(*rows))
        legacy_geometry = explained('g')
        del legacy_geometry['geometry_reason']
        rows += [row('u', direction='unknown'), legacy_geometry, explained('h')]
        session.accept(snapshot(*rows))
        report = self.diagnostics(session)
        self.assertEqual(report['observed_texts'], 3)
        self.assertEqual(report['reason_unavailable_texts'], 1)
        self.assertEqual(report['geometry_detail_unavailable_texts'], 1)
        self.assertEqual(report['reason_counts']['geometry_invalid'], 2)
        self.assertEqual(sum(report['geometry_reason_counts'].values()), 1)
        batch = report['first_unknown_batch']
        self.assertEqual((batch['unknown_texts'], batch['reason_unavailable_texts'],
                          batch['geometry_detail_unavailable_texts']), (3, 1, 1))

    def test_first_and_latest_unknown_batches_survive_later_success_and_report_mutation(self):
        session = VisualOccurrenceSession()
        rows = [row('a'), row('b')]
        session.accept(snapshot(*rows))
        rows.append(explained('u'))
        session.accept(snapshot(*rows))
        rows.append(explained('v', reason='self_bubble_unconfirmed', geometry=None))
        session.accept(snapshot(*rows))
        rows.append(explained('s', direction='self_candidate', reason='self_evidence', geometry=None))
        session.accept(snapshot(*rows))
        before = self.diagnostics(session)
        self.assertEqual(before['first_unknown_batch']['snapshot'], 2)
        self.assertEqual(before['latest_unknown_batch']['snapshot'], 3)
        self.assertEqual(before['first_unknown_batch']['reason_counts']['geometry_invalid'], 1)
        self.assertEqual(before['latest_unknown_batch']['reason_counts']['self_bubble_unconfirmed'], 1)
        changed = self.diagnostics(session)
        changed['reason_counts']['geometry_invalid'] = 99
        changed['first_unknown_batch']['geometry_reason_counts']['row_outside_list'] = 99
        changed['latest_unknown_batch']['reason_counts'].clear()
        self.assertEqual(self.diagnostics(session), before)

    def test_rejected_metadata_binding_or_continuity_never_commits_diagnostics(self):
        for failure in ('metadata', 'binding', 'continuity'):
            with self.subTest(failure=failure):
                session = VisualOccurrenceSession()
                rows = [row('a'), row('b')]
                session.accept(snapshot(*rows))
                rows.append(explained('u'))
                session.accept(snapshot(*rows))
                before = self.diagnostics(session)
                raw = snapshot(*rows, explained('new'))
                if failure == 'metadata':
                    raw['rows'][-1]['reason'] = 'PRIVATE_UNTRUSTED_REASON'
                elif failure == 'binding':
                    raw['window'] = 99
                else:
                    raw['rows'] = [explained('unrelated'), explained('new')]
                with self.assertRaises(ReadError):
                    session.accept(raw)
                self.assertEqual(self.diagnostics(session), before)
                self.assertNotIn('PRIVATE', json.dumps(self.diagnostics(session)))

    def test_unknown_marker_reason_is_available_after_source_closes_without_another_read(self):
        with source_fixtures.LiveSourceTests().opened() as (source, reader, _, _):
            rows = [row('a'), row('b')]
            reader.read.return_value = snapshot(*rows)
            self.assertEqual(source.poll(), [])
            rows.append(explained('m', source.challenge_text))
            reader.read.return_value = snapshot(*rows)
            with self.assertRaisesRegex(ReadError, '^preflight_marker_ambiguous$'):
                source.poll()
            report = self.diagnostics(source)
            self.assertEqual(source.report()['state'], 'closed')
            self.assertEqual(report['first_unknown_batch']['snapshot'], 2)
            self.assertEqual(report['first_unknown_batch']['geometry_reason_counts']['row_outside_list'], 1)
            self.assertEqual(reader.read.call_count, 2)
            self.assertNotIn('first_unknown_batch', source.report())

    def test_source_diagnostics_preserve_filtering_delivery_lifecycle_and_privacy(self):
        with source_fixtures.LiveSourceTests().opened() as (source, reader, _, _):
            rows = [row('a'), row('b')]
            reader.read.return_value = snapshot(*rows)
            source.poll()
            marker = source.challenge_text
            rows.append(explained('m', marker, 'incoming_candidate', 'incoming_evidence', None))
            reader.read.return_value = snapshot(*rows)
            self.assertEqual(source.poll(), [])
            rows.append(explained('u', reason='avatar_inconclusive', geometry=None))
            reader.read.return_value = snapshot(*rows)
            self.assertEqual(source.poll(), [])
            rows[-1].update(direction='self_candidate', reason='self_evidence')
            reader.read.return_value = snapshot(*rows)
            self.assertEqual(source.poll(), [])
            rows.append(explained('i', 'PRIVATE_INCOMING', 'incoming_candidate', 'incoming_evidence', None))
            reader.read.return_value = snapshot(*rows)
            candidates = source.poll()
            self.assertEqual([item.text for item in candidates], ['PRIVATE_INCOMING'])
            self.assertTrue(source.is_current(candidates[0]))
            report = self.diagnostics(source)
            self.assertEqual((report['snapshots'], report['observed_texts']), (5, 3))
            self.assertEqual(report['reason_counts']['incoming_evidence'], 2)
            self.assertEqual(report['reason_counts']['avatar_inconclusive'], 1)
            self.assertEqual(report['reason_counts']['self_evidence'], 0)
            source.close()
            self.assertFalse(source.is_current(candidates[0]))
            self.assertEqual(self.diagnostics(source), report)
            self.assertEqual(reader.read.call_count, 5)
            for private in ('PRIVATE', 'wxid_', marker, candidates[0].source_id,
                            candidates[0].observation_id):
                self.assertNotIn(private, json.dumps(report))


if __name__ == '__main__':
    unittest.main()
