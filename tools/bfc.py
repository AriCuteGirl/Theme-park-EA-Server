#!/usr/bin/env python3
"""Read Theme Park's resource archive (head_*.bfc index + N.bfc data files).

usage: bfc.py <dir with extracted OBB> list
       bfc.py <dir> ints <resource id>      # dump a resource as big-endian int32s
       bfc.py <dir> raw <resource id> <out>

Index (head_large.bfc): u16 count, then per entry: i32 id, i8 flags, u24 offset,
u8 data file number (N.bfc), u32 size. Data is stored uncompressed.
"""
import os
import struct
import sys


def read_index(root, head="head_large.bfc"):
    with open(os.path.join(root, head), "rb") as f:
        data = f.read()
    (count,) = struct.unpack_from(">H", data, 0)
    entries = {}
    pos = 2
    for _ in range(count):
        rid, flags = struct.unpack_from(">ib", data, pos)
        off = int.from_bytes(data[pos + 5:pos + 8], "big")
        fileno = data[pos + 8]
        (size,) = struct.unpack_from(">I", data, pos + 9)
        entries[rid] = (flags, fileno, off, size)
        pos += 13
    return entries


def read_resource(root, entries, rid):
    flags, fileno, off, size = entries[rid]
    with open(os.path.join(root, "%d.bfc" % fileno), "rb") as f:
        f.seek(off)
        return f.read(size)


def ints(blob):
    return list(struct.unpack(">%di" % (len(blob) // 4), blob[:len(blob) // 4 * 4]))


def main():
    root, cmd = sys.argv[1], sys.argv[2]
    entries = read_index(root)
    if cmd == "list":
        for rid, (flags, fileno, off, size) in sorted(entries.items(), key=lambda e: (e[1][1], e[1][2])):
            print(rid, flags, fileno, off, size)
    elif cmd == "ints":
        print(ints(read_resource(root, entries, int(sys.argv[3]))))
    elif cmd == "raw":
        with open(sys.argv[4], "wb") as f:
            f.write(read_resource(root, entries, int(sys.argv[3])))


if __name__ == "__main__":
    main()
