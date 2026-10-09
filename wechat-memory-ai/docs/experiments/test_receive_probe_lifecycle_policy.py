"""Offline lifecycle policy checks. No native attach or process creation."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import receive_probe_lifecycle as lifecycle
import receive_probe_timing as timing
from receive_pause_bounds import assess
from test_receive_pause_bounds import trace, basic


class LifecyclePolicyTests(unittest.TestCase):
    def test_idle_wait_slice_is_five_ms(self):
        debugger = object.__new__(lifecycle.LifecycleDebugger)
        for requested, expected in ((50, 5), (500, 5), (0, 0), (2, 2)):
            with patch.object(timing.TimedDebugger, 'wait', return_value=None) as wait:
                debugger.wait(requested)
                wait.assert_called_once_with(expected)

    def policy(self, records, record=True, history_unknown=False):
        debugger = object.__new__(lifecycle.LifecycleDebugger)
        debugger.history = []
        debugger.history_unknown = history_unknown
        debugger.stop_reason = 'marker_match'
        debugger.record = {'marker_match': True} if record else None
        with patch.object(timing, 'ENFORCE', True), patch.object(timing, 'TRACE', SimpleNamespace(records=records)):
            debugger.check_budget()
        return debugger

    def test_idle_gap_does_not_count_as_known_suspension(self):
        events = basic()[:3] + [(140, 'wait_begin', {}),
            (145, 'wait_end', {'has_event': False}), (146, 'wait_begin', {}),
            (150, 'wait_end', {'has_event': True, 'event_code': 1, 'tid': 7}),
            (151, 'continue_begin', {'tid': 7, 'status': 0x10002}),
            (152, 'continue_end', {'tid': 7, 'status': 0x10002, 'success': True}),
            (153, 'detach_begin', {}), (154, 'detach_end', {'success': True})]
        rows = trace(events)
        self.assertEqual(assess(rows)['policy'], 'within_conservative_bounds')
        self.assertEqual(self.policy(rows).stop_reason, 'marker_match')

    def test_frozen_owner_death_is_unknown_without_controller_clock(self):
        rows = trace(basic() + [(24, 'freeze_begin', {}), (25, 'freeze_active', {})])
        runtime = self.policy(rows)
        self.assertEqual(runtime.stop_reason, 'pause_timing_unknown')
        self.assertIsNone(runtime.record)
        controller = [dict(role='controller', op='kill_begin', ns=30_000_000, victim='owner'),
                      dict(role='controller', op='kill_end', ns=31_000_000, victim='owner')]
        self.assertEqual(assess(rows + controller)['policy'], 'within_conservative_bounds')
        self.assertEqual(assess(rows)['policy'], 'cannot_certify')

    def test_known_long_stop_discards_candidate(self):
        events = basic()
        events[5:] = [(ms + 150, op, values) for ms, op, values in events[5:]]
        runtime = self.policy(trace(events))
        self.assertEqual(runtime.stop_reason, 'pause_budget_upper')
        self.assertIsNone(runtime.record)

    def test_missing_history_discards_even_with_small_local_bounds(self):
        runtime = self.policy(trace(basic()), history_unknown=True)
        self.assertEqual(runtime.stop_reason, 'pause_timing_unknown')
        self.assertIsNone(runtime.record)

    def test_partial_continue_discards_candidate(self):
        runtime = self.policy(trace(basic()[:6]))
        self.assertEqual(runtime.stop_reason, 'pause_timing_unknown')
        self.assertIsNone(runtime.record)


if __name__ == '__main__':
    unittest.main()
