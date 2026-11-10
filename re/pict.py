"""Decode a Mac PICT (version 1 or 2) resource to PNG.

render(p) walks the picture's opcodes (walk(p)) and draws every bitmap
opcode - BitsRect/BitsRgn/PackBitsRect/PackBitsRgn (0x90, 0x91, 0x98,
0x99) with a 1-bit BitMap or an indexed PixMap of 1, 2, 4 or 8 bits and
its color table - into the picture frame (white first). Regions (the
opcodes' mask region and Clip) are applied pixel by pixel; transfer modes
srcCopy, srcOr, srcXor, srcBic and transparent are drawn, any other mode
as srcCopy (listed in the result's notes). DirectBits (0x9A/0x9B), text,
lines and shapes are not drawn (listed in the notes).

decode(p) is the older single 8-bit pixmap reader (returns indices and
palette); it stays for scripts that use it.

Usage: python3 pict.py <PICT.bin> <out.png>        (prints size and notes)
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topng import write_png


def unpack_bits(src, length):
    out = bytearray()
    i = 0
    while len(out) < length:
        n = src[i]
        i += 1
        if n < 128:
            out += src[i:i + n + 1]
            i += n + 1
        elif n > 128:
            out += bytes([src[i]]) * (257 - n)
            i += 1
    return bytes(out[:length]), i


def decode(p):
    for m in re.finditer(rb"\x00[\x98-\x9b]", p):
        op = m.start()
        pm = op + 2 + (4 if p[op + 1] in (0x9A, 0x9B) else 0)
        row_bytes = struct.unpack(">H", p[pm:pm + 2])[0]
        if not row_bytes & 0x8000 or pm + 54 > len(p):
            continue
        pixel_size = struct.unpack(">H", p[pm + 28:pm + 30])[0]
        ct = pm + 46
        _, flags, size = struct.unpack(">IHH", p[ct:ct + 8])
        if pixel_size != 8 or size > 255:
            continue
        break
    else:
        raise ValueError("no 8-bit pixmap found")
    row_bytes &= 0x3FFF
    top, left, bottom, right = struct.unpack(">hhhh", p[pm + 2:pm + 10])
    width, height = right - left, bottom - top
    palette = [(0, 0, 0)] * 256
    for k in range(size + 1):
        value, r, g, b = struct.unpack(">HHHH", p[ct + 8 + k * 8:ct + 16 + k * 8])
        palette[k if flags & 0x8000 else value] = (r >> 8, g >> 8, b >> 8)
    pos = ct + 8 + (size + 1) * 8 + 8 + 8 + 2  # srcRect, dstRect, mode
    if p[op + 1] in (0x99, 0x9B):
        pos += struct.unpack(">H", p[pos:pos + 2])[0]  # mask region
    rows = []
    for _ in range(height):
        if row_bytes > 250:
            count = struct.unpack(">H", p[pos:pos + 2])[0]
            pos += 2
        else:
            count = p[pos]
            pos += 1
        line, _ = unpack_bits(p[pos:pos + count], row_bytes)
        pos += count
        rows.append(line[:width])
    return width, height, rows, palette


# --- opcode walker -------------------------------------------------------

def _rect(p, o):
    return struct.unpack(">hhhh", p[o:o + 8])  # top, left, bottom, right


def region_mask(p, o):
    """A QuickDraw region at offset o -> (bbox, set of (x, y)) or (bbox, None)
    for a rectangular region. Returns also the region's byte size."""
    size = struct.unpack(">H", p[o:o + 2])[0]
    bbox = _rect(p, o + 2)
    if size <= 10:
        return bbox, None, size
    inside = set()
    xs = set()           # inversion points active on the current line
    q = o + 10
    end = o + size
    prev_y = None
    while q + 2 <= end:
        y = struct.unpack(">h", p[q:q + 2])[0]
        q += 2
        if y == 0x7FFF:
            break
        # fill lines from prev_y up to y with the current state
        if prev_y is not None:
            on = sorted(xs)
            for yy in range(prev_y, y):
                for a, b in zip(on[0::2], on[1::2]):
                    for x in range(a, b):
                        inside.add((x, yy))
        while True:
            x = struct.unpack(">h", p[q:q + 2])[0]
            q += 2
            if x == 0x7FFF:
                break
            xs ^= {x}
        prev_y = y
    return bbox, inside, size


def _bits_op(p, o, op, v2):
    """Parse a bitmap opcode's data at o. Returns (record, new offset)."""
    rb = struct.unpack(">H", p[o:o + 2])[0]
    rec = {"op": op}
    if rb & 0x8000:
        pm = o
        rec["rowbytes"] = rb & 0x3FFF
        rec["bounds"] = _rect(p, pm + 2)
        rec["packtype"] = struct.unpack(">H", p[pm + 12:pm + 14])[0]
        rec["depth"] = struct.unpack(">H", p[pm + 28:pm + 30])[0]
        ct = pm + 46
        _, flags, size = struct.unpack(">IHH", p[ct:ct + 8])
        pal = [(0, 0, 0)] * (1 << rec["depth"])
        for k in range(size + 1):
            value, r, g, b = struct.unpack(">HHHH", p[ct + 8 + k * 8:ct + 16 + k * 8])
            idx = k if flags & 0x8000 else value
            if idx < len(pal):
                pal[idx] = (r >> 8, g >> 8, b >> 8)
        rec["palette"] = pal
        o = ct + 8 + (size + 1) * 8
    else:
        rec["rowbytes"] = rb
        rec["bounds"] = _rect(p, o + 2)
        rec["packtype"] = 0
        rec["depth"] = 1
        rec["palette"] = [(255, 255, 255), (0, 0, 0)]
        o += 10
    rec["src"] = _rect(p, o)
    rec["dst"] = _rect(p, o + 8)
    rec["mode"] = struct.unpack(">H", p[o + 16:o + 18])[0]
    o += 18
    rec["mask"] = None
    if op in (0x91, 0x99):
        bbox, inside, size = region_mask(p, o)
        rec["mask"] = (bbox, inside)
        o += size
    top, left, bottom, right = rec["bounds"]
    height = bottom - top
    rowbytes = rec["rowbytes"]
    rows = []
    packed = op in (0x98, 0x99) and rowbytes >= 8 and rec["packtype"] != 1
    for _ in range(height):
        if packed:
            if rowbytes > 250:
                count = struct.unpack(">H", p[o:o + 2])[0]
                o += 2
            else:
                count = p[o]
                o += 1
            line, _ = unpack_bits(p[o:o + count], rowbytes)
            o += count
        else:
            line = p[o:o + rowbytes]
            o += rowbytes
        rows.append(line)
    rec["rows"] = rows
    return rec, o


def _pixel(rec, row, x):
    d = rec["depth"]
    bit = x * d
    byte = row[bit >> 3]
    shift = 8 - d - (bit & 7)
    return (byte >> shift) & ((1 << d) - 1)


# data lengths of the fixed-size opcodes (version 2 numbering; v1 the same below 0x100)
_FIXED = {0x00: 0, 0x02: 8, 0x03: 2, 0x04: 1, 0x05: 2, 0x06: 4, 0x07: 4,
          0x08: 2, 0x09: 8, 0x0A: 8, 0x0B: 4, 0x0C: 4, 0x0D: 2, 0x0E: 4,
          0x0F: 4, 0x10: 8, 0x15: 2, 0x16: 2, 0x17: 0, 0x18: 0, 0x19: 0,
          0x1A: 6, 0x1B: 6, 0x1C: 0, 0x1D: 6, 0x1E: 0, 0x1F: 6, 0x20: 8,
          0x21: 4, 0x22: 6, 0x23: 2, 0xA0: 2}


def walk(p):
    """Yield (offset, opcode, record or None) for the opcodes of PICT p.
    Bitmap opcodes come with their parsed record (see _bits_op)."""
    v2 = p[10:12] == b"\x00\x11"
    o = 10
    while o < len(p):
        if v2:
            o += o & 1
            op = struct.unpack(">H", p[o:o + 2])[0]
            o += 2
        else:
            op = p[o]
            o += 1
        start = o
        rec = None
        if op == 0xFF:
            yield start, op, None
            return
        if op == 0x11:
            o += 2 if v2 else 1
        elif op in _FIXED:
            o += _FIXED[op]
        elif op == 0x01 or 0x70 <= op <= 0x77 or 0x80 <= op <= 0x87:
            o += struct.unpack(">H", p[o:o + 2])[0]   # region / polygon
        elif op in (0x90, 0x91, 0x98, 0x99):
            rec, o = _bits_op(p, o, op, v2)
        elif op in (0x9A, 0x9B):
            raise ValueError("DirectBits (0x%X) not supported" % op)
        elif 0x12 <= op <= 0x14:
            raise ValueError("PixPat opcode 0x%X not supported" % op)
        elif op == 0x28:
            o += 4 + 1 + p[o + 4]
        elif op in (0x29, 0x2A):
            o += 1 + 1 + p[o + 1]
        elif op == 0x2B:
            o += 2 + 1 + p[o + 2]
        elif 0x24 <= op <= 0x2F or 0x92 <= op <= 0x97 or 0x9C <= op <= 0x9F or 0xA2 <= op <= 0xAF:
            o += 2 + struct.unpack(">H", p[o:o + 2])[0]
        elif 0x30 <= op <= 0x37 or 0x40 <= op <= 0x47 or 0x50 <= op <= 0x57:
            o += 8
        elif 0x38 <= op <= 0x3F or 0x48 <= op <= 0x4F or 0x58 <= op <= 0x5F or 0x78 <= op <= 0x7F or 0x88 <= op <= 0x8F:
            pass
        elif 0x60 <= op <= 0x67:
            o += 12
        elif 0x68 <= op <= 0x6F:
            o += 4
        elif op == 0xA1:
            o += 4 + struct.unpack(">H", p[o + 2:o + 4])[0]
        elif 0xB0 <= op <= 0xCF or 0x8000 <= op <= 0x80FF:
            pass
        elif 0xD0 <= op <= 0xFE or 0x8100 <= op:
            o += 4 + struct.unpack(">I", p[o:o + 4])[0]
        elif 0x0100 <= op <= 0x7FFF:
            o += (op >> 8) * 2
        else:
            raise ValueError("unknown opcode 0x%X at %d" % (op, start))
        yield start, op, rec


_DRAWN = {0x20, 0x21, 0x22, 0x23, 0x28, 0x29, 0x2A, 0x2B}


def render(p):
    """Draw the bitmap opcodes of PICT p into its frame.
    Returns (width, height, rgb rows as bytes, notes)."""
    ftop, fleft, fbottom, fright = _rect(p, 2)
    w, h = fright - fleft, fbottom - ftop
    canvas = [[(255, 255, 255)] * w for _ in range(h)]
    notes = []
    clip = None
    for off, op, rec in walk(p):
        if op == 0x01:
            bbox, inside, _ = region_mask(p, off)
            clip = (bbox, inside)
            continue
        if rec is None:
            if op in _DRAWN or 0x30 <= op <= 0x8F:
                notes.append("opcode 0x%X not drawn" % op)
            continue
        mode = rec["mode"] & ~64
        if mode not in (0, 1, 2, 3, 36):
            notes.append("mode %d drawn as srcCopy" % mode)
        st, sl, sb, sr = rec["src"]
        dt, dl, db, dr = rec["dst"]
        bt, bl = rec["bounds"][0], rec["bounds"][1]
        sw, sh, dw, dh = sr - sl, sb - st, dr - dl, db - dt
        if (sw, sh) != (dw, dh):
            notes.append("scaled %dx%d -> %dx%d" % (sw, sh, dw, dh))
        pal = rec["palette"]
        for y in range(dh):
            cy = dt + y - ftop
            if not 0 <= cy < h:
                continue
            row = rec["rows"][st + (y * sh) // dh - bt]
            for x in range(dw):
                cx = dl + x - fleft
                if not 0 <= cx < w:
                    continue
                px, py = dl + x, dt + y
                ok = True
                for m in (rec["mask"], clip):
                    if m is None:
                        continue
                    (mt, ml, mb, mr), inside = m
                    if not (mt <= py < mb and ml <= px < mr) or (inside is not None and (px, py) not in inside):
                        ok = False
                if not ok:
                    continue
                v = _pixel(rec, row, sl + (x * sw) // dw - bl)
                c = pal[v]
                if rec["depth"] == 1 and mode in (1, 2, 3):
                    if not v:
                        continue
                    if mode == 1:
                        canvas[cy][cx] = (0, 0, 0)
                    elif mode == 3:
                        canvas[cy][cx] = (255, 255, 255)
                    else:
                        canvas[cy][cx] = tuple(255 - k for k in canvas[cy][cx])
                    continue
                if mode == 36 and c == (255, 255, 255):
                    continue
                canvas[cy][cx] = c
    return w, h, [b"".join(bytes(c) for c in row) for row in canvas], sorted(set(notes))


if __name__ == "__main__":
    w, h, rows, notes = render(open(sys.argv[1], "rb").read())
    write_png(sys.argv[2], w, h, rows)
    print(w, h, *notes)
