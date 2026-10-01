"""Optional source-tree benchmark. Only fixed synthetic PNGs; never a chat adapter."""
import argparse
from collections import Counter
import contextlib
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[1]
CHINESE = '\u4e2d\u6587\u6d4b\u8bd5\u6536\u5230\u4f60\u597d'
EXPECTED = {name: [CHINESE, CHINESE, 'TEST12345'] for name in ('light', 'dark', 'large')}
EXPECTED.update(blank=[], symbol=[CHINESE, CHINESE, '_'])
DEPENDENCIES = {'rapidocr': '3.9.2', 'onnxruntime': '1.30.0', 'omegaconf': '2.3.1'}
FIXTURES = {
    'light': (8033, '70d07f3fa0a36518e6e0415ffe3d473356bd42106b24942e12665b35876da61f'),
    'dark': (8059, 'fd8944d65811bdf342e0ee0f930e89fcb244765789e885b2dca718102b68a8fa'),
    'large': (10237, 'edb08a58ee1ad2510fb796d773ddd21e36758e7234d5dfad1a2072ea131a041f'),
    'blank': (2595, '6fa05539ae3b827c2a4fa97c69ae9a49221e54f7b2fc646468e821e227585ce5'),
    'symbol': (7005, 'cb4c05d84cf72ab7821fc75752fc38cdad62f3c5526493e505790c333ce6c8ae'),
}
MODELS = {
    'PP-OCRv6_det_small.onnx': (9929594, '090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f'),
    'PP-OCRv6_rec_small.onnx': (21234383, '6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884'),
    'ch_ppocr_mobile_v2.0_cls_mobile.onnx': (585532, 'e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c'),
}
ERRORS = {'dependency_missing', 'dependency_version_mismatch', 'fixture_mismatch',
          'model_mismatch', 'candidate_failed', 'network_blocked'}


def empty_report(status):
    return dict(schema_version=1, status=status, confidence_threshold=0.9, dependencies={}, cases={},
                model_hashes_verified=False, native_telemetry_disabled=False,
                python_outbound_attempts=0, blocked_local_bind_checks=0,
                synthetic_only=True, screen_captured=False, real_chat_read=False,
                identity_verified=False, listener_ready=False, real_send_supported=False)


def evaluate(expected, texts, scores):
    if len(texts) != len(scores) or len(texts) > 32:
        raise ValueError('invalid_recognition')
    if any(not isinstance(text, str) or len(text) > 10000 for text in texts):
        raise ValueError('invalid_recognition')
    if any(type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1 for score in scores):
        raise ValueError('invalid_recognition')
    normalized = [''.join(text.split()) for text in texts]
    accepted = [text for text, score in zip(normalized, scores) if score >= 0.9]
    # Counts preserve repeated lines. No recognized text leaves this function.
    exact = Counter(accepted) == Counter(expected)
    uncertain = len(texts)-len(accepted)
    return dict(raw_count=len(texts), accepted_count=len(accepted), uncertain_count=uncertain,
                raw_exact=Counter(normalized) == Counter(expected), accepted_exact=exact,
                review_required=bool(uncertain or not exact))


def sanitize(raw):
    invalid = empty_report('invalid_output')
    if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
        return invalid
    status = raw.get('status')
    if not isinstance(status, str) or status not in ERRORS | {'benchmark_passed', 'review_required'}:
        return invalid
    if type(raw.get('confidence_threshold')) not in (int, float) or raw['confidence_threshold'] != 0.9:
        return invalid
    result = empty_report(status)
    for key in ('python_outbound_attempts', 'blocked_local_bind_checks'):
        if type(raw.get(key)) is not int or not 0 <= raw[key] <= 32:
            return invalid
        result[key] = raw[key]
    if status in ERRORS:
        return result
    if raw.get('dependencies') != DEPENDENCIES or raw.get('model_hashes_verified') is not True or raw.get('native_telemetry_disabled') is not True:
        return invalid
    cases = raw.get('cases')
    if not isinstance(cases, dict) or set(cases) != set(EXPECTED) or result['python_outbound_attempts']:
        return invalid
    checked = {}
    fields = {'raw_count', 'accepted_count', 'uncertain_count', 'raw_exact', 'accepted_exact', 'review_required'}
    for name, values in cases.items():
        if not isinstance(values, dict) or set(values) != fields:
            return invalid
        for key in ('raw_count', 'accepted_count', 'uncertain_count'):
            if type(values[key]) is not int or not 0 <= values[key] <= 32:
                return invalid
        if values['raw_count'] != values['accepted_count']+values['uncertain_count']:
            return invalid
        for key in ('raw_exact', 'accepted_exact', 'review_required'):
            if type(values[key]) is not bool:
                return invalid
        if values['raw_exact'] and values['raw_count'] != len(EXPECTED[name]):
            return invalid
        if values['accepted_exact'] and values['accepted_count'] != len(EXPECTED[name]):
            return invalid
        if not values['uncertain_count'] and values['raw_exact'] != values['accepted_exact']:
            return invalid
        if values['review_required'] != bool(values['uncertain_count'] or not values['accepted_exact']):
            return invalid
        checked[name] = dict(values)
    needs_review = any(value['review_required'] for value in checked.values())
    if (status == 'review_required') != needs_review:
        return invalid
    result.update(cases=checked, dependencies=dict(DEPENDENCIES),
                  model_hashes_verified=True, native_telemetry_disabled=True)
    return result


def run_check(python_path, timeout=30):
    if not isinstance(python_path, str) or not python_path or '\0' in python_path or type(timeout) not in (int, float) or not 0.5 <= timeout <= 60:
        return empty_report('invalid_arguments')
    try:
        done = subprocess.run([python_path, '-I', '-X', 'utf8', str(SCRIPT), '--worker'],
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if done.returncode:
            return empty_report('candidate_failed')
        if len(done.stdout) > 65536:
            return empty_report('invalid_output')
        return sanitize(json.loads(done.stdout.decode('utf-8-sig')))
    except subprocess.TimeoutExpired:
        return empty_report('check_timeout')
    except OSError:
        return empty_report('candidate_failed')
    except (UnicodeError, ValueError, RecursionError):
        return empty_report('invalid_output')


def matches(path, record):
    size, digest = record
    if not path.is_file() or path.stat().st_size != size:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == digest


def worker():
    report = empty_report('candidate_failed')
    def deny_network(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.sendmsg'}:
            report['python_outbound_attempts'] += 1
            raise RuntimeError('network_disabled')
        if event == 'socket.bind':
            # urllib3 performs a local IPv6 capability check during import.
            report['blocked_local_bind_checks'] += 1
            raise RuntimeError('network_disabled')
    sys.addaudithook(deny_network)
    try:
        versions = {key: importlib.metadata.version(key) for key in DEPENDENCIES}
        if versions != DEPENDENCIES:
            return empty_report('dependency_version_mismatch')
        if not all(matches(ROOT/'tests/fixtures/ocr'/(name+'.png'), record) for name, record in FIXTURES.items()):
            return empty_report('fixture_mismatch')
        import onnxruntime
        onnxruntime.disable_telemetry_events()
        import rapidocr
        models = Path(rapidocr.__file__).parent/'models'
        if not all(matches(models/name, record) for name, record in MODELS.items()):
            return empty_report('model_mismatch')
        # Keep the SDK's recognition-confidence filter open. All low-confidence
        # returned regions must reach our uncertainty accounting, including <0.5.
        params = {'Global.log_level': 'critical', 'Global.text_score': 0.0,
                  'EngineConfig.onnxruntime.intra_op_num_threads': 2,
                  'EngineConfig.onnxruntime.inter_op_num_threads': 1,
                  'Det.model_path': str(models/'PP-OCRv6_det_small.onnx'),
                  'Rec.model_path': str(models/'PP-OCRv6_rec_small.onnx'),
                  'Cls.model_path': str(models/'ch_ppocr_mobile_v2.0_cls_mobile.onnx')}
        engine = rapidocr.RapidOCR(params=params)
        if engine.text_score != 0.0:
            return empty_report('candidate_failed')
        cases = {}
        for name, expected in EXPECTED.items():
            output = engine(str(ROOT/'tests/fixtures/ocr'/(name+'.png')))
            texts = list(output.txts) if output.txts is not None else []
            scores = [float(value) for value in output.scores] if output.scores is not None else []
            cases[name] = evaluate(expected, texts, scores)
        report.update(status='review_required' if any(v['review_required'] for v in cases.values()) else 'benchmark_passed',
                      cases=cases, dependencies=versions, model_hashes_verified=True, native_telemetry_disabled=True)
    except importlib.metadata.PackageNotFoundError:
        report['status'] = 'dependency_missing'
    except Exception:
        report['status'] = 'candidate_failed'
    if report['python_outbound_attempts']:
        report['status'] = 'network_blocked'
    return sanitize(report)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Benchmark five fixed fictional images; no screen or chat access.')
    default = ROOT/'.ocr-env'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    parser.add_argument('--python', default=str(default) if default.is_file() else sys.executable)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        # Third-party output cannot become the public diagnostic report.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            report = worker()
        print(json.dumps(report, sort_keys=True))
        return 0
    report = run_check(args.python)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'benchmark_passed' else 3


if __name__ == '__main__':
    raise SystemExit(main())
