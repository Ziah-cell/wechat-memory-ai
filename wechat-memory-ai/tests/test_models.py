from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import socket
import threading
import time
import unittest

from wechat_memory.config import ConfigError, load_config
from wechat_memory.models import ChatCompletionsModel, ModelError


class ModelHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = []
        cls.status = 200
        cls.body = b'{}'
        cls.delay = 0
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                cls.requests.append({'path': self.path, 'auth': self.headers.get('Authorization'),
                                     'body': json.loads(self.rfile.read(int(self.headers['Content-Length'])))})
                time.sleep(cls.delay)
                self.send_response(cls.status)
                if cls.status == 302:
                    self.send_header('Location', '/stolen')
                self.end_headers()
                try:
                    self.wfile.write(cls.body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        type(self).requests = []
        type(self).status = 200
        type(self).delay = 0
        type(self).body = json.dumps({'choices':[{'message':{'content':'真实 HTTP，本地假服务'}}]}).encode()
        c = load_config(Path(__file__).parents[1] / 'config.example.toml', environ={})
        self.config = replace(c.model, provider='chat_completions', allow_network=True, api_key='TEST_ONLY_KEY',
                              endpoint=f'http://127.0.0.1:{self.server.server_port}/v1/chat/completions', name='test-model')

    def test_http_contract_no_tools_no_secret_in_body(self):
        result = ChatCompletionsModel(self.config).complete([{'role':'user','content':'你好'}])
        self.assertEqual(result, '真实 HTTP，本地假服务')
        request = self.requests[0]
        self.assertEqual(request['auth'], 'Bearer TEST_ONLY_KEY')
        self.assertEqual(request['body']['model'], 'test-model')
        self.assertEqual(request['body']['max_completion_tokens'], 512)
        self.assertNotIn('tools', request['body'])
        self.assertNotIn('TEST_ONLY_KEY', json.dumps(request['body']))

    def test_http_error_mapping_and_no_retry(self):
        for status, code in [(401,'auth'), (403,'auth'), (402,'quota'), (429,'quota'), (500,'server')]:
            type(self).status = status
            before = len(self.requests)
            with self.subTest(status=status), self.assertRaises(ModelError) as cm:
                ChatCompletionsModel(self.config).complete([{'role':'user','content':'hi'}])
            self.assertEqual(cm.exception.code, code)
            self.assertEqual(len(self.requests), before+1)

    def test_empty_malformed_and_nontext_responses_fail(self):
        for body in [b'bad json', b'{}', b'{"choices":[]}',
                     b'{"choices":[{"message":{"content":[]}}]}',
                     b'{"choices":[{"message":{"content":" "}}]}']:
            type(self).body = body
            with self.subTest(body=body), self.assertRaises(ModelError):
                ChatCompletionsModel(self.config).complete([{'role':'user','content':'hi'}])

    def test_redirect_is_not_followed_with_credentials(self):
        type(self).status = 302
        with self.assertRaises(ModelError):
            ChatCompletionsModel(self.config).complete([{'role':'user','content':'hi'}])
        self.assertEqual(len(self.requests), 1)

    def test_timeout_returns_safe_code(self):
        type(self).delay = 0.25
        with self.assertRaises(ModelError) as cm:
            ChatCompletionsModel(replace(self.config, timeout_seconds=0.05)).complete([{'role':'user','content':'hi'}])
        self.assertEqual(cm.exception.code, 'timeout')

    def test_network_is_disabled_at_client_boundary(self):
        with self.assertRaises(ModelError) as cm:
            ChatCompletionsModel(replace(self.config, allow_network=False)).complete([{'role':'user','content':'hi'}])
        self.assertEqual(cm.exception.code, 'network_disabled')
        self.assertEqual(self.requests, [])

    def test_external_service_unreachable(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
        config = replace(self.config, endpoint=f'http://127.0.0.1:{port}/v1/chat/completions')
        with self.assertRaises(ModelError) as cm:
            ChatCompletionsModel(config).complete([{'role':'user','content':'hi'}])
        self.assertEqual(cm.exception.code, 'network')
