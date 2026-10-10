"""Only executes this project's generated-code child fixture; no external PID input."""
import argparse
import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data/executed-trampoline-20261010'
CASES = [(kind, mode) for kind in ('integer', 'floating', 'fault')
         for mode in ('baseline', 'hooked', 'stopped')]
CASES += [('parallel', 'hooked'), ('parallel', 'stopped')]
CASES += [('transition', 'stopped')]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_case(exe, kind, mode, metadata):
    command = [str(exe), kind, mode, metadata]
    result = dict(kind=kind, mode=mode, metadata=metadata, command=command, passed=False)
    p = None
    try:
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        result['pid'] = p.pid
        stdout, stderr = p.communicate(timeout=12)
        result.update(child_exit=p.returncode, stdout=stdout, stderr=stderr)
        events = [json.loads(line) for line in stdout.splitlines()]
        result['events'] = events
        assert p.returncode == 0, ('child_exit', p.returncode)
        ready = next(e for e in events if e['event'] == 'ready')
        final = next(e for e in events if e['event'] == 'result')
        cleanup = next(e for e in events if e['event'] == 'cleanup')
        assert ready['registered_entries'] == 6 and ready['all_lookups_match']
        assert final['errors'] == 0 and final['register_mask'] == 31, final
        expected_calls = {'integer':1, 'floating':129, 'fault':2, 'parallel':20001, 'transition':2}[kind]
        expected_returns = expected_calls - (kind == 'fault')
        assert final['hook_entries'] == (0 if mode == 'baseline' else expected_calls), final
        assert final['hook_returns'] == (0 if mode == 'baseline' else expected_returns), final
        assert final['captures'] == (1 if kind == 'transition' else expected_calls if mode == 'hooked' else 0), final
        assert final['caught'] == (0xc0000005 if kind == 'fault' else 0), final
        assert final['installed'] == (mode != 'baseline')
        if kind == 'fault':
            unwinds = [e for e in events if e['event'] == 'fault_unwind']
            assert len(unwinds) == 1 and unwinds[0]['restored_mask'] == 63 and unwinds[0]['rsp_delta'] == 48, unwinds
            filters = [e for e in events if e['event'] == 'filter']
            assert len(filters) == 1 and filters[0]['in_original'] and filters[0]['access_violation'], filters
        assert cleanup == dict(event='cleanup', prefix_restored=True,
                               table_deleted=True, lookups_absent=True, freed=True), cleanup
        result['passed'] = True
    except subprocess.TimeoutExpired as exc:
        p.kill()
        stdout, stderr = p.communicate()
        result.update(error='own_child_timeout', stdout=stdout, stderr=stderr,
                      child_exit=p.returncode, killed_by_driver=True)
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        result['all_children_exited'] = p is None or p.poll() is not None
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, default=CACHE / 'executed_trampoline_fixture.exe')
    parser.add_argument('--metadata', choices=('exact', 'omit_rbp'), default='exact')
    parser.add_argument('--case', action='append', choices=[f'{k}:{m}' for k,m in CASES])
    parser.add_argument('--repeat', type=int, default=1)
    args = parser.parse_args()
    assert 1 <= args.repeat <= 3
    run = CACHE / ('run-' + uuid.uuid4().hex[:12]); run.mkdir(parents=True)
    sources = [Path(__file__), Path(__file__).with_name('executed_trampoline_fixture.c'),
               Path(__file__).with_name('trampoline_register_caller.S'), args.exe, CACHE/'build.json']
    hashes = {}
    for p in sources:
        if p.exists():
            shutil.copyfile(p, run / p.name); hashes[p.name] = sha(p)
    if args.exe.exists():
        build = json.loads((CACHE/'build.json').read_text())
        assert build['exe_sha256'] == sha(args.exe)
        for name,h in build['source_hashes'].items():
            assert sha(Path(__file__).with_name(name)) == h
    cases = [tuple(c.split(':')) for c in args.case] if args.case else CASES
    observations = [run_case(args.exe,k,m,args.metadata) for _ in range(args.repeat) for k,m in cases]
    result = dict(source_hashes=hashes, cases=observations, total=len(observations),
                  passed=sum(x['passed'] for x in observations), metadata=args.metadata,
                  target='self-created child; generated code and entry patches only in its own allocation',
                  live_wechat_hook=False)
    (run/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=run.relative_to(ROOT).as_posix(), passed=result['passed'], total=result['total'],
                         failures=[(x['kind'],x['mode'],x.get('error')) for x in observations if not x['passed']])))
    return int(result['passed'] != result['total'])


if __name__ == '__main__':
    raise SystemExit(main())
