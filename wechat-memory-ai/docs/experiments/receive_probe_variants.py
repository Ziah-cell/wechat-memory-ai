"""Throwaway fixture-only one-shot and controller-lease experiments."""
import argparse
import json
import sys
import threading

import receive_probe_observer as original


class OneShotEngine(original.Engine):
    def arm(self, address):
        super().arm(address)
        original.checked(self.breakpoint.call("AddFlags", [original.U32], 0x10), "one_shot")

    def event(self):
        kind, extra = super().event()
        if kind == 1:
            # DbgEng owns one-shot deletion on first trigger; do not reuse the
            # deleted COM breakpoint pointer during ordinary cleanup.
            self.breakpoint = None
        return kind, extra


class FreshStopEngine(original.Engine):
    def resume(self, status=1):
        current = original.U32()
        hr = self.control.call("GetExecutionStatus", [original.c.POINTER(original.U32)],
                               original.c.byref(current))
        if hr == 0 and current.value == status and status == 1:
            self.cleanup_steps.append({"api": "already_go", "status": current.value})
        else:
            try:
                super().resume(status)
            except original.ProbeError as error:
                self.cleanup_steps.append({"api": "resume_failed", "status": status,
                                           "hresult": error.hr})
                raise
        # A successful prior WaitForEvent is no longer proof of a usable stop
        # after requesting GO. Cancellation must reacquire a fresh stop before
        # it removes the hardware slot and consumes the owned exception.
        self.at_event = False


class ControllerLease:
    """Cancel the existing engine loop when our sibling controller exits."""
    def __init__(self, pid):
        self.identity = original.ProcessIdentity(pid)
        self.closed = threading.Event()
        self.lock = threading.Lock()

    def __iter__(self):
        while not self.closed.wait(0.02):
            with self.lock:
                if self.closed.is_set():
                    return
                ended = self.identity.exited()
            if ended:
                yield "cancel\n"
                return

    def close(self):
        with self.lock:
            self.closed.set()
            self.identity.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("one_shot", "broker", "controller"), required=True)
    parser.add_argument("--fixture-pid", type=int)
    parser.add_argument("--fixture-address", type=int)
    parser.add_argument("--controller-pid", type=int)
    args = parser.parse_args()
    if args.mode == "controller":
        print(json.dumps({"kind": "controller_ready"}), flush=True)
        for _ in sys.stdin:
            pass
        return 0
    if args.fixture_pid is None or args.fixture_address is None:
        parser.error("fixture identity required")
    lease = None
    if args.mode == "one_shot":
        original.Engine = OneShotEngine
    else:
        if args.controller_pid is None:
            parser.error("sibling controller required")
        original.Engine = FreshStopEngine
        lease = ControllerLease(args.controller_pid)
        sys.stdin = lease
    try:
        return original.observe_fixture(args.fixture_pid, args.fixture_address, 6, 200)
    finally:
        if lease:
            lease.close()


if __name__ == "__main__":
    raise SystemExit(main())
