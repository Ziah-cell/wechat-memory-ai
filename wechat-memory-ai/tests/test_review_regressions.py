"""Regressions derived from independent review; first run must fail on pre-fix code."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from hashlib import sha256
import io
import sqlite3
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile

from wechat_memory.backup import BackupError, backup_store, restore_backup
from wechat_memory.config import load_config
from wechat_memory.models import ChatCompletionsModel, ModelError
from wechat_memory.store import Store

ROOT = Path(__file__).parents[1]


class PrivacyReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root/'data')
        self.addCleanup(lambda: self.store.close())

    def test_clock_rollback_forget_and_old_backup_replay(self):
        with patch('wechat_memory.store.time.time_ns', return_value=200):
            row = self.store.remember('s','称呼','旧称呼','preference','m')
            self.store.add_turn('s','m','user','旧称呼')
            backup_store(self.store,self.root/'old.zip')
        with patch('wechat_memory.store.time.time_ns', return_value=100):
            self.assertTrue(self.store.forget('s',row['id']))
            self.assertEqual(self.store.memories('s'),[])
            self.assertEqual(self.store.history('s'),[])
        self.store.close()
        restore_backup(self.root/'old.zip',self.root/'data')
        self.store = Store(self.root/'data')
        self.assertEqual(self.store.memories('s'),[])
        self.assertEqual(self.store.history('s'),[])

    def test_clock_rollback_replacement_and_clear_purge_old_context(self):
        with patch('wechat_memory.store.time.time_ns', return_value=200):
            self.store.remember('s','称呼','旧称呼','preference','m')
            self.store.add_turn('s','m','user','旧称呼')
        with patch('wechat_memory.store.time.time_ns', return_value=100):
            self.store.remember('s','称呼','新称呼','preference','m2')
            self.assertEqual(self.store.history('s'),[])
            self.assertEqual(self.store.memories('s')[0]['value'],'新称呼')
            token = self.store.issue_clear_token('s')
            self.assertTrue(self.store.confirm_clear('s',token))
            self.assertEqual(self.store.memories('s'),[])
        self.store.close()
        self.store = Store(self.root/'data')
        self.assertEqual(self.store.memories('s'),[])

    def test_zero_byte_backup_must_not_initialize_over_healthy_data(self):
        self.store.remember('s','称呼','保留','preference','m')
        backup_store(self.store,self.root/'good.zip')
        with zipfile.ZipFile(self.root/'good.zip') as z:
            manifest = z.read('manifest.json')
        with zipfile.ZipFile(self.root/'bad.zip','w') as z:
            doc=json.loads(manifest)
            doc['state_sha256']=sha256(b'').hexdigest()
            z.writestr('manifest.json',json.dumps(doc))
            z.writestr('state.sqlite3',b'')
        self.store.close()
        with self.assertRaises(BackupError):
            restore_backup(self.root/'bad.zip',self.root/'data')
        self.store = Store(self.root/'data')
        self.assertEqual(self.store.memories('s')[0]['value'],'保留')

    def test_valid_sqlite_with_missing_schema_or_metadata_is_rejected(self):
        self.store.remember('s','称呼','保留','preference','m')
        backup_store(self.store,self.root/'good.zip')
        with zipfile.ZipFile(self.root/'good.zip') as z:
            manifest=json.loads(z.read('manifest.json'))
            original=z.read('state.sqlite3')
        for mutation in ["DROP TABLE memories", "UPDATE meta SET value='999' WHERE key='applied_seq'",
                         "UPDATE meta SET value='another' WHERE key='lineage'"]:
            with self.subTest(mutation=mutation):
                broken=self.root/'broken.sqlite3'
                broken.write_bytes(original)
                con=sqlite3.connect(broken)
                con.execute(mutation)
                con.commit()
                con.close()
                content=broken.read_bytes()
                manifest['state_sha256']=sha256(content).hexdigest()
                with zipfile.ZipFile(self.root/'bad.zip','w') as z:
                    z.writestr('manifest.json',json.dumps(manifest))
                    z.writestr('state.sqlite3',content)
                with self.assertRaises(BackupError):
                    restore_backup(self.root/'bad.zip',self.root/'data')
                self.assertEqual(self.store.memories('s')[0]['value'],'保留')

    def test_manifest_non_objects_and_wrong_types_are_cleanly_rejected(self):
        backup_store(self.store,self.root/'good.zip')
        with zipfile.ZipFile(self.root/'good.zip') as z:
            state=z.read('state.sqlite3')
        for value in [None,[],1,'bad',{'format':True,'privacy_seq':[],'lineage':self.store.lineage}]:
            with self.subTest(value=value):
                with zipfile.ZipFile(self.root/'bad.zip','w') as z:
                    z.writestr('manifest.json',json.dumps(value))
                    z.writestr('state.sqlite3',state)
                with self.assertRaises(BackupError):
                    restore_backup(self.root/'bad.zip',self.root/'data')


class InputReviewTests(unittest.TestCase):
    def test_huge_timestamp_rejects_record_and_continues_next_message(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp)/'config.toml'
            config.write_text((ROOT/'config.example.toml').read_text('utf-8'),'utf-8')
            records = [{'text':'坏时间','timestamp':10**400},
                       {'text':'类型错误','is_self':'false'},
                       {'text':'类型错误','is_group':0},
                       {'text':'类型错误','display_name':{}},
                       {'text':'下一条正常消息'}]
            result = subprocess.run([sys.executable,str(ROOT/'scripts/run.py'),'--config',str(config),'run','--jsonl'],
                                    input='\n'.join(json.dumps(r,ensure_ascii=False) for r in records)+'\n',
                                    capture_output=True,text=True,encoding='utf-8',timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            data=[json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([r['status'] for r in data], ['rejected']*4+['dry_run'])


class DeadlineReviewTests(unittest.TestCase):
    def test_slow_drip_has_total_deadline_and_prompt_cancellation(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200)
                self.end_headers()
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
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        c=load_config(ROOT/'config.example.toml',environ={}).model
        c=replace(c,provider='chat_completions',allow_network=True,api_key='TEST_ONLY',name='test',
                  endpoint=f'http://127.0.0.1:{server.server_port}/v1/chat/completions',timeout_seconds=.4)
        started=time.monotonic()
        with self.assertRaises(ModelError) as cm:
            ChatCompletionsModel(c).complete([{'role':'user','content':'你好'}])
        self.assertEqual(cm.exception.code,'timeout')
        self.assertLess(time.monotonic()-started,1.5)
        started=time.monotonic()
        def cancel():
            return 'stop' if time.monotonic()-started>.25 else ''
        with self.assertRaises(ModelError) as cm:
            ChatCompletionsModel(replace(c,timeout_seconds=10)).complete([{'role':'user','content':'你好'}],cancel_check=cancel)
        self.assertEqual(cm.exception.code,'cancelled')
        self.assertLess(time.monotonic()-started,1.5)
