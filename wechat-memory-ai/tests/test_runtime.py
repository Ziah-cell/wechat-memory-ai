from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

from wechat_memory.runtime import InstanceLock, AlreadyRunning

ROOT = Path(__file__).parents[1]
RUN = [sys.executable, '-X', 'utf8', str(ROOT/'scripts'/'run.py')]


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config.toml'
        self.config.write_text((ROOT/'config.example.toml').read_text('utf-8'), 'utf-8')

    def cli(self, *args, input=None):
        return subprocess.run(RUN+['--config', str(self.config), *args], input=input,
                              text=True, encoding='utf-8', capture_output=True, timeout=10)

    def start(self):
        process = subprocess.Popen(RUN+['--config', str(self.config), 'run'], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        self.addCleanup(cleanup)
        try:
            self.wait_state('running')
        except AssertionError:
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=2)
                self.fail(f'run exited {process.returncode}: {stdout!r} {stderr!r}')
            raise
        return process

    def wait_state(self, phase):
        deadline = time.monotonic()+5
        latest = None
        while time.monotonic() < deadline:
            result = self.cli('status')
            if result.returncode == 0:
                latest = json.loads(result.stdout)
                if latest['phase'] == phase:
                    return latest
            time.sleep(.03)
        self.fail(f'phase did not become {phase}: {latest}')

    def test_lock_competes_in_an_actual_subprocess(self):
        with InstanceLock(self.root/'data'):
            result = self.cli('run', input='你好\n')
            self.assertEqual(result.returncode, 3)
            self.assertIn('already_running', result.stderr)
        self.assertEqual(self.cli('run', input='你好\n').returncode, 0)

    def test_short_status_probe_contention_does_not_abort_startup(self):
        code = "import sys; from wechat_memory.runtime import InstanceLock; print('ready', flush=True); lock=InstanceLock(sys.argv[1]); lock.__enter__(); print('acquired',flush=True); lock.__exit__()"
        env = dict(os.environ, PYTHONPATH=str(ROOT/'src'))
        with InstanceLock(self.root/'data'):
            process = subprocess.Popen([sys.executable,'-c',code,str(self.root/'data')], env=env,
                                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            self.assertEqual(process.stdout.readline().strip(), 'ready')
            time.sleep(.1) # deterministic short competing status lock, not a readiness wait
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertIn('acquired', stdout)

    def test_cli_demo_and_restart_restore_preferences(self):
        first = self.cli('run', input='记住：称呼我为小禾，回复尽量简短\n你好\n')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn('离线模拟', first.stdout)
        self.assertIn('dry_run', first.stdout)
        second = self.cli('run', input='你好\n')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('小禾', second.stdout)

    def test_cli_uses_utf8_even_when_process_locale_requests_ascii(self):
        env = dict(os.environ, PYTHONUTF8='0', PYTHONIOENCODING='ascii')
        result = subprocess.run(
            [sys.executable, str(ROOT/'scripts/run.py'), '--config', str(self.config), 'run'],
            input='你好，绘画🎨\n', encoding='utf-8', capture_output=True, timeout=10, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'dry_run')
        self.assertIn('你好，绘画🎨', rows[0]['reply'])

    def test_runtime_pause_resume_stop_without_stdin(self):
        process = self.start()
        self.assertEqual(self.cli('pause').returncode, 0)
        self.wait_state('paused')
        self.assertEqual(self.cli('resume').returncode, 0)
        self.wait_state('running')
        self.assertEqual(self.cli('stop').returncode, 0)
        process.wait(timeout=5)
        self.assertEqual(process.returncode, 0)
        self.wait_state('stopped')

    def test_stop_cancels_an_actual_slow_http_call(self):
        received=threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200)
                self.end_headers()
                received.set()
                try:
                    for _ in range(100):
                        self.wfile.write(b' ')
                        self.wfile.flush()
                        time.sleep(.04)
                except (BrokenPipeError,ConnectionResetError):
                    pass
            def log_message(self,*args):
                pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.daemon_threads=True
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        config=self.config.read_text('utf-8').replace('provider = "fake"','provider = "chat_completions"')
        config=config.replace('allow_network = false','allow_network = true')
        config=config.replace('endpoint = ""',f'endpoint = "http://127.0.0.1:{server.server_port}/v1/chat/completions"')
        config=config.replace('name = ""','name = "test-only"')
        self.config.write_text(config,'utf-8')
        (self.root/'.env').write_text('WECHAT_AI_API_KEY=TEST_ONLY','utf-8')
        process=self.start()
        process.stdin.write('你好\n')
        process.stdin.flush()
        self.assertTrue(received.wait(timeout=5),'HTTP request never reached local test server')
        started=time.monotonic()
        self.assertEqual(self.cli('stop').returncode,0)
        process.wait(timeout=2)
        self.assertEqual(process.returncode,0)
        self.assertLess(time.monotonic()-started,2)

    def test_stop_on_stale_state_never_kills_an_unrelated_process(self):
        (self.root/'data').mkdir()
        (self.root/'data'/'runtime.json').write_text(json.dumps({'pid':os.getpid(),'run_id':'old','phase':'running'}))
        result = self.cli('stop')
        self.assertEqual(result.returncode, 4)
        self.assertIn('not_running', result.stderr)

    def test_killed_process_releases_os_lock(self):
        process = self.start()
        process.kill()
        process.wait(timeout=5)
        self.assertEqual(self.cli('run', input='新消息\n').returncode, 0)

    def test_jsonl_duplicate_multiline_and_malformed_record(self):
        event = {'id':'stable-id','text':'你好\n第二行'}
        payload = '\n'.join([json.dumps(event,ensure_ascii=False), 'bad-json', json.dumps(event,ensure_ascii=False)])+'\n'
        result = self.cli('run','--jsonl',input=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        results = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r['status'] for r in results], ['dry_run','invalid_input','duplicate'])
        self.assertIn('第二行', results[0]['reply'])

    def test_cli_backup_restore_requires_confirmation_and_guard(self):
        self.cli('run',input='记住：兴趣=绘画\n')
        backup = self.root/'backup.zip'
        self.assertEqual(self.cli('backup',str(backup)).returncode, 0)
        self.assertNotEqual(self.cli('restore',str(backup)).returncode, 0)
        restored = self.cli('restore',str(backup),'--confirm')
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertIn('绘画', self.cli('run',input='/记忆\n').stdout)

    def test_diagnose_does_not_claim_wechat_connected(self):
        result = self.cli('diagnose')
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertFalse(data['real_wechat_verified'])
        self.assertFalse(data['real_send_supported'])
        self.assertEqual(data['adapter'], 'mock')

    def test_windows_script_exists_without_system_mutation(self):
        text = (ROOT/'scripts'/'windows.ps1').read_text('utf-8')
        self.assertIn('scripts/run.py', text)
        for token in ['Set-ExecutionPolicy','Register-ScheduledTask','Start-Process -Verb RunAs']:
            self.assertNotIn(token, text)
