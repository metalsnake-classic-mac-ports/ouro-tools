"""Resolve the switch jump tables of a routine in a CodeWarrior PPC build.

Usage: python3 -I ppc_switch.py <ppc work dir> <routine name> [instructions per case]
The work dir holds the .pef, data.bin, traceback.txt and toc.txt (run_ghidra.sh).
CodeWarrior emits: addi rX,rX,-base; cmplwi rX,n-1; bgt default;
addi rT,r2,off; slwi rX,rX,2; lwzx rT,rT,rX; mtctr rT; bctr. The table
(n code addresses) lives in the data section at TOC + off. Ghidra's case
labels for these switches can be wrong - this reads the table itself.
"""
import os, struct, sys
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pef_traceback import code_section, find_pef, read_toc, BASE

ppc = sys.argv[1]
TOC = read_toc(ppc)
name = sys.argv[2].lstrip(".")
per_case = int(sys.argv[3]) if len(sys.argv) > 3 else 8
code = code_section(open(find_pef(ppc), "rb").read())
raw = open(os.path.join(ppc, "data.bin"), "rb").read()
dbase = struct.unpack(">I", raw[:4])[0]
data = raw[4:]
routines = {l.split()[2].lstrip("."): (int(l.split()[0], 16), int(l.split()[1])) for l in open(os.path.join(ppc, "traceback.txt"))}
start, size = routines[name]
md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
md.detail = True
ins = list(md.disasm(code[start - BASE:start - BASE + size], start))
for k, i in enumerate(ins):
    if i.mnemonic != "bctr":
        continue
    # walk back for the pattern
    lo = n = off = None
    for j in range(k - 1, max(k - 12, 0), -1):
        m, o = ins[j].mnemonic, ins[j].op_str
        if m == "addi" and o.split(", ")[1] == "r2" and off is None:
            off = int(o.split(", ")[2], 0)
        elif m == "cmplwi" and n is None:
            n = int(o.split(", ")[1], 0) + 1
        elif m == "addi" and n is not None and lo is None and o.split(", ")[0] == o.split(", ")[1]:
            lo = -int(o.split(", ")[2], 0)
    if off is None or n is None:
        print(f"bctr at {i.address:08x}: pattern not found")
        continue
    lo = lo or 0
    tab = TOC + off
    print(f"switch at {i.address:08x}: cases {lo}..{lo + n - 1}, table {tab:08x}")
    for c in range(n):
        t = struct.unpack(">I", data[tab - dbase + 4 * c:tab - dbase + 4 * c + 4])[0]
        out = []
        for x in md.disasm(code[t - BASE:t - BASE + 4 * per_case], t):
            out.append(f"{x.mnemonic} {x.op_str}")
            if x.mnemonic in ("b", "blr"):
                break
        print(f"  case {lo + c:3}: {t:08x}  " + " ; ".join(out))
