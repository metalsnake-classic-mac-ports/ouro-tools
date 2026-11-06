"""Disassemble a range of the PEF code section (Ghidra addresses, base 0x10000000).

Usage: python3 -I ppcdis.py <file.pef> <start hex> <end hex | +len hex>
Names from a "address size name" list (traceback.txt) are printed as labels
when traceback.txt exists next to the PEF.
"""
import os, struct, sys
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pef_traceback import code_section, BASE

pef = sys.argv[1]
code = code_section(open(pef, "rb").read())
start = int(sys.argv[2], 16)
end = start + int(sys.argv[3][1:], 16) if sys.argv[3].startswith("+") else int(sys.argv[3], 16)
names = {}
tb = os.path.join(os.path.dirname(pef), "traceback.txt")
if os.path.exists(tb):
    for l in open(tb):
        a, _, n = l.split()
        names[int(a, 16)] = n
md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
for i in md.disasm(code[start - BASE:end - BASE], start):
    if i.address in names:
        print(f"\n{names[i.address]}:")
    print(f"  {i.address:08x}  {i.bytes.hex()}  {i.mnemonic:8} {i.op_str}")
