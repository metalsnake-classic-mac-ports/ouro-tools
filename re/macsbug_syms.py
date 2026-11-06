"""List MacsBug symbols (routine names after rts/rtd/jmp (a0)) in 68k CODE segments.

Usage: python3 -I macsbug_syms.py <work dir>   -> prints "seg start end name" per routine
The routine start is the end of the previous symbol block (or 0), which holds
for CodeWarrior/THINK output where routines follow each other without gaps.
"""
import sys, os, re

def syms(code):
    out = []
    i = 0
    n = len(code)
    while i < n - 4:
        w = code[i:i+2]
        end = None
        if w in (b'\x4e\x75', b'\x4e\xd0'):
            end = i + 2
        elif w == b'\x4e\x74':
            end = i + 4
        if end is not None and end < n:
            b = code[end]
            name = None
            if 0x80 < b < 0xa0 + 0x20 and b != 0x80:
                ln = b - 0x80
                s = code[end+1:end+1+ln]
                if ln > 0 and len(s) == ln and re.fullmatch(rb'[A-Za-z_%.$][A-Za-z0-9_%.$:~]*', s):
                    name = s.decode(); stop = end + 1 + ln
                    if stop & 1: stop += 1
                    stop += 2  # literal constants size
                    if stop - 2 + 2 <= n:
                        lit = int.from_bytes(code[stop-2:stop], 'big')
                        stop += lit
            elif 0xc0 < b < 0xff and b - 0x80 >= 0x41:
                s = bytes([b & 0x7f]) + code[end+1:end+8]
                if re.fullmatch(rb'[A-Za-z_][A-Za-z0-9_ ]{7}', s):
                    name = s.decode().rstrip(); stop = end + 8
            if name:
                out.append((end, stop, name))
                i = stop
                continue
        i += 2
    return out

work = sys.argv[1]
for f in sorted(os.listdir(os.path.join(work, 'code'))):
    m = re.match(r'seg(\d+)\.bin', f)
    if not m: continue
    seg = int(m.group(1))
    code = open(os.path.join(work, 'code', f), 'rb').read()
    start = 0
    for end, stop, name in syms(code):
        print(f"{seg:2d} {start:06x} {end:06x} {name}")
        start = stop
