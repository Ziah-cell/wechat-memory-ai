"""Transport contracts and a local simulator. No desktop automation is imported."""
from collections import deque
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Protocol


@dataclass(frozen=True)
class Event:
    id: str
    peer_id: str
    conversation_id: str
    text: str
    timestamp: float
    is_self: bool = False
    is_group: bool = False
    kind: str = 'text'
    display_name: str = '' # never used for authorization or logs


@dataclass(frozen=True)
class Identity:
    peer_id: str
    conversation_id: str
    verified: bool = True
    connected: bool = True


class SendOutcome(Enum):
    DELIVERED = 'delivered'
    NOT_SENT = 'not_sent'
    UNKNOWN = 'unknown'


class Adapter(Protocol):
    mode: str
    def identity(self) -> Identity: ...
    def poll(self) -> list[Event]: ...
    def send(self, expected: Identity, text: str) -> SendOutcome: ...


class MockAdapter:
    mode = 'mock'

    def __init__(self, peer_id):
        self._identity = Identity(peer_id, peer_id)
        self._incoming = deque()
        self._lock = RLock()
        self.sent = [] # simulated outbox; contains only this local run

    def identity(self):
        with self._lock:
            return self._identity

    def select(self, identity):
        """Simulator equivalent of changing the active window/connection."""
        with self._lock:
            self._identity = identity

    def feed(self, event):
        with self._lock:
            if len(self._incoming) >= 1024:
                raise BufferError('mock_queue_full')
            self._incoming.append(event)

    def poll(self):
        with self._lock:
            if not self._identity.connected:
                raise ConnectionError('mock_disconnected')
            events = list(self._incoming)
            self._incoming.clear()
            return events

    def send(self, expected, text):
        # The simulator checks identity while holding the same lock as select().
        # Future UI adapters cannot infer atomicity from this mock implementation.
        with self._lock:
            current = self._identity
            if current != expected or not current.connected or not current.verified:
                return SendOutcome.NOT_SENT
            self.sent.append({'peer_id': current.peer_id, 'text': text})
            if len(self.sent) > 1024:
                del self.sent[:-1024]
            return SendOutcome.DELIVERED
