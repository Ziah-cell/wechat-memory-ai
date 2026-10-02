"""Explicit native bindings constrain the first read and cannot be mutated away."""
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from wechat_memory import live_read


def binding(**changes):
    value = dict(process=12, started='123456', window=34,
                 root='ChatSingleWindowwxid_fixture', list_token='1.2.3')
    value.update(changes)
    return value


def native_result(identity, *, status='snapshot'):
    raw = dict(identity, status=status, rows=[])
    return subprocess.CompletedProcess([], 0, json.dumps(raw).encode('utf-8'), b'')


class BoundReaderTests(unittest.TestCase):
    def test_binding_validation_returns_an_independent_copy(self):
        original = binding()
        validated = live_read.validate_binding(original)
        self.assertEqual(validated, binding())
        self.assertIsNot(validated, original)
        original['window'] = 99
        validated['process'] = 77
        self.assertEqual(validated['window'], 34)
        self.assertEqual(original['process'], 12)

    def test_binding_validation_rejects_missing_extra_and_malformed_values(self):
        invalid = [None, [], 'PRIVATE', {}, binding(status='snapshot'), binding(rows=[])]
        invalid.extend({key:value for key,value in binding().items() if key != missing}
                       for missing in binding())
        for key in ('process', 'window'):
            invalid.extend(binding(**{key:value}) for value in (True, 0, -1, 2**63, '12', None, []))
        for key in ('started', 'root', 'list_token'):
            invalid.extend(binding(**{key:value}) for value in ('', 'x'*257, None, False, 1, [], {}))
        invalid.extend(binding(root=value) for value in
                       ('PRIVATE', 'ChatSingleWindowwxid_', 'ChatSingleWindowwxid_unsafe.value'))
        for raw in invalid:
            with self.subTest(binding_type=type(raw).__name__):
                with self.assertRaises(live_read.ReadError) as error:
                    live_read.validate_binding(raw)
                self.assertIn(str(error.exception), ('invalid_snapshot', 'independent_private_chat_required'))

    def test_binding_uses_the_existing_snapshot_identity_contract(self):
        # These fields are opaque bounded strings under validate_snapshot;
        # explicit binding must not invent new identifier formats.
        raw = binding(process=2**63-1, window=2**63-1, started='opaque epoch',
                      root='ChatSingleWindowwxid_'+'x'*100, list_token='opaque token')
        self.assertEqual(live_read.validate_binding(raw), raw)

    def test_first_native_request_includes_the_expected_private_binding(self):
        expected = binding()
        reader = live_read.NativeReader('D:/Weixin.exe', expected_binding=expected)
        reader.executable = Path('never-executed.exe')
        with patch.object(live_read.subprocess, 'run',
                          return_value=native_result(expected, status='visual_text_snapshot')) as run:
            result = reader.read(visual_text=True)
        self.assertEqual(result, dict(expected, status='visual_text_snapshot', rows=[]))
        self.assertEqual(run.call_count, 1)
        self.assertEqual(json.loads(run.call_args.kwargs['input']), expected)
        self.assertEqual(run.call_args.args[0][-1], '--visual-text')
        self.assertEqual(reader.binding, expected)

    def test_changed_native_identity_is_rejected_without_rebinding(self):
        changes = dict(process=13, started='654321', window=35,
                       root='ChatSingleWindowwxid_other', list_token='4.5.6')
        for field, value in changes.items():
            with self.subTest(field=field):
                expected = binding()
                reader = live_read.NativeReader('D:/Weixin.exe', expected_binding=expected)
                reader.executable = Path('never-executed.exe')
                with patch.object(live_read.subprocess, 'run',
                                  return_value=native_result(binding(**{field:value}))) as run:
                    with self.assertRaises(live_read.ReadError) as error:
                        reader.read()
                self.assertEqual(str(error.exception), 'window_or_list_changed')
                self.assertEqual(reader.binding, expected)
                self.assertEqual(json.loads(run.call_args.kwargs['input']), expected)

    def test_caller_and_property_mutations_cannot_change_the_native_binding(self):
        original = binding()
        reader = live_read.NativeReader('D:/Weixin.exe', expected_binding=original)
        reader.executable = Path('never-executed.exe')
        original['window'] = 99
        exposed = reader.binding
        exposed['root'] = 'ChatSingleWindowwxid_other'
        with patch.object(live_read.subprocess, 'run', return_value=native_result(binding())) as run:
            result = reader.read()
        result['list_token'] = 'different'
        self.assertEqual(json.loads(run.call_args.kwargs['input']), binding())
        self.assertEqual(reader.binding, binding())
        self.assertIsNot(reader.binding, reader.binding)

    def test_malformed_explicit_binding_fails_before_any_subprocess(self):
        for raw in ({}, [], 'PRIVATE', binding(window=True), binding(text='PRIVATE')):
            with self.subTest(binding_type=type(raw).__name__), patch.object(live_read.subprocess, 'run') as run:
                with self.assertRaises(live_read.ReadError):
                    live_read.NativeReader('D:/Weixin.exe', expected_binding=raw)
                run.assert_not_called()

    def test_default_reader_still_binds_to_its_first_valid_response(self):
        for options in ({}, {'expected_binding':None}):
            with self.subTest(explicit_none=bool(options)):
                reader = live_read.NativeReader('D:/Weixin.exe', **options)
                self.assertIsNone(reader.binding)
                reader.executable = Path('never-executed.exe')
                with patch.object(live_read.subprocess, 'run', return_value=native_result(binding())) as run:
                    reader.read()
                self.assertIsNone(json.loads(run.call_args.kwargs['input']))
                self.assertEqual(reader.binding, binding())


if __name__ == '__main__':
    unittest.main()
