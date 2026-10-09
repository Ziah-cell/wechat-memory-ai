"""Integration harness; spawns only this project's own fictional fixture.

No process enumeration, WeChat selection or real-chat access is implemented.
"""
import json
import pathlib
import queue
import subprocess
import sys
import threading
import time
import unittest
import hashlib
import re

HERE = pathlib.Path(__file__).resolve().parent
TRANSCRIPTS = []


class Child:
    def __init__(self, script, *args):
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(HERE / script), *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, creationflags=0x08000000,
        )
        self.queue = queue.Queue()
        self.lines = []
        self.errors = []
        def consume(stream, save, parse):
            for line in stream:
                save.append(line.rstrip())
                if parse:
                    try:
                        self.queue.put(json.loads(line))
                    except ValueError:
                        self.queue.put({"kind": "invalid_output"})
        threading.Thread(target=consume, args=(self.process.stdout, self.lines, True), daemon=True).start()
        threading.Thread(target=consume, args=(self.process.stderr, self.errors, False), daemon=True).start()

    def send(self, value):
        self.process.stdin.write(value + "\n")
        self.process.stdin.flush()

    def event(self, kind, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                item = self.queue.get(timeout=0.05)
            except queue.Empty:
                if self.process.poll() is not None:
                    raise AssertionError(f"child ended before {kind}: {self.process.returncode}; {self.lines[-4:]}; {self.errors}")
                continue
            if item.get("kind") == kind:
                return item
        raise AssertionError(f"child did not report {kind}; {self.lines[-4:]}; {self.errors}")

    def close_fixture(self):
        if self.process.poll() is None:
            self.send("exit")
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # ONLY the fixture created by this harness, never a user app.
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


class NativeProbeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Child("receive_probe_fixture.py")
        self.info = self.fixture.event("ready")
        self.observer = None

    def tearDown(self):
        saved = {"test": self._testMethodName,
                 "fixture_exit_before_teardown": self.fixture.process.poll(),
                 "fixture_error_tail": self.fixture.errors[-1:]}
        if self.observer:
            saved["observer_events"] = [json.loads(line) for line in self.observer.lines
                                         if line.startswith('{')]
            if self.observer.process.poll() is None:
                self.observer.send("cancel")
                try:
                    self.observer.process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    # Debugger crash testing here is confined to self-owned fixture.
                    self.observer.process.kill()
                    self.observer.process.wait(timeout=3)
            for stream in (self.observer.process.stdin, self.observer.process.stdout, self.observer.process.stderr):
                stream.close()
        self.fixture.close_fixture()
        saved["fixture_exit_after_teardown"] = self.fixture.process.returncode
        TRANSCRIPTS.append(saved)

    def start(self, *extra):
        self.observer = Child("receive_probe_observer.py", "--fixture-pid", str(self.info["pid"]),
                              "--fixture-address", str(self.info["address"]), *extra)
        return self.observer.event("armed")

    def assert_recovers(self):
        self.assertIsNone(self.fixture.process.poll(), "fixture must survive observer exit")
        self.fixture.send("miss")
        self.fixture.event("called", timeout=3)
        first = self.fixture.event("heartbeat", timeout=3)["tick"]
        second = self.fixture.event("heartbeat", timeout=3)["tick"]
        self.assertGreater(second, first)

    def result(self):
        result = self.observer.event("result")
        self.assertEqual(result["cleanup"], "detached", result)
        self.assertEqual(self.observer.process.wait(timeout=3), 0, self.observer.errors)
        return result

    def test_native_read_match_and_detach(self):
        self.start()
        self.fixture.send("hit")
        r = self.result()
        self.assertEqual(r["stop_reason"], "marker_match")
        self.assertEqual(r["hits"], 1)
        self.assertEqual(r["record"]["origin"], "unknown")
        self.assertNotIn("fixture-A", "".join(self.observer.lines))
        self.assert_recovers()

    def test_new_thread_breakpoint(self):
        self.start()
        self.fixture.send("thread:hit")
        self.assertEqual(self.result()["stop_reason"], "marker_match")
        self.assert_recovers()

    def test_delay_then_match(self):
        self.start()
        time.sleep(0.4)
        self.fixture.send("hit")
        self.assertEqual(self.result()["stop_reason"], "marker_match")
        self.assert_recovers()

    def test_cancel_while_waiting(self):
        self.start()
        self.observer.send("cancel")
        self.assertEqual(self.result()["stop_reason"], "cancelled")
        self.assert_recovers()

    def test_deadline(self):
        self.start("--duration", "0.4")
        self.assertEqual(self.result()["stop_reason"], "deadline")
        self.assert_recovers()

    def test_layout_error_detaches(self):
        self.start()
        self.fixture.send("bad")
        self.assertEqual(self.result()["stop_reason"], "layout_rejected")
        self.assert_recovers()

    def test_hit_budget(self):
        self.start("--max-hits", "2")
        for _ in range(2):
            self.fixture.send("miss")
            self.fixture.event("called")
        r = self.result()
        self.assertEqual((r["stop_reason"], r["hits"]), ("hit_budget", 2))
        self.assert_recovers()

    def test_target_exits(self):
        self.start()
        self.fixture.send("exit")
        self.fixture.process.wait(timeout=3)
        r = self.observer.event("result")
        self.assertEqual(r["stop_reason"], "target_exited")
        self.assertEqual(self.observer.process.wait(timeout=3), 0)

    def test_observer_abrupt_exit_target_survives(self):
        self.start()
        self.fixture.send("miss")
        self.fixture.event("called")  # debugger has resumed a real native hit
        self.observer.process.kill()  # only this harness's debugger and fixture
        self.observer.process.wait(timeout=3)
        self.assert_recovers()

    def test_unrelated_exception_passed_to_target(self):
        self.start()
        self.fixture.send("exception")
        self.fixture.event("exception_caught")
        self.fixture.send("hit")
        self.assertEqual(self.result()["stop_reason"], "marker_match")
        self.assert_recovers()

    def test_unhandled_native_exception_not_swallowed(self):
        self.start()
        self.fixture.send("fatal")
        self.assertEqual(self.fixture.process.wait(timeout=3), 0xc000001d)
        self.assertEqual(self.result()["stop_reason"], "target_exited")


class BindingContractTests(unittest.TestCase):
    def test_com_slots_against_pinned_microsoft_header(self):
        from receive_probe_observer import SLOTS
        cache = HERE.parents[1] / "data/bounded-receive-native-20261009"
        metadata = json.loads((cache / "header-source.json").read_text())
        raw = (cache / "DbgEng.h.txt").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata["sha256"])
        header = raw.decode("utf-8-sig")
        count = 0
        for interface, used in SLOTS.items():
            start = header.index("DECLARE_INTERFACE_(" + interface + ", IUnknown)")
            end = header.index("\n};", start)
            # Include STDMETHODV: omitting its three methods caused the initial ABI error.
            names = re.findall(r"STDMETHOD(?:V)?(?:_\([^,]+,\s*|\()([A-Za-z0-9_]+)\)", header[start:end])
            for method, slot in used.items():
                self.assertEqual(names[slot], method, (interface, method, slot))
                count += 1
        self.assertGreater(count, 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
