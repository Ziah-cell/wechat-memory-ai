"""Ephemeral, supervised read-only gate; no Engine, model, storage or sending.

A fresh marker blocks candidates caused by starting in an older viewport.
It does not establish server time or rule out later history synchronization.
"""
import secrets

from .live_read import ReadError, VisualOccurrenceSession


class PreflightSession:
    def __init__(self):
        self._session = VisualOccurrenceSession()
        self._challenge = None
        self._boundary_observed = False
        self._closed = False
        self._discarded = 0
        self._incoming = 0
        self._self = 0
        self._unknown = 0

    @property
    def challenge_text(self):
        if not self._closed and not self._boundary_observed:
            return self._challenge
        return None

    def close(self):
        self._closed = True

    def stop(self, reason):
        self.close()
        self._session.stop(reason)

    def _reject(self, reason):
        self.stop(reason)
        raise ReadError('read_session_stopped')

    def accept(self, raw):
        if self._closed:
            raise ReadError('session_stopped')
        try:
            observations = self._session.accept(raw)
        except ReadError:
            self.close()
            raise
        if self._challenge is None:
            if self._session.report()['status'] == 'reading':
                # Generate only after a nonempty, bound baseline. Never reuse a
                # previous session's test text as evidence for a new boundary.
                self._challenge = '只读验证' + secrets.token_hex(8)
                if any(row['text'] == self._challenge for row in raw['rows']):
                    self._reject('preflight_marker_in_baseline')
            return []
        markers = [item for item in observations if item.text == self._challenge]
        if not self._boundary_observed:
            if markers:
                texts = [row['text'] for row in raw['rows']
                         if row['kind'] == 'text' and row['text'].strip()]
                if (len(markers) != 1 or markers[0].direction != 'incoming_candidate'
                        or texts.count(self._challenge) != 1 or texts[-1] != self._challenge):
                    self._reject('preflight_marker_ambiguous')
                self._boundary_observed = True
            # Discard the whole marker batch, including any other candidates.
            self._discarded += len(observations)
            return []
        if markers:
            self._reject('preflight_marker_repeated')
        incoming = [item for item in observations if item.direction == 'incoming_candidate']
        self._incoming += len(incoming)
        self._self += sum(item.direction == 'self_candidate' for item in observations)
        self._unknown += sum(item.direction == 'unknown' for item in observations)
        return incoming

    def report(self):
        report = self._session.report()
        state = ('closed' if self._closed else 'armed' if self._boundary_observed
                 else 'waiting_marker' if self._challenge is not None else 'waiting_baseline')
        report.update(mode='supervised_readonly_preflight', preflight_state=state,
                      marker_boundary_observed=self._boundary_observed,
                      pre_marker_discarded_texts=self._discarded,
                      post_marker_incoming_candidates=self._incoming,
                      filtered_self_texts=self._self, filtered_unknown_texts=self._unknown)
        return report
