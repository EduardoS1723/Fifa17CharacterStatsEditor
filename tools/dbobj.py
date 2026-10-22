"""Reader for Frosty's legacy DbObject project format (FrostySdk/IO/DbReader.cs)."""
import struct, uuid

def read(data):
    pos = [0]
    def byte():
        b = data[pos[0]]; pos[0] += 1; return b
    def v7():
        r = s = 0
        while True:
            b = byte(); r |= (b & 0x7F) << s; s += 7
            if not b & 0x80: return r
    def cstr():
        e = data.index(b"\0", pos[0]); s = data[pos[0]:e].decode("utf-8", "replace"); pos[0] = e + 1; return s
    def take(n):
        b = data[pos[0]:pos[0] + n]; pos[0] += n; return b
    def obj():
        t = byte(); typ = t & 0x1F
        if typ == 0: return None, None
        name = "" if t & 0x80 else cstr()
        if typ in (1, 2):
            size = v7(); start = pos[0]; items = [] if typ == 1 else {}
            while pos[0] - start < size:
                n, v = obj()
                if n is None and v is None: break
                if typ == 1: items.append(v)
                else: items[n] = v
            return name, items
        if typ == 6: return name, byte() == 1
        if typ == 7: return name, take(v7()).decode("utf-8", "replace").rstrip("\0")
        if typ == 8: return name, struct.unpack("<i", take(4))[0]
        if typ == 9: return name, struct.unpack("<q", take(8))[0]
        if typ == 11: return name, struct.unpack("<f", take(4))[0]
        if typ == 12: return name, struct.unpack("<d", take(8))[0]
        if typ == 15: return name, uuid.UUID(bytes_le=take(16))
        if typ == 16: return name, take(20)
        if typ == 19: return name, take(v7())
        raise ValueError(f"type {typ} at {pos[0]}")
    return obj()[1]
