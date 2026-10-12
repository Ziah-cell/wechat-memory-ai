"""Removed reader modes cannot launch a worker or revive an old status."""
from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory import monitor
from wechat_memory.live_read import NativeReader, ReadError


class OpenWindowContractTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows compiler required')
    def test_native_discovery_checks_minimization_before_uia(self):
        # Pure discovery inputs: no windows, native UI fixtures or WeChat access.
        # A throwing callback detects any accidental UIA access while all windows
        # are minimized. Other cases preserve uniqueness and fail-closed identity.
        source = r'''
using System;
using System.Reflection;
class DiscoveryContract {
    static int reads;
    static IntPtr[] windows = { new IntPtr(1), new IntPtr(2) };
    static void Reason(string expected, Action action) {
        try { action(); throw new Exception("missing stop"); }
        catch (InvalidOperationException) {
            string actual = (string)typeof(LiveReader).GetField("failureReason",
                BindingFlags.NonPublic | BindingFlags.Static).GetValue(null);
            if (actual != expected) throw new Exception("wrong reason");
        }
    }
    static int Main() {
        try { Run(); return 0; }
        catch (Exception ex) { Console.WriteLine(ex.Message); return 1; }
    }
    static void Run() {
        Reason("window_minimized", delegate {
            LiveReader.FindPrivateWindow(windows, h => true,
                h => { reads++; throw new Exception("UIA must not run"); });
        });
        if (reads != 0) throw new Exception("unexpected read");
        Reason("private_window_not_unique", delegate {
            LiveReader.FindPrivateWindow(new IntPtr[0], h => false, h => "");
        });
        Reason("window_identity_unavailable", delegate {
            LiveReader.FindPrivateWindow(windows, h => false, h => "");
        });
        Reason("private_window_not_unique", delegate {
            LiveReader.FindPrivateWindow(windows, h => false, h => "ChatSingleWindowwxid_fixture");
        });
        Reason("window_minimized", delegate {
            LiveReader.FindPrivateWindow(windows, h => h == windows[1],
                h => h == windows[1] ? "ChatSingleWindowwxid_fixture" : "MainWindow");
        });
        IntPtr result = LiveReader.FindPrivateWindow(windows, h => false,
            h => h == windows[1] ? "ChatSingleWindowwxid_fixture" : "MainWindow");
        if (result != windows[1]) throw new Exception("wrong target");
        Console.WriteLine("discovery_contract_passed");
    }
}
'''
        framework = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319'
        package = Path(__file__).resolve().parents[1]/'src/wechat_memory'
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory)/'discovery.cs'
            harness.write_text(source, encoding='utf-8')
            executable = Path(directory)/'discovery.exe'
            args = [str(framework/'csc.exe'), '/nologo', '/target:exe',
                    '/main:DiscoveryContract', '/out:'+str(executable),
                    '/reference:'+str(framework/'System.Web.Extensions.dll'),
                    '/reference:'+str(framework/'System.Drawing.dll')]
            args += ['/reference:'+str(framework/'WPF'/name) for name in
                     ('UIAutomationClient.dll','UIAutomationTypes.dll','WindowsBase.dll')]
            args += [str(package/'live_reader.cs'),str(package/'visual_direction.cs'),str(harness)]
            compiled = subprocess.run(args,capture_output=True,timeout=25,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(compiled.returncode,0,compiled.stdout.decode('utf-8','replace'))
            result = subprocess.run([str(executable)],capture_output=True,timeout=8,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout.decode('utf-8','replace'))
            self.assertEqual(result.stdout.strip(), b'discovery_contract_passed')

    @unittest.skipUnless(os.name == 'nt', 'Windows compiler required')
    def test_native_retired_modes_are_rejected_before_client_access(self):
        # Compile the product, without UI fixtures or an actual WeChat process.
        with tempfile.TemporaryDirectory() as temp, NativeReader(str(Path(temp)/'Weixin.exe')) as reader:
            for mode in ('selection-text','background-text','window-state','inbound-capabilities'):
                result = subprocess.run([str(reader.executable),reader.client_path,'--'+mode],
                                        input=b'null',capture_output=True,timeout=8,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stdout, b'')

    def test_retired_reader_modes_fail_before_launch(self):
        for mode in ('selection', 'background'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)/'absent'
                with patch.object(monitor.subprocess, 'Popen') as launch, redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        monitor.main(['--data-dir',str(directory),'start','--client-path','fixture.exe','--reader',mode])
                self.assertEqual(error.exception.code, 2)
                launch.assert_not_called()
                self.assertFalse(directory.exists())

    def test_legacy_minimized_status_cannot_advertise_a_supported_mode(self):
        report = monitor._public_status(dict(reader_mode='background', minimized_snapshots=8,
                                             minimized_observation_enabled=True, window_minimized=True))
        self.assertEqual(report['reader_mode'], 'unsupported')
        for removed in ('minimized_snapshots','minimized_observation_enabled','window_minimized','minimized_supported'):
            self.assertNotIn(removed, report)
        self.assertFalse(report['reply_ready'])

    def test_inaccessible_window_stops_without_retry_or_text_delivery(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(monitor, 'NativeReader') as manager:
            reader = manager.return_value.__enter__.return_value
            reader.snapshot_change_retries = 0
            reader.diagnostics = {}
            reader.read.side_effect = ReadError('window_identity_unavailable')
            self.assertEqual(monitor.run_monitor('fixture.exe', temp), 3)
            reader.read.assert_called_once_with(visual_text=True)
            status = monitor.monitor_status(temp)
            self.assertEqual(status['stop_reason'], 'window_identity_unavailable')
            self.assertEqual(status['snapshots'], 0)
            self.assertFalse(status['active'])
            self.assertFalse(status['reply_ready'])
