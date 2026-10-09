"""Disk-only, fixed-image audit of OS event/notification surface indicators.

This is an inventory, not provider discovery or a callable WeChat adapter.
No native module loading, process access, registry/notification access or tracing.
"""
import hashlib
import json
import struct
from pathlib import Path

IMAGE = Path("D:/软件/Weixin/4.1.15.50/Weixin.dll")
EXPECTED_SHA256 = "0cf6379405432385a1c442766443450f26a7689f45e53c1b4ad2822061f3113b"
API_NAMES = frozenset({
    "EventRegister", "EventUnregister", "EventWrite", "EventWriteEx",
    "EventWriteTransfer", "EventEnabled", "EventProviderEnabled",
    "RegisterTraceGuidsA", "RegisterTraceGuidsW", "TraceEvent", "TraceMessage",
    "RoGetActivationFactory", "RoActivateInstance", "WindowsCreateString",
    "WindowsDeleteString", "Shell_NotifyIconW", "Shell_NotifyIconA",
})
TOKENS = (
    "Windows.UI.Notifications.ToastNotificationManager",
    "Windows.UI.Notifications.ToastNotification",
    "Windows.UI.Notifications.Management.UserNotificationListener",
    "Microsoft.Windows.AppNotifications.AppNotificationManager",
    "ToastGeneric", "<toast", "TraceLogging",
)


def inspect():
    before = IMAGE.stat()
    data = IMAGE.read_bytes()
    after = IMAGE.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    digest = hashlib.sha256(data).hexdigest()
    assert digest == EXPECTED_SHA256, "fixed_image_changed"

    def unpack(fmt, pos):
        assert 0 <= pos <= len(data) - struct.calcsize(fmt)
        return struct.unpack_from(fmt, data, pos)

    pe = unpack("<I", 0x3c)[0]
    assert data[:2] == b"MZ" and data[pe:pe + 4] == b"PE\0\0"
    machine, nsects = unpack("<HH", pe + 4)
    opt_size = unpack("<H", pe + 20)[0]
    opt = pe + 24
    assert machine == 0x8664 and unpack("<H", opt)[0] == 0x20b
    sections = []
    for i in range(nsects):
        pos = opt + opt_size + 40 * i
        vs, rva, size, raw = unpack("<IIII", pos + 8)
        assert raw + size <= len(data)
        sections.append(dict(name=data[pos:pos + 8].split(b"\0")[0].decode("ascii"),
                             rva=rva, virtual_size=vs, size=size, raw=raw))

    def file_off(rva, size=1):
        for s in sections:
            delta = rva - s["rva"]
            if 0 <= delta and delta + size <= s["size"]:
                return s["raw"] + delta
        raise ValueError("rva_not_file_backed")

    def cstr(rva):
        pos = file_off(rva)
        end = data.index(b"\0", pos, min(pos + 1024, len(data)))
        file_off(rva, end - pos + 1)
        return data[pos:end].decode("ascii")

    imports = []
    directory_summary = []
    for kind, index, width in (("normal", 1, 20), ("delay", 13, 32)):
        start, size = unpack("<II", opt + 112 + index * 8)
        descriptors = symbols = 0
        terminated = not start
        if start:
            file_off(start, size)
            for pos in range(start, start + size - width + 1, width):
                vals = unpack("<" + "I" * (width // 4), file_off(pos, width))
                if not any(vals):
                    terminated = True
                    break
                if kind == "normal":
                    lookup, _, _, name, iat = vals
                else:
                    attrs, name, _, iat, lookup, _, _, _ = vals
                    assert attrs == 1, "delay_descriptor_not_rva_based"
                module = cstr(name)
                descriptors += 1
                lookup = lookup or iat
                for n in range(65536):
                    val = unpack("<Q", file_off(lookup + n * 8, 8))[0]
                    if not val:
                        break
                    symbols += 1
                    symbol = None if val >> 63 else cstr(val + 2)
                    if symbol in API_NAMES:
                        imports.append(dict(kind=kind, module=module, symbol=symbol,
                                            iat_rva=hex(iat + n * 8)))
                else:
                    raise ValueError("unterminated_lookup_table")
        assert terminated, "unterminated_import_directory"
        directory_summary.append(dict(kind=kind, descriptors=descriptors, symbols=symbols))

    matches = []
    for token in TOKENS:
        for encoding in ("ascii", "utf-16-le"):
            pattern = token.encode(encoding)
            offsets = []
            pos = 0
            while True:
                pos = data.find(pattern, pos)
                if pos < 0:
                    break
                offsets.append(pos)
                pos += 1
            rows = []
            for pos in offsets[:16]:
                sect = next((s for s in sections if s["raw"] <= pos < s["raw"] + s["size"]), None)
                rows.append(dict(file_offset=hex(pos), section=sect["name"] if sect else None,
                                 rva=hex(pos - sect["raw"] + sect["rva"]) if sect else None))
            matches.append(dict(token=token, encoding=encoding, count=len(offsets), first_matches=rows))
    return dict(image_sha256=digest, image_size=len(data), directories=directory_summary,
                api_name_allowlist=sorted(API_NAMES), matched_imports=imports, exact_substrings=matches,
                provider_guid_identified=False, message_schema_identified=False,
                runtime_observed=False, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                limits=["Only this exact disk image and normal/delay import directories were inspected.",
                        "Substring absence does not exclude dynamic lookup, other modules or other encodings.",
                        "API/string presence does not establish reachability, a message provider or message semantics."])


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, indent=2))
