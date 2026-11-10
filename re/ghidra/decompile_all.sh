#!/bin/sh
# Decompile all CODE segments into WORK/decomp/segNN.c with Ghidra headless.
# Usage: decompile_all.sh WORK   (run patch_traps.py WORK first)
# Input: WORK/code_patched/segNN.bin (segment without its 4-byte header,
# A-line traps replaced by TRAP #15, see patch_traps.py). Function starts are
# seeded from the jump table in CODE 0 (WORK/rsrc/CODE_0.bin).
# Needs: brew install ghidra (path below), processor 68000:BE:32:MC68020.
# Java: GHIDRA_JAVA_HOME if set, else the newest Homebrew openjdk@N (a
# Ghidra update may need a newer JDK than JAVA_HOME points to; headless
# Ghidra cannot ask for one and quietly decompiles nothing).
set -e
if [ -n "$GHIDRA_JAVA_HOME" ]; then
    JAVA_HOME="$GHIDRA_JAVA_HOME"
else
    J=$(ls -d /opt/homebrew/opt/openjdk@* 2>/dev/null | sort -t@ -k2 -n | tail -1)
    [ -n "$J" ] && JAVA_HOME="$J/libexec/openjdk.jdk/Contents/Home"
fi
export JAVA_HOME
W="$(cd "$1" && pwd)"
mkdir -p "$W/decomp" "$W/ghidra-proj"
python3 -I - "$W" <<'PY'
import struct, sys, os
w = sys.argv[1]
c0 = open(f"{w}/rsrc/CODE_0.bin", "rb").read()
jtlen = struct.unpack(">I", c0[8:12])[0]
seeds = {}
for k in range(jtlen // 8):
    off, _, seg, _ = struct.unpack(">HHHH", c0[16 + k * 8:24 + k * 8])
    seeds.setdefault(seg, set()).add(off)
os.makedirs(f"{w}/seeds", exist_ok=True)
for seg, offs in seeds.items():
    open(f"{w}/seeds/seg{seg:02d}.txt", "w").write("\n".join(f"{o:x}" for o in sorted(offs)) + "\n")
PY
for f in "$W"/code_patched/seg*.bin; do
    n=$(basename "$f" .bin)
    /opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless "$W/ghidra-proj" game -import "$f" -overwrite \
        -processor 68000:BE:32:MC68020 -loader BinaryLoader \
        -scriptPath "$(dirname "$0")" \
        -postScript CreateFuncs.java "$W/seeds/$n.txt" \
        -postScript DecompileAll.java "$W/decomp/$n.c" 2>&1 | grep 'created functions' | sed "s/^/$n: /"
    [ -s "$W/decomp/$n.c" ] || { echo "$n: Ghidra wrote no output (Java? run analyzeHeadless by hand)" >&2; exit 1; }
done
