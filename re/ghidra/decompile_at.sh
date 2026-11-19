#!/bin/sh
# Decompile one segment's routines at given offsets, in the project that
# decompile_all.sh made (WORK/ghidra-proj), without changing it: functions
# Ghidra did not find (no LINK A6, an entry into another routine) are made
# for this run only (-readOnly). After each routine's C the Toolbox traps in
# its body are listed by name (Ghidra shows them as TRAP #15: patch_traps.py).
# Usage: decompile_at.sh WORK SEG OFFSET...   e.g. decompile_at.sh re/work/app 2 0x1222 3f7e
# Java and Ghidra as in decompile_all.sh.
set -e
[ $# -ge 3 ] || { echo "usage: $0 WORK SEG OFFSET..." >&2; exit 2; }
if [ -n "$GHIDRA_JAVA_HOME" ]; then
    JAVA_HOME="$GHIDRA_JAVA_HOME"
else
    J=$(ls -d /opt/homebrew/opt/openjdk@* 2>/dev/null | sort -t@ -k2 -n | tail -1)
    [ -n "$J" ] && JAVA_HOME="$J/libexec/openjdk.jdk/Contents/Home"
fi
export JAVA_HOME
W="$(cd "$1" && pwd)"
SEG=$(printf "seg%02d" "$2")
shift 2
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$W/ghidra-proj/game.gpr" ] || { echo "no project in $W/ghidra-proj: run decompile_all.sh first" >&2; exit 1; }
OUT=$(mktemp "${TMPDIR:-/tmp}/decompile_at.XXXXXX")
LOG="$OUT.log"
/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless "$W/ghidra-proj" game -process "$SEG.bin" -readOnly -noanalysis \
    -scriptPath "$HERE" -postScript DecompileAt.java "$OUT" "$@" > "$LOG" 2>&1 || { cat "$LOG" >&2; rm -f "$OUT" "$LOG"; exit 1; }
[ -s "$OUT" ] || { echo "Ghidra wrote nothing:" >&2; cat "$LOG" >&2; rm -f "$OUT" "$LOG"; exit 1; }
# the C, and after each routine its traps by name
python3 -I - "$OUT" "$W/code_patched/$SEG.traps.txt" "$HERE/.." <<'PY'
import re, sys
out, traps_file, re_dir = sys.argv[1:4]
sys.path.insert(0, re_dir)
from disasm import trap_name
traps = [(int(o, 16), int(w, 16)) for o, w in (l.split() for l in open(traps_file) if l.strip())]
body = None
def flush():
    if body:
        inside = [(o, w) for o, w in traps if body[0] <= o <= body[1]]
        if inside:
            print("// traps: " + ", ".join(f"{o:x} {trap_name(w)}" for o, w in inside))
for line in open(out):
    h = re.match(r"===== .* body (?:ram:)?([0-9a-f]+)-(?:ram:)?([0-9a-f]+)", line)
    if h:
        flush()
        body = (int(h.group(1), 16), int(h.group(2), 16))
    print(line, end="")
flush()
PY
rm -f "$OUT" "$LOG"
