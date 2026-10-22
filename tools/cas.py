"""Decode Frostbite CAS-compressed chunk data (blocks: BE u32 size, BE u16 code, BE u16 len)."""
import struct, subprocess, zlib

def decompress(d):
    out = bytearray(); p = 0
    while p + 8 <= len(d):
        dsz = struct.unpack_from(">I", d, p)[0]; code = struct.unpack_from(">H", d, p + 4)[0]
        bsz = struct.unpack_from(">H", d, p + 6)[0]; p += 8
        typ = code >> 8
        if bsz == 0 and typ == 0:  # stored, size in dsz
            bsz = dsz
        blk = d[p:p + bsz]; p += bsz
        if typ == 0x0F:
            r = subprocess.run(["zstd", "-d", "-c", "-q"], input=blk, capture_output=True)
            if r.returncode: raise ValueError("zstd failed")
            out += r.stdout
        elif typ == 0x02:
            out += zlib.decompress(blk)
        elif typ == 0x00:
            out += blk
        else:
            raise ValueError(f"compression {code:#x}")
    return bytes(out)
