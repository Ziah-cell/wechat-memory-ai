"""Text-only model clients with an opt-in network and cancellable overall deadlines."""
from dataclasses import asdict
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import Protocol
import json
import os
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener


class ModelError(RuntimeError):
    def __init__(self, code):
        allowed = {'timeout','auth','quota','network','server','format','empty','network_disabled','model_failure','cancelled','truncated'}
        self.code = code if code in allowed else 'model_failure'
        super().__init__(self.code)


class Model(Protocol):
    def complete(self, messages: list[dict[str,str]], cancel_check=None) -> str: ...


class FakeModel:
    def complete(self, messages, cancel_check=None):
        name = ''
        for message in messages:
            if message['content'].startswith('记忆数据 JSON：'):
                try:
                    rows = json.loads(message['content'].split('：',1)[1])
                    name = next((r['value'] for r in rows if r['key'] == '称呼'), '')
                except (ValueError, TypeError, KeyError):
                    pass
        latest = messages[-1]['content']
        return f'（离线模拟）{name + "，" if name else ""}收到：{latest[:200]}。此回复来自假模型。'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_request(c, messages):
    request_body = {'model':c.name, 'messages':messages, 'stream':False}
    if c.provider == 'deepseek':
        request_body.update(max_tokens=c.max_completion_tokens, thinking={'type':'disabled'})
    elif c.provider == 'chat_completions':
        request_body.update(max_completion_tokens=c.max_completion_tokens, store=False)
    else:
        raise ModelError('model_failure')
    payload = json.dumps(request_body, ensure_ascii=False).encode('utf-8')
    try:
        request = Request(c.endpoint, data=payload, headers={'Content-Type':'application/json',
                          'Authorization':'Bearer '+c.api_key}, method='POST')
        with build_opener(NoRedirect()).open(request, timeout=float(c.timeout_seconds)) as response:
            body = response.read(1_048_577)
        if len(body)>1_048_576:
            raise ModelError('format')
        obj = json.loads(body)
        choice = obj['choices'][0]
        message = choice['message']
        reply = message['content']
        if not isinstance(reply,str):
            raise ModelError('format')
        if not reply.strip():
            raise ModelError('empty')
        if c.provider == 'deepseek':
            if choice.get('finish_reason') == 'length':
                raise ModelError('truncated')
            if (choice.get('finish_reason') != 'stop'
                    or message.get('reasoning_content') not in (None, '')
                    or message.get('tool_calls') or message.get('function_call')):
                raise ModelError('format')
            if len(reply.strip()) > c.max_reply_chars:
                raise ModelError('truncated')
        return reply.strip()[:c.max_reply_chars]
    except HTTPError as error:
        code = 'auth' if error.code in (401,403) else 'quota' if error.code in (402,429) else 'server'
        error.close()
        raise ModelError(code) from None
    except (TimeoutError,socket.timeout):
        raise ModelError('timeout') from None
    except URLError as error:
        raise ModelError('timeout' if isinstance(error.reason,(TimeoutError,socket.timeout)) else 'network') from None
    except (OSError,ConnectionError):
        raise ModelError('network') from None
    except (ValueError,KeyError,IndexError,TypeError,UnicodeError):
        raise ModelError('format') from None


def _http_worker():
    """Private UTF-8 pipe protocol; credentials never appear in process arguments."""
    try:
        request = json.loads(sys.stdin.buffer.read())
        result = ('ok', _http_request(SimpleNamespace(**request['config']), request['messages']))
    except ModelError as error:
        result = ('error', error.code)
    except BaseException:
        result = ('error', 'model_failure')
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
    sys.stdout.buffer.flush()


class ChatCompletionsModel:
    def __init__(self, config):
        self.config = config

    def complete(self, messages, cancel_check=None):
        c = self.config
        if not c.allow_network:
            raise ModelError('network_disabled')
        if not c.api_key:
            raise ModelError('auth')
        # Explicit standard handles avoid Windows spawn stalling when the CLI's
        # reader is blocked on stdin. Only pipe I/O runs in a thread; the network
        # request stays in a process that can be terminated on cancel or timeout.
        deadline = time.monotonic()+float(c.timeout_seconds)
        request = json.dumps({'config':asdict(c), 'messages':messages}, ensure_ascii=False).encode('utf-8')
        worker = None
        exchange_thread = None
        try:
            worker = subprocess.Popen(
                [sys.executable, '-X', 'utf8', str(Path(__file__).resolve())],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            finished = Event()
            responses = []

            def exchange():
                try:
                    output, _ = worker.communicate(request)
                    responses.append(output)
                except (OSError, ValueError):
                    pass
                finally:
                    finished.set()

            exchange_thread = Thread(target=exchange, daemon=True)
            exchange_thread.start()
            while True:
                if cancel_check and cancel_check():
                    raise ModelError('cancelled')
                remaining = deadline-time.monotonic()
                if remaining<=0:
                    raise ModelError('timeout')
                if finished.wait(min(.05, remaining)):
                    if not responses or worker.returncode != 0:
                        raise ModelError('network')
                    status, payload = json.loads(responses[0])
                    if not isinstance(payload, str) or status not in ('ok', 'error'):
                        raise ModelError('format')
                    if status == 'ok':
                        return payload
                    raise ModelError(payload)
        except OSError:
            raise ModelError('network') from None
        except (ValueError, TypeError):
            raise ModelError('format') from None
        finally:
            if worker is not None:
                if worker.poll() is None:
                    worker.terminate()
                try:
                    worker.wait(timeout=.3)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=.3)
                if exchange_thread is not None:
                    exchange_thread.join(timeout=.3)
                else:
                    worker.stdin.close()
                    worker.stdout.close()


if __name__ == '__main__':
    _http_worker()
