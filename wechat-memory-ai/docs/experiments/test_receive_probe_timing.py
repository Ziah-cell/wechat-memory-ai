"""Timing validation of own fixtures only; never accepts a user application."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import time
import uuid
from test_receive_probe_native import Child,HERE
from compare_receive_probe_methods import close_child

MODES=('normal','idle','new_thread','queued','received','attach','cleanup','cumulative','total','owner_crash','history_truncated','history_missing')
CRASH=('owner_crash','history_truncated','history_missing')

def run_case(mode,legacy=False,enforce=False):
    fixture=Child('receive_probe_timed_fixture.py');owner=guardian=None
    r={'mode':mode,'legacy':legacy,'enforce':enforce,'passed':False};stage='setup'
    traces=[]
    cache=HERE.parents[1]/'data/bounded-receive-timing-20261009'
    journal=cache/('journal-'+uuid.uuid4().hex)
    try:
        info=fixture.event('ready')
        fixture.send('timing_begin');fixture.event('timing_started')
        args=['--fixture-pid',str(info['pid']),'--fixture-tid',str(info['main_tid']),
              '--fixture-address',str(info['address'])]
        script='receive_probe_guarded.py' if legacy else 'receive_probe_timing.py'
        options=['--duration','3']
        if mode in CRASH:options+=['--fault','received']
        if mode in ('cumulative','total'):options+=['--max-hits','20']
        if not legacy:options+=['--timing-case','owner_crash' if mode in CRASH else mode,'--timing-journal',str(journal)]
        if enforce:options+=['--enforce-timing']
        owner=Child(script,'--role','owner',*args,*options);owner.event('owner_ready')
        guardian=Child(script,'--role','guardian',*args,'--owner-pid',str(owner.process.pid),
                       *(['--enforce-timing'] if enforce else []),
                       *(['--timing-journal',str(journal)] if not legacy and mode!='history_missing' else []))
        ready=guardian.event('guardian_ready')
        owner.send(json.dumps({'debug_handle':ready['remote_handle'],'guardian_pid':guardian.process.pid}))
        early_stop=enforce and mode=='attach'
        if not early_stop:owner.event('armed')
        r['armed_expected']=not early_stop;stage='trigger'
        if mode=='queued':
            fixture.send('miss');fixture.event('called');owner.event('timing_boundary')
        if mode=='idle':time.sleep(0.25)
        if not early_stop:fixture.send('thread:hit' if mode=='new_thread' else 'miss' if mode in CRASH or mode in ('cumulative','total') else 'hit')
        if mode in CRASH:
            owner.event('fault_boundary')
            traces.append({'role':'controller','op':'kill_begin','ns':time.perf_counter_ns(),'victim':'owner'})
            owner.process.kill();owner.process.wait(timeout=3)
            traces.append({'role':'controller','op':'kill_end','ns':time.perf_counter_ns(),'victim':'owner'})
            if mode=='history_truncated':
                path=journal.with_suffix('.owner.jsonl')
                path.write_bytes(path.read_bytes()[:-1])
        elif mode in ('cumulative','total'):
            for _ in range(19):
                fixture.event('called')
                if mode=='total':time.sleep(0.02)
                fixture.send('miss')
        stage='cleanup';survivor=guardian if mode in CRASH else owner
        r['result']=survivor.event('result',timeout=5)
        assert r['result']['cleanup'] in ('detached','already_detached','target_exited')
        assert survivor.process.wait(timeout=3)==0
        if mode not in CRASH:
            r['guardian_result']=guardian.event('result',timeout=5)
            assert r['guardian_result']['cleanup'] in ('detached','already_detached')
            assert guardian.process.wait(timeout=3)==0
        stage='timing'
        fixture.send('ping');fixture.event('pong')
        if early_stop:fixture.send('miss');fixture.event('called')
        fixture.send('timing_end');witness=fixture.event('timing')
        assert not witness['overflow']
        fixture.send('thread:miss');fixture.event('called')
        fixture.send('miss');fixture.event('called')
        fixture.send('ping');fixture.event('pong');r['recovered']=True
        for child in (owner,guardian):
            traces.extend(json.loads(s) for s in child.lines if s.startswith('{') and json.loads(s).get('kind')=='timing_trace')
        r['target_call_max_ms']=max((b-a)/1e6 for a,b in witness['calls'])
        r['target_gap_max_ms']=max((b-a)/1e6 for a,b in zip(witness['ticks'],witness['ticks'][1:]))
        r['old_event_processing_max_ms']=r['result']['max_event_processing_ms']
        if legacy:
            assert mode=='owner_crash' and r['target_call_max_ms']>=150
            r['legacy_underreports_known_delay']=r['old_event_processing_max_ms']<100
            assert not r['legacy_underreports_known_delay']
        else:
            from receive_pause_bounds import assess
            r['bounds']=assess(traces,witness)
            if mode in ('normal','idle','new_thread'):
                assert r['bounds']['policy']!='exceeded'
            else:
                assert r['bounds']['policy'] in ('exceeded','cannot_certify')
                assert r['bounds']['upper_total_ms']>=1000 if mode=='total' else r['bounds']['upper_max_ms']>=100
            if mode in ('received','cleanup',*CRASH):
                assert r['bounds']['lower_max_ms']>=100
            if mode=='cumulative' and not enforce:assert r['bounds']['lower_total_ms']>=1000
            if mode=='queued':assert r['target_call_max_ms']>=150
            if enforce and mode not in ('normal','idle','new_thread'):
                assert r['result']['stop_reason']==('pause_timing_unknown' if mode.startswith('history_') else 'pause_budget_upper')
                assert r['result']['record'] is None
                if mode in ('cumulative','total'):assert r['result']['hits']<20
            if mode=='total':assert r['bounds']['upper_max_ms']<100
            assert r['bounds']['witness_ticks_inside_known_stop']==0
            assert not r['bounds']['unclosed_intervals']
        assert all(not x.errors for x in (fixture,owner,guardian))
        r['passed']=True
    except (AssertionError,OSError,RuntimeError,subprocess.TimeoutExpired) as error:
        r['failure_stage']=stage;r['failure_type']=type(error).__name__
    finally:
        for child in (owner,guardian):
            if child:
                if child.process.poll() is None:child.process.kill();child.process.wait(timeout=3)
                if not r['passed']:
                    events=[json.loads(s) for s in child.lines if s.startswith('{')]
                    r.setdefault('failure_results',[]).extend(x for x in events if x.get('kind')=='result')
                close_child(child)
        fixture.close_fixture();r['fixture_exit']=fixture.process.returncode
        r['stderr_present']=any(bool(x.errors) for x in (fixture,owner,guardian) if x)
        r['journal_files']=[{'path':p.relative_to(HERE.parents[1]).as_posix(),
                            'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in cache.glob(journal.name+'.*.jsonl')]
    if 'witness' in locals():
        origin=witness['ticks'][0]
        for x in traces:x['ns']-=origin
        # Preserve only relative times and pseudonymous thread indexes.
        tids={}
        for x in traces:
            if 'tid' in x:x['thread']=tids.setdefault(x.pop('tid'),len(tids)+1)
        r['trace']=sorted(traces,key=lambda x:x['ns'])
        r['witness']={'ticks':[x-origin for x in witness['ticks']],
                      'calls':[[a-origin,b-origin] for a,b in witness['calls']],
                      'overflow':witness['overflow']}
    return r

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=MODES)
    p.add_argument('--legacy',action='store_true');p.add_argument('--repeat',type=int,default=1)
    p.add_argument('--enforce',action='store_true')
    a=p.parse_args()
    if not 1<=a.repeat<=5:p.error('repeat')
    if a.legacy and a.mode!='owner_crash':p.error('legacy contrast is owner_crash only')
    paths=[pathlib.Path(__file__)]+[HERE/n for n in ('receive_probe_timed_fixture.py','receive_probe_guarded.py',
        'receive_probe_parallel_fixture.py','receive_probe_transfer.py','receive_probe_win32.py',
        'receive_probe_observer.py','probe_fixture_freeze.py','check_receive_probe_layout.py',
        'test_receive_probe_native.py','compare_receive_probe_methods.py','receive_probe_variants.py')]
    if not a.legacy:paths += [HERE/'receive_probe_timing.py',HERE/'receive_pause_bounds.py']
    r={'source_hashes':{str(s.relative_to(HERE.parents[1])).replace('\\','/'):hashlib.sha256(s.read_bytes()).hexdigest() for s in paths},'cases':[]}
    cache=HERE.parents[1]/'data/bounded-receive-timing-20261009'
    output=cache/('run-'+uuid.uuid4().hex[:12]+'.json');print(json.dumps({'output':str(output)}),flush=True)
    for mode in [a.mode] if a.mode else MODES:
        for repeat in range(a.repeat):
            case=run_case(mode,a.legacy,a.enforce);case['repeat']=repeat;r['cases'].append(case)
            output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:case.get(k) for k in ('mode','passed','failure_stage','bounds','target_call_max_ms','old_event_processing_max_ms')}),flush=True)
    return 0 if all(x['passed'] for x in r['cases']) else 1

if __name__=='__main__':raise SystemExit(main())
