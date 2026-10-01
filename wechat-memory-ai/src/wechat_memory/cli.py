"""Local console simulator and maintenance commands; stdout is intentionally user-visible."""
import argparse
from dataclasses import asdict
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
import json
import platform
import sqlite3
import sys
import time
import uuid

from .adapters import Event, MockAdapter
from .audit import Audit
from .backup import BackupError, backup_store, restore_backup
from .config import ConfigError, load_config
from .engine import Engine
from .models import ChatCompletionsModel, FakeModel
from .operations import Operations
from .runtime import AlreadyRunning, Controller, InstanceLock, runtime_status, send_control
from .store import Store


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def _stdin_reader(queue):
    # Daemon reader lets the main thread receive stop while stdin is idle.
    while True:
        line = sys.stdin.readline(65537)
        if not line:
            queue.put(None)
            return
        if len(line) > 65536:
            while line and not line.endswith('\n'):
                line = sys.stdin.readline(65537)
            queue.put({'invalid':True})
        else:
            queue.put(line.rstrip('\r\n'))


def run_console(config, jsonl=False):
    with InstanceLock(config.data_dir):
        store = Store(config.data_dir)
        audit = Audit(config.data_dir / 'logs')
        controller = Controller(config.data_dir)
        model = FakeModel() if config.model.provider == 'fake' else ChatCompletionsModel(config.model)
        adapter = MockAdapter(config.peer_id)
        engine = Engine(config, store, adapter, model, audit, controller.poll)
        queue = Queue(maxsize=128)
        reader = Thread(target=_stdin_reader, args=(queue,), daemon=True)
        reader.start()
        controller.publish('running')
        try:
            while True:
                state = engine._control()
                controller.publish(state or ('review_required' if engine.ops.unresolved() else 'running'))
                if engine.stopped:
                    break
                try:
                    line = queue.get(timeout=.1)
                except Empty:
                    continue
                if line is None or (not jsonl and line == '/退出'):
                    break
                try:
                    if not isinstance(line, str):
                        raise ValueError
                    obj = json.loads(line) if jsonl else {'text':line}
                    if not isinstance(obj, dict):
                        raise ValueError
                    # Missing timestamps describe NEW simulated input only, never real history.
                    values = dict(id=uuid.uuid4().hex, peer_id=config.peer_id,
                                  conversation_id=config.peer_id, timestamp=time.time())
                    values.update(obj)
                    event = Event(**values)
                    adapter.feed(event)
                except (ValueError, TypeError):
                    emit({'status':'invalid_input','reply':'输入格式错误；未调用模型或发送。'})
                    continue
                for event in adapter.poll():
                    result = engine.process(event)
                    emit(asdict(result))
        except KeyboardInterrupt:
            pass
        finally:
            controller.publish('stopped')
            audit.close()
            store.close()
    return 0


def parser():
    p = argparse.ArgumentParser(description='普通个人微信 AI 的离线核心；本版不接入真实微信')
    p.add_argument('--config', default='config.toml')
    sub = p.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', help='控制台模拟聊天')
    run.add_argument('--jsonl', action='store_true', help='每行一条 JSON 模拟事件')
    for command in ('status','pause','resume','stop','diagnose'):
        sub.add_parser(command)
    backup = sub.add_parser('backup')
    backup.add_argument('destination')
    restore = sub.add_parser('restore')
    restore.add_argument('source')
    restore.add_argument('--guard', help='新电脑上显式提供最新 guard.sqlite3')
    restore.add_argument('--confirm', action='store_true', help='确认替换本地会话内容库')
    review = sub.add_parser('review')
    review.add_argument('--resolve', help='待核查的事件散列 ID')
    review.add_argument('--outcome', choices=['sent','not_sent'])
    return p


def main(argv=None):
    # JSONL and redirected console input use UTF-8 regardless of Windows' ANSI
    # code page. Configure before starting the reader thread.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == 'run':
            return run_console(config, args.jsonl)
        if args.command == 'status':
            emit(runtime_status(config.data_dir))
        elif args.command in ('pause','resume','stop'):
            send_control(config.data_dir, args.command)
            emit({'status':'requested','action':args.command})
        elif args.command == 'diagnose':
            emit({'python':platform.python_version(), 'os':platform.system(), 'sqlite':sqlite3.sqlite_version,
                  'adapter':config.adapter, 'model_provider':config.model.provider, 'dry_run':config.dry_run,
                  'network_enabled':config.model.allow_network, 'real_send_supported':False,
                  'real_wechat_verified':False, 'wechat_client_version':'not_checked'})
        elif args.command == 'restore':
            if not args.confirm:
                raise BackupError('restore_requires_--confirm')
            with InstanceLock(config.data_dir):
                restore_backup(Path(args.source).resolve(), config.data_dir,
                               Path(args.guard).resolve() if args.guard else None)
            emit({'status':'restored','warning':'only local content; latest guard preserved'})
        elif args.command == 'backup':
            with InstanceLock(config.data_dir):
                store = Store(config.data_dir)
                try:
                    backup_store(store, Path(args.destination).resolve())
                finally:
                    store.close()
            emit({'status':'backed_up','warning':'preserve latest guard.sqlite3 separately after stopping the app'})
        elif args.command == 'review':
            with InstanceLock(config.data_dir):
                store = Store(config.data_dir)
                try:
                    ops = Operations(store)
                    ops.recover()
                    if args.resolve:
                        if not args.outcome:
                            raise ValueError('review_outcome_required')
                        emit({'resolved':ops.resolve(args.resolve,args.outcome),'automatic_resend':False})
                    else:
                        emit({'unresolved':ops.unresolved()})
                finally:
                    store.close()
        return 0
    except AlreadyRunning:
        print('already_running: 此数据目录正被另一实例或维护操作占用。', file=sys.stderr)
        return 3
    except ConfigError as error:
        print('config_error: '+str(error), file=sys.stderr)
        return 2
    except BackupError as error:
        print('backup_error: '+str(error), file=sys.stderr)
        return 4
    except ValueError as error:
        safe = str(error) if str(error) in ('not_running','review_outcome_required','guard_missing: use the latest guard before opening existing content',
                                           'guard_lineage_mismatch','guard_older_than_content') else 'invalid_operation'
        print(safe, file=sys.stderr)
        return 4
    except (OSError, sqlite3.Error):
        print('local_io_error: 请检查配置、数据目录与剩余磁盘空间。', file=sys.stderr)
        return 5


if __name__ == '__main__':
    raise SystemExit(main())
