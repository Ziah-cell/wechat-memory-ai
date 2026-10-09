"""Fixture-only acceptance checks for thread-aware guarded observation."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import uuid

from test_receive_probe_native import Child, HERE
from compare_receive_probe_methods import close_child


def run_case(mode, legacy=False):
    fixture = Child('receive_probe_fixture.py')
    owner = guardian = None
    r = {'mode':mode,'legacy':legacy,'passed':False,'fixture_only':True}
    try:
        info = fixture.event('ready')
        args = ['--fixture-pid',str(info['pid']),'--fixture-tid',str(info['main_tid']),
                '--fixture-address',str(info['address'])]
        script = 'receive_probe_transfer.py' if legacy else 'receive_probe_guarded.py'
        owner = Child(script,'--role','owner',*args)
        owner.event('owner_ready')
        guardian = Child(script,'--role','guardian',*args,'--owner-pid',str(owner.process.pid),
                         *(['--replay'] if legacy else []))
        ready = guardian.event('guardian_ready')
        owner.send(json.dumps({'debug_handle':ready['remote_handle'],'guardian_pid':guardian.process.pid}))
        owner.event('armed')
        fixture.send('ping'); fixture.event('pong')
        fixture.send('thread:hit' if mode=='new_thread' else 'hit')
        fixture.event('called')
        if legacy:
            guardian.process.kill(); guardian.process.wait(timeout=3)
        r['result'] = owner.event('result',timeout=4)
        assert owner.process.wait(timeout=3)==0
        assert r['result']['hits']==1, 'new-thread hardware hit missing'
        assert r['result'].get('record',{}).get('marker_match'), 'bounded marker record missing'
        assert r['result']['record']['origin']=='unknown'
        if not legacy:
            r['guardian_result']=guardian.event('result',timeout=4)
            assert guardian.process.wait(timeout=3)==0
        fixture.send('thread:miss'); fixture.event('called')
        fixture.send('miss'); fixture.event('called')
        a=fixture.event('heartbeat')['tick'];b=fixture.event('heartbeat')['tick']
        assert b>a
        r['passed']=True
    except (AssertionError,OSError,subprocess.TimeoutExpired) as e:
        r['failure_type']=type(e).__name__
        # Assertion strings are fixed harness checks only; child output may
        # contain addresses, so do not persist arbitrary exception text.
    finally:
        r['fixture_exit_before_teardown']=fixture.process.poll()
        for child,name in ((owner,'owner'),(guardian,'guardian')):
            if child:
                if child.process.poll() is None:
                    child.process.kill();child.process.wait(timeout=3)
                events=[json.loads(s) for s in child.lines if s.startswith('{')]
                for e in events:e.pop('remote_handle',None)
                r[name+'_events']=events
                r[name+'_error_tail']=child.errors[-2:]
                r[name+'_exit']=child.process.returncode
                close_child(child)
        fixture.close_fixture()
        r['fixture_exit_after_teardown']=fixture.process.returncode
        r['fixture_error_tail']=fixture.errors[-2:]
    return r


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--legacy',action='store_true')
    p.add_argument('--mode',choices=('new_thread','main_match'),default='new_thread')
    args=p.parse_args()
    cache=HERE.parents[1]/'data/bounded-receive-guarded-20261009'
    cache.mkdir(exist_ok=True)
    paths=[pathlib.Path(__file__),HERE/'receive_probe_fixture.py',HERE/'receive_probe_transfer.py',
           HERE/'receive_probe_win32.py',HERE/'check_receive_probe_layout.py',HERE/'test_receive_probe_native.py']
    if not args.legacy:paths.append(HERE/'receive_probe_guarded.py')
    r={'source_hashes':{s.relative_to(HERE.parents[1]).as_posix():hashlib.sha256(s.read_bytes()).hexdigest() for s in paths},
       'cases':[run_case(args.mode,args.legacy)]}
    output=cache/('run-'+uuid.uuid4().hex[:12]+'.json')
    output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(output),'passed':r['cases'][0]['passed'],'result':r['cases'][0].get('result')}))
    return 0 if r['cases'][0]['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
