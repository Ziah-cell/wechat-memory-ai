"""Real UI snapshots have session identity, not invented server message IDs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory import live_read

ROOT=Path(__file__).resolve().parents[1]


def snapshot(rows=(), **changes):
    value = dict(status='snapshot', process=12, started='123456', window=34,
                 root='ChatSingleWindowwxid_fixture', list_token='1.2.3',
                 rows=[dict(token=token, text=text, kind='text') for token, text in rows])
    value.update(changes)
    return value


class LiveReadTests(unittest.TestCase):
    def test_baseline_ignores_history_and_preserves_identical_new_rows(self):
        session = live_read.ReadSession()
        self.assertEqual(session.accept(snapshot([('1', 'old')])), [])
        result = session.accept(snapshot([('1', 'old'), ('2', 'hello'), ('3', 'hello')]))
        self.assertEqual([row.text for row in result], ['hello', 'hello'])
        self.assertNotEqual(result[0].observation_id, result[1].observation_id)
        self.assertEqual(session.accept(snapshot([('1', 'old'), ('2', 'hello'), ('3', 'hello')])), [])
        self.assertFalse(session.report()['real_send_supported'])
        self.assertNotIn('hello', json.dumps(session.report()))
        self.assertNotIn('wxid_fixture', json.dumps(session.report()))

    def test_restart_baselines_current_rows_without_replaying(self):
        first = live_read.ReadSession()
        first.accept(snapshot([]))
        first.accept(snapshot([('1', 'new')]))
        restarted = live_read.ReadSession()
        self.assertEqual(restarted.accept(snapshot([('1', 'new')])), [])
        self.assertEqual(restarted.report()['observed_new_rows'], 0)

    def test_identity_and_list_changes_stop_and_cannot_rearm(self):
        for change in ({'root':'ChatSingleWindowwxid_other'}, {'window':35},
                       {'process':13}, {'started':'other'}, {'list_token':'new'}):
            session = live_read.ReadSession()
            session.accept(snapshot([('1', 'old')]))
            with self.assertRaises(live_read.ReadError):
                session.accept(snapshot([('1', 'old'), ('2', 'private')], **change))
            with self.assertRaises(live_read.ReadError):
                session.accept(snapshot([('1', 'old')]))

    def test_rebuild_removed_history_or_reused_token_stops(self):
        for rows in ([('2','old')], [], [('1','changed')], [('1','old'),('1','new')],
                     [('2','new'),('1','old')]):
            session = live_read.ReadSession()
            session.accept(snapshot([('1','old')]))
            with self.assertRaises(live_read.ReadError):
                session.accept(snapshot(rows))

    def test_bad_schema_and_non_independent_chats_rejected(self):
        for change in ({'root':'ChatGroupWindowroom'}, {'process':True}, {'rows':'PRIVATE'},
                       {'rows':[dict(token='1', text='x'*10001, kind='text')]},
                       {'rows':[dict(token='1', text='x', kind='guessed')]},
                       {'status':'PRIVATE'}, {'list_token':''}):
            raw = snapshot()
            raw.update(change)
            with self.assertRaises(live_read.ReadError) as error:
                live_read.ReadSession().accept(raw)
            self.assertNotIn('PRIVATE', str(error.exception))

    def test_non_text_rows_never_become_text_observations(self):
        session = live_read.ReadSession()
        session.accept(snapshot([('1','baseline')]))
        raw = snapshot([('1','baseline')])
        raw['rows'].append(dict(token='2', text='private', kind='other'))
        self.assertEqual(session.accept(raw), [])
        self.assertEqual(session.report()['observed_new_rows'], 1)
        self.assertEqual(session.report()['observed_new_texts'], 0)

    def test_initial_empty_list_never_promotes_late_history(self):
        session=live_read.ReadSession()
        self.assertEqual(session.accept(snapshot([])),[])
        self.assertEqual(session.accept(snapshot([('1','late history')])),[])
        self.assertEqual(session.report()['observed_new_texts'],0)
        self.assertFalse(session.report()['history_boundary_verified'])

    def test_reader_transmits_binding_before_subsequent_native_reads(self):
        reader=live_read.NativeReader('D:/Weixin.exe')
        reader.executable=Path('fixture.exe')
        done=subprocess.CompletedProcess([],0,json.dumps(snapshot([('1','private')])).encode(),b'')
        with patch.object(live_read.subprocess,'run',return_value=done) as run:
            reader.read()
            reader.read()
        second=run.call_args_list[1].kwargs
        binding=json.loads(second['input'])
        self.assertEqual(binding['window'],34)
        self.assertEqual(binding['root'],'ChatSingleWindowwxid_fixture')
        self.assertNotIn('private',second['input'].decode())

    @unittest.skipUnless(os.name=='nt','Windows native compiler required')
    def test_temporary_creation_and_cleanup_errors_are_sanitized(self):
        reader=live_read.NativeReader('D:/Weixin.exe')
        with patch.object(Path,'is_file',side_effect=PermissionError('PRIVATE')):
            with self.assertRaises(live_read.ReadError) as result:
                reader.__enter__()
            self.assertNotIn('PRIVATE',str(result.exception))
        with patch.object(live_read.tempfile,'TemporaryDirectory',side_effect=OSError('PRIVATE')):
            with self.assertRaises(live_read.ReadError) as result:
                reader.__enter__()
            self.assertNotIn('PRIVATE',str(result.exception))
        temporary=unittest.mock.Mock()
        temporary.cleanup.side_effect=OSError('PRIVATE')
        reader._temporary=temporary
        with self.assertRaises(live_read.ReadError) as result:
            reader.__exit__(None,None,None)
        self.assertNotIn('PRIVATE',str(result.exception))

    def test_timeout_child_failure_and_private_errors_are_sanitized(self):
        reader = live_read.NativeReader('D:/Weixin.exe')
        reader.executable = Path('fixture.exe')
        for error in (OSError('PRIVATE'), subprocess.TimeoutExpired('SECRET', 5)):
            with patch.object(live_read.subprocess, 'run', side_effect=error):
                with self.assertRaises(live_read.ReadError) as result:
                    reader.read()
                self.assertNotIn('PRIVATE', str(result.exception))
                self.assertNotIn('SECRET', str(result.exception))

    def test_literal_child_arguments_and_malformed_output(self):
        reader = live_read.NativeReader('D:/spaces & quote/Weixin.exe')
        reader.executable = Path('fixture.exe')
        for output in (b'PRIVATE', b'[]', b'{"status":"PRIVATE"}',b'x'*4_000_001):
            done=subprocess.CompletedProcess([],0,output,b'PRIVATE')
            with patch.object(live_read.subprocess,'run',return_value=done) as run:
                with self.assertRaises(live_read.ReadError):
                    reader.read()
                args,kwargs=run.call_args
                self.assertEqual(args[0],[str(reader.executable),reader.client_path])
                self.assertFalse(kwargs.get('shell',False))
                self.assertEqual(kwargs['timeout'],8)
                self.assertEqual(kwargs['input'],b'null')

    @unittest.skipUnless(os.name=='nt','Windows native compiler required')
    def test_real_native_build_missing_client_and_temporary_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            with live_read.NativeReader(str(Path(directory)/'Weixin.exe')) as reader:
                executable=reader.executable
                self.assertTrue(executable.is_file())
                with self.assertRaises(live_read.ReadError):
                    reader.read()
            self.assertFalse(executable.parent.exists())

    @unittest.skipUnless(os.name=='nt','Windows entry points required')
    def test_windows_entry_points_preserve_config_and_propagate_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            config=directory/'private.toml'
            config.write_text('PRIVATE: deliberately invalid personal configuration')
            for shell in filter(None,(shutil.which('powershell.exe'),shutil.which('pwsh.exe'))):
                with self.subTest(shell=shell):
                    done=subprocess.run([shell,'-NoProfile','-NonInteractive','-File',
                        str(ROOT/'scripts/windows.ps1'),'-Action','listen-wechat',
                        '-ClientPath',str(directory/'Weixin.exe'),'-ListenSeconds','1',
                        '-Python',sys.executable,'-Config',str(config)],capture_output=True,timeout=30)
                    self.assertEqual(done.returncode,3)
                    report=json.loads(done.stdout)
                    self.assertEqual(report['status'],'stopped')
                    self.assertFalse(report['real_send_supported'])
                    self.assertNotIn('PRIVATE',done.stdout.decode())
                    self.assertEqual(config.read_text(),'PRIVATE: deliberately invalid personal configuration')
            self.assertEqual(list(directory.iterdir()),[config])


if __name__ == '__main__':
    unittest.main()
