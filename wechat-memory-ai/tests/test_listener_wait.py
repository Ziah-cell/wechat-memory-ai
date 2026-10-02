"""Bounded live acceptance waits must distinguish arrivals from time expiry."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from wechat_memory import live_read

ROOT = Path(__file__).resolve().parents[1]


def row(token, text='PRIVATE', kind='text'):
    return dict(token=token, text=text, kind=kind)


def snapshot(*rows):
    return dict(status='snapshot', process=12, started='123456', window=34,
                root='ChatSingleWindowwxid_fixture', list_token='list', rows=list(rows))


class ListenerWaitTests(unittest.TestCase):
    def run_listener(self, snapshots, arguments, clock):
        stream = io.StringIO()
        with patch.object(live_read, 'NativeReader') as factory, redirect_stdout(stream), \
                patch.object(live_read.time, 'sleep'), \
                patch.object(live_read.time, 'monotonic', side_effect=clock):
            reader = factory.return_value.__enter__.return_value
            reader.read.side_effect = snapshots
            with redirect_stderr(io.StringIO()):
                try:
                    result = live_read.main(['--client-path', 'fixture.exe', *arguments])
                except SystemExit as error:
                    self.fail(f'Valid listener arguments were rejected with exit code {error.code}')
        self.assertEqual(factory.return_value.__exit__.call_count, 1)
        self.assertNotIn('PRIVATE', stream.getvalue())
        self.assertNotIn('wxid_', stream.getvalue())
        return result, [json.loads(line) for line in stream.getvalue().splitlines()], reader

    def test_target_ignores_baseline_blank_and_nontext_and_keeps_both_duplicates(self):
        a, b = row('a'), row('b')
        c, d = row('c', 'PRIVATE timestamp', 'other'), row('d', '  ')
        snapshots = [snapshot(a,b), snapshot(a,b,c,d), snapshot(a,b,c,d,row('e')),
                     snapshot(a,b,c,d,row('e'),row('f'))]
        code, reports, reader = self.run_listener(snapshots,
            ['--seconds','3600','--until-texts','2'], [0,1,2,3,4])
        self.assertEqual(code, 0)
        self.assertEqual(reader.read.call_count, 4)
        self.assertEqual([r['observed_new_texts'] for r in reports], [0,0,1,2])
        self.assertEqual(reports[-1]['completion_reason'], 'text_limit_reached')
        self.assertEqual(reports[-1]['status'], 'completed')
        self.assertNotIn('completion_reason', reports[0])

    def test_target_preserves_whole_accepted_batch_in_all_observation_modes(self):
        for mode in ([], ['--observe-occurrences'], ['--observe-visual-occurrences']):
            with self.subTest(mode=mode):
                snapshots = [snapshot(row('a'),row('b')),
                             snapshot(row('a'),row('b'),row('c'),row('d'),row('e'))]
                if mode == ['--observe-visual-occurrences']:
                    for raw in snapshots:
                        raw['status'] = 'visual_text_snapshot'
                        for item in raw['rows']: item['direction'] = 'incoming_candidate'
                code, reports, reader = self.run_listener(snapshots,
                    [*mode,'--seconds','3600','--until-texts','2'], [0,1,2])
                self.assertEqual(code, 0)
                key = 'candidate_texts' if mode else 'observed_new_texts'
                self.assertEqual(reports[-1][key], 3)
                self.assertEqual(reports[-1]['completion_reason'], 'text_limit_reached')
                self.assertFalse(reports[-1]['real_send_supported'])
                self.assertFalse(reports[-1]['model_called'])
                self.assertEqual(reader.read.call_count, 2)

    def test_deadline_without_arrivals_is_not_reported_as_target_reached(self):
        code, reports, _ = self.run_listener([snapshot(row('a'),row('b'))],
            ['--seconds','3600','--until-texts','2'], [0,3600])
        self.assertEqual(code, 0)
        self.assertEqual(reports[-1]['observed_new_texts'], 0)
        self.assertEqual(reports[-1]['completion_reason'], 'deadline_reached')

    def test_default_duration_remains_thirty_seconds(self):
        raw = snapshot(row('a'),row('b'))
        code, reports, reader = self.run_listener([raw,raw], [], [0,29,30])
        self.assertEqual(code, 0)
        self.assertEqual(reader.read.call_count, 2)
        self.assertEqual(reports[-1]['completion_reason'], 'deadline_reached')

    def test_zero_seconds_waits_past_one_hour_until_text_target_in_all_modes(self):
        for mode in ([], ['--observe-occurrences'], ['--observe-visual-occurrences']):
            with self.subTest(mode=mode):
                a, b = row('a'), row('b')
                snapshots = [snapshot(a,b), snapshot(a,b), snapshot(a,b),
                             snapshot(a,b,row('c')), snapshot(a,b,row('c'),row('d'))]
                if mode == ['--observe-visual-occurrences']:
                    for raw in snapshots:
                        raw['status'] = 'visual_text_snapshot'
                        for item in raw['rows']: item['direction'] = 'unknown'
                code, reports, reader = self.run_listener(snapshots,
                    [*mode,'--seconds','0','--until-texts','2'], [0,1,3601,7200,7201,7202])
                key = 'candidate_texts' if mode else 'observed_new_texts'
                self.assertEqual(code, 0)
                self.assertEqual([report[key] for report in reports], [0,0,0,1,2])
                self.assertEqual(reader.read.call_count, 5)
                self.assertTrue(all('completion_reason' not in report for report in reports[:-1]))
                self.assertEqual(reports[-1]['status'], 'completed')
                self.assertEqual(reports[-1]['completion_reason'], 'text_limit_reached')

    def test_zero_seconds_error_and_interrupt_stop_and_release_reader(self):
        for error, reason in ((live_read.ReadError('client_unavailable'), 'client_unavailable'),
                              (KeyboardInterrupt(), 'interrupted')):
            with self.subTest(reason=reason):
                raw = snapshot(row('a'),row('b'))
                code, reports, reader = self.run_listener([raw,raw,error],
                    ['--seconds','0','--until-texts','2'], [0,3601,7201])
                self.assertEqual(code, 3)
                self.assertEqual(reader.read.call_count, 3)
                self.assertEqual(reports[-1]['status'], 'stopped')
                self.assertEqual(reports[-1]['stop_reason'], reason)
                self.assertEqual(reports[-1]['observed_new_texts'], 0)
                self.assertTrue(all('completion_reason' not in report for report in reports))

    def test_failure_never_becomes_normal_completion(self):
        code, reports, _ = self.run_listener([snapshot(row('a'),row('b')),
                                            live_read.ReadError('client_unavailable')],
            ['--seconds','3600','--until-texts','2'], [0,1])
        self.assertEqual(code, 3)
        self.assertEqual(reports[-1]['status'], 'stopped')
        self.assertNotIn('completion_reason', reports[-1])

    def test_bad_limits_and_inspection_target_are_rejected_before_reader_creation(self):
        invalid = [['--seconds', str(value)] for value in (-1,0,3601)]
        invalid += [['--until-texts', str(value)] for value in (0,257)]
        invalid += [['--seconds','0','--until-texts',str(value)] for value in (0,257)]
        invalid += [[mode,'--until-texts','2'] for mode in
                    ('--inspect-layout','--inspect-capabilities','--inspect-visual')]
        invalid += [[mode,'--seconds','0',*target] for mode in
                    ('--inspect-layout','--inspect-capabilities','--inspect-visual')
                    for target in ([], ['--until-texts','2'])]
        for args in invalid:
            with self.subTest(args=args), patch.object(live_read,'NativeReader') as reader, \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                live_read.main(['--client-path','fixture.exe',*args])
            self.assertEqual(error.exception.code, 2)
            reader.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows entry points required')
    def test_windows_wrappers_accept_one_hour_and_preserve_native_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            for shell in filter(None, (shutil.which('powershell.exe'),shutil.which('pwsh.exe'))):
                with self.subTest(shell=shell):
                    done = subprocess.run([shell,'-NoProfile','-NonInteractive','-File',
                        str(ROOT/'scripts/windows.ps1'),'-Action','listen-wechat',
                        '-ClientPath',str(Path(directory)/'Weixin.exe'),'-ListenSeconds','3600',
                        '-Python',sys.executable], capture_output=True, timeout=30)
                    self.assertEqual(done.returncode, 3)
                    self.assertEqual(json.loads(done.stdout)['stop_reason'], 'client_unavailable')


if __name__ == '__main__': unittest.main()
