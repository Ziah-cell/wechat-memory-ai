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

    def deepseek_config(self, **changes):
        return replace(self.config, provider='deepseek', name='deepseek-flash', **changes)

    def deepseek_response(self, *, finish='stop', content='模拟的自然回复', **fields):
        return json.dumps({'choices':[{'finish_reason':finish,
                          'message':dict(content=content, **fields)}]}).encode('utf-8')

    def test_deepseek_non_thinking_payload_and_complete_text_contract(self):
        type(self).body = b'\n \n' + self.deepseek_response(reasoning_content=None)
        messages = [{'role':'system','content':'虚构测试上下文'}, {'role':'user','content':'你好'}]
        result = ChatCompletionsModel(self.deepseek_config(max_completion_tokens=128)).complete(messages)
        self.assertEqual(result, '模拟的自然回复')
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0]['body'], {
            'model':'deepseek-flash', 'messages':messages, 'stream':False,
            'max_tokens':128, 'thinking':{'type':'disabled'}})
        self.assertEqual(self.requests[0]['auth'], 'Bearer TEST_ONLY_KEY')

    def test_deepseek_incomplete_or_missing_finish_reason_never_returns_partial_reply(self):
        for reason in ('length', 'content_filter', 'tool_calls', 'insufficient_system_resource', None):
            type(self).body = self.deepseek_response(finish=reason, content='PRIVATE_PARTIAL')
            with self.subTest(reason=reason):
                with self.assertRaises(ModelError) as error:
                    ChatCompletionsModel(self.deepseek_config()).complete([{'role':'user','content':'fixture'}])
                self.assertEqual(error.exception.code, 'truncated' if reason == 'length' else 'format')
                self.assertNotIn('PRIVATE_PARTIAL', str(error.exception))
        type(self).body = b'{"choices":[{"message":{"content":"PRIVATE_PARTIAL"}}]}'
        with self.assertRaises(ModelError) as error:
            ChatCompletionsModel(self.deepseek_config()).complete([{'role':'user','content':'fixture'}])
        self.assertEqual(error.exception.code, 'format')

    def test_deepseek_unexpected_reasoning_or_actions_are_rejected_without_exposing_them(self):
        for fields in ({'reasoning_content':'PRIVATE_REASON'}, {'reasoning_content':[]},
                       {'tool_calls':[{'function':{'name':'PRIVATE_ACTION'}}]},
                       {'function_call':{'name':'PRIVATE_ACTION'}}):
            type(self).body = self.deepseek_response(**fields)
            with self.subTest(field=next(iter(fields))):
                with self.assertRaises(ModelError) as error:
                    ChatCompletionsModel(self.deepseek_config()).complete([{'role':'user','content':'fixture'}])
                self.assertEqual(error.exception.code, 'format')
                self.assertNotIn('PRIVATE_', str(error.exception))

    def test_deepseek_oversized_reply_is_rejected_instead_of_cut_mid_sentence(self):
        type(self).body = self.deepseek_response(content='字'*101)
        with self.assertRaises(ModelError) as error:
            ChatCompletionsModel(self.deepseek_config(max_reply_chars=100)).complete(
                [{'role':'user','content':'fixture'}])
        self.assertEqual(error.exception.code, 'truncated')

    def test_deepseek_retains_opt_in_error_mapping_and_no_automatic_retry(self):
        with self.assertRaises(ModelError) as error:
            ChatCompletionsModel(self.deepseek_config(allow_network=False)).complete(
                [{'role':'user','content':'fixture'}])
        self.assertEqual(error.exception.code, 'network_disabled')
        self.assertEqual(self.requests, [])
        for status, code in ((401,'auth'), (429,'quota'), (503,'server')):
            type(self).status = status
            before = len(self.requests)
            with self.subTest(status=status):
                with self.assertRaises(ModelError) as error:
                    ChatCompletionsModel(self.deepseek_config()).complete([{'role':'user','content':'fixture'}])
                self.assertEqual(error.exception.code, code)
                self.assertEqual(len(self.requests), before+1)

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
