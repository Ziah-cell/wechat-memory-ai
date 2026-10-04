"""Offline countermodels for the pinned source audit, not a transport adapter.

Only small decision-rule projections are exercised; no upstream module is
imported or executed. Inputs are fictional. Passing means the documented gap
was reproduced, NOT that an upstream client or real message source passed.
Run from any directory with Python 3.11+; no network, config, UI or database.
"""
import io
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from wechat_memory.live_read import BackgroundOccurrenceSession, ReadError


def prefix_role(peer, label):
    # Projection of the binary display-label decision, not verified identity.
    return 'peer' if re.search(r'^' + re.escape(peer) + r'\s', label) else 'self'


def unseen_controls(previous_ids, rows):
    return [row for row in rows if row[0] not in previous_ids]


def count_tail_candidates(previous_ids, rows):
    # Relevant count-increase branch only; no claim to emulate the full client.
    increase = len(rows) - len(previous_ids)
    if increase <= 0:
        return unseen_controls(previous_ids, rows)
    tail_ids = [row[0] for row in rows[-increase:]]
    return [row for row in rows if row[0] in tail_ids]


def snapshot(*rows):
    return dict(status='background_text_snapshot', process=12, started='123456',
                window=34, root='ChatSingleWindowwxid_fixture', list_token='1.2.3',
                minimized=True,
                rows=[dict(token=token, text=text, kind='text') for token, text in rows])


class Countermodels(unittest.TestCase):
    def test_same_display_name_cannot_distinguish_self_from_peer(self):
        possible_inputs = [('self', 'Fixture Peer hello'), ('peer', 'Fixture Peer hello')]
        # Either role can have this display name; the observation is equal.
        self.assertEqual(possible_inputs[0][1], possible_inputs[1][1])
        self.assertEqual([prefix_role('Fixture Peer', label) for _, label in possible_inputs],
                         ['peer', 'peer'])
        self.assertNotEqual(prefix_role('Fixture Peer', possible_inputs[0][1]), possible_inputs[0][0])

    def test_nested_self_display_name_matches_peer_prefix(self):
        self.assertEqual(prefix_role('Fixture Peer', 'Fixture Peer Extra hello'), 'peer')

    def test_unknown_label_is_forced_to_self(self):
        self.assertEqual(prefix_role('Fixture Peer', 'unclassified label'), 'self')

    def test_reused_runtime_id_hides_changed_body(self):
        self.assertEqual(unseen_controls(['a', 'b'], [('b', 'anchor'), ('a', 'new body')]), [])

    def test_history_returning_to_viewport_is_reported_new(self):
        # Earlier viewport [a,b], then [b,c]; returning old a looks new.
        self.assertEqual(unseen_controls(['b', 'c'], [('c', 'current'), ('a', 'old body')]),
                         [('a', 'old body')])

    def test_history_prepend_is_not_distinguished_from_arrival(self):
        self.assertEqual(unseen_controls(['a', 'b'], [('h', 'history'), ('a', 'old'), ('b', 'last')]),
                         [('h', 'history')])

    def test_tail_only_mcp_projection_misses_a_burst(self):
        rows = [('a', 'baseline'), ('b', 'new1'), ('c', 'new2')]
        tail_observations = [rows[-1]] if rows[-1][0] != 'a' else []
        self.assertEqual(tail_observations, [('c', 'new2')])
        self.assertNotIn(('b', 'new1'), tail_observations)

    def test_count_growth_with_history_prepend_delivers_old_tail(self):
        rows = [('h', 'history'), ('a', 'old'), ('b', 'old tail')]
        self.assertEqual(count_tail_candidates(['a', 'b'], rows), [('b', 'old tail')])


class CurrentProjectGuards(unittest.TestCase):
    def test_prefix_and_self_looking_texts_still_have_unknown_direction(self):
        session = BackgroundOccurrenceSession()
        a, b = ('a', 'baseline'), ('b', 'anchor')
        session.accept(snapshot(a, b))
        events = session.accept(snapshot(a, b, ('c', 'Fixture Peer hello'), ('d', 'Fixture Self hello')))
        self.assertEqual([event.direction for event in events], ['unknown', 'unknown'])
        self.assertFalse(session.report()['sender_verified'])
        self.assertFalse(session.report()['history_boundary_verified'])

    def test_reused_token_with_new_body_is_only_unknown_occurrence(self):
        session = BackgroundOccurrenceSession()
        session.accept(snapshot(('a', 'old body'), ('b', 'anchor1'), ('c', 'anchor2')))
        events = session.accept(snapshot(('b', 'anchor1'), ('c', 'anchor2'), ('a', 'new body')))
        self.assertEqual([event.direction for event in events], ['unknown'])

    def test_old_occurrence_return_stops(self):
        session = BackgroundOccurrenceSession()
        a, b, c, d = ('a', 'old'), ('b', 'anchor1'), ('c', 'anchor2'), ('d', 'current')
        session.accept(snapshot(a, b, c))
        session.accept(snapshot(b, c, d))
        with self.assertRaises(ReadError):
            session.accept(snapshot(c, d, a))
        self.assertEqual(session.report()['stop_reason'], 'occurrence_reappeared')

    def test_history_prepend_stops_instead_of_delivering(self):
        session = BackgroundOccurrenceSession()
        a, b = ('a', 'old'), ('b', 'anchor')
        session.accept(snapshot(a, b))
        with self.assertRaises(ReadError):
            session.accept(snapshot(('h', 'history'), a, b))
        self.assertEqual(session.report()['stop_reason'], 'message_continuity_lost')


if __name__ == '__main__':
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(Countermodels),
        unittest.defaultTestLoader.loadTestsFromTestCase(CurrentProjectGuards)])
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = dict(scope='synthetic decision-rule projections and current pure-Python guards',
                  countermodels=8, current_guard_checks=4, checks_run=result.testsRun,
                  failures=len(result.failures), errors=len(result.errors),
                  successful=result.wasSuccessful(), upstream_code_executed=False,
                  network_used=False, native_or_ui_executed=False, model_called=False,
                  real_memory_written=False, message_sent=False,
                  cases=[test_id for test_id in stream.getvalue().splitlines() if test_id.startswith('test_')])
    print(json.dumps(report, indent=2))
    if not result.wasSuccessful():
        print(stream.getvalue(), file=sys.stderr)
    raise SystemExit(0 if result.wasSuccessful() else 1)
