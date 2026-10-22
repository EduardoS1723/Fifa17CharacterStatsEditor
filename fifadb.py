"""Reader/writer for EA's binary t3db database (FIFA 17 .db files and squad saves).

The binary file stores each table as bit-packed fixed-size records. The field
layout (type, bit offset, bit depth) is stored in the file itself, but names
and value ranges are not -- those come from the matching *-meta.XML file.

Some details of the binary layout differ between FIFA versions/platforms, so
this module detects them from the file instead of hard-coding them:
  * byte order of the 4-character short names
  * the size of the per-table header
  * the order of the four values inside a field descriptor
  * the bit order used to pack values into records
  * the CRC32 variant protecting each block of records
Field edits are made in place, so only the CRC of the modified record blocks has
to be recomputed when saving. Rows can be appended to tables without a string
pool (Table.append_row); that shifts every later table, so the table list
offsets, the database size and the header/list CRCs are fixed up immediately.
"""

import datetime
import os
import shutil
import struct
import xml.etree.ElementTree as ET
import zlib

SIGNATURE = b"DB\x00\x08"
FIFA_EPOCH = datetime.date(1582, 10, 14)

TYPE_STRING = "string"
FILE_TYPE_POOLED_STRING = 13  # record holds a u32 offset into the table's string pool
FILE_TYPE_POOLED_LONG = 14  # same, but the pool entry has a 2-byte (big-endian) length
POOLED_LEN_BYTES = {FILE_TYPE_POOLED_STRING: 1, FILE_TYPE_POOLED_LONG: 2}
TYPE_INT = "int"
TYPE_REAL = "real"
TYPE_DATE = "date"

_META_TYPES = {
    "DBOFIELDTYPE_INTEGER": TYPE_INT,
    "DBOFIELDTYPE_REAL": TYPE_REAL,
    "DBOFIELDTYPE_STRING": TYPE_STRING,
    "DBOFIELDTYPE_DATE": TYPE_DATE,
}


class DBError(Exception):
    pass


# --------------------------------------------------------------------------
# CRC variants
# --------------------------------------------------------------------------

def _make_msb_table():
    table = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) if c & 0x80000000 else (c << 1)
        table.append(c & 0xFFFFFFFF)
    return table


_MSB_TABLE = _make_msb_table()


def _crc_msb(data, init=0xFFFFFFFF):
    crc = init
    tbl = _MSB_TABLE
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ tbl[((crc >> 24) ^ b) & 0xFF]
    return crc


CRC_VARIANTS = {
    "crc32": lambda d: zlib.crc32(d) & 0xFFFFFFFF,
    "jamcrc": lambda d: (~zlib.crc32(d)) & 0xFFFFFFFF,
    "mpeg2": lambda d: _crc_msb(d),
    "bzip2": lambda d: _crc_msb(d) ^ 0xFFFFFFFF,
}


def _detect_crc(data, stored):
    for name, fn in CRC_VARIANTS.items():
        if fn(data) == stored:
            return name
    return None


# --------------------------------------------------------------------------
# Meta XML
# --------------------------------------------------------------------------

class MetaField:
    def __init__(self, el):
        self.name = el.get("name")
        self.shortname = el.get("shortname")
        self.type = _META_TYPES.get(el.get("type"), TYPE_INT)
        self.depth = int(el.get("depth", "0"))
        self.low = int(el.get("rangelow", "0"))
        self.high = int(el.get("rangehigh", "0"))
        self.key = el.get("key") == "True"
        self.fk = el.get("fkparenttable")


class MetaTable:
    def __init__(self, el):
        self.name = el.get("name")
        self.shortname = el.get("shortname")
        self.fields = [MetaField(f) for f in el.iter("field")]
        self.by_short = {f.shortname: f for f in self.fields}


class Meta:
    def __init__(self, path):
        root = ET.parse(path).getroot()
        self.dbname = root.get("name")
        self.tables = [MetaTable(t) for t in root.iter("table")]
        self.by_short = {t.shortname: t for t in self.tables}
        self.by_name = {t.name: t for t in self.tables}


# --------------------------------------------------------------------------
# Binary database
# --------------------------------------------------------------------------

class Field:
    """A field as laid out in the binary file, joined with its meta info."""

    def __init__(self, shortname, ftype_code, bitoffset, depth, meta):
        self.shortname = shortname
        self.type_code = ftype_code
        self.bitoffset = bitoffset
        self.depth = depth
        self.meta = meta
        self.name = meta.name if meta else shortname
        self.type = meta.type if meta else TYPE_INT
        self.low = meta.low if meta else 0
        self.high = meta.high if meta else (1 << depth) - 1 + 0
        self.pooled = ftype_code in POOLED_LEN_BYTES
        if self.pooled:
            self.type = TYPE_STRING
        if self.type == TYPE_STRING:
            self.high = 0

    @property
    def editable(self):
        if self.pooled:
            return False
        return self.type != TYPE_STRING or self.bitoffset % 8 == 0


class Table:
    def __init__(self, db, shortname, meta):
        self.db = db
        self.shortname = shortname
        self.meta = meta
        self.name = meta.name if meta else shortname
        self.pos = 0  # absolute offset of the 32-byte table header
        self.fields = []
        self.by_name = {}
        self.record_size = 0
        self.n_rows = 0
        self.records_start = 0
        self.records_len = 0
        self.crc_pos = None
        self.crc_start = 0
        self.crc_variant = None
        self.pool_start = 0
        self.pool_len = 0
        self.huffman = None  # list of (child0, child1) when the pool is compressed
        self._pool_cache = {}
        self.dirty = False

    # -- raw access --------------------------------------------------------
    def _rec(self, row):
        start = self.records_start + row * self.record_size
        return start, self.db.data[start:start + self.record_size]

    def _get_bits(self, rec, bitoffset, depth):
        if self.db.bit_order == "lsb":
            return (int.from_bytes(rec, "little") >> bitoffset) & ((1 << depth) - 1)
        total = len(rec) * 8
        return (int.from_bytes(rec, "big") >> (total - bitoffset - depth)) & ((1 << depth) - 1)

    def _set_bits(self, row, bitoffset, depth, value):
        start, rec = self._rec(row)
        mask = (1 << depth) - 1
        value &= mask
        if self.db.bit_order == "lsb":
            n = int.from_bytes(rec, "little")
            n = (n & ~(mask << bitoffset)) | (value << bitoffset)
            new = n.to_bytes(len(rec), "little")
        else:
            total = len(rec) * 8
            shift = total - bitoffset - depth
            n = int.from_bytes(rec, "big")
            n = (n & ~(mask << shift)) | (value << shift)
            new = n.to_bytes(len(rec), "big")
        self.db.data[start:start + len(rec)] = new

    def _read_pooled(self, off, len_bytes=1):
        """A pool entry is a length (1 byte, or 2 big-endian bytes for type 14)
        followed by the string; in compressed pools the string is Huffman-coded
        (MSB-first bits, 0 = first child) and the length counts decoded bytes."""
        data = self.db.data
        p = self.pool_start + off
        n = int.from_bytes(data[p:p + len_bytes], "big")
        p += len_bytes
        if not self.huffman:
            raw = bytes(data[p:p + n])
        else:
            nodes = self.huffman
            out = bytearray()
            bit = 0
            end = self.pool_start + self.pool_len
            while len(out) < n:
                node = 0
                while True:
                    byte_pos = p + (bit >> 3)
                    if byte_pos >= end:
                        return out.decode("utf-8", errors="replace")
                    b = (data[byte_pos] >> (7 - (bit & 7))) & 1
                    bit += 1
                    kind, val = nodes[node][b]
                    if kind == 0:
                        out.append(val)
                        break
                    node = kind
            raw = bytes(out)
        return raw.decode("utf-8", errors="replace")

    def _load_pool(self):
        """Detect a Huffman tree at the start of the pool: it ends where the first
        string begins, so the smallest referenced offset is the tree size."""
        pooled = [f for f in self.fields if f.pooled]
        offs = [self._get_bits(self._rec(r)[1], f.bitoffset, 32)
                for f in pooled for r in self.rows()]
        offs = [o for o in offs if o != 0xFFFFFFFF]
        tree_len = min(offs) if offs else 0
        if tree_len and tree_len % 4 == 0:
            d = self.db.data
            p = self.pool_start
            self.huffman = [((d[p + i], d[p + i + 1]), (d[p + i + 2], d[p + i + 3]))
                            for i in range(0, tree_len, 4)]

    def _encode_pooled(self, text, len_bytes):
        """Bytes of one pool entry, Huffman-coded with this table's existing tree."""
        raw = str(text).encode("utf-8")
        if len(raw) >= 1 << (8 * len_bytes):
            raise DBError(f"'{text[:20]}…' is too long for '{self.name}'")
        if not self.huffman:
            return len(raw).to_bytes(len_bytes, "big") + raw
        if not hasattr(self, "_codes"):
            codes, stack = {}, [(0, "")]
            while stack:  # walk the tree: (node, bits so far)
                node, bits = stack.pop()
                for b in (0, 1):
                    kind, val = self.huffman[node][b]
                    if kind == 0:
                        codes.setdefault(val, bits + str(b))
                    else:
                        stack.append((kind, bits + str(b)))
            self._codes = codes
        missing = sorted({chr(c) if c < 128 else f"\\x{c:02x}" for c in raw
                          if c not in self._codes})
        if missing:
            raise DBError(f"'{self.name}' can't store the character(s) {' '.join(missing)}")
        bits = "".join(self._codes[c] for c in raw)
        bits += "0" * (-len(bits) % 8)
        return len(raw).to_bytes(len_bytes, "big") + int(bits or "0", 2).to_bytes(
            len(bits) // 8, "big")

    def set_pooled(self, updates):
        """Point (row, field) -> text at new pool entries. The entries are appended
        to the pool (old ones stay, unreferenced), the pad/CRC move behind it and
        every later table shifts."""
        if not updates:
            return
        if not self.crc_variant:
            raise DBError(f"Can't edit '{self.name}': its checksum type is unknown")
        if self.db.skipped:
            raise DBError("Can't edit strings: some tables could not be parsed")
        d = self.db.data
        new = bytearray()
        offsets = {}
        for (row, field), text in updates.items():
            f = field if isinstance(field, Field) else self.by_name[field]
            if not f.pooled:
                raise DBError(f"'{f.name}' is not a pooled string")
            offsets[(row, f)] = self.pool_len + len(new)
            new += self._encode_pooled(text, POOLED_LEN_BYTES[f.type_code])
        pool_end = self.pool_start + self.pool_len
        new_end = pool_end + len(new)
        pad = -new_end % 4 or 4  # the CRC sits on a 4-byte boundary after 1-4 pad bytes
        region = bytes(new) + bytes(pad)
        delta = len(region) - (self.crc_pos - pool_end)
        d[pool_end:self.crc_pos] = region
        self.pool_len += len(new)
        self.crc_pos += delta
        struct.pack_into("<I", d, self.pos + 12, self.pool_len)
        struct.pack_into("<I", d, self.pos + 32, _crc_msb(bytes(d[self.pos:self.pos + 32])))
        for (row, f), off in offsets.items():
            self._set_bits(row, f.bitoffset, 32, off)
        if delta:
            self.db._shift_after(self.pos, delta)
            self.db.grown = True
        self.dirty = True
        self.db.dirty = True

    # -- typed access ------------------------------------------------------
    def get(self, row, field):
        f = field if isinstance(field, Field) else self.by_name[field]
        _, rec = self._rec(row)
        if f.pooled:
            off = self._get_bits(rec, f.bitoffset, 32)
            if off == 0xFFFFFFFF or off >= self.pool_len:
                return ""
            if off not in self._pool_cache:
                self._pool_cache[off] = self._read_pooled(off, POOLED_LEN_BYTES[f.type_code])
            return self._pool_cache[off]
        if f.type == TYPE_STRING:
            off = f.bitoffset // 8
            raw = bytes(rec[off:off + f.depth // 8])
            raw = raw.split(b"\x00", 1)[0]
            return raw.decode("utf-8", errors="replace")
        raw = self._get_bits(rec, f.bitoffset, f.depth)
        if f.type == TYPE_REAL:
            return struct.unpack("<f", struct.pack("<I", raw & 0xFFFFFFFF))[0]
        return raw + f.low

    def set(self, row, field, value):
        f = field if isinstance(field, Field) else self.by_name[field]
        if f.pooled:
            self.set_pooled({(row, f): value})
            return
        if f.type == TYPE_STRING:
            size = f.depth // 8
            enc = str(value).encode("utf-8")
            if len(enc) >= size:
                raise DBError(f"'{f.name}' can hold at most {size - 1} bytes")
            start, _ = self._rec(row)
            off = start + f.bitoffset // 8
            self.db.data[off:off + size] = enc + b"\x00" * (size - len(enc))
        elif f.type == TYPE_REAL:
            raw = struct.unpack("<I", struct.pack("<f", float(value)))[0]
            self._set_bits(row, f.bitoffset, f.depth, raw)
        else:
            value = int(value)
            if f.meta and not (f.low <= value <= f.high):
                raise DBError(f"'{f.name}' must be between {f.low} and {f.high}")
            if not 0 <= value - f.low < (1 << f.depth):
                raise DBError(f"'{f.name}' value {value} does not fit in {f.depth} bits")
            self._set_bits(row, f.bitoffset, f.depth, value - f.low)
        self.dirty = True
        self.db.dirty = True

    def record(self, row):
        return bytes(self._rec(row)[1])

    def append_row(self, copy_from=None, record=None):
        return self.insert_row(self.n_rows, copy_from, record)

    def sorted_pos(self, field, value):
        """Index where a row with `value` goes in a table sorted by `field`."""
        f = self.by_name[field]
        lo, hi = 0, self.n_rows
        while lo < hi:
            mid = (lo + hi) // 2
            if self.get(mid, f) <= value:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def insert_row(self, index, copy_from=None, record=None):
        """Insert a record at row `index` (a copy of row `copy_from`, the given
        `record` bytes, or all zero bits) and return `index`. The file grows by one
        record; rows from `index` on and all later tables are shifted."""
        if any(f.pooled for f in self.fields):
            raise DBError(f"Can't add rows to '{self.name}': it has a string pool")
        if not self.crc_variant:
            raise DBError(f"Can't add rows to '{self.name}': its checksum type is unknown")
        if self.db.skipped:
            raise DBError("Can't add rows: some tables could not be parsed (" +
                          ", ".join(self.db.skipped) + ")")
        d = self.db.data
        n_records = self.db._u16(self.pos + 16)
        if n_records != self.n_rows or self.crc_pos != self.records_start + self.records_len:
            raise DBError(f"Unexpected layout in '{self.name}'; not adding rows")
        if n_records >= 0xFFFF:
            raise DBError(f"'{self.name}' is full")
        if not 0 <= index <= self.n_rows:
            raise DBError(f"Row {index} is outside '{self.name}'")
        if record is None:
            record = self.record(copy_from) if copy_from is not None \
                else bytes(self.record_size)
        if len(record) != self.record_size:
            raise DBError(f"Record for '{self.name}' must be {self.record_size} bytes")
        at = self.records_start + index * self.record_size
        d[at:at] = record
        struct.pack_into("<HH", d, self.pos + 16, n_records + 1, n_records + 1)
        struct.pack_into("<I", d, self.pos + 32, _crc_msb(bytes(d[self.pos:self.pos + 32])))
        self.records_len += self.record_size
        self.crc_pos += self.record_size
        self.n_rows += 1
        self.db._shift_after(self.pos, self.record_size)
        self.dirty = True
        self.db.dirty = True
        self.db.grown = True
        return index

    def rows(self):
        return range(self.n_rows)

    def index_by(self, fieldname):
        f = self.by_name[fieldname]
        return {self.get(r, f): r for r in self.rows()}


class _NoMeta:
    """Stand-in for files without a meta XML (the data/loc/*.db language files)."""
    dbname = None
    tables = ()
    by_short = {}
    by_name = {}


class Database:
    def __init__(self, path, meta):
        self.path = path
        self.meta = meta or _NoMeta()
        with open(path, "rb") as fh:
            self.data = bytearray(fh.read())
        self.dirty = False
        self.grown = False  # rows were appended: file layout differs from disk
        self.warnings = []
        self.skipped = []
        self.tables = {}
        self.bit_order = "lsb"
        self._parse()

    # -- parsing -----------------------------------------------------------
    def _u32(self, pos):
        return struct.unpack_from("<I", self.data, pos)[0]

    def _u16(self, pos):
        return struct.unpack_from("<H", self.data, pos)[0]

    def _name(self, pos, known):
        raw = bytes(self.data[pos:pos + 4])
        for cand in (raw, raw[::-1]):
            try:
                s = cand.decode("ascii")
            except UnicodeDecodeError:
                continue
            if s in known:
                return s
        return raw.decode("latin-1")

    def _parse(self):
        base = self.data.find(SIGNATURE)
        if base < 0:
            raise DBError("This is not a FIFA database (no 'DB' signature found).")
        if base:
            self.warnings.append(
                f"Database starts at byte {base} (squad/career save). "
                "The game may refuse a save file whose outer checksum isn't updated; "
                "keep the backup.")
        self.base = base
        n_tables = self._u32(base + 16)
        if not 0 < n_tables < 2000:
            raise DBError(f"Implausible table count {n_tables}; unsupported file layout.")
        list_pos = base + 24
        data_start = list_pos + n_tables * 8 + 4
        self.n_tables, self.list_pos, self.data_start = n_tables, list_pos, data_start
        entries = []
        for i in range(n_tables):
            p = list_pos + i * 8
            short = self._name(p, self.meta.by_short)
            entries.append((short, data_start + self._u32(p + 4)))
        entries.sort(key=lambda e: e[1])
        db_size = self._u32(base + 8)
        db_end = base + db_size if base + db_size <= len(self.data) else len(self.data)
        for i, (short, pos) in enumerate(entries):
            end = entries[i + 1][1] if i + 1 < len(entries) else db_end
            try:
                t = self._parse_table(short, pos, end)
            except Exception as exc:  # keep going; one odd table shouldn't block the rest
                self.warnings.append(f"Skipped table {short}: {exc}")
                self.skipped.append(short)
                continue
            self.tables[t.name] = t
        self._detect_bit_order()

    def _parse_table(self, short, pos, end):
        meta = self.meta.by_short.get(short)
        t = Table(self, short, meta)
        t.pos = pos
        t.record_size = self._u32(pos + 4)
        n_records = self._u16(pos + 16)
        n_valid = self._u16(pos + 18)
        n_fields = self.data[pos + 24]
        known = meta.by_short if meta else {}

        # locate the field descriptors: first offset where every descriptor is sane
        layout = None
        for fstart in range(pos + 25, pos + 64):
            layout = self._try_fields(fstart, n_fields, t.record_size, known)
            if layout:
                break
        if not layout:
            raise DBError("could not locate field descriptors")
        fstart, fields = layout
        for (sn, tc, bo, dp) in fields:
            fmeta = known.get(sn)
            fobj = Field(sn, tc, bo, dp, fmeta)
            t.fields.append(fobj)
            t.by_name[fobj.name] = fobj
        t.fields.sort(key=lambda f: f.name)

        # locate records + their CRC; prefer a layout whose CRC verifies.
        # In real FIFA 17 files records follow the field descriptors directly and
        # one CRC (mpeg2) covers descriptors + records together. Tables with pooled
        # strings continue with the pool (length at header +12) and 1-6 pad bytes,
        # and the CRC sits in the last 4 bytes before the next table.
        fend = fstart + n_fields * 16
        candidates = []
        for rstart in (fend, fend + 4):
            for count in dict.fromkeys((n_records, n_valid)):
                rlen = count * t.record_size
                if rstart + rlen + 4 <= end + 4 and rstart + rlen <= len(self.data):
                    candidates.append((rstart, count, rlen))
        if not candidates:
            raise DBError("record block does not fit in file")
        chosen = None
        for rstart, count, rlen in candidates:
            if chosen or rstart + rlen + 4 > len(self.data):
                continue
            for crc_pos in dict.fromkeys((rstart + rlen, end - 4)):
                if crc_pos < rstart + rlen or crc_pos + 4 > len(self.data):
                    continue
                stored = self._u32(crc_pos)
                for cstart in (fstart, rstart):
                    variant = _detect_crc(bytes(self.data[cstart:crc_pos]), stored)
                    if variant:
                        chosen = (rstart, count, rlen, variant, cstart, crc_pos)
                        break
                if chosen:
                    break
        if chosen is None:
            rstart, count, rlen = candidates[0]
            chosen = (rstart, count, rlen, None, rstart, rstart + rlen)
        (t.records_start, t.n_rows, t.records_len, t.crc_variant, t.crc_start,
         t.crc_pos) = chosen
        # only expose valid (in-use) records
        t.n_rows = min(n_valid, t.n_rows) if n_valid else t.n_rows
        if any(f.pooled for f in t.fields):
            t.pool_start = t.records_start + t.records_len
            t.pool_len = self._u32(pos + 12)
            t._load_pool()
        return t

    def _try_fields(self, fstart, n_fields, record_size, known):
        """Try reading n_fields 16-byte descriptors at fstart; return them if sane."""
        if fstart + n_fields * 16 > len(self.data) or n_fields == 0:
            return None
        recbits = record_size * 8
        out = []
        unknown = 0
        for i in range(n_fields):
            p = fstart + i * 16
            # find the slot holding the 4-letter short name
            name_slot = None
            for s in range(4):
                raw = bytes(self.data[p + s * 4:p + s * 4 + 4])
                if all(65 <= c <= 90 or 97 <= c <= 122 for c in raw):
                    name_slot = s
                    break
            if name_slot is None:
                return None
            sn = self._name(p + name_slot * 4, known)
            if known and sn not in known:
                unknown += 1
            ints = [self._u32(p + s * 4) for s in range(4) if s != name_slot]
            # order in file is (type, bitoffset, name, depth) in FIFA 13-17,
            # but check against meta depth to be safe
            meta_depth = known[sn].depth if sn in known else None
            type_code, a, b = ints
            if meta_depth is not None and a == meta_depth and b != meta_depth:
                a, b = b, a
            bitoffset, depth = a, b
            # pooled strings occupy a 32-bit offset in the record; depth is max length
            used = 32 if type_code in POOLED_LEN_BYTES else depth
            if type_code > 64 or depth == 0 or bitoffset + used > recbits:
                return None
            out.append((sn, type_code, bitoffset, depth))
        if known and unknown * 5 > n_fields:
            return None
        return fstart, out

    def _detect_bit_order(self):
        """Pick the bit order under which integer values best respect meta ranges."""
        scores = {}
        for order in ("lsb", "msb"):
            self.bit_order = order
            bad = 0
            for name in ("players", "teams", "teamplayerlinks", "nations"):
                t = self.tables.get(name)
                if not t:
                    continue
                for r in range(min(t.n_rows, 300)):
                    for f in t.fields:
                        if f.meta and f.type == TYPE_INT and f.depth < 32:
                            v = t.get(r, f)
                            if not f.low <= v <= f.high:
                                bad += 1
            scores[order] = bad
        self.bit_order = min(scores, key=scores.get)
        if scores[self.bit_order]:
            self.warnings.append(
                f"{scores[self.bit_order]} values are outside their meta ranges; "
                "the meta XML may not match this database.")

    def _shift_after(self, pos, delta):
        """`delta` bytes were inserted inside the table whose header is at `pos`:
        move every later table and fix the table list, db size and their CRCs."""
        d, base = self.data, self.base
        for i in range(self.n_tables):
            p = self.list_pos + i * 8 + 4
            off = self._u32(p)
            if self.data_start + off > pos:
                struct.pack_into("<I", d, p, off + delta)
        list_end = self.list_pos + self.n_tables * 8
        struct.pack_into("<I", d, list_end, _crc_msb(bytes(d[self.list_pos:list_end])))
        struct.pack_into("<I", d, base + 8, self._u32(base + 8) + delta)
        struct.pack_into("<I", d, base + 20, _crc_msb(bytes(d[base:base + 20])))
        for t in self.tables.values():
            if t.pos > pos:
                t.pos += delta
                t.records_start += delta
                t.crc_start += delta
                t.crc_pos += delta
                if t.pool_start:
                    t.pool_start += delta
                t._pool_cache = {}

    # -- saving ------------------------------------------------------------
    def save(self, path=None, backup=True):
        path = path or self.path
        unknown = [t.name for t in self.tables.values() if t.dirty and not t.crc_variant]
        if unknown:
            raise DBError("Can't update checksums for tables: " + ", ".join(unknown) +
                          ". Saving would likely produce a file the game rejects.")
        for t in self.tables.values():
            if t.dirty:
                crc = CRC_VARIANTS[t.crc_variant](bytes(self.data[t.crc_start:t.crc_pos]))
                struct.pack_into("<I", self.data, t.crc_pos, crc)
        if backup:
            import os
            bak = path + ".bak"
            if os.path.exists(path) and not os.path.exists(bak):
                shutil.copy2(path, bak)
        with open(path, "wb") as fh:
            fh.write(self.data)
        for t in self.tables.values():
            t.dirty = False
        self.dirty = False
        self.path = path


TEAM_POS_SUB = 28  # teamplayerlinks.position for substitutes
TEAM_POS_RESERVE = 29
LEAGUE_REST_OF_WORLD = 76

# Every table keyed by team id that create_team adds rows to, with its id field.
# All but the last two are sorted by that id; new rows are inserted in order.
TEAM_KEYED = (("teams", "teamid"), ("teamstadiumlinks", "teamid"),
              ("default_teamsheets", "teamid"), ("defaultteamdata", "teamid"),
              ("manager", "teamid"), ("teamkits", "teamtechid"),
              ("formations", "teamid"),
              ("leagueteamlinks", "teamid"), ("teamplayerlinks", "teamid"))
TEAM_SORTED = TEAM_KEYED[:7]

# Team ids whose kit bundles exist in the FIFA 17 game data
# (content/character/kit/kit_<id//500*500>/<folder>_<id>/...) but which have no
# team (FUT/promo kits, unlicensed Chinese clubs). A new team created with one of
# these ids wears those kits, and their textures can be replaced in Frosty, which
# can't create new kit bundles. Ids used by the user's FIP17 V3 mod are left out.
# (id, folder, kit types: 0 home, 1 away, 2 goalkeeper)
KIT_SLOTS = (
    # ordinary club kits first; FUT/promo kits may only load in their own modes
    (110955, "greenland_shenhua", (0, 1, 2)), (111724, "taishan_dui", (0, 1, 2)),
    (111768, "beijing_guoan", (0, 1, 2)), (111839, "guangzhou", (0, 1, 2)),
    (112537, "guizhou_renhe", (0, 1, 2)), (7201, "fut_custom_team", (0, 1, 2)),
    (7200, "fut_custom_team", (0, 2)),
    *((i, f"power_style_{s}", (0, 2)) for i, s in zip(
        range(113261, 113283),
        ("a1", "a2", "a3", "a4", "a5", "a6", "access_ea", "access_origin", "b1", "b2",
         "c1", "c2", "c3", "c4", "e1", "e2", "e3", "e4", "i1", "i2", "i3", "i4"))),
    (113284, "power_style_j1", (0, 2)), (113285, "power_style_j2", (0, 2)),
    (113286, "power_style_j3", (0, 2)), (113287, "theme_style_chinese", (0, 2)),
    (113290, "theme_style_futties", (0, 2)), (113291, "theme_style_halloween", (0, 2)),
    (113292, "theme_style_lgbt", (0, 2)), (113293, "theme_style_movember", (0, 2)),
    (113294, "theme_style_stpatricks", (0, 2)), (113295, "theme_style_toty", (0, 2)),
    (113307, "coca_cola_custom", (0, 2)), (113313, "custom_adidas_1", (0, 2)),
    (113315, "art_of1_kygo", (0, 2)), (113316, "art_of2_zedd", (0, 2)),
    (113317, "art_of3_damian_marley", (0, 2)), (113318, "art_of4_major_lazer", (0, 2)),
    (113319, "art_of5_kasabian", (0, 2)), (113320, "unicorn", (0, 2)),
    (113321, "men_in_blazers", (0, 2)), (113335, "des_of16_angelo", (0, 2)),
    (113336, "des_of17_angelo", (0, 2)),
)
KIT_DIRS = {0: "home_0_0", 1: "away_1_0", 2: "goalie_home_2_0"}


def kit_folder(tid, folder):
    return f"content/character/kit/kit_{tid // 500 * 500}/{folder}_{tid}"


def free_kit_slots(db):
    """KIT_SLOTS entries not yet taken by a team in this database."""
    T = db.tables["teams"]
    taken = {T.get(r, "teamid") for r in T.rows()}
    return [s for s in KIT_SLOTS if s[0] not in taken]


SQUAD_COPY, SQUAD_SHARE, SQUAD_EMPTY = "copy", "share", "empty"


def name_index(db):
    """(nameid -> name, name -> first nameid) over playernames and dcplayernames;
    cached and kept up to date by name_id_for."""
    if not hasattr(db, "_name_index"):
        by_id, by_name = {}, {}
        for tname in ("playernames", "dcplayernames"):
            t = db.tables.get(tname)
            if t:
                for r in t.rows():
                    nid, name = t.get(r, "nameid"), t.get(r, "name")
                    by_id[nid] = name
                    by_name.setdefault(name, nid)
        db._name_index = (by_id, by_name)
    return db._name_index


def name_id_for(db, text):
    """Name id for `text`: an existing playernames/dcplayernames entry, or a new
    dcplayernames row (ids 30000+, inline text). This is how FIP17 adds names;
    players' firstnameid/lastnameid/... point straight at these ids."""
    if not text:
        return 0
    by_id, by_name = name_index(db)
    if text in by_name:
        return by_name[text]
    dc = db.tables.get("dcplayernames")
    if dc is None:
        raise DBError("This database has no dcplayernames table for new names")
    idf = dc.by_name["nameid"]
    nid = max([dc.get(r, idf) for r in dc.rows()] + [idf.low - 1]) + 1
    if nid > idf.high:
        raise DBError("No free name ids left in dcplayernames")
    size = dc.by_name["name"].depth // 8 - 1
    if len(text.encode("utf-8")) > size:
        raise DBError(f"Name '{text}' is longer than {size} bytes")
    r = dc.append_row()
    dc.set(r, "nameid", nid)
    dc.set(r, "name", text)
    by_id[nid] = text
    by_name[text] = nid
    return nid


def generic_heads(db):
    """headtypecodes used by generic-head players (headclasscode 1); cached."""
    if not hasattr(db, "_generic_heads"):
        P = db.tables["players"]
        db._generic_heads = {P.get(r, "headtypecode") for r in P.rows()
                             if P.get(r, "headclasscode") == 1}
    return db._generic_heads


def rows_where(table, field, value):
    f = table.by_name[field]
    return [r for r in table.rows() if table.get(r, f) == value]


def _is_player_ref(name):
    return name.endswith(("takerid", "captainid")) or (
        name.startswith("playerid") and name[8:].isdigit())


def create_team(db, template_tid, name, league_id=LEAGUE_REST_OF_WORLD, squad=SQUAD_COPY,
                team_id=None, asset_id=None):
    """Add a team cloned from `template_tid`: one row (or several, for kits and
    formations) in every TEAM_KEYED table.

    `asset_id` picks the menu crest (data/ui/imgAssets/crest*/l<assetid>.dds).
    None means: the slot's own crest set for a KIT_SLOTS id (replaceable in
    Frosty), otherwise the template's crest. crests.SPARE_CRESTS lists real
    clubs' crests that ship with the game.

    `team_id`: None picks a fresh id (no kit textures exist for it in the game);
    a KIT_SLOTS id makes the team wear that slot's existing kits, keeping the
    slot's teamkits rows instead of copying the template's.

    `squad`: SQUAD_COPY clones every template player (new ids, generic faces, same
    names); SQUAD_SHARE links the template's own players to the new team as well
    (real faces, but they stay at their club too); SQUAD_EMPTY adds nobody. The
    lineup/captain/takers follow the squad.
    Returns (new team id, {template playerid: playerid in the new team})."""
    T = db.tables["teams"]
    missing = [t for t, _ in TEAM_KEYED if t not in db.tables]
    if missing:
        raise DBError("Missing tables: " + ", ".join(missing))
    trows = rows_where(T, "teamid", template_tid)
    if not trows:
        raise DBError(f"No team with id {template_tid}")
    if team_id is None:
        new_tid = max(max((db.tables[t].get(r, f) for r in db.tables[t].rows()), default=0)
                      for t, f in TEAM_KEYED) + 1
    else:
        new_tid = team_id
        busy = [t for t, f in TEAM_KEYED if t != "teamkits"
                and rows_where(db.tables[t], f, new_tid)]
        if busy:
            raise DBError(f"Team id {new_tid} is already used in: " + ", ".join(busy))
    if not T.by_name["teamid"].low <= new_tid <= T.by_name["teamid"].high:
        raise DBError("No free team ids left")

    def clone(tname, record, **values):
        """Insert `record` with `values` set, at its sorted place by team id."""
        t = db.tables[tname]
        f = dict(TEAM_SORTED).get(tname)
        r = t.insert_row(t.sorted_pos(f, new_tid) if f else t.n_rows, record=record)
        for field, v in values.items():
            t.set(r, field, v)
        return r

    def records(tname, field="teamid"):
        """Template rows as bytes: inserting rows moves row indices."""
        t = db.tables[tname]
        return [t.record(r) for r in rows_where(t, field, template_tid)]

    def next_key(tname, field):
        t = db.tables[tname]
        return max((t.get(r, field) for r in t.rows()), default=-1) + 1

    # squad first, so the lineup and takers can be remapped
    pid_map = {}
    links = db.tables["teamplayerlinks"]
    P = db.tables["players"]
    pid_row = {P.get(r, "playerid"): r for r in P.rows()}
    template_links = [(links.get(lr, "playerid"), links.get(lr, "jerseynumber"),
                       links.get(lr, "position"))
                      for lr in rows_where(links, "teamid", template_tid)]
    if squad == SQUAD_COPY:
        by_id = name_index(db)[0]
        for old, jersey, position in template_links:
            if old not in pid_row:
                continue
            pr = pid_row[old]

            def nm(field):
                return by_id.get(P.get(pr, field), "")
            first, last = nm("firstnameid"), nm("lastnameid")
            pid_map[old] = create_player(
                db, pr, new_tid, jersey, first or "Player", last or str(old),
                nm("commonnameid"), nm("playerjerseynameid"), position)
    elif squad == SQUAD_SHARE:
        key = next_key("teamplayerlinks", "artificialkey")
        for old, jersey, position in template_links:
            if old not in pid_row:
                continue
            lr = links.append_row()
            for field, value in (("artificialkey", key), ("teamid", new_tid),
                                 ("playerid", old), ("jerseynumber", jersey),
                                 ("position", position), ("form", 3), ("prevform", 3)):
                links.set(lr, field, value)
            key += 1
            pid_map[old] = old

    def remap(t, r):
        for f in t.fields:
            if _is_player_ref(f.name):
                v = t.get(r, f)
                if v in pid_map:
                    t.set(r, f, pid_map[v])
                elif v != -1:
                    t.set(r, f, f.low)  # -1 in teamsheets ("nobody"); 1 in teams

    if asset_id is None and any(s[0] == new_tid for s in KIT_SLOTS):
        asset_id = new_tid
    r = clone("teams", T.record(trows[0]), teamid=new_tid, teamname=name)
    if asset_id is not None:
        T.set(r, "assetid", asset_id)
    remap(T, r)
    for tname in ("teamstadiumlinks", "defaultteamdata", "manager"):
        for rec in records(tname):
            clone(tname, rec, teamid=new_tid)
    for rec in records("default_teamsheets"):
        r = clone("default_teamsheets", rec, teamid=new_tid)
        remap(db.tables["default_teamsheets"], r)
    # formations are sorted by team id *and* numbered 1..n in row order (nothing
    # refers to formationid), so renumber everything after the inserted row
    F = db.tables["formations"]
    for rec in records("formations"):
        r = clone("formations", rec, teamid=new_tid)
        for row in range(F.n_rows):
            F.set(row, "formationid", row + 1)
    K = db.tables["teamkits"]
    if not rows_where(K, "teamtechid", new_tid):  # a kit slot keeps its own kit rows
        for rec in records("teamkits", "teamtechid"):
            clone("teamkits", rec, teamtechid=new_tid,
                  teamkitid=next_key("teamkits", "teamkitid"))

    # league entry: copy a team already in the target league so the per-league
    # values (grouping, objectives) fit, then clear its match statistics
    L = db.tables["leagueteamlinks"]
    src = rows_where(L, "leagueid", league_id) or rows_where(L, "teamid", template_tid)
    if not src:
        raise DBError(f"No league entry to copy for league {league_id}")
    r = clone("leagueteamlinks", L.record(src[0]), teamid=new_tid, leagueid=league_id,
              prevleagueid=league_id, artificialkey=next_key("leagueteamlinks",
                                                             "artificialkey"))
    for f in L.fields:
        if f.name.startswith(("home", "away")) or f.name in (
                "points", "nummatchesplayed", "champion", "unbeatenallcomps",
                "unbeatenaway", "unbeatenhome", "unbeatenleague", "yettowin"):
            L.set(r, f, f.low)
    return new_tid, pid_map


def create_player(db, template_row, team_id, jersey, first, last, common="",
                  jersey_name="", team_position=TEAM_POS_RESERVE):
    """Add a new player cloned from players row `template_row` and link it to
    `team_id`. Name fields point at playernames entries when the exact name
    exists there (so commentary may say it), else at new dcplayernames rows.
    Returns the new playerid."""
    P = db.tables["players"]
    links = db.tables["teamplayerlinks"]
    pid_f = P.by_name["playerid"]
    new_id = P.get(P.n_rows - 1, pid_f) + 1  # rows are sorted by id
    if new_id > pid_f.high:
        raise DBError("No free player ids left")
    real_face = P.get(template_row, "headclasscode") == 0
    ids = {field: name_id_for(db, text) for field, text in (
        ("firstnameid", first), ("lastnameid", last), ("commonnameid", common),
        ("playerjerseynameid", jersey_name or last))}

    r = P.append_row(template_row)
    P.set(r, "playerid", new_id)
    for field, nid in ids.items():
        P.set(r, field, nid)
    # Scanned faces are bundles named after the playerid ("..._<id>_starhead_brt"),
    # so a new id can only have a generic head. Scanned-face players nearly always
    # carry a matching generic headtypecode too; keep it when it is a real one.
    P.set(r, "headclasscode", 1)
    P.set(r, "hashighqualityhead", 0)
    if real_face and P.get(r, "headtypecode") not in generic_heads(db):
        P.set(r, "headtypecode", 2004)  # most common generic head
    P.set(r, "usercaneditname", 1)

    key = max((links.get(x, "artificialkey") for x in links.rows()), default=-1) + 1
    lr = links.append_row()
    for field, value in (("artificialkey", key), ("teamid", team_id), ("playerid", new_id),
                         ("jerseynumber", jersey), ("position", team_position),
                         ("form", 3), ("prevform", 3)):
        links.set(lr, field, value)
    return new_id


CREATE_PLAYER_SLOTS = 62  # createplayer.create_artificialkey is 0..61


def created_player_row(db, pid):
    """The createplayer row registering `pid` as an in-game Create Player player."""
    t = db.tables.get("createplayer")
    if t is None:
        return None
    return next((r for r in t.rows() if t.get(r, "create_playerid") == pid), None)


def register_created_player(db, pid):
    """Add a createplayer row for `pid`, the table the game's own Create Player uses
    (face sliders, celebration, ...). Meant to make the player customisable in-game;
    UNVERIFIED in-game. Sliders/styles start at 0; their indices don't match the
    players-table look codes, so nothing is copied. Returns the row."""
    t = db.tables.get("createplayer")
    if t is None:
        raise DBError("This database has no createplayer table")
    r = created_player_row(db, pid)
    if r is not None:
        return r
    used = {t.get(x, "create_artificialkey") for x in t.rows()}
    key = next((k for k in range(CREATE_PLAYER_SLOTS) if k not in used), None)
    if key is None:
        raise DBError(f"All {CREATE_PLAYER_SLOTS} Create Player slots are in use")
    P = db.tables["players"]
    pr = next(x for x in P.rows() if P.get(x, "playerid") == pid)
    r = t.append_row()
    for field, value in (("create_artificialkey", key), ("create_playerid", pid),
                         ("create_originalplayerid", pid), ("commentaryid", -1),
                         ("personaid", -1), ("skincolor", -1)):
        t.set(r, field, value)
    P.set(pr, "usercaneditname", 1)
    return r


class LocFile:
    """A data/loc/<language>.db file: one table of (key, text, hash) where key and
    text are Huffman-coded pool strings (text with a 2-byte length). Only texts of
    existing keys are changed; adding keys would need EA's hash, which is unknown
    (a missing key makes the game fall back to the database name)."""

    TEAM_KEYS = ("TeamName_{}", "TeamName_Abbr15_{}", "TeamName_Abbr10_{}",
                 "TeamName_Abbr3_{}", "CT_TeamName_{}")

    def __init__(self, path):
        self.db = Database(path, None)
        if len(self.db.tables) != 1:
            raise DBError(f"{os.path.basename(path)} is not a FIFA language file")
        self.table = t = next(iter(self.db.tables.values()))
        by_type = {f.type_code: f for f in t.fields}
        if FILE_TYPE_POOLED_STRING not in by_type or FILE_TYPE_POOLED_LONG not in by_type:
            raise DBError(f"{os.path.basename(path)} is not a FIFA language file")
        self.key_f = by_type[FILE_TYPE_POOLED_STRING]
        self.text_f = by_type[FILE_TYPE_POOLED_LONG]
        self.rows = {t.get(r, self.key_f): r for r in t.rows()}
        self.pending = {}

    @property
    def path(self):
        return self.db.path

    @property
    def language(self):
        return os.path.splitext(os.path.basename(self.path))[0].lower()

    @property
    def dirty(self):
        return bool(self.pending) or self.db.dirty

    def get(self, key):
        if key in self.pending:
            return self.pending[key]
        r = self.rows.get(key)
        return None if r is None else self.table.get(r, self.text_f)

    def set(self, key, text):
        """Change an existing key's text; returns False when the key doesn't exist."""
        if key not in self.rows:
            return False
        self.table._encode_pooled(text, 2)  # fail now on characters the tree lacks
        self.pending[key] = text
        return True

    def team_names(self, tid):
        return {k.format(tid): self.get(k.format(tid)) for k in self.TEAM_KEYS
                if k.format(tid) in self.rows}

    def save(self, path=None):
        if self.pending:
            self.table.set_pooled({(self.rows[k], self.text_f): v
                                   for k, v in self.pending.items()})
            self.pending = {}
        self.db.save(path)


def short_names(name):
    """Default (abbr15, abbr10, abbr3) for a team name."""
    words = name.split()

    def fit(limit):  # whole words while they fit, else a cut first word
        out = ""
        for w in words:
            if len(out) + bool(out) + len(w) > limit:
                break
            out = f"{out} {w}" if out else w
        return out or name[:limit].strip()
    alpha = [w for w in name.replace("-", " ").split() if w[:1].isalpha()]
    abbr3 = "".join(w[0] for w in alpha)[:3] if len(alpha) >= 3 else \
        "".join(c for c in (alpha[0] if alpha else name) if c.isalnum())[:3]
    return fit(15), fit(10), abbr3.upper()


def date_to_days(d):
    return (d - FIFA_EPOCH).days


def days_to_date(n):
    return FIFA_EPOCH + datetime.timedelta(days=int(n))
