"""Disk Copy 6 image (NDIF: 'rohd' / 'hdro' images of the Legacy Recovery
CD and Apple's downloads) -> raw disk image, as hfsutils, Basilisk II and
MAME read them. macOS's hdiutil no longer reads NDIF.

The data fork holds the chunks; resource 'bcem' 128 lists them:
  0x00 version (word), 0x04 name (Pascal string), 0x44 sector count,
  0x7c chunk count, from 0x80 entries of 12 bytes: start sector (3 bytes),
  type (1), offset in the data fork (4), length (4).
Types: 0x00 zeros, 0x02 raw, 0x83 ADC (Apple Data Compression), 0xff end.
The end of a chunk is the start of the next.

Usage: python3 -I ndif.py <image.bin (MacBinary)> <out.dsk>
       python3 -I ndif.py <data fork> <resource fork> <out.dsk>
"""
import struct
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from macres import parse  # noqa: E402

SECTOR = 512


def adc(src):
    """Apple Data Compression: literals and back references."""
    out = bytearray()
    i = 0
    while i < len(src):
        b = src[i]
        if b & 0x80:  # literal run
            n = (b & 0x7F) + 1
            out += src[i + 1:i + 1 + n]
            i += 1 + n
            continue
        if b & 0x40:  # three-byte code
            n = (b & 0x3F) + 4
            dist = (src[i + 1] << 8 | src[i + 2]) + 1
            i += 3
        else:  # two-byte code
            n = ((b >> 2) & 0x0F) + 3
            dist = ((b & 0x03) << 8 | src[i + 1]) + 1
            i += 2
        for _ in range(n):  # may overlap
            out.append(out[-dist])
    return bytes(out)


def macbinary(path):
    b = open(path, "rb").read()
    if b[0] != 0 or b[74] != 0 or not 1 <= b[1] <= 63:
        sys.exit(f"{path}: not MacBinary")
    dlen, rlen = struct.unpack(">II", b[83:91])
    data = b[128:128 + dlen]
    roff = 128 + (dlen + 127) // 128 * 128
    return data, b[roff:roff + rlen]


def convert(data, rsrc):
    bcem = [d for t, i, _, d in parse(rsrc) if t == "bcem"]
    if not bcem:
        sys.exit("no 'bcem' resource: not an NDIF image")
    h = bcem[0]
    sectors = struct.unpack(">I", h[0x44:0x48])[0]
    count = struct.unpack(">I", h[0x7C:0x80])[0]
    chunks = []
    for k in range(count):
        e = h[0x80 + 12 * k:0x8C + 12 * k]
        start = e[0] << 16 | e[1] << 8 | e[2]
        kind = e[3]
        off, length = struct.unpack(">II", e[4:12])
        chunks.append((start, kind, off, length))
    out = bytearray(sectors * SECTOR)
    for (start, kind, off, length), nxt in zip(chunks, chunks[1:] + [(sectors, 0xFF, 0, 0)]):
        if kind == 0xFF:
            break
        size = (nxt[0] - start) * SECTOR
        if kind == 0x00:
            block = bytes(size)
        elif kind == 0x02:
            block = data[off:off + length]
        elif kind == 0x83:
            block = adc(data[off:off + length])
        else:
            sys.exit(f"chunk type {kind:#x} at sector {start} not supported")
        if len(block) != size:
            sys.exit(f"chunk at sector {start}: {len(block)} bytes, expected {size}")
        out[start * SECTOR:start * SECTOR + size] = block
    return bytes(out)


def main():
    if len(sys.argv) == 3:
        data, rsrc = macbinary(sys.argv[1])
    elif len(sys.argv) == 4:
        data, rsrc = open(sys.argv[1], "rb").read(), open(sys.argv[2], "rb").read()
    else:
        sys.exit(__doc__)
    raw = convert(data, rsrc)
    open(sys.argv[-1], "wb").write(raw)
    print(f"{sys.argv[-1]}: {len(raw)} bytes")


if __name__ == "__main__":
    main()
