"""Concurrent fixture output must keep each JSON event on its own line."""
import io
import json
import threading
import time
import unittest
from contextlib import redirect_stdout
import receive_probe_lifecycle_fixture as fixture
from test_receive_probe_timing_lifecycle import parse_events


class YieldingBuffer(io.StringIO):
    def write(self, value):
        size = super().write(value)
        # print writes its JSON value and newline separately; allow another
        # fixture worker to run between those writes, as the native run did.
        time.sleep(0.0005)
        return size


class OutputTests(unittest.TestCase):
    def test_invalid_output_is_retained_as_failure_count(self):
        rows, invalid = parse_events(['{"kind":"a"}', '{"kind":"b"}{"kind":"c"}', '', '[]'])
        self.assertEqual(rows, [{'kind':'a'}])
        self.assertEqual(invalid, 3)

    def test_concurrent_events_remain_complete_json_lines(self):
        stream = YieldingBuffer()
        barrier = threading.Barrier(3)
        def worker(index):
            barrier.wait()
            for sequence in range(20):
                fixture.emit(dict(kind='test', worker=index, sequence=sequence))
        with redirect_stdout(stream):
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
            for thread in threads:thread.start()
            for thread in threads:thread.join()
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(len(rows), 60)
        self.assertEqual({(x['worker'], x['sequence']) for x in rows},
                         {(i, j) for i in range(3) for j in range(20)})


if __name__ == '__main__':
    unittest.main()
