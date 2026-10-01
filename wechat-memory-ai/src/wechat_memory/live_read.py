"""Bounded read-only WeChat connection; no input, model, database or send calls.

Observation IDs identify this local reading session, not WeChat server messages.
Runtime IDs are only continuity tokens within an unchanged window/list instance.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid


class ReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Observation:
    observation_id: str
    text: str
    direction: str = 'unverified'


def validate_snapshot(raw):
    if not isinstance(raw, dict) or set(raw) != {'status','process','started','window','root','list_token','rows'}:
        raise ReadError('invalid_snapshot')
    if raw['status'] != 'snapshot':
        raise ReadError('reader_unavailable')
    for field in ('process','window'):
        if type(raw[field]) is not int or not 0 < raw[field] < 2**63:
            raise ReadError('invalid_snapshot')
    for field in ('started','root','list_token'):
        if not isinstance(raw[field], str) or not 1 <= len(raw[field]) <= 256:
            raise ReadError('invalid_snapshot')
    if not re.fullmatch(r'ChatSingleWindowwxid_[A-Za-z0-9_-]{1,100}', raw['root']):
        raise ReadError('independent_private_chat_required')
    if not isinstance(raw['rows'], list) or len(raw['rows']) > 256:
        raise ReadError('invalid_snapshot')
    rows, seen = [], set()
    for row in raw['rows']:
        if not isinstance(row,dict) or set(row) != {'token','text','kind'}:
            raise ReadError('invalid_snapshot')
        if (not isinstance(row['token'],str) or not 1 <= len(row['token']) <= 256
                or row['token'] in seen or row['kind'] not in ('text','other')
                or not isinstance(row['text'],str) or len(row['text']) > 10000):
            raise ReadError('invalid_snapshot')
        seen.add(row['token'])
        # Remember content consistency without retaining old message plaintext.
        fingerprint = hashlib.sha256((row['kind']+'\0'+row['text']).encode('utf-8')).hexdigest()
        rows.append((row['token'], fingerprint, row['kind'], row['text']))
    identity = tuple(raw[k] for k in ('process','started','window','root','list_token'))
    return identity, rows


class ReadSession:
    def __init__(self):
        self._identity = None
        self._rows = []
        self._seen_tokens = set()
        self._epoch = uuid.uuid4().hex
        self._sequence = 0
        self._texts = 0
        self._snapshots = 0
        self._state = 'waiting'

    def accept(self, raw):
        if self._state == 'stopped':
            raise ReadError('session_stopped')
        try:
            identity, rows = validate_snapshot(raw)
            current = [(r[0],r[1]) for r in rows]
            if self._identity is None:
                self._identity, self._rows = identity, current
                self._seen_tokens.update(r[0] for r in current)
                self._state = 'reading' if current else 'initializing'
                self._snapshots += 1
                return []
            if identity != self._identity:
                raise ReadError('window_or_list_changed')
            if self._state == 'initializing':
                self._rows = current
                self._seen_tokens.update(r[0] for r in current)
                self._state = 'reading' if current else 'initializing'
                self._snapshots += 1
                return []
            overlap = len(self._rows)
            if current[:overlap] != self._rows:
                # Only a complete old suffix may anchor a front eviction.
                # Require two unchanged rows and at least one appended row.
                for start in range(1, len(self._rows) - 1):
                    overlap = len(self._rows) - start
                    if len(current) > overlap and current[:overlap] == self._rows[start:]:
                        break
                else:
                    raise ReadError('message_continuity_lost')
            appended = rows[overlap:]
            new_tokens = {r[0] for r in appended}
            # Validate the entire batch before advancing counters or returning
            # observations. Evicted tokens remain known for this session.
            if new_tokens & self._seen_tokens:
                raise ReadError('message_token_reused')
            if len(self._seen_tokens) + len(new_tokens) > 4096:
                raise ReadError('session_token_limit')
            observations = []
            for _, _, kind, text in appended:
                self._sequence += 1
                if kind == 'text' and text.strip():
                    self._texts += 1
                    observations.append(Observation(self._epoch+':'+str(self._sequence),text))
            self._rows = current
            self._seen_tokens.update(new_tokens)
            self._snapshots += 1
            return observations
        except (ReadError, TypeError, ValueError):
            self._state = 'stopped'
            raise ReadError('read_session_stopped') from None

    def report(self):
        return dict(status=self._state, snapshots=self._snapshots,
                    window_bound=self._identity is not None,
                    observed_new_rows=self._sequence, observed_new_texts=self._texts,
                    sender_verified=False, server_message_ids_available=False,
                    history_boundary_verified=False,
                    real_send_supported=False, model_called=False)


class NativeReader:
    def __init__(self, client_path):
        try:
            self.client_path = str(Path(client_path).resolve())
        except (OSError,ValueError,TypeError):
            raise ReadError('invalid_client_path') from None
        self.executable = None
        self._temporary = None
        self._binding = None

    def __enter__(self):
        if os.name != 'nt':
            raise ReadError('windows_required')
        framework = Path(os.environ.get('SystemRoot',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319'
        compiler = framework/'csc.exe'
        try:
            if not compiler.is_file():
                raise ReadError('system_compiler_unavailable')
            self._temporary = tempfile.TemporaryDirectory(prefix='wechat-read-')
            self.executable = Path(self._temporary.name)/'reader.exe'
            args = [str(compiler),'/nologo','/target:exe','/platform:x64',
                    '/out:'+str(self.executable),'/reference:'+str(framework/'System.Web.Extensions.dll')]
            args += ['/reference:'+str(framework/'WPF'/name) for name in
                     ('UIAutomationClient.dll','UIAutomationTypes.dll','WindowsBase.dll')]
            args.append(str(Path(__file__).with_name('live_reader.cs')))
            done = subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,timeout=25,
                                  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if done.returncode or not self.executable.is_file():
                raise ReadError('reader_build_failed')
            return self
        except (OSError,subprocess.TimeoutExpired,ReadError):
            self.__exit__(ReadError,None,None)
            raise ReadError('reader_build_failed') from None

    def __exit__(self, *args):
        if self._temporary:
            try:
                self._temporary.cleanup()
            except OSError:
                if not args or args[0] is None:
                    raise ReadError('reader_cleanup_failed') from None
            finally:
                self._temporary = None

    def read(self):
        try:
            done = subprocess.run([str(self.executable),self.client_path],
                                  input=json.dumps(self._binding).encode('utf-8'),capture_output=True,timeout=8,
                                  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if done.returncode or len(done.stdout) > 4_000_000:
                raise ReadError('native_reader_failed')
            raw = json.loads(done.stdout.decode('utf-8-sig'))
            validate_snapshot(raw)
            binding = {key:raw[key] for key in ('process','started','window','root','list_token')}
            if self._binding is not None and binding != self._binding:
                raise ReadError('bound_window_changed')
            self._binding = binding
            return raw
        except (OSError,subprocess.TimeoutExpired,ValueError,TypeError,RecursionError,ReadError):
            raise ReadError('native_reader_unavailable') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read only one independent WeChat private-chat window.')
    parser.add_argument('--client-path',required=True)
    parser.add_argument('--seconds',type=int,default=30)
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 300:
        parser.error('seconds must be between 1 and 300')
    session = ReadSession()
    try:
        with NativeReader(args.client_path) as reader:
            deadline = time.monotonic()+args.seconds
            while True:
                session.accept(reader.read())
                print(json.dumps(session.report(),sort_keys=True),flush=True)
                if time.monotonic() >= deadline:
                    break
                time.sleep(1)
        return 0
    except (ReadError,KeyboardInterrupt):
        session._state = 'stopped'
        print(json.dumps(session.report(),sort_keys=True),flush=True)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
