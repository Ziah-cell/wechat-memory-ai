"""OS-owned instance locking and local, generation-bound control messages."""
from pathlib import Path
import json
import os
import tempfile
import time
import uuid


class AlreadyRunning(RuntimeError):
    pass


class InstanceLock:
    def __init__(self, directory, timeout=.5):
        self.directory = Path(directory)
        self.file = None
        self.timeout = timeout

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.file = open(self.directory / 'instance.lock', 'a+b')
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    self.file.close()
                    self.file = None
                    raise AlreadyRunning('already_running') from None
                time.sleep(.01)
        return self

    def __exit__(self, *_):
        if self.file:
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None
        # Never unlink an OS lock file: unlinking can allow two inode-based locks.


def atomic_json(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.control-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as target:
            json.dump(value, target, ensure_ascii=False)
            target.flush()
            os.fsync(target.fileno())
        # Windows readers can briefly deny replacement of an open status file.
        # Keep the last complete JSON until publication succeeds, and never
        # spin indefinitely on a persistent permission or sharing failure.
        for attempt in range(20):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(.01)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path):
    try:
        path = Path(path)
        if path.stat().st_size > 4096:
            return {}
        value = json.loads(path.read_text('utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def runtime_status(directory):
    directory = Path(directory)
    result = read_json(directory / 'runtime.json')
    try:
        with InstanceLock(directory, timeout=0):
            active = False
    except AlreadyRunning:
        active = True
    if not active:
        result['phase'] = 'stopped'
    else:
        result.setdefault('phase', 'busy')
    result['active'] = active
    return result


def send_control(directory, action):
    if action not in ('pause','resume','stop'):
        raise ValueError('invalid_control')
    directory = Path(directory)
    status = runtime_status(directory)
    if not status['active'] or not status.get('run_id'):
        raise ValueError('not_running')
    atomic_json(directory / 'control.json', {'action':action, 'run_id':status['run_id'], 'id':uuid.uuid4().hex})


class Controller:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.run_id = uuid.uuid4().hex
        self.last_id = None
        self.phase = None

    def publish(self, phase):
        if phase != self.phase:
            atomic_json(self.directory / 'runtime.json', {'pid':os.getpid(), 'run_id':self.run_id, 'phase':phase})
            self.phase = phase

    def poll(self):
        item = read_json(self.directory / 'control.json')
        if item.get('run_id') != self.run_id or not item.get('id') or item.get('id') == self.last_id:
            return None
        self.last_id = item['id']
        return item.get('action')
