"""One supervised window source; no Engine, model, memory, or send integration."""
from dataclasses import dataclass, field
import math
from threading import current_thread
import time
import uuid
from weakref import WeakValueDictionary

from .live_read import NativeReader, ReadError, _STOP_REASONS, validate_binding
from .preflight import PreflightSession


@dataclass(frozen=True)
class LiveCandidate:
    source_id: str = field(repr=False)
    observation_id: str = field(repr=False)
    text: str = field(repr=False)
    observed_at: float
    sender_verified: bool = field(default=False, init=False)
    history_boundary_verified: bool = field(default=False, init=False)


_SOURCE_REASONS = frozenset({
    'source_closed', 'source_not_active', 'source_already_entered',
    'source_deadline_reached', 'source_owner_thread_required',
    'source_operation_in_progress', 'source_clock_invalid',
    'source_observation_time_invalid', 'source_open_failed',
    'source_read_failed', 'source_context_failed', 'source_candidate_limit',
})


class ReadOnlyWeChatSource:
    """Serial, owner-thread access to a single explicitly authorized binding.

    Candidate IDs and observed_at are local observations, not server metadata.
    Closing revokes is_current; it cannot revoke values already held by callers.
    """

    def __init__(self, client_path, *, expected_binding, seconds=300):
        if expected_binding is None:
            raise ReadError('invalid_snapshot')
        self._expected_binding = validate_binding(expected_binding)
        if type(seconds) not in (int, float) or not 1 <= seconds <= 3600 or not math.isfinite(seconds):
            raise ReadError('invalid_source_duration')
        self._client_path = client_path
        self._seconds = float(seconds)
        self._owner = current_thread()
        self._busy = False
        self._state = 'new'
        self._stop_reason = None
        self._source_id = uuid.uuid4().hex
        self._session = PreflightSession()
        self._manager = None
        self._reader = None
        self._reader_entered = False
        self._deadline = None
        self._last_clock = None
        self._emitted = 0
        self._issued = WeakValueDictionary()

    def _check_access(self):
        if current_thread() is not self._owner:
            raise ReadError('source_owner_thread_required')
        if self._busy:
            raise ReadError('source_operation_in_progress')

    def _clock(self):
        try:
            value = time.monotonic()
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or (self._last_clock is not None and value < self._last_clock)):
                raise ValueError()
            value = float(value)
        except Exception:
            raise ReadError('source_clock_invalid') from None
        self._last_clock = value
        return value

    def _check_deadline(self):
        if self._clock() >= self._deadline:
            raise ReadError('source_deadline_reached')

    def _reason(self, error, fallback):
        reason = str(error) if isinstance(error, ReadError) else fallback
        if reason == 'read_session_stopped':
            reason = self._session.report()['stop_reason']
        return reason if reason in _STOP_REASONS or reason in _SOURCE_REASONS else fallback

    def _finish(self, reason, exc_info=(None, None, None), *, suppress_cleanup=False):
        if self._state == 'closed':
            return
        # Revoke before cleanup, including when cleanup itself fails.
        self._state = 'closed'
        self._stop_reason = reason
        self._session.close()
        self._issued.clear()
        manager = self._manager if self._reader_entered else None
        self._reader_entered = False
        self._reader = None
        self._manager = None
        if manager is not None:
            try:
                manager.__exit__(*exc_info)
            except Exception:
                if not suppress_cleanup:
                    self._stop_reason = 'reader_cleanup_failed'
                    raise ReadError('reader_cleanup_failed') from None

    def _abort(self, error, fallback):
        reason = 'interrupted' if isinstance(error, KeyboardInterrupt) else self._reason(error, fallback)
        self._finish(reason, (type(error), error, error.__traceback__), suppress_cleanup=True)
        if not isinstance(error, Exception):
            raise error
        raise ReadError(reason) from None

    def __enter__(self):
        self._check_access()
        if self._state != 'new':
            raise ReadError('source_closed' if self._state == 'closed' else 'source_already_entered')
        self._busy = True
        try:
            self._deadline = self._clock() + self._seconds
            if not math.isfinite(self._deadline):
                raise ReadError('source_clock_invalid')
            self._manager = NativeReader(self._client_path, expected_binding=dict(self._expected_binding))
            self._reader = self._manager.__enter__()
            self._reader_entered = True
            self._check_deadline()
            self._state = 'active'
            return self
        except BaseException as error:
            self._abort(error, 'source_open_failed')
        finally:
            self._busy = False

    def __exit__(self, exc_type, exc_value, traceback):
        self._check_access()
        self._busy = True
        try:
            self._finish('source_closed' if exc_type is None else 'source_context_failed',
                         (exc_type, exc_value, traceback), suppress_cleanup=exc_type is not None)
        finally:
            self._busy = False
        return False

    def close(self):
        self._check_access()
        self._busy = True
        try:
            self._finish('source_closed')
        finally:
            self._busy = False

    def poll(self):
        self._check_access()
        if self._state != 'active':
            raise ReadError('source_closed' if self._state == 'closed' else 'source_not_active')
        self._busy = True
        try:
            self._check_deadline()
            raw = self._reader.read(visual_text=True)
            self._check_deadline()
            if not isinstance(raw, dict) or not self._expected_binding.keys() <= raw.keys():
                raise ReadError('invalid_snapshot')
            actual = validate_binding({key: raw[key] for key in self._expected_binding})
            if actual != self._expected_binding:
                raise ReadError('window_or_list_changed')
            observations = self._session.accept(raw)
            if not observations:
                return []
            if self._emitted + len(observations) > 4096:
                raise ReadError('source_candidate_limit')
            try:
                observed_at = time.time()
                if (type(observed_at) not in (int, float) or observed_at < 0
                        or not math.isfinite(observed_at)):
                    raise ValueError()
                observed_at = float(observed_at)
            except Exception:
                raise ReadError('source_observation_time_invalid') from None
            candidates = [LiveCandidate(self._source_id, item.observation_id, item.text, observed_at)
                          for item in observations]
            self._check_deadline()
            # Commit the complete batch only after all checks. Weak references
            # prove object issuance without keeping consumers' plaintext alive.
            for item in candidates:
                self._issued[item.observation_id] = item
            self._emitted += len(candidates)
            return candidates
        except BaseException as error:
            self._abort(error, 'source_read_failed')
        finally:
            self._busy = False

    def _refresh_active(self):
        if self._state != 'active':
            return False
        self._busy = True
        try:
            self._check_deadline()
        except ReadError as error:
            self._finish(self._reason(error, 'source_read_failed'), suppress_cleanup=True)
        finally:
            self._busy = False
        return self._state == 'active'

    @property
    def challenge_text(self):
        self._check_access()
        return self._session.challenge_text if self._refresh_active() else None

    def is_current(self, candidate):
        self._check_access()
        return (self._refresh_active() and type(candidate) is LiveCandidate
                and isinstance(candidate.observation_id, str)
                and self._issued.get(candidate.observation_id) is candidate)

    def report(self):
        self._check_access()
        active = self._refresh_active()
        progress = self._session.report()
        return dict(state=self._state, active=active, stop_reason=self._stop_reason,
                    emitted_candidates=self._emitted, snapshots=progress['snapshots'],
                    marker_boundary_observed=progress['marker_boundary_observed'],
                    observation_ids_are_local=True, observed_at_is_local=True,
                    sender_verified=False, history_boundary_verified=False,
                    server_message_ids_available=False, real_send_supported=False,
                    model_called=False, memory_written=False)

    def send(self, *args, **kwargs):
        raise ReadError('real_send_disabled')
