"""Native evidence for old first-breakpoint classification; failures stay failures."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import uuid
from test_receive_probe_native import Child,HERE
from test_receive_probe_timing_lifecycle import parse_events
from compare_receive_probe_methods import close_child

MODES=('baseline_breakpoint','normal_attach','application_after_attach','race_raise','race_same_address')

def run_case(mode,strict=False):
    fixture=Child('receive_probe_attach_fixture.py');owner=guardian=None
    r=dict(mode=mode,strict=strict,passed=False,fixture_only=True);stage='setup'
    journal=HERE.parents[1]/'data/bounded-receive-timing-20261009'/('journal-'+uuid.uuid4().hex)
    try:
        info=fixture.event('ready')
        if mode=='baseline_breakpoint':
            fixture.send('breakpoint');r['native_exit']=fixture.process.wait(timeout=3)
            assert r['native_exit']==0x80000003;r['passed']=True
        else:
            args=['--fixture-pid',str(info['pid']),'--fixture-tid',str(info['main_tid']),
                  '--fixture-address',str(info['address']),'--enforce-timing','--timing-journal',str(journal)]
            owner=Child('receive_probe_attach_audit.py','--role','owner',*args,
                        *(['--strict-attach'] if strict else []),
                        *(['--attach-race'] if mode.startswith('race_') else []))
            owner.event('owner_ready')
            guardian=Child('receive_probe_attach_audit.py','--role','guardian',*args,'--owner-pid',str(owner.process.pid))
            ready=guardian.event('guardian_ready')
            owner.send(json.dumps(dict(debug_handle=ready['remote_handle'],guardian_pid=guardian.process.pid)))
            stage='trigger'
            owner.event('attach_hold' if mode.startswith('race_') else 'armed')
            fixture.send('hit' if mode=='normal_attach' else 'ntdll_breakpoint' if mode=='race_same_address' else 'breakpoint')
            stage='cleanup'
            r['owner_result']=owner.event('result',timeout=4);assert owner.process.wait(timeout=3)==0
            r['guardian_result']=guardian.event('result',timeout=4);assert guardian.process.wait(timeout=3)==0
            assert r['owner_result']['cleanup'] in ('detached','target_exited')
            r['audits']=r['owner_result']['attach_audits']
            if mode=='application_after_attach' or strict and mode.startswith('race_'):
                r['native_exit']=fixture.process.wait(timeout=3);assert r['native_exit']==0x80000003
                assert any(not x['legacy_consumed_as_initial'] for x in r['audits'])
            else:
                fixture.send('ping');fixture.event('pong')
                fixture.send('miss');fixture.event('called')
                fixture.send('thread:miss');fixture.event('called');r['target_resumed']=True
            stage='classification'
            if mode.startswith('race_'):
                assert r['owner_result']['controlled_hold_released']
                application=[x for x in r['audits'] if x['main_thread']]
                assert len(application)==(2 if strict else 1)
                r['application_audit']=application[0]
                assert not application[0]['legacy_consumed_as_initial']
            else:assert r['audits'][0]['candidate_match'] and r['audits'][0]['legacy_consumed_as_initial']
            assert not fixture.errors and not owner.errors and not guardian.errors
            r['passed']=True
    except (AssertionError,OSError,RuntimeError,subprocess.TimeoutExpired) as error:
        r['failure_stage']=stage;r['failure_type']=type(error).__name__
    finally:
        r['fixture_exit_before_teardown']=fixture.process.poll()
        for child,role in ((owner,'owner'),(guardian,'guardian')):
            if child:
                if child.process.poll() is None:child.process.kill();child.process.wait(timeout=3)
                events,invalid=parse_events(child.lines);r[role+'_invalid_lines']=invalid
                r[role+'_result_events']=[x for x in events if x.get('kind')=='result']
                if role=='owner':
                    r['breakpoint_dispositions']=[];pending=None
                    for event in events:
                        if event.get('op')=='wait_end' and event.get('exception_code')==0x80000003:pending=event['tid']
                        elif pending is not None and event.get('op')=='continue_end' and event.get('tid')==pending:
                            r['breakpoint_dispositions'].append(dict(status=hex(event['status']),success=event['success']));pending=None
                r[role+'_stderr']=child.errors[-4:];r[role+'_exit']=child.process.returncode;close_child(child)
        fixture.close_fixture();r['fixture_exit_after_teardown']=fixture.process.returncode
        r['fixture_stderr']=fixture.errors[-6:]
        r['journal_files']=[dict(path=p.relative_to(HERE.parents[1]).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                            for p in journal.parent.glob(journal.name+'.*.jsonl')]
    return r

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=MODES)
    p.add_argument('--repeat',type=int,default=1);p.add_argument('--strict',action='store_true');args=p.parse_args()
    if not 1<=args.repeat<=3:p.error('repeat1..3')
    root=HERE.parents[1];cache=root/'data/bounded-receive-fault-boundaries-20261009';cache.mkdir(exist_ok=True)
    old=json.loads((root/'docs/evidence/501-bounded-receive-lifecycle-validation.json').read_text())
    paths=[root/x for x in old['source_hashes']]+[pathlib.Path(__file__),HERE/'receive_probe_attach_audit.py',HERE/'receive_probe_attach_fixture.py']
    r=dict(source_hashes={x.relative_to(root).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in paths},cases=[])
    output=cache/('attach-'+uuid.uuid4().hex[:12]+'.json');print(json.dumps(dict(output=str(output))),flush=True)
    for mode in [args.mode] if args.mode else MODES:
        for repeat in range(args.repeat):
            case=run_case(mode,args.strict);case['repeat']=repeat;r['cases'].append(case)
            output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:case.get(k) for k in ('mode','passed','failure_stage','native_exit','target_resumed','application_audit','breakpoint_dispositions')}),flush=True)
    return 0 if all(c['passed'] for c in r['cases']) else 1

if __name__=='__main__':raise SystemExit(main())
