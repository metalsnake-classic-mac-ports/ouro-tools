"""Decode a colour pixel pattern ('ppat' resource) to PNG.

A ppat starts with a PixPat record: patType (1 = full colour), offsets of
its PixMap and pixel data, and an 8x8 1-bit fallback pattern (pat1Data,
for 1-bit screens). The PixMap (rowBytes with the 0x8000 flag, bounds,
pixelSize 1/2/4/8, pmTable = offset of the colour table in the resource)
describes one tile; the pixel data is not packed. patType 0 is a plain
8x8 1-bit pattern (black on white).

decode(data) -> (width, height, rgb rows as bytes, info dict)

Usage: python3 ppat.py <ppat.bin> <out.png> [tiles_x tiles_y]
       (with tiles: the tile repeated, to look at how it joins)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topng import write_png  # noqa: E402


def decode(d):
    pat_type, pmap, pdata = struct.unpack(">HII", d[:10])
    pat1 = d[0x14:0x1C]
    if pat_type == 0:
        rows = [b"".join(bytes((0, 0, 0) if (b >> (7 - x)) & 1 else (255, 255, 255))
                         for x in range(8)) for b in pat1]
        return 8, 8, rows, {"type": 0, "depth": 1}
    if pat_type != 1:
        raise ValueError("patType %d not supported" % pat_type)
    row_bytes = struct.unpack(">H", d[pmap + 4:pmap + 6])[0] & 0x3FFF
    top, left, bottom, right = struct.unpack(">hhhh", d[pmap + 6:pmap + 14])
    depth = struct.unpack(">H", d[pmap + 32:pmap + 34])[0]
    ct = struct.unpack(">I", d[pmap + 42:pmap + 46])[0]
    _, flags, size = struct.unpack(">IHH", d[ct:ct + 8])
    pal = [(0, 0, 0)] * 256
    for k in range(size + 1):
        value, r, g, b = struct.unpack(">HHHH", d[ct + 8 + k * 8:ct + 16 + k * 8])
        pal[k if flags & 0x8000 else value & 0xFF] = (r >> 8, g >> 8, b >> 8)
    w, h = right - left, bottom - top
    rows = []
    for y in range(h):
        line = d[pdata + y * row_bytes:pdata + (y + 1) * row_bytes]
        px = []
        for x in range(w):
            bit = x * depth
            v = (line[bit >> 3] >> (8 - depth - (bit & 7))) & ((1 << depth) - 1)
            px.append(bytes(pal[v]))
        rows.append(b"".join(px))
    info = {"type": 1, "depth": depth, "colors": size + 1,
            "pat1": pat1.hex(), "palette": pal[:size + 1]}
    return w, h, rows, info


if __name__ == "__main__":
    w, h, rows, info = decode(open(sys.argv[1], "rb").read())
    if len(sys.argv) >= 5:
        tx, ty = int(sys.argv[3]), int(sys.argv[4])
        rows = [r * tx for _ in range(ty) for r in rows]
        w, h = w * tx, h * ty
    write_png(sys.argv[2], w, h, rows)
    print(w, h, "depth", info["depth"], "colors", info.get("colors"))
