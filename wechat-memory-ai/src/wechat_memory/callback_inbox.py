"""Bounded callback transport; no UI, database, model or identity inference.

Generation tokens only revoke in-process subscriptions. They are NOT peer or
message IDs. An event already handed to a consumer cannot be recalled; that
consumer must still check identity and cancellation at its own boundaries.
"""
from collections import deque
from threading import RLock, current_thread

from .adapters import Event


def _bounded_event(event):
    if type(event) is not Event:
        return False
    if any(type(value) is not str or len(value) > bound for value, bound in (
            (event.id, 256), (event.peer_id, 256), (event.conversation_id, 256),
            (event.text, 10000), (event.display_name, 256), (event.kind, 256))):
        return False
    return (bool(event.id) and type(event.timestamp) in (int, float)
            and 0 <= event.timestamp <= 1e12
            and type(event.is_self) is bool and type(event.is_group) is bool)


class CallbackInbox:
    """Many producers enqueue; only the constructing thread may consume/rearm."""
    def __init__(self, capacity=128):
        if type(capacity) is not int or not 1 <= capacity <= 1024:
            raise ValueError('invalid_capacity')
        self._capacity = capacity
        self._owner = current_thread()
        self._lock = RLock()
        self._pending = deque()
        self._generation = object()
        self._state = 'idle'

    def _require_owner(self):
        if current_thread() is not self._owner:
            raise RuntimeError('owner_thread_required')

    def _invalidate(self, state):
        self._generation = object()
        self._pending.clear()
        self._state = state

    def begin(self):
        """Discard prior backlog and return a new callback; never infer identity."""
        self._require_owner()
        with self._lock:
            if self._state == 'closed':
                raise RuntimeError('inbox_closed')
            self._invalidate('accepting')
            generation = self._generation

        def callback(event):
            # Non-blocking with respect to queue capacity: no producer waits for
            # the consumer/model/SQLite. The lock protects short memory changes.
            with self._lock:
                if generation is not self._generation or self._state != 'accepting':
                    return 'stale_callback'
                if not _bounded_event(event):
                    return 'invalid_event'
                if len(self._pending) >= self._capacity:
                    self._invalidate('overflow')
                    return 'overflow'
                self._pending.append(event)
                return 'queued'
        return callback

    def suspend(self, reason='paused'):
        if reason not in ('paused', 'window_changed', 'disconnected'):
            raise ValueError('invalid_suspend_reason')
        with self._lock:
            if self._state != 'closed':
                self._invalidate(reason)

    def close(self):
        with self._lock:
            self._invalidate('closed')

    def status(self):
        with self._lock:
            return {'state': self._state, 'pending': len(self._pending)}

    def consume(self, consumer, limit=1024):
        self._require_owner()
        if not callable(consumer) or type(limit) is not int or not 1 <= limit <= 1024:
            raise ValueError('invalid_consumer_or_limit')
        with self._lock:
            generation = self._generation
        consumed = 0
        while consumed < limit:
            with self._lock:
                if (self._state != 'accepting' or generation is not self._generation
                        or not self._pending):
                    break
                event = self._pending.popleft()
            # Never hold the queue lock during database/model/user code.
            try:
                consumer(event)
            except Exception:
                with self._lock:
                    if self._state != 'closed':
                        self._invalidate('consumer_failed')
                raise RuntimeError('consumer_failed') from None
            consumed += 1
        return consumed
