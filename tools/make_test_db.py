"""Build a synthetic FIFA-style t3db file from the meta XML for testing.

Usage: python3 make_test_db.py META.XML OUT.db [lsb|msb]
Contains 4 players (Messi, Ronaldo, Müller, ...), 3 teams, 3 nations; other values random.
"""
import random, struct, sys, zlib, datetime
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import fifadb
meta = fifadb.Meta(sys.argv[1]); out = sys.argv[2]; order = sys.argv[3] if len(sys.argv) > 3 else 'lsb'
random.seed(1)
names = ['Lionel','Messi','Cristiano','Ronaldo','Thomas','Müller','Neymar','Sergio','Ramos','Manuel','Neuer','Paul','Pogba']
data = {
 'players': [], 'playernames': [], 'teams': [], 'teamplayerlinks': [], 'nations': [],
}
for i,n in enumerate(names): data['playernames'].append({'nameid': i+1, 'name': n, 'commentaryid': 900000})
data['nations'] += [{'nationid':52,'nationname':'Argentina'},{'nationid':38,'nationname':'Portugal'},{'nationid':21,'nationname':'Germany'}]
data['teams'] += [{'teamid':241,'teamname':'FC Barcelona'},{'teamid':243,'teamname':'Real Madrid'},{'teamid':21,'teamname':'FC Bayern München'}]
plist = [(158023,1,2,52,241,93,'1987-06-24'),(20801,3,4,38,243,94,'1985-02-05'),(189596,5,6,21,21,86,'1989-09-13'),(190871,0,8,52,241,92,'1992-02-05')]
for pid,fn,ln,nat,team,ovr,bd in plist:
    p = {'playerid':pid,'firstnameid':fn,'lastnameid':ln,'commonnameid':0,'nationality':nat,'overallrating':ovr,
         'birthdate': fifadb.date_to_days(datetime.date.fromisoformat(bd))}
    data['players'].append(p)
    data['teamplayerlinks'].append({'artificialkey':pid%1000,'playerid':pid,'teamid':team,'jerseynumber':10,'position':25})
crc = lambda d: fifadb.CRC_VARIANTS['mpeg2'](d)
def build_table(mt, rows):
    fields = []
    bit = 0
    for f in mt.fields:
        if f.type == fifadb.TYPE_STRING:
            bit = (bit + 7)//8*8
        fields.append((f, bit)); bit += f.depth
    rs = (bit + 31)//32*4
    recs = bytearray()
    for row in rows:
        n = 0; rec = bytearray(rs)
        for f,bo in fields:
            if f.type == fifadb.TYPE_STRING:
                s = row.get(f.name,'').encode(); rec[bo//8:bo//8+len(s)] = s; continue
            if f.name in row: v = row[f.name]
            else: v = random.randint(max(f.low,40) if f.high==99 else f.low, f.high) if f.type!=fifadb.TYPE_REAL else 0
            raw = (struct.unpack('<I',struct.pack('<f',float(v)))[0] if f.type==fifadb.TYPE_REAL else v - f.low) & ((1<<f.depth)-1)
            if order=='lsb': n |= raw << bo
            else: n |= raw << (rs*8 - bo - f.depth)
        nb = n.to_bytes(rs, 'little' if order=='lsb' else 'big')
        rec = bytearray(a|b for a,b in zip(rec, nb))
        recs += rec
    # layout verified against a real FIFA 17 save: 32-byte header + CRC, then field
    # descriptors immediately followed by records, one mpeg2 CRC over both
    crc = lambda d: fifadb.CRC_VARIANTS['mpeg2'](d)
    hdr = struct.pack('<IIIIHHIB', 3, rs, bit, 0, len(rows), len(rows), 0xFFFF0000, len(fields)) + b'\0'*7
    hdr += struct.pack('<I', crc(hdr))
    fd = b''.join(struct.pack('<I',{'int':3,'real':4,'string':0,'date':3}[f.type]) + struct.pack('<I',bo) + f.shortname.encode()[::-1] + struct.pack('<I',f.depth) for f,bo in fields)
    return hdr + fd + bytes(recs) + struct.pack('<I', crc(fd + bytes(recs)))
blobs = [(meta.by_name[n].shortname, build_table(meta.by_name[n], rows)) for n,rows in data.items()]
body = b''; offs = []
for sn,b in blobs: offs.append((sn,len(body))); body += b
tl = b''.join(sn.encode()[::-1] + struct.pack('<I',o) for sn,o in offs)
head = b'DB\x00\x08\x00\x00\x00\x00' + struct.pack('<III', 0, 0, len(blobs))
full_len = len(head) + 4 + len(tl) + 4 + len(body)
head = head[:8] + struct.pack('<I', full_len) + head[12:]
head += struct.pack('<I', crc(head))
full = head + tl + struct.pack('<I', crc(tl)) + body
open(out,'wb').write(full); print('wrote', len(full))
