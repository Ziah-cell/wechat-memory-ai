"""Read-only admission must never mistake viewport novelty for freshness."""
import importlib
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from wechat_memory import live_read


def row(token, text='PRIVATE', direction='incoming_candidate', kind='text'):
    return dict(token=token, text=text, direction=direction, kind=kind)


def snapshot(*rows):
    return dict(status='visual_text_snapshot', process=12, started='123456',
                window=34, root='ChatSingleWindowwxid_fixture', list_token='list',
                rows=list(rows))


class PreflightTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module('wechat_memory.preflight')
        except ModuleNotFoundError:
            self.fail('The read-only preflight boundary is not implemented')

    def session(self):
        return self.module().PreflightSession()

    def armed(self):
        session = self.session()
        rows = [row('a'), row('b')]
        session.accept(snapshot(*rows))
        marker = row('m', session.challenge_text)
        rows.append(marker)
        self.assertEqual(session.accept(snapshot(*rows)), [])
        self.assertTrue(session.report()['marker_boundary_observed'])
        return session, rows

    def test_shared_filter_preserves_objects_order_duplicates_and_inputs(self):
        first = live_read.Observation('one', 'same', 'incoming_candidate')
        second = live_read.Observation('two', 'same', 'incoming_candidate')
        own = live_read.Observation('self', 'same', 'self_candidate')
        unknown = live_read.Observation('unknown', 'same', 'unknown')
        observations = [first, own, unknown, second, first]
        original_sequence = observations.copy()
        original_values = [vars(item).copy() for item in observations]
        result = self.module().filter_incoming(observations)
        self.assertEqual(len(result), 3)
        for actual, expected in zip(result, (first, second, first)):
            self.assertIs(actual, expected)
        self.assertEqual(len(observations), len(original_sequence))
        for actual, expected in zip(observations, original_sequence):
            self.assertIs(actual, expected)
        self.assertEqual([vars(item) for item in observations], original_values)
        self.assertEqual(self.module().filter_incoming([own, unknown]), [])

    def test_challenge_is_generated_only_after_nonempty_baseline_and_changes_on_restart(self):
        session = self.session()
        self.assertIsNone(session.challenge_text)
        session.accept(snapshot())
        self.assertIsNone(session.challenge_text)
        session.accept(snapshot(row('a'), row('b')))
        marker = session.challenge_text
        self.assertRegex(marker, r'^只读验证[0-9a-f]{16}$')
        self.assertEqual(session.accept(snapshot(row('a'), row('b'))), [])
        self.assertEqual(session.challenge_text, marker)
        another = self.session()
        another.accept(snapshot(row('a'), row('b'), row('m', marker)))
        self.assertNotEqual(another.challenge_text, marker)
        self.assertFalse(another.report()['marker_boundary_observed'])

    def test_history_scroll_shape_cannot_unlock_even_with_incoming_directions(self):
        for direction in ('unknown', 'incoming_candidate'):
            with self.subTest(direction=direction):
                session = self.session()
                session.accept(snapshot(row('a'), row('b'), row('c')))
                result = session.accept(snapshot(row('b'), row('c'),
                    row('d', 'old', direction), row('e', 'old', direction)))
                self.assertEqual(result, [])
                report = session.report()
                self.assertEqual(report['candidate_texts'], 2)
                self.assertEqual(report['pre_marker_discarded_texts'], 2)
                self.assertEqual(report['post_marker_incoming_candidates'], 0)
                self.assertEqual(report['preflight_state'], 'waiting_marker')

    def test_entire_marker_batch_is_discarded_then_only_subsequent_incoming_passes(self):
        session = self.session()
        rows = [row('a'), row('b')]
        session.accept(snapshot(*rows))
        rows += [row('c', 'old'), row('m', session.challenge_text),
                 row('time', 'time', 'unknown', 'other')]
        self.assertEqual(session.accept(snapshot(*rows)), [])
        self.assertIsNone(session.challenge_text)
        rows += [row('d', 'same'), row('e', 'same'), row('f', 'self', 'self_candidate'),
                 row('g', 'unclear', 'unknown'), row('space', ' ')]
        observations = session.accept(snapshot(*rows))
        self.assertEqual([item.text for item in observations], ['same', 'same'])
        self.assertEqual(len({item.observation_id for item in observations}), 2)
        report = session.report()
        self.assertEqual(report['pre_marker_discarded_texts'], 2)
        self.assertEqual(report['post_marker_incoming_candidates'], 2)
        self.assertEqual(report['filtered_self_texts'], 1)
        self.assertEqual(report['filtered_unknown_texts'], 1)
        for key in ('history_boundary_verified', 'sender_verified',
                    'server_message_ids_available', 'real_send_supported', 'model_called'):
            self.assertFalse(report[key])
        for private in ('PRIVATE', 'same', 'wxid_', '只读验证'):
            self.assertNotIn(private, json.dumps(report, ensure_ascii=False))

    def test_marker_in_generated_baseline_collision_stops_without_unlocking(self):
        module = self.module()
        with patch.object(module.secrets, 'token_hex', return_value='0'*16):
            session = module.PreflightSession()
            with self.assertRaises(live_read.ReadError):
                session.accept(snapshot(row('a'), row('m', '只读验证'+'0'*16)))
        self.assertEqual(session.report()['stop_reason'], 'preflight_marker_in_baseline')
        self.assertFalse(session.report()['marker_boundary_observed'])

    def test_self_unknown_duplicate_or_nonlast_marker_stops_atomically(self):
        for case in ('self_candidate', 'unknown', 'duplicate', 'nonlast'):
            with self.subTest(case=case):
                session = self.session()
                rows = [row('a'), row('b')]
                session.accept(snapshot(*rows))
                marker = session.challenge_text
                rows.append(row('m', marker, case if case in ('self_candidate', 'unknown')
                                else 'incoming_candidate'))
                if case == 'duplicate': rows.append(row('m2', marker))
                if case == 'nonlast': rows.append(row('c', 'after'))
                with self.assertRaises(live_read.ReadError): session.accept(snapshot(*rows))
                report = session.report()
                self.assertEqual(report['stop_reason'], 'preflight_marker_ambiguous')
                self.assertFalse(report['marker_boundary_observed'])
                self.assertEqual(report['post_marker_incoming_candidates'], 0)
                self.assertEqual(report['preflight_state'], 'closed')
                self.assertIsNone(session.challenge_text)

    def test_unknown_is_dropped_permanently_and_self_cannot_make_reply_loop(self):
        session, rows = self.armed()
        rows += [row('u', 'unclear', 'unknown'), row('s', 'self', 'self_candidate')]
        self.assertEqual(session.accept(snapshot(*rows)), [])
        rows[-2]['direction'] = 'incoming_candidate'
        self.assertEqual(session.accept(snapshot(*rows)), [])
        self.assertEqual(session.report()['post_marker_incoming_candidates'], 0)

    def test_repeated_marker_is_control_only_and_stops_without_partial_delivery(self):
        session, rows = self.armed()
        rows += [row('c', 'would pass'), row('again', rows[-1]['text'])]
        with self.assertRaises(live_read.ReadError): session.accept(snapshot(*rows))
        self.assertEqual(session.report()['stop_reason'], 'preflight_marker_repeated')
        self.assertEqual(session.report()['post_marker_incoming_candidates'], 0)

    def test_window_change_continuity_loss_and_explicit_stop_close_without_rearming(self):
        for failure in ('window', 'rows', 'explicit'):
            with self.subTest(failure=failure):
                session, rows = self.armed()
                raw = snapshot(*rows, row('next'))
                if failure == 'window': raw['window'] = 56
                if failure == 'rows': raw['rows'] = [row('x'), row('y')]
                if failure == 'explicit': session.stop('PRIVATE EXTERNAL ERROR')
                with self.assertRaises(live_read.ReadError): session.accept(raw)
                self.assertEqual(session.report()['preflight_state'], 'closed')
                self.assertEqual(session.report()['post_marker_incoming_candidates'], 0)
                self.assertIsNone(session.challenge_text)
                self.assertNotIn('PRIVATE', json.dumps(session.report()))

    def test_completion_closes_gate_and_rejects_further_accepts(self):
        session, rows = self.armed()
        session.close()
        self.assertEqual(session.report()['preflight_state'], 'closed')
        with self.assertRaises(live_read.ReadError): session.accept(snapshot(*rows, row('next')))
        self.assertEqual(session.report()['post_marker_incoming_candidates'], 0)

    def test_cli_challenge_once_and_target_counts_only_post_marker_incoming(self):
        module = self.module()
        marker = '只读验证'+'1'*16
        rows = [row('a'), row('b')]
        snapshots = [snapshot(*rows), snapshot(*rows)]
        rows = rows + [row('m', marker)]
        snapshots.append(snapshot(*rows))
        rows = rows + [row('s', 'PRIVATE', 'self_candidate'), row('u', 'PRIVATE', 'unknown')]
        snapshots.append(snapshot(*rows))
        snapshots.append(snapshot(*rows, row('c'), row('d')))
        stream = io.StringIO()
        with patch.object(module.secrets, 'token_hex', return_value='1'*16), \
                patch.object(live_read, 'NativeReader') as factory, redirect_stdout(stream), \
                redirect_stderr(io.StringIO()), patch.object(live_read.time, 'sleep'), \
                patch.object(live_read.time, 'monotonic', side_effect=[0,1,2,3,4,5]):
            reader = factory.return_value.__enter__.return_value
            reader.read.side_effect = snapshots
            result = live_read.main(['--client-path', 'fixture.exe', '--preflight',
                                     '--seconds', '3600', '--until-texts', '2'])
        self.assertEqual(result, 0)
        reports = [json.loads(line) for line in stream.getvalue().splitlines()]
        challenges = [item for item in reports if item['status'] == 'preflight_challenge']
        self.assertEqual(challenges, [dict(status='preflight_challenge', challenge=marker)])
        self.assertEqual(reports[-1]['post_marker_incoming_candidates'], 2)
        self.assertEqual(reports[-1]['completion_reason'], 'text_limit_reached')
        self.assertEqual(reports[-1]['preflight_state'], 'closed')
        self.assertEqual(reader.read.call_count, 5)
        self.assertTrue(all(call.kwargs == {'visual_text': True} for call in reader.read.call_args_list))
        self.assertNotIn('PRIVATE', stream.getvalue())
        self.assertNotIn('wxid_', stream.getvalue())
        self.assertEqual(factory.return_value.__exit__.call_count, 1)

    def test_cli_requires_bounded_time_and_cannot_combine_modes(self):
        self.module()
        for other in (['--seconds','0','--until-texts','2'], ['--observe-visual-occurrences'],
                      ['--inspect-visual'], ['--observe-occurrences']):
            with self.subTest(other=other), patch.object(live_read, 'NativeReader') as factory, \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                live_read.main(['--client-path', 'fixture.exe', '--preflight', *other])
            self.assertEqual(error.exception.code, 2)
            factory.assert_not_called()

    def test_cli_challenge_json_works_with_ascii_redirected_stdout(self):
        module = self.module()
        marker = '只读验证'+'3'*16
        output = io.BytesIO()
        stream = io.TextIOWrapper(output, encoding='ascii', write_through=True)
        with patch.object(module.secrets, 'token_hex', return_value='3'*16), \
                patch.object(live_read, 'NativeReader') as factory, redirect_stdout(stream), \
                patch.object(live_read.time, 'monotonic', side_effect=[0,1]):
            factory.return_value.__enter__.return_value.read.return_value = snapshot(row('a'), row('b'))
            result = live_read.main(['--client-path','fixture.exe','--preflight','--seconds','1'])
        reports = [json.loads(line) for line in output.getvalue().decode('ascii').splitlines()]
        self.assertEqual(result, 0)
        self.assertEqual(reports[0], dict(status='preflight_challenge', challenge=marker))
        self.assertEqual(reports[-1]['preflight_state'], 'closed')
        self.assertEqual(factory.return_value.__exit__.call_count, 1)
        self.assertNotIn('PRIVATE', output.getvalue().decode('ascii'))

    def test_cli_deadline_or_reader_error_never_leaves_gate_armed(self):
        module = self.module()
        for failed in (False, True):
            marker = '只读验证'+'2'*16
            rows = [row('a'), row('b')]
            snapshots = [snapshot(*rows), snapshot(*rows, row('m', marker))]
            if failed: snapshots.append(live_read.ReadError('window_minimized'))
            stream = io.StringIO()
            with patch.object(module.secrets, 'token_hex', return_value='2'*16), \
                    patch.object(live_read, 'NativeReader') as factory, redirect_stdout(stream), \
                    patch.object(live_read.time, 'sleep'), \
                    patch.object(live_read.time, 'monotonic', side_effect=[0,0,0 if failed else 2]):
                factory.return_value.__enter__.return_value.read.side_effect = snapshots
                result = live_read.main(['--client-path','fixture.exe','--preflight','--seconds','1'])
            report = json.loads(stream.getvalue().splitlines()[-1])
            self.assertEqual(report['preflight_state'], 'closed')
            self.assertEqual(report['post_marker_incoming_candidates'], 0)
            self.assertEqual(result, 3 if failed else 0)


if __name__ == '__main__': unittest.main()
