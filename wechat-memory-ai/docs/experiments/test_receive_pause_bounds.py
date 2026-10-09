"""Offline checks for interval union, uncertainty and fail-closed timing."""
import unittest
import json
import pathlib
import uuid
from receive_pause_bounds import merged,metrics,assess

def trace(events):
    return [dict(role='owner',seq=i,ns=int(ms*1e6),op=op,**values)
            for i,(ms,op,values) in enumerate(events,1)]

def basic():
    return [(0,'role_start',{}),(1,'attach_begin',{}),(2,'attach_end',{'success':True}),
            (3,'wait_begin',{}),(10,'wait_end',{'has_event':True,'event_code':1,'tid':7}),
            (20,'continue_begin',{'tid':7,'status':0x10002}),
            (21,'continue_end',{'tid':7,'status':0x10002,'success':True}),
            (22,'detach_begin',{}),(23,'detach_end',{'success':True})]

class BoundsTests(unittest.TestCase):
    def test_overlap_and_adjacency_are_not_double_counted(self):
        self.assertEqual(merged([[3,9],[1,5],[9,11],[15,16]]),[[1,11],[15,16]])
        self.assertEqual(metrics([[1,5],[3,8]])[:2],(0.000007,0.000007))
    def test_reversed_interval_rejected(self):
        with self.assertRaises(ValueError):merged([[4,3]])
    def test_known_stop_is_shorter_than_upper_envelope(self):
        r=assess(trace(basic()))
        self.assertAlmostEqual(r['lower_max_ms'],9.998)
        self.assertGreater(r['upper_max_ms'],20)
        self.assertEqual(r['policy'],'within_conservative_bounds')
    def test_freeze_overlap_not_double_counted(self):
        events=basic()+[(11,'freeze_begin',{}),(12,'freeze_active',{}),
                       (18,'thaw_begin',{}),(19,'thaw_end',{})]
        r=assess(trace(sorted(events)))
        self.assertAlmostEqual(r['lower_total_ms'],9.998)
    def test_missing_continue_is_unknown(self):
        r=assess(trace(basic()[:5]))
        self.assertEqual(r['policy'],'cannot_certify');self.assertGreater(r['unclosed_intervals'],0)
    def test_sequence_gap_cannot_pass(self):
        rows=trace(basic());rows[3]['seq']=44
        r=assess(rows)
        self.assertIn('trace_sequence',r['errors']);self.assertEqual(r['policy'],'cannot_certify')
    def test_witness_contradiction_cannot_pass(self):
        r=assess(trace(basic()),{'ticks':[15_000_000]})
        self.assertEqual(r['witness_ticks_inside_known_stop'],1)
        self.assertEqual(r['policy'],'cannot_certify')
    def test_poll_start_not_poll_end_bounds_queued_event(self):
        events=basic()[:3]+[(6,'wait_begin',{}),(56,'wait_end',{'has_event':False}),
            (80,'wait_begin',{}),(90,'wait_end',{'has_event':True,'event_code':1,'tid':7}),
            (91,'continue_begin',{'tid':7,'status':0x10002}),
            (92,'continue_end',{'tid':7,'status':0x10002,'success':True}),
            (93,'detach_begin',{}),(94,'detach_end',{'success':True})]
        r=assess(trace(events));self.assertGreater(r['upper_max_ms'],86)
    def test_twenty_separate_stops_exceed_total_not_lower_single(self):
        events=basic()[:3]
        for i in range(20):
            b=10+100*i
            events.extend([(b,'wait_begin',{}),(b+1,'wait_end',{'has_event':False}),
                (b+2,'wait_begin',{}),(b+3,'wait_end',{'has_event':True,'event_code':1,'tid':7}),
                (b+63,'continue_begin',{'tid':7,'status':0x10002}),
                (b+64,'continue_end',{'tid':7,'status':0x10002,'success':True})])
        events.extend([(2000,'detach_begin',{}),(2001,'detach_end',{'success':True})])
        r=assess(trace(events));self.assertLess(r['lower_max_ms'],100)
        self.assertGreater(r['lower_total_ms'],1000);self.assertEqual(r['policy'],'exceeded')
    def test_replay_gap_is_not_counted_as_known_stop(self):
        events=basic()[:5]+[(100,'continue_begin',{'tid':7,'status':0x40010001}),
            (101,'continue_end',{'tid':7,'status':0x40010001,'success':True}),
            (101.5,'wait_begin',{}),(102,'wait_end',{'has_event':True,'event_code':1,'tid':7}),
            (150,'continue_begin',{'tid':7,'status':0x10002}),
            (151,'continue_end',{'tid':7,'status':0x10002,'success':True}),
            (152,'detach_begin',{}),(153,'detach_end',{'success':True})]
        r=assess(trace(events));self.assertAlmostEqual(r['lower_total_ms'],137.996)
        self.assertEqual(r['unclosed_intervals'],0)

class JournalTests(unittest.TestCase):
    def check_file(self,raw):
        import receive_probe_timing as probe
        base=pathlib.Path(__file__).resolve().parents[2]/'data/bounded-receive-timing-20261009'/('unit-'+uuid.uuid4().hex)
        path=base.with_suffix('.owner.jsonl');old=probe.JOURNAL
        try:
            path.write_bytes(raw);probe.JOURNAL=base
            return probe.owner_history()
        finally:
            probe.JOURNAL=old
            path.unlink()
    def valid(self):
        return [dict(x,kind='timing_trace') for x in trace(basic())]
    def encode(self,rows):return ('\r\n'.join(json.dumps(x) for x in rows)+'\r\n').encode()
    def test_complete_windows_framing(self):
        self.assertEqual(len(self.check_file(self.encode(self.valid()))),9)
    def test_truncated_crlf_is_rejected_before_newline_translation(self):
        with self.assertRaisesRegex(RuntimeError,'truncated'):
            self.check_file(self.encode(self.valid())[:-1])
    def test_mixed_actor_rejected(self):
        rows=self.valid();rows[3]['role']='guardian'
        with self.assertRaisesRegex(RuntimeError,'sequence'):self.check_file(self.encode(rows))
    def test_clock_type_rejected(self):
        rows=self.valid();rows[3]['ns']='unknown'
        with self.assertRaisesRegex(RuntimeError,'clock'):self.check_file(self.encode(rows))

if __name__=='__main__':unittest.main()
