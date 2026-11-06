#!/bin/sh
# Import a PowerPC PEF (CodeWarrior) into Ghidra headless, name and type
# what we know, and decompile everything.
# Usage: run_ghidra.sh PEF OUT [globals.txt] [struct.txt SIZE NAME PATTERN]
#   PEF          the PowerPC fragment (data fork of the app, see cfrg 0)
#   OUT          output folder (e.g. re/work/ppc); it receives:
#     game.pef          a copy of PEF (the Python tools find it here)
#     traceback.txt     routine starts and names (pef_traceback.py)
#     toc.txt           the TOC (r2)
#     functions.txt     all functions after naming
#     toc_functions.txt TOC slots that lead to a function (TVectors)
#     imports.txt       the import slots (Toolbox routines)
#     data.bin          the unpacked data section (start address first)
#     game.c            decompiled C of every function
#   names.txt in OUT (optional, "address size name"): names for routines
#     without a traceback table (libraries, assembly).
#   globals.txt (ApplyLabels.java format) and a struct list for the first
#     parameter of the routines that take it (ApplyStruct.java) are
#     optional; rerun the script whenever they grow.
# Needs: brew install ghidra (path below); python3 with capstone.
# Java: GHIDRA_JAVA_HOME if set, else the newest Homebrew openjdk@N (a
# Ghidra update may need a newer JDK than JAVA_HOME points to; headless
# Ghidra cannot ask for one and stops).
set -e
PEF="$1"
OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
D="$(cd "$(dirname "$0")" && pwd)"
G=/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless
if [ -n "$GHIDRA_JAVA_HOME" ]; then
    JAVA_HOME="$GHIDRA_JAVA_HOME"
else
    J=$(ls -d /opt/homebrew/opt/openjdk@* 2>/dev/null | sort -t@ -k2 -n | tail -1)
    [ -n "$J" ] && JAVA_HOME="$J/libexec/openjdk.jdk/Contents/Home"
fi
export JAVA_HOME
mkdir -p "$OUT/ghidra-proj"
cp "$PEF" "$OUT/game.pef"
python3 -I "$D/pef_traceback.py" "$OUT/game.pef" > "$OUT/traceback.txt"
[ -f "$OUT/names.txt" ] || : > "$OUT/names.txt"
GLOBALS="$3" STRUCT="$4" SIZE="$5" SNAME="$6" PATTERN="$7"
set --
[ -n "$GLOBALS" ] && set -- "$@" -postScript ApplyLabels.java "$GLOBALS"
[ -n "$STRUCT" ] && set -- "$@" -postScript ApplyStruct.java "$STRUCT" "$SIZE" "$SNAME" "$PATTERN"
# processor given explicitly: auto-detection picks a 64-bit VLE variant
"$G" "$OUT/ghidra-proj" game-ppc -import "$OUT/game.pef" -overwrite \
    -processor PowerPC:BE:32:default -cspec default \
    -scriptPath "$D/ghidra" \
    -postScript ApplyNames.java "$OUT/traceback.txt" \
    -postScript ApplyNames.java "$OUT/names.txt" \
    -postScript NopTOCRestore.java \
    -postScript SetTOC.java "$OUT/toc.txt" \
    -postScript NameTOC.java "$OUT/toc_functions.txt" \
    "$@" \
    -postScript ExportFunctions.java "$OUT/functions.txt" \
    -postScript DumpData.java "$OUT/data.bin" \
    -postScript ExportImports.java "$OUT/imports.txt" \
    -postScript DecompileAll.java "$OUT/game.c" > "$OUT/ghidra.log" 2>&1
grep -E "ApplyNames|NopTOC|SetTOC|NameTOC|ApplyLabels|ApplyStruct|DumpData|ExportImports|ERROR" "$OUT/ghidra.log"
