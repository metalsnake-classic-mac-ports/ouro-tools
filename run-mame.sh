#!/bin/sh
# Run a 68k / PowerPC Mac in MAME with the ROMs in roms/mame.
#
# Usage: run-mame.sh <machine> <work dir> [mame options...]
#   machine   e.g. macqd700 (Quadra 700), macqd630, maciici, pmac6100
#   work dir  keeps the machine's PRAM (nvram/), MAME's settings (cfg/) and
#             screenshots (snap/); a port uses its re/work/mame
# Without a window and as fast as possible: MAME_HEADLESS=1.
# Timed keys, screenshots and memory dumps: MAME_DRIVE (see re/mame/drive.lua).
#
# Examples (from a port's repository root):
#   ../ouro-tools/run-mame.sh macqd700 re/work/mame -ramsize 8M -hard1 re/work/mame/boot.hd
#   MAME_HEADLESS=1 MAME_DRIVE="40 shot; 41 exit" ../ouro-tools/run-mame.sh macqd700 re/work/mame -hard1 ...
set -e
TOOLS="$(cd "$(dirname "$0")" && pwd)"
MACHINE="$1"; WORK="$2"
[ -n "$MACHINE" ] && [ -n "$WORK" ] || { sed -n '2,15p' "$0"; exit 2; }
shift 2
command -v mame >/dev/null || { echo "mame not found: build-emulators.sh mame"; exit 1; }
mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd)"
set -- -rompath "$TOOLS/roms/mame" -skip_gameinfo \
    -nvram_directory "$WORK/nvram" -cfg_directory "$WORK/cfg" \
    -snapshot_directory "$WORK/snap" -state_directory "$WORK/sta" "$@"
[ -n "$MAME_DRIVE" ] && set -- -autoboot_script "$TOOLS/re/mame/drive.lua" -autoboot_delay 0 "$@"
[ -n "$MAME_HEADLESS" ] && set -- -video none -sound none -nothrottle "$@"
exec mame "$MACHINE" "$@"
