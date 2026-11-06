"""Function starts and names from the traceback tables of a PowerPC PEF.

Usage: python3 -I pef_traceback.py <file.pef>  -> "address size name" per routine
CodeWarrior writes an AIX-style traceback table after each routine: a zero
word, 8 fixed bytes (version, language, flags...), then optional fields:
parminfo (if fixed/float parameters), tb_offset (= routine length, if
has_tboff), handler mask, ctl info, name (2-byte length + text, if
name_present). Addresses are given as Ghidra loads the code section
(base 0x10000000).
"""
import glob, os, struct, sys

BASE = 0x10000000


def find_pef(ppc_dir):
    """The one *.pef file in a ppc work folder."""
    found = sorted(glob.glob(os.path.join(ppc_dir, "*.pef")))
    if not found:
        raise FileNotFoundError(f"no .pef in {ppc_dir}")
    return found[0]


def read_toc(ppc_dir):
    """The TOC (r2) written by ghidra/SetTOC.java into toc.txt."""
    return int(open(os.path.join(ppc_dir, "toc.txt")).read().split()[0], 16)


def code_section(pef):
    nsec = struct.unpack(">H", pef[0x20:0x22])[0]
    for i in range(nsec):
        h = pef[40 + 28 * i:40 + 28 * (i + 1)]
        size, off, kind = struct.unpack(">I", h[16:20])[0], struct.unpack(">I", h[20:24])[0], h[24]
        if kind == 0:
            return pef[off:off + size]
    raise ValueError("no code section")


def tracebacks(code):
    out = []
    for p in range(0, len(code) - 16, 4):
        if code[p:p + 4] != b"\0\0\0\0":
            continue
        t = p + 4
        version, lang, f1, f2, f3, f4, fixedp, floatp = code[t:t + 8]
        if version != 0 or not (f1 & 0x20) or not (f2 & 0x40):
            continue
        q = t + 8
        if fixedp or (floatp >> 1):
            q += 4
        tboff = struct.unpack(">I", code[q:q + 4])[0]
        q += 4
        if f2 & 0x80:      # int_hndl
            q += 4
        if f1 & 0x08:      # has_ctl
            n = struct.unpack(">I", code[q:q + 4])[0]
            q += 4 + 4 * n
        ln = struct.unpack(">H", code[q:q + 2])[0]
        name = code[q + 2:q + 2 + ln]
        if not (0 < ln < 128) or not all(32 < c < 127 for c in name):
            continue
        start = p - tboff
        if start < 0 or start % 4:
            continue
        out.append((BASE + start, tboff, name.decode()))
    return out


if __name__ == "__main__":
    code = code_section(open(sys.argv[1], "rb").read())
    for addr, size, name in tracebacks(code):
        print(f"{addr:08x} {size} {name}")
