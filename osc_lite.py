"""
osc_lite.py  -  Minimal OSC (Open Sound Control) encoder/decoder.
Pure Python standard library only. NO pip install needed.

Behringer X32 / Midas M32 ke sathe kaam karva mate banavelu.
"""

import struct


# ---------------------------------------------------------------- helpers
def _pad(data: bytes) -> bytes:
    """OSC ma badhu 4 byte na multiple ma hovu joiye."""
    return data + b"\x00" * ((4 - len(data) % 4) % 4)


def _enc_string(s: str) -> bytes:
    return _pad(s.encode("utf-8") + b"\x00")


def _dec_string(data: bytes, idx: int):
    end = data.index(b"\x00", idx)
    s = data[idx:end].decode("utf-8", "replace")
    idx = end + 1
    idx += (4 - idx % 4) % 4
    return s, idx


# ---------------------------------------------------------------- build
def build_message(address: str, *args) -> bytes:
    """
    OSC message banave.
    Supported types: int, float, str, bytes (blob), bool
    """
    types = ","
    body = b""

    for a in args:
        if isinstance(a, bool):
            types += "T" if a else "F"
        elif isinstance(a, int):
            types += "i"
            body += struct.pack(">i", a)
        elif isinstance(a, float):
            types += "f"
            body += struct.pack(">f", a)
        elif isinstance(a, str):
            types += "s"
            body += _enc_string(a)
        elif isinstance(a, (bytes, bytearray)):
            types += "b"
            body += struct.pack(">i", len(a)) + _pad(bytes(a))
        else:
            raise TypeError("OSC ma aa type support nathi: %r" % type(a))

    return _enc_string(address) + _enc_string(types) + body


# ---------------------------------------------------------------- parse
def parse_message(data: bytes):
    """
    Ek OSC packet parse kare.
    Return: list of (address, [args])  -- bundle hoy to ek karta vadhare.
    """
    if not data:
        return []

    if data[:8] == b"#bundle\x00":
        out = []
        idx = 16  # 8 (#bundle) + 8 (timetag)
        while idx + 4 <= len(data):
            size = struct.unpack(">i", data[idx:idx + 4])[0]
            idx += 4
            if size <= 0 or idx + size > len(data):
                break
            out.extend(parse_message(data[idx:idx + size]))
            idx += size
        return out

    try:
        address, idx = _dec_string(data, 0)
        if idx >= len(data):
            return [(address, [])]

        types, idx = _dec_string(data, idx)
        args = []

        for t in types[1:]:
            if t == "i":
                args.append(struct.unpack(">i", data[idx:idx + 4])[0]); idx += 4
            elif t == "f":
                args.append(struct.unpack(">f", data[idx:idx + 4])[0]); idx += 4
            elif t == "s":
                s, idx = _dec_string(data, idx); args.append(s)
            elif t == "b":
                n = struct.unpack(">i", data[idx:idx + 4])[0]; idx += 4
                args.append(data[idx:idx + n]); idx += n + ((4 - n % 4) % 4)
            elif t == "T":
                args.append(True)
            elif t == "F":
                args.append(False)
            elif t in "N I":
                args.append(None)
            else:
                break  # unknown type -- aatlethi j band

        return [(address, args)]
    except Exception:
        return []


# ---------------------------------------------------------------- X32 meter blob
def decode_meter_blob(blob: bytes):
    """
    X32/M32 meter blob ne float list ma convert kare.
    Format: [int32 count (little endian)] + [count x float32 (little endian)]
    """
    if not blob or len(blob) < 4:
        return []
    count = struct.unpack("<i", blob[:4])[0]
    if count <= 0 or count > 4096:
        return []
    avail = (len(blob) - 4) // 4
    count = min(count, avail)
    return list(struct.unpack("<%df" % count, blob[4:4 + 4 * count]))
