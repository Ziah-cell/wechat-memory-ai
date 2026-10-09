"""Throwaway offline probe: fictional bytes only; no OS/process/network access.

Projects the selected .50 AddMsg input layout into a bounded, redacted record.
This is NOT a debugger, collector, identity classifier, or production adapter.
"""
import hashlib
import hmac
import json
import struct
import unittest

MAX_ADDRESS = (1 << 47) - 1
MARKER = b"VXPROBE:" + b"0123456789abcdef" * 2  # fictional, never a live nonce
KEY = b"fictional-session-key-not-for-live-use"


class Rejected(Exception):
    """Fixed error, containing no target bytes or addresses."""


class Reader:
    def __init__(self, read):
        self.read = read
        self.bytes = 0
        self.calls = 0

    def take(self, address, size):
        if (type(address) is not int or type(size) is not int or
                address < 0x10000 or size < 1 or address > MAX_ADDRESS - size + 1 or
                self.bytes + size > 512 or self.calls >= 12):
            raise Rejected("layout_rejected")
        self.bytes += size
        self.calls += 1
        try:
            value = self.read(address, size)
        except Exception:
            raise Rejected("read_rejected") from None
        if type(value) is not bytes or len(value) != size:
            raise Rejected("short_read")
        return value

    def string(self, nested, limit, exact=None):
        obj = u64(self.take(nested + 8, 8))
        desc = self.take(obj, 32)
        length, capacity = struct.unpack_from("<QQ", desc, 16)
        if length > capacity or (capacity < 16 and capacity != 15):
            raise Rejected("layout_rejected")
        if exact is not None and length != exact:
            return None  # do not read other-length message bodies
        if length == 0 or length > limit:
            raise Rejected("layout_rejected")
        if capacity < 16:
            return desc[:length]
        return self.take(u64(desc), length)


def u64(value, offset=0):
    return struct.unpack_from("<Q", value, offset)[0]


def project(read, raw_address, marker=MARKER, key=KEY):
    """Read at most 512 bytes/12 calls; return only redacted diagnostic fields.

    The reader is a byte-source dependency, not an assertion of pointer validity.
    Freshness/direction and field-12 uniqueness remain unknown even on a match.
    """
    if type(marker) is not bytes or len(marker) != 40 or type(key) is not bytes or len(key) < 32:
        raise Rejected("invalid_probe_parameters")
    reader = Reader(read)
    header = reader.take(raw_address, 0x58)
    if struct.unpack_from("<I", header, 0x14)[0] != 1:
        return None
    body = reader.string(u64(header, 0x20), 40, exact=40)
    if body is None or not hmac.compare_digest(body, marker):
        return None
    endpoints = [reader.string(u64(header, offset), 128) for offset in (8, 0x18)]
    def tag(domain, value):
        return hmac.new(key, domain + b"\0" + value, hashlib.sha256).hexdigest()
    return {
        "marker_match": True,
        "endpoint_a_tag": tag(b"endpoint", endpoints[0]),
        "endpoint_b_tag": tag(b"endpoint", endpoints[1]),
        "field12_tag": tag(b"field12", header[0x50:0x58]),
        "field12_nonzero": u64(header, 0x50) != 0,
        "direction": "unknown", "origin": "unknown",
        "read_bytes": reader.bytes, "read_calls": reader.calls,
    }


class FictionalMemory:
    def __init__(self, body=MARKER, endpoints=(b"endpoint-A", b"endpoint-B"), msg_type=1, source_id=99):
        self.data = bytearray(0x5000)
        self.requests = []
        self.endpoint_ranges = []
        self.put(0x10014, struct.pack("<I", msg_type))
        self.put(0x10050, struct.pack("<Q", source_id))
        for index, (offset, value) in enumerate(zip((0x20, 8, 0x18), (body, *endpoints))):
            nested, obj, heap = 0x11000 + index * 0x1000, 0x11100 + index * 0x1000, 0x11200 + index * 0x1000
            self.put(0x10000 + offset, struct.pack("<Q", nested))
            self.put(nested + 8, struct.pack("<Q", obj))
            if len(value) <= 15:
                self.put(obj, value.ljust(16, b"\0") + struct.pack("<QQ", len(value), 15))
            else:
                self.put(obj, struct.pack("<QQQQ", heap, 0, len(value), len(value)))
                self.put(heap, value)
            if index:
                self.endpoint_ranges.append((nested, heap + len(value)))

    def put(self, address, value):
        start = address - 0x10000
        self.data[start:start + len(value)] = value

    def read(self, address, size):
        self.requests.append((address, size))
        start = address - 0x10000
        return bytes(self.data[start:start + size])


class ProjectionTests(unittest.TestCase):
    def test_heap_marker_and_inline_endpoints(self):
        m = FictionalMemory()
        r = project(m.read, 0x10000)
        self.assertTrue(r["marker_match"])
        self.assertEqual((r["direction"], r["origin"]), ("unknown", "unknown"))
        self.assertEqual((r["read_bytes"], r["read_calls"]), (248, 8))

    def test_largest_endpoints_fit_budget(self):
        r = project(FictionalMemory(endpoints=(b"A"*128, b"B"*128)).read, 0x10000)
        self.assertEqual((r["read_bytes"], r["read_calls"]), (504, 10))

    def test_no_plaintext_in_output(self):
        encoded = json.dumps(project(FictionalMemory().read, 0x10000))
        for value in (MARKER.decode(), "endpoint-A", "endpoint-B"):
            self.assertNotIn(value, encoded)

    def test_nonmatch_does_not_read_endpoints(self):
        m = FictionalMemory(body=b"X"*40)
        self.assertIsNone(project(m.read, 0x10000))
        self.assertFalse(any(a <= address <= b for address, _ in m.requests for a, b in m.endpoint_ranges))

    def test_different_length_does_not_read_body(self):
        m = FictionalMemory(body=MARKER+b"x")
        self.assertIsNone(project(m.read, 0x10000))
        self.assertNotIn((0x11200, 41), m.requests)
        self.assertEqual(len(m.requests), 3)

    def test_other_type_reads_only_header(self):
        m = FictionalMemory(msg_type=49)
        self.assertIsNone(project(m.read, 0x10000))
        self.assertEqual(m.requests, [(0x10000, 0x58)])

    def test_zero_id_does_not_become_identity(self):
        r = project(FictionalMemory(source_id=0).read, 0x10000)
        self.assertFalse(r["field12_nonzero"])
        self.assertEqual(r["origin"], "unknown")

    def test_equal_endpoints_have_equal_tags(self):
        r = project(FictionalMemory(endpoints=(b"same", b"same")).read, 0x10000)
        self.assertEqual(r["endpoint_a_tag"], r["endpoint_b_tag"])

    def test_session_key_separates_tags(self):
        a = project(FictionalMemory().read, 0x10000)
        b = project(FictionalMemory().read, 0x10000, key=b"Z"*32)
        self.assertNotEqual(a["endpoint_a_tag"], b["endpoint_a_tag"])

    def test_short_read(self):
        with self.assertRaisesRegex(Rejected, "short_read"):
            project(lambda a, n: bytes(n-1), 0x10000)

    def test_read_exception_is_redacted(self):
        def broken(a, n):
            raise RuntimeError("sensitive target data")
        with self.assertRaisesRegex(Rejected, "^read_rejected$"):
            project(broken, 0x10000)

    def test_bad_header_addresses(self):
        for address in (0, -1, MAX_ADDRESS, 1 << 63):
            with self.subTest(address=address), self.assertRaises(Rejected):
                project(FictionalMemory().read, address)

    def test_null_nested_pointer(self):
        m = FictionalMemory()
        m.put(0x10020, bytes(8))
        with self.assertRaises(Rejected):
            project(m.read, 0x10000)

    def test_length_exceeds_capacity(self):
        m = FictionalMemory()
        m.put(0x11118, struct.pack("<Q", 20))
        with self.assertRaises(Rejected):
            project(m.read, 0x10000)

    def test_oversized_endpoint(self):
        m = FictionalMemory(endpoints=(b"A"*129, b"B"))
        with self.assertRaises(Rejected):
            project(m.read, 0x10000)

    def test_read_budget_and_call_budget(self):
        r = Reader(lambda a, n: bytes(n))
        r.take(0x10000, 512)
        with self.assertRaises(Rejected):
            r.take(0x10000, 1)
        r = Reader(lambda a, n: bytes(n))
        for _ in range(12):
            r.take(0x10000, 1)
        with self.assertRaises(Rejected):
            r.take(0x10000, 1)

    def test_bad_parameters(self):
        for marker, key in ((b"short", KEY), (MARKER, b"short")):
            with self.subTest(), self.assertRaises(Rejected):
                project(FictionalMemory().read, 0x10000, marker=marker, key=key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
