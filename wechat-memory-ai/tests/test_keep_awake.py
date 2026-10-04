"""Optional monitor power requests; every system call is replaced in these tests."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from wechat_memory import monitor
from wechat_memory.live_read import ReadError
from test_monitor import row, snapshot


class KeepAwakeTests(unittest.TestCase):
    def power(self):
        from wechat_memory import power
        return power

    def test_disabled_does_not_load_or_call_windows_api(self):
        power = self.power()
        with patch.object(power, '_set_execution_state', side_effect=AssertionError('unexpected API')):
            with power.KeepAwake(False) as request:
                self.assertFalse(request.active)

    def test_request_only_system_and_restore_prior_thread_state(self):
        power = self.power()
        for prior in (0x80000000, 0x80000002, 0x80000001):
            with self.subTest(prior=prior), patch.object(power, '_set_execution_state', return_value=prior) as api:
                with power.KeepAwake(True) as request:
                    self.assertTrue(request.active)
                self.assertFalse(request.active)
                self.assertEqual([c.args[0] for c in api.call_args_list], [0x80000001, prior])

    def test_body_failure_still_releases_request(self):
        power = self.power()
        with patch.object(power, '_set_execution_state', return_value=0x80000000) as api:
            with self.assertRaisesRegex(ReadError, 'window_or_list_changed'):
                with power.KeepAwake(True):
                    raise ReadError('window_or_list_changed')
            self.assertEqual(api.call_count, 2)

    def test_failed_acquisition_is_fixed_error_and_never_claims_active(self):
        power = self.power()
        for failure in (0, OSError('FICTIONAL_PRIVATE_ERROR')):
            with self.subTest(failure=type(failure).__name__):
                api = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
                request = power.KeepAwake(True)
                with patch.object(power, '_set_execution_state', api):
                    with self.assertRaisesRegex(power.PowerRequestError, '^keep_awake_failed$'):
                        with request:
                            self.fail('failed acquisition must not run body')
                self.assertFalse(request.active)
                self.assertEqual(api.call_count, 1)

    def test_release_failure_reported_without_masking_existing_read_error(self):
        power = self.power()
        for body_error in (None, ReadError('native_reader_timeout')):
            with self.subTest(body_error=body_error), patch.object(power, '_set_execution_state', side_effect=[0x80000000, 0]):
                expected = ReadError if body_error else power.PowerRequestError
                reason = 'native_reader_timeout' if body_error else 'keep_awake_failed'
                with self.assertRaisesRegex(expected, '^'+reason+'$'):
                    with power.KeepAwake(True):
                        if body_error:
                            raise body_error

    def test_monitor_holds_request_before_reader_and_releases_on_read_failure(self):
        power = self.power()
        events = []
        class Reader:
            snapshot_change_retries = 0
            def __init__(self, *_):
                events.append('reader')
            def __enter__(self): return self
            def __exit__(self, *_): events.append('reader_closed')
            def read_background_text(self): raise ReadError('native_reader_timeout')
        def api(flags):
            events.append(flags)
            return 0x80000000
        with tempfile.TemporaryDirectory() as directory, patch.object(power, '_set_execution_state', side_effect=api), patch.object(monitor, 'NativeReader', Reader):
            self.assertEqual(monitor.run_monitor('fixture.exe', directory, reader_mode='background', keep_awake=True), 3)
            status = monitor.monitor_status(directory)
        self.assertEqual(events, [0x80000001, 'reader', 'reader_closed', 0x80000000])
        self.assertEqual(status['stop_reason'], 'native_reader_timeout')
        self.assertTrue(status['keep_awake_requested'])
        self.assertFalse(status['keep_awake_request_active'])

    def test_power_failure_stops_before_reader_and_releases_instance_lock(self):
        power = self.power()
        with tempfile.TemporaryDirectory() as directory, patch.object(power, '_set_execution_state', return_value=0), patch.object(monitor, 'NativeReader') as reader:
            self.assertEqual(monitor.run_monitor('fixture.exe', directory, keep_awake=True), 3)
            reader.assert_not_called()
            status = monitor.monitor_status(directory)
            self.assertFalse(status['active'])
            self.assertEqual(status['stop_reason'], 'keep_awake_failed')
            self.assertNotIn('fixture.exe', json.dumps(status))

    def test_active_status_and_normal_stop_release_opt_in(self):
        power = self.power()
        observed = []
        with tempfile.TemporaryDirectory() as directory:
            class Reader:
                snapshot_change_retries = 0
                calls = 0
                def __init__(self, *_): pass
                def __enter__(self): return self
                def __exit__(self, *_): pass
                def read(self, **_):
                    self.calls += 1
                    if self.calls == 2:
                        observed.append(monitor.monitor_status(directory))
                        monitor.send_control(directory, 'stop')
                    return snapshot(row('a'))
            with patch.object(power, '_set_execution_state', return_value=0x80000000) as api, patch.object(monitor, 'NativeReader', Reader), patch.object(monitor.time, 'sleep'):
                self.assertEqual(monitor.run_monitor('fixture.exe', directory, keep_awake=True), 0)
                status = monitor.monitor_status(directory)
            self.assertTrue(observed[0]['keep_awake_request_active'])
            self.assertFalse(status['keep_awake_request_active'])
            self.assertEqual(status['stop_reason'], 'requested')
            self.assertEqual(status['snapshots'], 1)
            self.assertEqual(api.call_count, 2)

    def test_unsupported_platform_fails_only_when_enabled(self):
        power = self.power()
        with patch.object(power.os, 'name', 'posix'):
            with power.KeepAwake(False):
                pass
            with self.assertRaisesRegex(power.PowerRequestError, '^keep_awake_failed$'):
                with power.KeepAwake(True):
                    self.fail('unsupported platform')

    def test_status_request_is_boolean_and_never_active_after_process_exit(self):
        for active, requested, held, expected in ((True, True, True, True), (False, True, True, False),
                (True, 'private', True, False), (True, True, 'private', False), (True, False, True, False)):
            status = monitor._public_status(dict(active=active, keep_awake_requested=requested, keep_awake_request_active=held))
            self.assertEqual(status['keep_awake_request_active'], expected)
            self.assertEqual(status['keep_awake_requested'], requested is True)
            self.assertNotIn('private', json.dumps(status))
        self.assertFalse(monitor._public_status({})['keep_awake_requested'])

    def test_start_propagates_opt_in_to_hidden_child_only_when_enabled(self):
        for enabled in (False, True):
            token = 'a'*32
            statuses = [dict(active=False), dict(active=True, run_id=token, phase='observing')]
            with tempfile.TemporaryDirectory() as directory, patch.object(monitor, 'Controller', return_value=Mock(run_id=token)), patch.object(monitor, 'runtime_status', side_effect=statuses), patch.object(monitor.subprocess, 'Popen') as launch:
                code, _ = monitor._start('fixture.exe', directory, reader_mode='background', keep_awake=enabled)
                self.assertEqual(code, 0)
                self.assertEqual('--keep-awake' in launch.call_args.args[0], enabled)

    def test_start_cli_parses_explicit_opt_in_and_default_off(self):
        for extra, expected in (([], False), (['--keep-awake'], True)):
            with patch.object(monitor, '_start', return_value=(0, {})) as start, redirect_stdout(io.StringIO()):
                self.assertEqual(monitor.main(['start', '--client-path', 'fixture.exe', *extra]), 0)
                self.assertIs(start.call_args.kwargs['keep_awake'], expected)

    def test_invalid_option_never_acquires_power_request(self):
        power = self.power()
        for invalid in ('false', 0, 1, None, [], {}):
            with self.subTest(value=invalid), patch.object(power, '_set_execution_state') as api:
                with self.assertRaisesRegex(ValueError, '^invalid_keep_awake$'):
                    with power.KeepAwake(invalid):
                        pass
                api.assert_not_called()

    def test_invalid_monitor_options_rejected_before_file_or_process_creation(self):
        power = self.power()
        for invalid in ('false', 0, 1, None, [], {}):
            with self.subTest(value=invalid), tempfile.TemporaryDirectory() as temporary, patch.object(monitor, 'NativeReader') as reader, patch.object(monitor.subprocess, 'Popen') as launch, patch.object(power, '_set_execution_state', return_value=0x80000000) as api:
                directory = Path(temporary)/'not-created'
                self.assertEqual(monitor.run_monitor('fixture.exe', directory, keep_awake=invalid), 2)
                with self.assertRaisesRegex(ValueError, '^invalid_keep_awake$'):
                    monitor._start('fixture.exe', directory, keep_awake=invalid)
                self.assertFalse(directory.exists())
                reader.assert_not_called()
                launch.assert_not_called()
                api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
