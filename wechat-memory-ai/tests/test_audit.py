from pathlib import Path
import json
import tempfile
import unittest

from wechat_memory.audit import Audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audit = Audit(self.root)
        self.addCleanup(self.audit.close)

    def test_truncated_model_failure_keeps_its_fixed_reason(self):
        event_key = 'a' * 64
        self.audit.write('model_failed', event_key, 'truncated')
        self.audit.close()
        record = json.loads((self.root / 'audit.log').read_text('utf-8'))
        self.assertEqual(set(record), {'time', 'status', 'event', 'code'})
        self.assertEqual(record['status'], 'model_failed')
        self.assertEqual(record['event'], event_key)
        self.assertEqual(record['code'], 'truncated')

    def test_unknown_values_are_normalized_without_logging_private_text(self):
        private_fixture = 'PRIVATE_BODY_AND_SECRET_TEST_ONLY'
        self.audit.write(private_fixture, private_fixture, private_fixture)
        self.audit.close()
        raw = (self.root / 'audit.log').read_text('utf-8')
        record = json.loads(raw)
        self.assertEqual(set(record), {'time', 'status', 'event', 'code'})
        self.assertEqual(record['status'], 'rejected')
        self.assertEqual(record['event'], '')
        self.assertEqual(record['code'], 'model_failure')
        self.assertNotIn(private_fixture, raw)


if __name__ == '__main__':
    unittest.main()
