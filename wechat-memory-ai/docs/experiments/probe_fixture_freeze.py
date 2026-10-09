"""Self-owned fixture probe for process-state-handle automatic resume."""
import argparse
import ctypes as c
import hashlib
import json
import pathlib
import time
import uuid
from receive_probe_observer import ProcessIdentity
from receive_probe_win32 import PTR,U32,emit
from test_receive_probe_native import Child,HERE
from compare_receive_probe_methods import close_child


class StateFreeze:
    def __init__(self, process):
        self.process=process
        self.handle=PTR()
        self.n=c.WinDLL('ntdll',use_last_error=True)
        self.k=c.WinDLL('kernel32',use_last_error=True)
        self.k.CloseHandle.argtypes=[PTR]
        self.n.NtCreateProcessStateChange.argtypes=[c.POINTER(PTR),U32,PTR,PTR,U32]
        self.n.NtCreateProcessStateChange.restype=c.c_int32
        self.n.NtChangeProcessState.argtypes=[PTR,PTR,U32,PTR,c.c_size_t,U32]
        self.n.NtChangeProcessState.restype=c.c_int32
        self.check(self.n.NtCreateProcessStateChange(c.byref(self.handle),0xf0001,None,process,0))

    @staticmethod
    def check(status):
        if status<0:raise RuntimeError('state_change_failed:'+hex(status & 0xffffffff))

    def suspend(self):
        self.check(self.n.NtChangeProcessState(self.handle,self.process,0,None,0,0))

    def close(self):
        if self.handle.value:
            self.k.CloseHandle(self.handle)
            self.handle=PTR()


def worker(pid):
    identity=ProcessIdentity(pid)
    k=c.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[U32,c.c_int,U32];k.OpenProcess.restype=PTR
    k.CloseHandle.argtypes=[PTR]
    # Creation requires SET_INFORMATION; applying suspend requires SUSPEND_RESUME.
    process=k.OpenProcess(0xa00,False,pid)
    if not process:raise c.WinError(c.get_last_error())
    freeze=StateFreeze(process)
    try:
        freeze.suspend();emit(kind='frozen',fixture_only=True)
        time.sleep(8)
    finally:
        freeze.close();k.CloseHandle(process);identity.close()


def probe():
    results=[]
    for repeat in range(3):
        f=Child('receive_probe_fixture.py');w=None
        r={'repeat':repeat,'passed':False}
        try:
            info=f.event('ready')
            f.send('ping');f.event('pong')
            w=Child('probe_fixture_freeze.py','--fixture-pid',str(info['pid']))
            w.event('frozen')
            f.send('ping')
            blocked=False
            try:f.event('pong',timeout=0.2)
            except AssertionError:blocked=True
            assert blocked and f.process.poll() is None
            r['blocked_before_worker_exit']=True
            # The reply cannot be produced until the main thread resumes.
            w.process.kill();w.process.wait(timeout=3)
            f.event('pong',timeout=2)
            f.send('miss');f.event('called',timeout=2)
            r['passed']=True
        except (AssertionError,OSError,RuntimeError) as error:
            r['failure_type']=type(error).__name__
        finally:
            if w:
                if w.process.poll() is None:w.process.kill();w.process.wait(timeout=3)
                r['worker_error_tail']=w.errors[-2:];close_child(w)
            f.close_fixture();r['fixture_exit']=f.process.returncode
            results.append(r)
    cache=HERE.parents[1]/'data/bounded-receive-guarded-20261009'
    output=cache/('freeze-'+uuid.uuid4().hex[:12]+'.json')
    r={'cases':results,'source_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
    output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    emit(output=str(output),cases=results)
    return 0 if all(x['passed'] for x in results) else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture-pid',type=int)
    a=p.parse_args()
    raise SystemExit(worker(a.fixture_pid) if a.fixture_pid else probe())
