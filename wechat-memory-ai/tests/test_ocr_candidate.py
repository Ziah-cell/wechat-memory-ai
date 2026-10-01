"""A candidate benchmark must preserve duplicates and uncertainty."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1]/'scripts/ocr-candidate-check.py'
candidate = None
if SCRIPT.exists():
    spec = importlib.util.spec_from_file_location('ocr_candidate', SCRIPT)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)


class CandidateExistsTests(unittest.TestCase):
    def test_candidate_benchmark_exists(self):
        self.assertIsNotNone(candidate, 'candidate benchmark not implemented')


@unittest.skipUnless(candidate, 'candidate benchmark not implemented')
class CandidateTests(unittest.TestCase):
    def test_exact_duplicates_are_preserved(self):
        result = candidate.evaluate(['hello', 'hello'], ['hello', 'hello'], [0.99, 0.98])
        self.assertTrue(result['raw_exact'])
        self.assertTrue(result['accepted_exact'])
        self.assertFalse(result['review_required'])
        result = candidate.evaluate(['hello', 'hello'], ['hello'], [0.99])
        self.assertFalse(result['raw_exact'])
        self.assertTrue(result['review_required'])

    def test_uncertain_text_requires_review_even_when_filter_matches(self):
        result = candidate.evaluate(['hello'], ['hello', '_'], [0.99, 0.74])
        self.assertTrue(result['accepted_exact'])
        self.assertFalse(result['raw_exact'])
        self.assertEqual(result['uncertain_count'], 1)
        self.assertTrue(result['review_required'])
        self.assertNotIn('hello', json.dumps(result))
        # A legitimate low-confidence symbol must not be declared safely discarded.
        result = candidate.evaluate(['_'], ['_'], [0.74])
        self.assertTrue(result['raw_exact'])
        self.assertFalse(result['accepted_exact'])
        self.assertTrue(result['review_required'])

    def test_invalid_outputs_reject_before_scoring(self):
        for texts, scores in ((['x'], []), (['x'], [float('nan')]), (['x'], [True]),
                              (['x'], [-0.1]), (['x'], [1.1]), (['x'*10001], [1.0]),
                              (['x']*33, [1.0]*33), ([None], [0.9])):
            with self.subTest(texts_type=type(texts), score_count=len(scores)):
                with self.assertRaises(ValueError):
                    candidate.evaluate(['x'], texts, scores)

    def test_report_allowlist_never_exposes_text_or_promotes_identity(self):
        raw = candidate.empty_report('benchmark_passed')
        raw['cases'] = {name: candidate.evaluate(expected, expected, [1.0]*len(expected))
                        for name, expected in candidate.EXPECTED.items()}
        raw.update(dependencies=dict(candidate.DEPENDENCIES), model_hashes_verified=True, native_telemetry_disabled=True,
                   identity_verified=True, real_send_supported=True, text='SECRET')
        clean = candidate.sanitize(raw)
        self.assertEqual(clean['status'], 'benchmark_passed')
        self.assertFalse(clean['identity_verified'])
        self.assertFalse(clean['real_send_supported'])
        self.assertNotIn('SECRET', json.dumps(clean))
        raw['cases']['light']['uncertain_count'] = 1
        self.assertEqual(candidate.sanitize(raw)['status'], 'invalid_output')

    def test_contradictory_raw_and_accepted_results_are_rejected(self):
        raw = candidate.empty_report('benchmark_passed')
        raw.update(dependencies=dict(candidate.DEPENDENCIES), model_hashes_verified=True,
                   native_telemetry_disabled=True)
        raw['cases'] = {name: candidate.evaluate(expected, expected, [1.0]*len(expected))
                        for name, expected in candidate.EXPECTED.items()}
        raw['cases']['light']['raw_exact'] = False
        self.assertEqual(candidate.sanitize(raw)['status'], 'invalid_output')

    def test_worker_preserves_results_below_sdk_default_threshold(self):
        class Engine:
            def __init__(self, params):
                self.text_score = params.get('Global.text_score', 0.5)
            def __call__(self, image):
                expected = candidate.EXPECTED[Path(image).stem]
                texts, scores = list(expected)+['_'], [1.0]*len(expected)+[0.2]
                keep = [(text, score) for text, score in zip(texts, scores) if score >= self.text_score]
                return SimpleNamespace(txts=[row[0] for row in keep], scores=[row[1] for row in keep])
        rapid = SimpleNamespace(__file__=str(SCRIPT.parent/'fake.py'), RapidOCR=Engine)
        ort = SimpleNamespace(disable_telemetry_events=lambda: None)
        with patch.dict(sys.modules, {'rapidocr': rapid, 'onnxruntime': ort}), \
             patch.object(candidate.importlib.metadata, 'version', side_effect=candidate.DEPENDENCIES.__getitem__), \
             patch.object(candidate, 'matches', return_value=True), \
             patch.object(candidate.sys, 'addaudithook'):
            report = candidate.worker()
        self.assertEqual(report['status'], 'review_required')
        self.assertTrue(all(row['uncertain_count'] == 1 for row in report['cases'].values()))

    def test_subprocess_is_literal_bounded_and_errors_are_sanitized(self):
        with patch.object(candidate.subprocess, 'run', side_effect=
                          subprocess.TimeoutExpired('SECRET', 1, output=b'PRIVATE')) as run:
            report = candidate.run_check(sys.executable, timeout=1)
        self.assertEqual(report['status'], 'check_timeout')
        self.assertNotIn('PRIVATE', json.dumps(report))
        args, kwargs = run.call_args
        self.assertEqual(kwargs['timeout'], 1)
        self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
        self.assertFalse(kwargs.get('shell', False))
        self.assertIn('-I', args[0])
        with patch.object(candidate.subprocess, 'run') as run:
            self.assertEqual(candidate.run_check(sys.executable, timeout=True)['status'], 'invalid_arguments')
            run.assert_not_called()

    def test_actual_timeout_terminates_child(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/'slow.py'
            script.write_text("import time\nprint('PRIVATE',flush=True)\ntime.sleep(30)\n")
            with patch.object(candidate, 'SCRIPT', script):
                start = time.monotonic()
                report = candidate.run_check(sys.executable, timeout=0.5)
            self.assertEqual(report['status'], 'check_timeout')
            self.assertLess(time.monotonic()-start, 5)
            self.assertNotIn('PRIVATE', json.dumps(report))
