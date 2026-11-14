#!/bin/sh
# Build a System 7.1.1 ("System 7 Pro") hard disk by running Apple's
# installer in MAME (Quadra 700, Easy Install, the floppies fed by
# re/mame/drive.lua), then remove PowerTalk (it asks to be set up at every
# start and needs memory). Writes into systems/ next to this script (or
# OUT_DIR):
#   system711.dsk        the bare 80 MB HFS volume (Basilisk II)
#   system711.hd         the same as a bootable SCSI disk (MAME: -hard1);
#                        boots the Quadra 700, IIci and SE/30
#   scsi-driver-722.bin  HD SC Setup 7.2.2's driver, for re/mkscsidisk.py
#
# Usage: make-system711-disk.sh SSW-7-Pro-Disk-Images.sit [OUT_DIR]
# (the 12 Disk Copy 4.2 floppy images of System 7 Pro)
# Needs: brew install unar hfsutils; MAME and roms/mame (README, "MAME").
# Optional tools, each from its archive: MACSBUG_SIT=MacsBug_6.2.2_0.sit
# (into the System Folder), DEBUGGER_SIT=Debugger.sit and
# STUFFIT=stuffit_expander_4.0.2.sea_.bin (into a folder Utilities).
# Takes about 3 minutes (15 emulated minutes at 6x).
set -e
SIT="$1"
[ -f "$SIT" ] || { echo "usage: $0 SSW-7-Pro-Disk-Images.sit [OUT_DIR]" >&2; exit 1; }
TOOLS="$(cd "$(dirname "$0")" && pwd)"
SYSTEMS="${2:-$TOOLS/systems}"
mkdir -p "$SYSTEMS"
SYSTEMS="$(cd "$SYSTEMS" && pwd)"
TMP="$(mktemp -d)"
trap 'humount >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT

# Disk Copy 4.2 images -> raw floppies named without spaces (Install2.dsk, ...)
mkdir "$TMP/sit" "$TMP/fd"
unar -q -o "$TMP/sit" -forks fork "$SIT"
python3 -I - "$TMP/sit" "$TMP/fd" <<'EOF'
import os, struct, sys
src, out = sys.argv[1], sys.argv[2]
for root, _, files in os.walk(src):
    for f in files:
        if not f.endswith(".image"):
            continue
        b = open(os.path.join(root, f), "rb").read()
        if b[82:84] != b"\x01\x00":
            sys.exit(f"{f}: not a Disk Copy 4.2 image")
        size = struct.unpack(">I", b[64:68])[0]
        name = "".join(c for c in f[:-6] if c.isalnum())
        open(os.path.join(out, name + ".dsk"), "wb").write(b[84:84 + size])
EOF
[ -f "$TMP/fd/Install.dsk" ] && [ -f "$TMP/fd/DiskTools.dsk" ] ||
    { echo "Install / Disk Tools images missing" >&2; exit 1; }

# the SCSI driver of HD SC Setup 7.2.2 (on Disk Tools) and a blank disk
hmount "$TMP/fd/DiskTools.dsk" >/dev/null
hcopy -m ':Apple HD SC Setup' "$TMP/hdsc.bin"
humount
python3 -I "$TOOLS/re/macres.py" dump "$TMP/hdsc.bin" "$TMP/hdsc"
cp "$TMP/hdsc/scsi_128.bin" "$SYSTEMS/scsi-driver-722.bin"
dd if=/dev/zero of="$TMP/vol.dsk" bs=1m count=80 2>/dev/null
hformat -l "Macintosh HD" "$TMP/vol.dsk" >/dev/null
humount
python3 -I "$TOOLS/re/mkscsidisk.py" "$TMP/vol.dsk" "$TMP/hdsc/scsi_128.bin" "$TMP/inst.hd" >/dev/null

# The installer, timed on the emulated clock: welcome (Return), Tab =
# Switch Disk to the hard disk, Return = Install; then the floppies in the
# order it asks for them (a wrong one is answered with Continue and fed
# the next). It ends at the Restart / Shut Down alert (about t=840).
LIST=""
for f in Install2 Install3 Tidbits Fonts Printing PowerTalk PowerTalk2 \
         AppleScriptSetup QuickTime Install DiskTools BeforeYouInstall; do
    [ -f "$TMP/fd/$f.dsk" ] && LIST="$LIST|$TMP/fd/$f.dsk"
done
MAME_HEADLESS=1 \
MAME_DRIVE="121 key return; 135 key tab; 141 key return; 142 feed flop,${LIST#|}; 1100 shot; 1101 exit" \
    "$TOOLS/run-mame.sh" macqd700 "$TMP/mame" -ramsize 8M -hard1 "$TMP/inst.hd" \
    -flop "$TMP/fd/Install.dsk" >"$TMP/mame.log" 2>&1 || { cat "$TMP/mame.log"; exit 1; }

# the optional tools
. "$TOOLS/disk-extras.sh"
: > "$TMP/macsbug.list"
[ -n "$MACSBUG_SIT" ] && extra_macsbug "$MACSBUG_SIT" "$TMP/x" > "$TMP/macsbug.list"
[ -n "$DEBUGGER_SIT" ] && extra_debugger "$DEBUGGER_SIT" "$TMP/x" >/dev/null
[ -n "$STUFFIT" ] && extra_expander "$STUFFIT" "$TMP/x" >/dev/null

# the volume back out of the disk (HFS at block 128), PowerTalk removed
dd if="$TMP/inst.hd" of="$TMP/out.dsk" bs=512 skip=128 2>/dev/null
hmount "$TMP/out.dsk" >/dev/null
hls ':System Folder:Extensions' | grep -q '^Finder Help$' ||
    { humount; echo "installation incomplete (see $TMP/mame)" >&2; trap - EXIT; exit 1; }
for f in "PowerTalk Extension" "PowerTalk Manager" "Catalogs Extension" "Mailbox Extension"; do
    hdel ":System Folder:Extensions:$f" 2>/dev/null || true
done
hdel ":System Folder:Control Panels:PowerTalk Setup" 2>/dev/null || true
hls ':PowerTalk Folder' 2>/dev/null | while read -r f; do hdel ":PowerTalk Folder:$f"; done
hrmdir ':PowerTalk Folder' 2>/dev/null || true
hdel ':Shutdown Check' 2>/dev/null || true  # MAME was not shut down
while read -r f; do hcopy -m "$f" ':System Folder:'; done < "$TMP/macsbug.list"
if [ -f "$TMP/x/debugger.bin" ] || [ -f "$TMP/x/expander.bin" ]; then
    hmkdir ':Utilities'
    [ -f "$TMP/x/debugger.bin" ] && hcopy -m "$TMP/x/debugger.bin" ':Utilities:Debugger!'
    [ -f "$TMP/x/expander.bin" ] && hcopy -m "$TMP/x/expander.bin" ':Utilities:StuffIt Expander'
fi
humount
cp "$TMP/out.dsk" "$SYSTEMS/system711.dsk"
python3 -I "$TOOLS/re/mkscsidisk.py" "$SYSTEMS/system711.dsk" "$SYSTEMS/scsi-driver-722.bin" "$SYSTEMS/system711.hd"
echo "wrote $SYSTEMS/system711.dsk, system711.hd, scsi-driver-722.bin"
