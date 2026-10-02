"""Bounded read-only WeChat connection; no input, model, database or send calls.

Observation IDs identify this local reading session, not WeChat server messages.
Runtime IDs are only continuity tokens within an unchanged window/list instance.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid


class ReadError(RuntimeError):
    pass


_NATIVE_REASONS = frozenset({
    'client_unavailable', 'process_inspection_failed', 'window_discovery_failed',
    'private_window_not_unique', 'window_minimized', 'window_binding_unavailable',
    'window_or_list_changed', 'message_tree_unavailable', 'message_list_unavailable',
    'message_rows_unavailable', 'layout_unavailable', 'capabilities_unavailable', 'native_reader_failed',
    'visual_capture_unavailable', 'visual_snapshot_changed',
})

_STOP_REASONS = _NATIVE_REASONS | frozenset({
    'invalid_snapshot', 'reader_unavailable', 'independent_private_chat_required',
    'window_or_list_changed', 'message_continuity_lost', 'message_token_reused',
    'session_token_limit', 'windows_required', 'invalid_client_path',
    'reader_build_failed', 'reader_cleanup_failed', 'native_reader_unavailable',
    'interrupted', 'read_failed', 'native_reader_timeout',
    'occurrence_reappeared', 'session_occurrence_limit',
})


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


def layout_report(raw):
    """Inspect geometry availability, never infer a sender or expose row identity."""
    if (not isinstance(raw,dict) or raw.get('status') != 'layout_snapshot'
            or not isinstance(raw.get('rows'),list) or len(raw['rows']) > 256):
        raise ReadError('invalid_snapshot')
    text_rows = []
    validation_rows = []
    for row in raw['rows']:
        if not isinstance(row,dict) or set(row) != {
                'token','kind','left_gap','right_gap','width_ratio','has_children'}:
            raise ReadError('invalid_snapshot')
        for field in ('left_gap','right_gap','width_ratio'):
            value = row[field]
            if type(value) not in (int,float) or not -100 <= value <= 100 or not math.isfinite(value):
                raise ReadError('invalid_snapshot')
        if row['width_ratio'] <= 0 or type(row['has_children']) is not bool:
            raise ReadError('invalid_snapshot')
        validation_rows.append(dict(token=row['token'],kind=row['kind'],text=''))
        if row['kind'] == 'text':
            text_rows.append(row)
    # Reuse the strict binding, token, row-count and kind contract without
    # requesting or retaining message names in the layout provider.
    validate_snapshot(dict(raw,status='snapshot',rows=validation_rows))
    return dict(status='layout_observed',rows=len(raw['rows']),text_rows=len(text_rows),
                full_width_text_rows=sum(abs(r['left_gap']) <= 0.01 and abs(r['right_gap']) <= 0.01
                                         and abs(r['width_ratio']-1) <= 0.02 for r in text_rows),
                text_rows_with_children=sum(r['has_children'] for r in text_rows),
                sender_verified=False,history_boundary_verified=False,
                real_send_supported=False,model_called=False)


def capability_report(raw):
    """Count UIA metadata/pattern availability, without exporting its values."""
    extras={'scroll_pattern','vertical_scrollable','vertical_scroll_percent','distinct_automation_ids'}
    flags={'automation_id','help_text','item_status','item_type','labeled_by','text_pattern'}
    if (not isinstance(raw,dict) or raw.get('status') != 'capability_snapshot'
            or not extras <= set(raw) or not isinstance(raw.get('rows'),list)
            or len(raw['rows']) > 256 or type(raw['scroll_pattern']) is not bool):
        raise ReadError('invalid_snapshot')
    percent=raw['vertical_scroll_percent']
    scrollable=raw['vertical_scrollable']
    if raw['scroll_pattern']:
        if (type(scrollable) is not bool or type(percent) not in (int,float)
                or not -1 <= percent <= 100 or not math.isfinite(percent)
                or (scrollable and percent < 0) or (not scrollable and percent != -1)):
            raise ReadError('invalid_snapshot')
        bottom=not scrollable or percent == 100
    else:
        if percent is not None or scrollable is not None:
            raise ReadError('invalid_snapshot')
        bottom=None
    validation_rows=[]
    for row in raw['rows']:
        if (not isinstance(row,dict) or set(row) != flags | {'token','kind'}
                or any(type(row[key]) is not bool for key in flags)):
            raise ReadError('invalid_snapshot')
        validation_rows.append(dict(token=row['token'],kind=row['kind'],text=''))
    validation={k:v for k,v in raw.items() if k not in extras}
    validate_snapshot(dict(validation,status='snapshot',rows=validation_rows))
    report={key+'_rows':sum(row[key] for row in raw['rows']) for key in flags}
    distinct=raw['distinct_automation_ids']
    if (type(distinct) is not int or not 0 <= distinct <= report['automation_id_rows']
            or (distinct == 0) != (report['automation_id_rows'] == 0)):
        raise ReadError('invalid_snapshot')
    report.update(status='capabilities_observed',rows=len(raw['rows']),
                  distinct_automation_ids=distinct,
                  text_rows=sum(row['kind']=='text' for row in raw['rows']),
                  scroll_pattern=raw['scroll_pattern'],bottom_observed=bottom,
                  sender_verified=False,history_boundary_verified=False,
                  real_send_supported=False,model_called=False)
    return report


def visual_report(raw):
    """Visual hints cannot promote rows to verified incoming messages."""
    if (not isinstance(raw,dict) or raw.get('status') != 'visual_snapshot'
            or not isinstance(raw.get('rows'),list) or len(raw['rows'])>256):
        raise ReadError('invalid_snapshot')
    validation_rows=[]
    for row in raw['rows']:
        if (not isinstance(row,dict) or set(row) != {'token','kind','direction'}
                or row['direction'] not in ('incoming_candidate','self_candidate','unknown')
                or (row['kind']!='text' and row['direction']!='unknown')):
            raise ReadError('invalid_snapshot')
        validation_rows.append(dict(token=row['token'],kind=row['kind'],text=''))
    validate_snapshot(dict(raw,status='snapshot',rows=validation_rows))
    text_rows=[row for row in raw['rows'] if row['kind']=='text']
    return dict(status='visual_observed',rows=len(raw['rows']),text_rows=len(text_rows),
                incoming_candidates=sum(row['direction']=='incoming_candidate' for row in text_rows),
                self_candidates=sum(row['direction']=='self_candidate' for row in text_rows),
                unknown_texts=sum(row['direction']=='unknown' for row in text_rows),
                sender_verified=False,history_boundary_verified=False,
                real_send_supported=False,model_called=False)


def validate_visual_text_snapshot(raw):
    """Validate a single provider read; visual directions remain candidates."""
    if (not isinstance(raw,dict) or raw.get('status') != 'visual_text_snapshot'
            or not isinstance(raw.get('rows'),list) or len(raw['rows'])>256):
        raise ReadError('invalid_snapshot')
    validation_rows, directions = [], []
    for row in raw['rows']:
        if (not isinstance(row,dict) or set(row) != {'token','kind','text','direction'}
                or row['direction'] not in ('incoming_candidate','self_candidate','unknown')
                or (row['kind']!='text' and row['direction']!='unknown')):
            raise ReadError('invalid_snapshot')
        validation_rows.append({key:row[key] for key in ('token','kind','text')})
        directions.append(row['direction'])
    identity, rows = validate_snapshot(dict(raw,status='snapshot',rows=validation_rows))
    return identity, [(*record,direction) for record,direction in zip(rows,directions)]


class ReadSession:
    def __init__(self):
        self._identity = None
        self._rows = []
        self._seen_tokens = set()
        self._epoch = uuid.uuid4().hex
        self._sequence = 0
        self._texts = 0
        self._snapshots = 0
        self._front_evictions = 0
        self._stop_reason = None
        self._state = 'waiting'

    def _validate(self, raw):
        return validate_snapshot(raw)

    def _continuity_key(self, row):
        return row[0], row[1]

    def _direction(self, row):
        return 'unverified'

    def _check_appended(self, appended):
        new_tokens = {r[0] for r in appended}
        if new_tokens & self._seen_tokens:
            raise ReadError('message_token_reused')
        if len(self._seen_tokens) + len(new_tokens) > 4096:
            raise ReadError('session_token_limit')

    def _remember_rows(self, rows, *, appended=False):
        self._seen_tokens.update(r[0] for r in rows)

    def stop(self, reason):
        # Preserve the first failure, including when the CLI catches the
        # sanitized exception raised by accept(). Never expose arbitrary text.
        if self._state != 'stopped':
            self._stop_reason = reason if isinstance(reason,str) and reason in _STOP_REASONS else 'read_failed'
            self._state = 'stopped'

    def accept(self, raw):
        if self._state == 'stopped':
            raise ReadError('session_stopped')
        try:
            identity, rows = self._validate(raw)
            current = [self._continuity_key(r) for r in rows]
            if self._identity is None:
                self._identity, self._rows = identity, current
                self._remember_rows(rows)
                self._state = 'reading' if current else 'initializing'
                self._snapshots += 1
                return []
            if identity != self._identity:
                raise ReadError('window_or_list_changed')
            if self._state == 'initializing':
                self._rows = current
                self._remember_rows(rows)
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
            # Validate the entire batch before advancing counters or returning
            # observations. Evicted tokens remain known for this session.
            self._check_appended(appended)
            observations = []
            for row in appended:
                kind, text = row[2:4]
                self._sequence += 1
                if kind == 'text' and text.strip():
                    self._texts += 1
                    observations.append(Observation(self._epoch+':'+str(self._sequence),text,self._direction(row)))
            if overlap < len(self._rows):
                self._front_evictions += 1
            self._rows = current
            self._remember_rows(appended,appended=True)
            self._snapshots += 1
            return observations
        except ReadError as error:
            self.stop(str(error))
            raise ReadError('read_session_stopped') from None
        except (TypeError, ValueError):
            self.stop('invalid_snapshot')
            raise ReadError('read_session_stopped') from None

    def report(self):
        return dict(status=self._state, snapshots=self._snapshots,
                    stop_reason=self._stop_reason, front_evictions=self._front_evictions,
                    seen_tokens=len(self._seen_tokens),
                    window_bound=self._identity is not None,
                    observed_new_rows=self._sequence, observed_new_texts=self._texts,
                    sender_verified=False, server_message_ids_available=False,
                    history_boundary_verified=False,
                    real_send_supported=False, model_called=False)


class OccurrenceSession(ReadSession):
    """Opt-in UI occurrence candidates, never durable message identities.

    Keep the same binding/suffix rules as ReadSession. A recycled token with a
    different payload may be another UI occurrence; it is not proof of a newly
    received message. A previously seen token/payload pair is ambiguous and
    stops the session, even if it might also be a legitimate repeated message.
    """
    def __init__(self):
        super().__init__()
        self._seen_occurrences = set()
        self._reused_token_candidates = 0

    def _check_appended(self, appended):
        occurrences = {(r[0],r[1]) for r in appended}
        if occurrences & self._seen_occurrences:
            raise ReadError('occurrence_reappeared')
        if len(self._seen_occurrences) + len(occurrences) > 4096:
            raise ReadError('session_occurrence_limit')

    def _remember_rows(self, rows, *, appended=False):
        if appended:
            self._reused_token_candidates += sum(r[0] in self._seen_tokens for r in rows)
        self._seen_occurrences.update((r[0],r[1]) for r in rows)
        super()._remember_rows(rows,appended=appended)

    def report(self):
        report = super().report()
        report['mode'] = 'occurrence_candidates'
        report['candidate_rows'] = report.pop('observed_new_rows')
        report['candidate_texts'] = report.pop('observed_new_texts')
        report['seen_occurrences'] = len(self._seen_occurrences)
        report['reused_token_candidates'] = self._reused_token_candidates
        return report


class VisualOccurrenceSession(OccurrenceSession):
    """Joined candidates; unknown visibility never erases known direction."""
    def __init__(self):
        super().__init__()
        self._direction_counts = {'incoming_candidate':0,'self_candidate':0,'unknown':0}
        self._known_directions = {}
        self._pending_directions = {}

    def _validate(self, raw):
        identity, rows = validate_visual_text_snapshot(raw)
        for row in rows:
            key, direction = (row[0],row[1]), row[4]
            if direction != 'unknown':
                previous = self._known_directions.get(key)
                if previous is not None and previous != direction:
                    raise ReadError('message_continuity_lost')
                self._pending_directions[key] = direction
        return identity, rows

    def _direction(self, row):
        return row[4]

    def accept(self, raw):
        try:
            observations = super().accept(raw)
            # Only committed rows may strengthen the direction evidence. This
            # dictionary shares the 4096 occurrence bound with pair history.
            self._known_directions.update(self._pending_directions)
            for observation in observations:
                self._direction_counts[observation.direction] += 1
            return observations
        finally:
            self._pending_directions.clear()

    def report(self):
        report = super().report()
        report.update(mode='visual_occurrence_candidates',
                      incoming_candidate_texts=self._direction_counts['incoming_candidate'],
                      self_candidate_texts=self._direction_counts['self_candidate'],
                      unknown_candidate_texts=self._direction_counts['unknown'])
        return report


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
                    '/out:'+str(self.executable),'/reference:'+str(framework/'System.Web.Extensions.dll'),
                    '/reference:'+str(framework/'System.Drawing.dll')]
            args += ['/reference:'+str(framework/'WPF'/name) for name in
                     ('UIAutomationClient.dll','UIAutomationTypes.dll','WindowsBase.dll')]
            args.append(str(Path(__file__).with_name('live_reader.cs')))
            args.append(str(Path(__file__).with_name('visual_direction.cs')))
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

    def read(self, *, layout=False, capabilities=False, visual=False, visual_text=False):
        try:
            if sum(bool(value) for value in (layout,capabilities,visual,visual_text))>1:
                raise ReadError('invalid_snapshot')
            command = [str(self.executable),self.client_path]
            if layout:
                command.append('--layout')
            if capabilities:
                command.append('--capabilities')
            if visual:
                command.append('--visual')
            if visual_text:
                command.append('--visual-text')
            done = subprocess.run(command,
                                  input=json.dumps(self._binding).encode('utf-8'),capture_output=True,timeout=8,
                                  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if len(done.stdout) > 4_000_000:
                raise ReadError('native_reader_unavailable')
            raw = json.loads(done.stdout.decode('utf-8-sig'))
            if done.returncode:
                if (done.returncode == 3 and isinstance(raw,dict)
                        and set(raw) == {'status','reason'} and raw['status'] == 'reader_error'
                        and isinstance(raw['reason'],str) and raw['reason'] in _NATIVE_REASONS):
                    raise ReadError(raw['reason'])
                raise ReadError('native_reader_unavailable')
            try:
                if layout:
                    layout_report(raw)
                elif capabilities:
                    capability_report(raw)
                elif visual:
                    visual_report(raw)
                elif visual_text:
                    validate_visual_text_snapshot(raw)
                else:
                    validate_snapshot(raw)
            except ReadError:
                raise ReadError('native_reader_unavailable') from None
            binding = {key:raw[key] for key in ('process','started','window','root','list_token')}
            if self._binding is not None and binding != self._binding:
                raise ReadError('window_or_list_changed')
            self._binding = binding
            return raw
        except subprocess.TimeoutExpired:
            raise ReadError('native_reader_timeout') from None
        except (OSError,ValueError,TypeError,RecursionError):
            raise ReadError('native_reader_unavailable') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read only one independent WeChat private-chat window.')
    parser.add_argument('--client-path',required=True)
    parser.add_argument('--seconds',type=int,default=30)
    inspections=parser.add_mutually_exclusive_group()
    inspections.add_argument('--inspect-layout',action='store_true',help='Report geometry counts without reading message text.')
    inspections.add_argument('--inspect-capabilities',action='store_true',help='Report UIA metadata availability without exporting its values.')
    inspections.add_argument('--inspect-visual',action='store_true',help='Report conservative direction hints from an in-memory window image.')
    inspections.add_argument('--observe-occurrences',action='store_true',help='Observe local UI occurrence candidates, including reused tokens with changed content; never verify new messages.')
    inspections.add_argument('--observe-visual-occurrences',action='store_true',help='Observe text and direction candidates from a single bounded read; never verify senders or new messages.')
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 300:
        parser.error('seconds must be between 1 and 300')
    session = (VisualOccurrenceSession() if args.observe_visual_occurrences
               else OccurrenceSession() if args.observe_occurrences else ReadSession())
    try:
        with NativeReader(args.client_path) as reader:
            if args.inspect_layout:
                print(json.dumps(layout_report(reader.read(layout=True)),sort_keys=True),flush=True)
                return 0
            if args.inspect_capabilities:
                print(json.dumps(capability_report(reader.read(capabilities=True)),sort_keys=True),flush=True)
                return 0
            if args.inspect_visual:
                print(json.dumps(visual_report(reader.read(visual=True)),sort_keys=True),flush=True)
                return 0
            deadline = time.monotonic()+args.seconds
            while True:
                session.accept(reader.read(visual_text=True) if args.observe_visual_occurrences else reader.read())
                print(json.dumps(session.report(),sort_keys=True),flush=True)
                if time.monotonic() >= deadline:
                    break
                time.sleep(1)
        return 0
    except (ReadError,KeyboardInterrupt) as error:
        session.stop('interrupted' if isinstance(error,KeyboardInterrupt) else str(error))
        print(json.dumps(session.report(),sort_keys=True),flush=True)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
