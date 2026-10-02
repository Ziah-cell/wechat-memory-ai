"""A bound read-only source owns local candidates, never real transport events."""
import copy
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
import gc
import importlib
import json
from threading import Thread
import unittest
from unittest.mock import patch
import weakref

from wechat_memory.live_read import ReadError


def binding():
    return dict(process=12, started='123456', window=34,
                root='ChatSingleWindowwxid_fixture', list_token='list')


def row(token, text='PRIVATE', direction='incoming_candidate'):
    return dict(token=token, kind='text', text=text, direction=direction)


def snapshot(*rows, **changes):
    raw = dict(status='visual_text_snapshot', **binding(), rows=list(rows))
    raw.update(changes)
    return raw


class LiveSourceTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module('wechat_memory.live_source')
        except ModuleNotFoundError:
            self.fail('The bound read-only source is not implemented')

    @contextmanager
    def opened(self, seconds=300):
        module = self.module()
        clock = [10.0]
        with patch.object(module, 'NativeReader') as factory, \
                patch.object(module.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(module.time, 'time', return_value=1234567890.25):
            source = module.ReadOnlyWeChatSource('fixture.exe', expected_binding=binding(), seconds=seconds)
            reader = factory.return_value.__enter__.return_value
            with source:
                yield source, reader, clock, factory

    def armed(self, source, reader):
        rows = [row('a'), row('b')]
        reader.read.return_value = snapshot(*rows)
        self.assertEqual(source.poll(), [])
        self.assertIsNotNone(source.challenge_text)
        rows += [row('old'), row('marker', source.challenge_text)]
        reader.read.return_value = snapshot(*rows)
        self.assertEqual(source.poll(), [])
        self.assertIsNone(source.challenge_text)
        return rows

    def emit(self, source, reader):
        rows = self.armed(source, reader)
        reader.read.return_value = snapshot(*rows, row('new', 'PRIVATE NEW'))
        return source.poll()[0]

    def test_binding_is_required_validated_and_defensively_copied_before_first_read(self):
        module = self.module()
        with patch.object(module, 'NativeReader') as factory:
            with self.assertRaises(TypeError):
                module.ReadOnlyWeChatSource('fixture.exe')
            invalid = [None, {}, dict(binding(), extra='PRIVATE'), dict(binding(), process=True)]
            for value in invalid:
                with self.subTest(value_type=type(value).__name__), self.assertRaises(ReadError):
                    module.ReadOnlyWeChatSource('fixture.exe', expected_binding=value)
            factory.assert_not_called()
            supplied = binding()
            source = module.ReadOnlyWeChatSource('fixture.exe', expected_binding=supplied)
            supplied['window'] = 99
            with patch.object(module.time, 'monotonic', return_value=10.0), source:
                factory.assert_called_once_with('fixture.exe', expected_binding=binding())
                # NativeReader receives its own copy; its mutation cannot rebind the source.
                factory.call_args.kwargs['expected_binding']['window'] = 88
                reader = factory.return_value.__enter__.return_value
                reader.read.return_value = snapshot(row('a'))
                self.assertEqual(source.poll(), [])
                reader.read.assert_called_once_with(visual_text=True)

    def test_duration_requires_finite_nonboolean_number_within_bounds(self):
        module = self.module()
        with patch.object(module, 'NativeReader') as factory:
            for seconds in (0, -1, 0.5, 3600.1, True, False, '300', None, float('nan'), float('inf')):
                with self.subTest(seconds=seconds), self.assertRaisesRegex(ReadError, '^invalid_source_duration$'):
                    module.ReadOnlyWeChatSource('fixture.exe', expected_binding=binding(), seconds=seconds)
            factory.assert_not_called()
        for seconds in (1, 1.5, 3600):
            with self.opened(seconds=seconds) as (source, _, _, _):
                self.assertTrue(source.report()['active'])

    def test_source_enters_once_and_cannot_poll_before_enter_or_reopen(self):
        module = self.module()
        with patch.object(module, 'NativeReader') as factory, \
                patch.object(module.time, 'monotonic', return_value=10.0):
            source = module.ReadOnlyWeChatSource('fixture.exe', expected_binding=binding())
            with self.assertRaisesRegex(ReadError, '^source_not_active$'): source.poll()
            with source:
                with self.assertRaises(ReadError): source.__enter__()
                self.assertTrue(source.report()['active'])
            with self.assertRaisesRegex(ReadError, '^source_closed$'): source.poll()
            with self.assertRaisesRegex(ReadError, '^source_closed$'): source.__enter__()
            source.close()
            factory.assert_called_once()
            factory.return_value.__exit__.assert_called_once()

    def test_close_before_enter_is_terminal_without_constructing_reader(self):
        module = self.module()
        with patch.object(module, 'NativeReader') as factory:
            source = module.ReadOnlyWeChatSource('fixture.exe', expected_binding=binding())
            source.close()
            self.assertEqual(source.report()['state'], 'closed')
            with self.assertRaisesRegex(ReadError, '^source_closed$'): source.__enter__()
            factory.assert_not_called()

    def test_empty_baseline_marker_batch_and_duplicates_use_same_preflight(self):
        with self.opened() as (source, reader, _, _):
            reader.read.return_value = snapshot()
            self.assertEqual(source.poll(), [])
            self.assertIsNone(source.challenge_text)
            rows = self.armed(source, reader)
            rows += [row('one', 'same'), row('self', 'same', 'self_candidate'),
                     row('unknown', 'same', 'unknown'), row('two', 'same')]
            reader.read.return_value = snapshot(*rows)
            items = source.poll()
            self.assertEqual([item.text for item in items], ['same', 'same'])
            self.assertNotEqual(items[0].observation_id, items[1].observation_id)
            self.assertEqual(items[0].source_id, items[1].source_id)
            self.assertTrue(all(source.is_current(item) for item in items))
            self.assertEqual(source.report()['emitted_candidates'], 2)
            rows[-2]['direction'] = 'incoming_candidate'
            reader.read.return_value = snapshot(*rows)
            self.assertEqual(source.poll(), [])
            self.assertEqual(source.report()['emitted_candidates'], 2)

    def test_candidate_is_frozen_local_time_and_hides_private_fields_in_repr(self):
        module = self.module()
        with self.opened() as (source, reader, _, _):
            item = self.emit(source, reader)
            self.assertIs(type(item), module.LiveCandidate)
            self.assertEqual(item.observed_at, 1234567890.25)
            self.assertIs(type(item.observed_at), float)
            self.assertFalse(item.sender_verified)
            self.assertFalse(item.history_boundary_verified)
            self.assertFalse(hasattr(item, 'timestamp'))
            with self.assertRaises(FrozenInstanceError): item.text = 'changed'
            with self.assertRaises(ValueError): replace(item, sender_verified=True)
            with self.assertRaises(TypeError):
                module.LiveCandidate(item.source_id, item.observation_id, item.text,
                                     item.observed_at, sender_verified=True)
            for private in (item.text, item.source_id, item.observation_id, 'wxid_'):
                self.assertNotIn(private, repr(item))
                self.assertNotIn(private, json.dumps(source.report()))

    def test_only_exact_issued_objects_are_current_and_close_invalidates(self):
        module = self.module()
        with self.opened() as (source, reader, _, _):
            item = self.emit(source, reader)
            fabricated = module.LiveCandidate(item.source_id, item.observation_id, item.text, item.observed_at)
            for other in (fabricated, copy.copy(item), copy.deepcopy(item), replace(item), None, object()):
                self.assertFalse(source.is_current(other))
            self.assertTrue(source.is_current(item))
            source.close()
            self.assertFalse(source.is_current(item))
            self.assertIsNone(source.challenge_text)

    def test_issued_registry_does_not_retain_delivered_plaintext_objects(self):
        with self.opened() as (source, reader, _, _):
            item = self.emit(source, reader)
            reference = weakref.ref(item)
            self.assertTrue(source.is_current(item))
            del item
            gc.collect()
            self.assertIsNone(reference())
            self.assertEqual(source.report()['emitted_candidates'], 1)

    def test_expiry_before_read_does_not_read_and_invalidates_issued_objects(self):
        with self.opened(seconds=5) as (source, reader, clock, factory):
            item = self.emit(source, reader)
            before = reader.read.call_count
            clock[0] = 15.0
            with self.assertRaisesRegex(ReadError, '^source_deadline_reached$'): source.poll()
            self.assertEqual(reader.read.call_count, before)
            self.assertFalse(source.is_current(item))
            self.assertEqual(source.report()['state'], 'closed')
            factory.return_value.__exit__.assert_called_once()

    def test_expiry_during_read_discards_whole_batch_before_preflight_accept(self):
        with self.opened(seconds=5) as (source, reader, clock, _):
            rows = self.armed(source, reader)
            before = source.report()['snapshots']
            def finish_late(**kwargs):
                self.assertEqual(kwargs, {'visual_text': True})
                clock[0] = 15.0
                return snapshot(*rows, row('new'))
            reader.read.side_effect = finish_late
            with self.assertRaisesRegex(ReadError, '^source_deadline_reached$'): source.poll()
            self.assertEqual(source.report()['emitted_candidates'], 0)
            self.assertEqual(source.report()['snapshots'], before)

    def test_current_query_observes_expiry_without_another_poll(self):
        with self.opened(seconds=5) as (source, reader, clock, _):
            item = self.emit(source, reader)
            clock[0] = 15.0
            self.assertFalse(source.is_current(item))
            self.assertFalse(source.report()['active'])
            self.assertEqual(source.report()['state'], 'closed')

    def test_wrong_binding_is_rejected_before_session_baseline(self):
        with self.opened() as (source, reader, _, _):
            reader.read.return_value = snapshot(row('private'), window=99)
            with self.assertRaisesRegex(ReadError, '^window_or_list_changed$'): source.poll()
            self.assertEqual(source.report()['snapshots'], 0)
            self.assertEqual(source.report()['emitted_candidates'], 0)
            self.assertIsNone(source.challenge_text)

    def test_reader_errors_close_and_never_expose_external_messages(self):
        for error, expected in ((ReadError('window_minimized'), 'window_minimized'),
                                (ReadError('PRIVATE'), 'source_read_failed'),
                                (RuntimeError('PRIVATE'), 'source_read_failed')):
            with self.subTest(expected=expected), self.opened() as (source, reader, _, factory):
                item = self.emit(source, reader)
                reader.read.side_effect = error
                with self.assertRaisesRegex(ReadError, '^'+expected+'$'): source.poll()
                self.assertFalse(source.is_current(item))
                self.assertNotIn('PRIVATE', json.dumps(source.report()))
                factory.return_value.__exit__.assert_called_once()

    def test_unknown_marker_closes_source_without_emitting(self):
        with self.opened() as (source, reader, _, _):
            rows = [row('a'), row('b')]
            reader.read.return_value = snapshot(*rows)
            source.poll()
            reader.read.return_value = snapshot(*rows, row('marker', source.challenge_text, 'unknown'))
            with self.assertRaisesRegex(ReadError, '^preflight_marker_ambiguous$'): source.poll()
            self.assertEqual(source.report()['state'], 'closed')
            self.assertEqual(source.report()['emitted_candidates'], 0)

    def test_invalid_local_wall_time_discards_batch_and_closes(self):
        module = self.module()
        for value in (float('nan'), float('inf'), -1.0, True, 'PRIVATE'):
            with self.subTest(value_type=type(value).__name__), self.opened() as (source, reader, _, _):
                rows = self.armed(source, reader)
                reader.read.return_value = snapshot(*rows, row('new'))
                with patch.object(module.time, 'time', return_value=value), \
                        self.assertRaisesRegex(ReadError, '^source_observation_time_invalid$'):
                    source.poll()
                self.assertEqual(source.report()['emitted_candidates'], 0)
                self.assertEqual(source.report()['state'], 'closed')

    def test_invalid_monotonic_clock_closes_before_reader_construction(self):
        module = self.module()
        for value in (float('nan'), float('inf'), True, 'PRIVATE'):
            with self.subTest(value_type=type(value).__name__), patch.object(module, 'NativeReader') as factory, \
                    patch.object(module.time, 'monotonic', return_value=value):
                source = module.ReadOnlyWeChatSource('fixture.exe', expected_binding=binding())
                with self.assertRaisesRegex(ReadError, '^source_clock_invalid$'): source.__enter__()
                self.assertEqual(source.report()['state'], 'closed')
                factory.assert_not_called()

    def test_enter_failure_is_terminal_and_does_not_call_unentered_exit(self):
        module = self.module()
        with patch.object(module, 'NativeReader') as factory, \
                patch.object(module.time, 'monotonic', return_value=10.0):
            factory.return_value.__enter__.side_effect = RuntimeError('PRIVATE')
            source = module.ReadOnlyWeChatSource('fixture.exe', expected_binding=binding())
            with self.assertRaisesRegex(ReadError, '^source_open_failed$'): source.__enter__()
            self.assertEqual(source.report()['state'], 'closed')
            factory.return_value.__exit__.assert_not_called()
            with self.assertRaisesRegex(ReadError, '^source_closed$'): source.__enter__()

    def test_expiry_while_opening_cleans_up_the_entered_reader(self):
        module = self.module()
        clock = [10.0]
        with patch.object(module, 'NativeReader') as factory, \
                patch.object(module.time, 'monotonic', side_effect=lambda: clock[0]):
            def entered():
                clock[0] = 15.0
                return factory.return_value
            factory.return_value.__enter__.side_effect = entered
            source = module.ReadOnlyWeChatSource('fixture.exe', expected_binding=binding(), seconds=5)
            with self.assertRaisesRegex(ReadError, '^source_deadline_reached$'): source.__enter__()
            self.assertEqual(source.report()['state'], 'closed')
            factory.return_value.__exit__.assert_called_once()
            factory.return_value.read.assert_not_called()

    def test_interrupt_during_read_closes_without_swallowing_interrupt(self):
        with self.opened() as (source, reader, _, factory):
            item = self.emit(source, reader)
            reader.read.side_effect = KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt): source.poll()
            self.assertFalse(source.is_current(item))
            self.assertEqual(source.report()['stop_reason'], 'interrupted')
            factory.return_value.__exit__.assert_called_once()

    def test_owner_thread_checks_enter_poll_and_close_without_touching_reader(self):
        with self.opened() as (source, reader, _, factory):
            errors = []
            def other_thread():
                for action in (source.__enter__, source.poll, source.close):
                    try: action()
                    except ReadError as error: errors.append(str(error))
            thread = Thread(target=other_thread)
            thread.start()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, ['source_owner_thread_required']*3)
            reader.read.assert_not_called()
            factory.return_value.__exit__.assert_not_called()
            self.assertTrue(source.report()['active'])

    def test_reentrant_poll_is_rejected_and_outer_read_closes(self):
        with self.opened() as (source, reader, _, _):
            reader.read.side_effect = lambda **kwargs: source.poll()
            with self.assertRaisesRegex(ReadError, '^source_operation_in_progress$'): source.poll()
            self.assertEqual(reader.read.call_count, 1)
            self.assertEqual(source.report()['state'], 'closed')

    def test_cleanup_failure_still_revokes_objects_and_does_not_retry_cleanup(self):
        with self.opened() as (source, reader, _, factory):
            item = self.emit(source, reader)
            factory.return_value.__exit__.side_effect = OSError('PRIVATE')
            with self.assertRaisesRegex(ReadError, '^reader_cleanup_failed$'): source.close()
            self.assertFalse(source.is_current(item))
            source.close()
            factory.return_value.__exit__.assert_called_once()
            self.assertNotIn('PRIVATE', json.dumps(source.report()))

    def test_context_exception_is_not_suppressed_and_closes_source(self):
        module = self.module()
        with patch.object(module, 'NativeReader') as factory, \
                patch.object(module.time, 'monotonic', return_value=10.0):
            source = module.ReadOnlyWeChatSource('fixture.exe', expected_binding=binding())
            with self.assertRaisesRegex(ValueError, '^consumer failure$'):
                with source:
                    raise ValueError('consumer failure')
            self.assertFalse(source.report()['active'])
            factory.return_value.__exit__.assert_called_once()

    def test_send_always_rejects_without_reading_changing_state_or_calling_native_send(self):
        module = self.module()
        with patch.object(module, 'NativeReader') as factory, \
                patch.object(module.time, 'monotonic', return_value=10.0):
            source = module.ReadOnlyWeChatSource('fixture.exe', expected_binding=binding())
            for phase in ('new', 'active', 'closed'):
                if phase == 'active': source.__enter__()
                if phase == 'closed': source.close()
                before = source.report()
                with self.assertRaisesRegex(ReadError, '^real_send_disabled$'):
                    source.send(object(), 'PRIVATE', unexpected=True)
                self.assertEqual(source.report(), before)
            factory.return_value.__enter__.return_value.read.assert_not_called()
            factory.return_value.__enter__.return_value.send.assert_not_called()


if __name__ == '__main__': unittest.main()
