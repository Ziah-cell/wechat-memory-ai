"""Bound joint reads resample only torn snapshots within one shared time budget."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from wechat_memory import live_read


def binding():
    return dict(process=12, started='123456', window=34,
                root='ChatSingleWindowwxid_fixture', list_token='1.2.3')


def snapshot(*tokens, **changes):
    raw = dict(binding(), status='visual_text_snapshot', rows=[
        dict(token=token, kind='text', text='PRIVATE BODY '+token, direction='incoming_candidate')
        for token in tokens])
    raw.update(changes)
    return raw


def result(raw, code=0):
    return subprocess.CompletedProcess([], code, json.dumps(raw).encode('utf-8'), b'')


def failure(reason='visual_snapshot_changed'):
    return result(dict(status='reader_error', reason=reason), 3)


def reader(*, bound=True):
    value = live_read.NativeReader('D:/Weixin.exe', expected_binding=binding() if bound else None)
    value.executable = Path('never-executed.exe')
    return value


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class VisualResampleTests(unittest.TestCase):
    def test_bound_torn_snapshot_recovers_without_changing_the_session_checkpoint(self):
        native, clock = reader(), Clock()
        session = live_read.VisualOccurrenceSession()
        self.assertEqual(session.accept(snapshot('a', 'b')), [])
        before = session.report()
        responses = [failure(), result(snapshot('a', 'b', 'c'))]
        calls = []

        def run(command, **kwargs):
            self.assertEqual(session.report(), before)
            calls.append((command, kwargs))
            clock.now += 0.2
            return responses.pop(0)

        output, errors = io.StringIO(), io.StringIO()
        with patch.object(live_read.subprocess, 'run', side_effect=run), \
                patch.object(live_read.time, 'monotonic', side_effect=clock.monotonic), \
                patch.object(live_read.time, 'sleep', side_effect=clock.sleep), \
                redirect_stdout(output), redirect_stderr(errors):
            raw = native.read(visual_text=True)
        self.assertEqual(session.report(), before)
        observations = session.accept(raw)
        self.assertEqual([item.text for item in observations], ['PRIVATE BODY c'])
        self.assertEqual(session.report()['snapshots'], 2)
        self.assertEqual(session.report()['candidate_texts'], 1)
        self.assertEqual(len(calls), 2)
        for command, kwargs in calls:
            self.assertEqual(command[-1], '--visual-text')
            self.assertEqual(json.loads(kwargs['input']), binding())
        self.assertEqual(native.binding, binding())
        self.assertEqual(native.snapshot_change_retries, 1)
        self.assertEqual(output.getvalue()+errors.getvalue(), '')

    def test_three_torn_children_stop_with_the_original_error_and_no_rebinding(self):
        native, clock = reader(), Clock()
        with patch.object(live_read.subprocess, 'run', return_value=failure()) as run, \
                patch.object(live_read.time, 'monotonic', side_effect=clock.monotonic), \
                patch.object(live_read.time, 'sleep', side_effect=clock.sleep):
            with self.assertRaises(live_read.ReadError) as error:
                native.read(visual_text=True)
        self.assertEqual(str(error.exception), 'visual_snapshot_changed')
        self.assertEqual(run.call_count, 3)
        self.assertEqual(clock.sleeps, [0.05, 0.05])
        self.assertEqual(native.snapshot_change_retries, 2)
        self.assertEqual(native.binding, binding())

    def test_child_time_and_waits_reduce_one_original_eight_second_budget(self):
        native, clock = reader(), Clock()
        responses = [(2.0, failure()), (1.0, failure()), (0.1, result(snapshot('a')))]
        timeouts = []

        def run(command, **kwargs):
            timeouts.append(kwargs['timeout'])
            duration, response = responses.pop(0)
            clock.now += duration
            return response

        with patch.object(live_read.subprocess, 'run', side_effect=run), \
                patch.object(live_read.time, 'monotonic', side_effect=clock.monotonic), \
                patch.object(live_read.time, 'sleep', side_effect=clock.sleep):
            self.assertEqual(native.read(visual_text=True), snapshot('a'))
        self.assertEqual(len(timeouts), 3)
        for actual, expected in zip(timeouts, (8.0, 5.95, 4.9)):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(clock.sleeps, [0.05, 0.05])
        self.assertEqual(native.snapshot_change_retries, 2)

    def test_wait_is_capped_by_remaining_budget_and_no_child_starts_after_expiry(self):
        native, clock = reader(), Clock()

        def run(command, **kwargs):
            clock.now += 7.98
            return failure()

        with patch.object(live_read.subprocess, 'run', side_effect=run) as run_call, \
                patch.object(live_read.time, 'monotonic', side_effect=clock.monotonic), \
                patch.object(live_read.time, 'sleep', side_effect=clock.sleep):
            with self.assertRaises(live_read.ReadError) as error:
                native.read(visual_text=True)
        self.assertEqual(str(error.exception), 'native_reader_timeout')
        self.assertEqual(run_call.call_count, 1)
        self.assertEqual(len(clock.sleeps), 1)
        self.assertAlmostEqual(clock.sleeps[0], 0.02)
        self.assertEqual(native.snapshot_change_retries, 0)
        self.assertEqual(native.binding, binding())

    def test_exhausted_budget_does_not_wait_or_start_another_child(self):
        native, clock = reader(), Clock()

        def run(command, **kwargs):
            clock.now = 8.0
            return failure()

        with patch.object(live_read.subprocess, 'run', side_effect=run) as run_call, \
                patch.object(live_read.time, 'monotonic', side_effect=clock.monotonic), \
                patch.object(live_read.time, 'sleep', side_effect=clock.sleep):
            with self.assertRaises(live_read.ReadError) as error:
                native.read(visual_text=True)
        self.assertEqual(str(error.exception), 'native_reader_timeout')
        self.assertEqual(run_call.call_count, 1)
        self.assertEqual(clock.sleeps, [])
        self.assertEqual(native.snapshot_change_retries, 0)

    def test_success_returned_after_the_shared_deadline_is_not_delivered(self):
        native, clock = reader(), Clock()

        def run(command, **kwargs):
            clock.now = 8.01
            return result(snapshot('a'))

        with patch.object(live_read.subprocess, 'run', side_effect=run) as run_call, \
                patch.object(live_read.time, 'monotonic', side_effect=clock.monotonic), \
                patch.object(live_read.time, 'sleep', side_effect=clock.sleep):
            with self.assertRaises(live_read.ReadError) as error:
                native.read(visual_text=True)
        self.assertEqual(str(error.exception), 'native_reader_timeout')
        self.assertEqual(run_call.call_count, 1)
        self.assertEqual(clock.sleeps, [])
        self.assertEqual(native.snapshot_change_retries, 0)

    def test_other_native_errors_timeouts_protocol_errors_and_binding_changes_are_not_retried(self):
        cases = [
            (failure('window_minimized'), 'window_minimized'),
            (failure('window_or_list_changed'), 'window_or_list_changed'),
            (failure('visual_capture_unavailable'), 'visual_capture_unavailable'),
            (failure('PRIVATE BODY'), 'native_reader_unavailable'),
            (result(dict(status='reader_error', reason='visual_snapshot_changed', text='PRIVATE BODY'), 3),
             'native_reader_unavailable'),
            (result(snapshot('a', window=99)), 'window_or_list_changed'),
            (result(snapshot('a', status='snapshot')), 'native_reader_unavailable'),
            (subprocess.CompletedProcess([], 0, b'PRIVATE BODY', b'PRIVATE ERROR'), 'native_reader_unavailable'),
            (subprocess.TimeoutExpired('PRIVATE COMMAND', 8, output=b'PRIVATE BODY'), 'native_reader_timeout'),
            (OSError('PRIVATE ERROR'), 'native_reader_unavailable'),
        ]
        for response, reason in cases:
            with self.subTest(reason=reason):
                native, clock = reader(), Clock()
                output, errors = io.StringIO(), io.StringIO()
                with patch.object(live_read.subprocess, 'run', side_effect=[response]) as run, \
                        patch.object(live_read.time, 'monotonic', side_effect=clock.monotonic), \
                        patch.object(live_read.time, 'sleep', side_effect=clock.sleep), \
                        redirect_stdout(output), redirect_stderr(errors):
                    with self.assertRaises(live_read.ReadError) as error:
                        native.read(visual_text=True)
                self.assertEqual(str(error.exception), reason)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(clock.sleeps, [])
                self.assertEqual(native.snapshot_change_retries, 0)
                self.assertEqual(native.binding, binding())
                self.assertEqual(output.getvalue()+errors.getvalue(), '')

    def test_plain_diagnostics_and_first_unbound_joint_read_keep_one_exact_eight_second_call(self):
        cases = [(True, {}), (True, dict(layout=True)), (True, dict(capabilities=True)),
                 (True, dict(visual=True)), (False, dict(visual_text=True))]
        for bound, options in cases:
            with self.subTest(bound=bound, options=options):
                native = reader(bound=bound)
                with patch.object(live_read.subprocess, 'run', return_value=failure()) as run, \
                        patch.object(live_read.time, 'monotonic') as monotonic, \
                        patch.object(live_read.time, 'sleep') as sleep:
                    with self.assertRaises(live_read.ReadError) as error:
                        native.read(**options)
                self.assertEqual(str(error.exception), 'visual_snapshot_changed')
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.kwargs['timeout'], 8)
                self.assertEqual(native.snapshot_change_retries, 0)
                monotonic.assert_not_called()
                sleep.assert_not_called()

    def test_learned_binding_enables_retries_on_later_reads_and_counter_is_cumulative(self):
        native, clock = reader(bound=False), Clock()
        responses = [result(snapshot('a')), failure(), result(snapshot('a', 'b')),
                     failure(), result(snapshot('a', 'b', 'c'))]
        with patch.object(live_read.subprocess, 'run', side_effect=responses) as run, \
                patch.object(live_read.time, 'monotonic', side_effect=clock.monotonic), \
                patch.object(live_read.time, 'sleep', side_effect=clock.sleep):
            self.assertEqual(native.read(visual_text=True), snapshot('a'))
            self.assertEqual(native.read(visual_text=True), snapshot('a', 'b'))
            self.assertEqual(native.read(visual_text=True), snapshot('a', 'b', 'c'))
        inputs = [json.loads(call.kwargs['input']) for call in run.call_args_list]
        self.assertEqual(inputs, [None, binding(), binding(), binding(), binding()])
        self.assertEqual(native.snapshot_change_retries, 2)
        with self.assertRaises(AttributeError):
            native.snapshot_change_retries = 0

    def test_changed_binding_after_a_transient_is_not_retried_or_committed(self):
        native, clock = reader(), Clock()
        with patch.object(live_read.subprocess, 'run',
                          side_effect=[failure(), result(snapshot('a', window=99))]) as run, \
                patch.object(live_read.time, 'monotonic', side_effect=clock.monotonic), \
                patch.object(live_read.time, 'sleep', side_effect=clock.sleep):
            with self.assertRaises(live_read.ReadError) as error:
                native.read(visual_text=True)
        self.assertEqual(str(error.exception), 'window_or_list_changed')
        self.assertEqual(run.call_count, 2)
        self.assertEqual(native.snapshot_change_retries, 1)
        self.assertEqual(native.binding, binding())


if __name__ == '__main__':
    unittest.main()
