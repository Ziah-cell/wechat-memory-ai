"""Owned-fixture lifecycle integration; no live application selector."""
import receive_probe_timing as timing


class LifecycleDebugger(timing.TimedDebugger):
    def wait(self, ms=50):
        # An empty wait's START is the last conservative running boundary.
        # Two 50 ms slices can make a short event exceed the 100 ms upper limit.
        # Keep zero-time cleanup polls zero, and record the actual requested slice.
        return super().wait(min(ms, 5))


original_result = timing.original.result_for


def result_for(debugger, cleanup):
    result = original_result(debugger, cleanup)
    result['runtime_timing'] = timing.assess(debugger.history + timing.TRACE.records)
    result['runtime_history_unknown'] = debugger.history_unknown
    # The guardian has no controller kill-request/exit timestamps. Its missing
    # freeze interval must stay unknown even if the test parent can bound it.
    result['runtime_controller_clock_available'] = False
    return result


def main():
    timing.TimedDebugger = LifecycleDebugger
    timing.original.result_for = result_for
    return timing.main()


if __name__ == '__main__':
    raise SystemExit(main())
