#!/bin/sh
# Build a full System 7.5.5 hard disk by running Apple's installers in MAME
# (Quadra 700): System 7.5.3 from the retail CD (Easy Install), then the
# System 7.5.5 Update from the Apple Legacy Recovery CD; then add with
# hfsutils MacsBug 6.5.3, the File System Manager 1.2 (Basilisk II's shared
# folder needs it), Disk Copy 6.3.3 and StuffIt Expander 4.0.2. Writes into
# systems/ next to this script (or OUT_DIR):
#   system755.dsk   the bare 160 MB HFS volume (Basilisk II)
#   system755.hd    the same as a bootable SCSI disk (MAME: -hard1)
#
# Usage: make-system755-disk.sh SYSTEM_7-5-3-RETAIL.ISO Apple-Legacy-Feb_2000.iso \
#            MacsBug_6.5.3.sit stuffit_expander_4.0.2.sea_.bin [OUT_DIR]
# Needs: brew install unar hfsutils; MAME and roms/mame (README, "MAME");
# systems/scsi-driver-722.bin (make-system711-disk.sh; the driver of the
# 7.5.3 CD's HD SC Setup does not mount this disk); the File System Manager
# from systems/system75-sound-harry.dsk (FSM_DISK: another disk with
# ':System Folder:Extensions:File System Manager').
# Takes about 6 minutes (30 emulated minutes at 6x).
set -e
CD753="$1"; LEGACY="$2"; MACSBUG="$3"; STUFFIT="$4"
[ -f "$CD753" ] && [ -f "$LEGACY" ] && [ -f "$MACSBUG" ] && [ -f "$STUFFIT" ] || {
    sed -n '14,15p' "$0" >&2; exit 1; }
TOOLS="$(cd "$(dirname "$0")" && pwd)"
SYSTEMS="${5:-$TOOLS/systems}"
mkdir -p "$SYSTEMS"
SYSTEMS="$(cd "$SYSTEMS" && pwd)"
DRIVER="$TOOLS/systems/scsi-driver-722.bin"
FSM_DISK="${FSM_DISK:-$TOOLS/systems/system75-sound-harry.dsk}"
[ -f "$DRIVER" ] || { echo "$DRIVER missing: run make-system711-disk.sh" >&2; exit 1; }
[ -f "$FSM_DISK" ] || { echo "$FSM_DISK missing (FSM_DISK)" >&2; exit 1; }
TMP="$(mktemp -d)"
trap 'humount >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT
RE="$TOOLS/re"
mame_run() {  # mame_run DRIVE HD [options]: headless Quadra 700
    drive="$1"; hd="$2"; shift 2
    MAME_HEADLESS=1 MAME_DRIVE="$drive" "$TOOLS/run-mame.sh" macqd700 "$TMP/mame" \
        -ramsize 8M -hard1 "$hd" "$@" >>"$TMP/mame.log" 2>&1 || { cat "$TMP/mame.log"; exit 1; }
}
volume() { dd if="$1" of="$2" bs=512 skip=128 2>/dev/null; }  # HFS out of a disk

# 1. System 7.5.3 from the CD. It boots from the CD (the blank disk has no
# system); Tab selects the first item by name ("•System Software
# Installers•", "•Install System Software•": the bullet sorts first);
# Return = Continue, Return = Install. "Installation was successful" at
# about t=640.
dd if=/dev/zero of="$TMP/vol.dsk" bs=1m count=160 2>/dev/null
hformat -l "Macintosh HD" "$TMP/vol.dsk" >/dev/null
humount
python3 -I "$RE/mkscsidisk.py" "$TMP/vol.dsk" "$DRIVER" "$TMP/a.hd" >/dev/null
ln -s "$CD753" "$TMP/cd.iso"
mame_run "60 key tab; 62 key cmd+o; 70 key tab; 70.5 key tab; 72 key cmd+o; 130 key return; 146 key return; 760 exit" \
    "$TMP/a.hd" -cdrom "$TMP/cd.iso"
volume "$TMP/a.hd" "$TMP/v753.dsk"

# 2. The 7.5.5 update: its three floppies (NDIF images on the Legacy CD) as
# folders named like the disks, which the Installer takes for the disks.
hmount "$LEGACY" >/dev/null
for i in 1 2 3; do
    hcopy -m ":Mac OS:System Updates:System 7.5.5 Update:System 7.5.5 Update - $i.img" "$TMP/u$i.bin"
done
hcopy -m ':Apple SW (A-D):Disk Copy 6.3.3:Disk Copy' "$TMP/diskcopy.bin"
humount
hmount "$TMP/v753.dsk" >/dev/null
hls ':System Folder' | grep -qx System || { humount; echo "7.5.3 installation failed (see $TMP)" >&2; trap - EXIT; exit 1; }
hmkdir ':Update 755'
humount
for i in 1 2 3; do
    python3 -I "$RE/ndif.py" "$TMP/u$i.bin" "$TMP/u$i.dsk" >/dev/null
    hmount "$TMP/u$i.dsk" >/dev/null
    n=0
    hls | while read -r f; do n=$((n + 1)); hcopy -m ":$f" "$TMP/u$i-$n.bin"; done
    humount
    hmount "$TMP/v753.dsk" >/dev/null
    hmkdir ":Update 755:System 7.5.5 Update - $i"
    for b in "$TMP"/u$i-*.bin; do hcopy -m "$b" ":Update 755:System 7.5.5 Update - $i:"; done
    humount
done
python3 -I "$RE/mkscsidisk.py" "$TMP/v753.dsk" "$DRIVER" "$TMP/b.hd" >/dev/null
# Finder: m(acintosh HD), u(pdate 755), s(ystem 7.5.5 Update - 1), then
# "system " = the installer script; Return = Continue, click Agree (no
# default button), Return = Install. Successful at about t=890.
rm -rf "$TMP/mame"
mame_run "80 key m; 81 key cmd+o; 91 key u; 92 key cmd+o; 100 key s; 101 key cmd+o; 110 key s; 110.4 key y; 110.8 key s; 111.2 key t; 111.6 key e; 112 key m; 112.4 key space; 114 key cmd+o; 135 key return; 149 click 507,389; 159 key return; 960 exit" \
    "$TMP/b.hd"
volume "$TMP/b.hd" "$TMP/out.dsk"

# 3. Clean up and add the tools
mkdir "$TMP/mb" "$TMP/se"
unar -q -forks fork -o "$TMP/mb" "$MACSBUG" >/dev/null
python3 -I "$RE/tomacbinary.py" "$TMP/mb/MacsBug 6.5.3/Put into System folder/MacsBug" "$TMP/macsbug.bin"
unar -q -forks fork -o "$TMP/se" "$STUFFIT" >/dev/null
img="$(find "$TMP/se" -name '*.img' | head -1)"
python3 -I "$RE/ndif.py" "$img" "$img/..namedfork/rsrc" "$TMP/se.dsk" >/dev/null
python3 -I -c "import sys; f=open(sys.argv[1],'r+b'); f.truncate(max(819200, f.seek(0,2)))" "$TMP/se.dsk"
hmount "$TMP/se.dsk" >/dev/null
d="$(hls | head -1)"
app="$(hls ":$d" | grep -v '^Read Us' | head -1)"
hcopy -m ":$d:$app" "$TMP/expander.bin"
humount
hmount "$FSM_DISK" >/dev/null
hcopy -m ':System Folder:Extensions:File System Manager' "$TMP/fsm.bin"
humount

hmount "$TMP/out.dsk" >/dev/null
hls ':System Folder' | grep -qx 'System' && hls | grep -qx 'About System 7.5.5 Update' ||
    { humount; echo "7.5.5 update failed (see $TMP)" >&2; trap - EXIT; exit 1; }
for i in 1 2 3; do
    hls ":Update 755:System 7.5.5 Update - $i" | while read -r f; do
        hdel ":Update 755:System 7.5.5 Update - $i:$f"; done
    hrmdir ":Update 755:System 7.5.5 Update - $i"
done
hrmdir ':Update 755'
hdel ':Shutdown Check' 2>/dev/null || true  # MAME was not shut down
hcopy -m "$TMP/macsbug.bin" ':System Folder:MacsBug'
hcopy -m "$TMP/fsm.bin" ':System Folder:Extensions:File System Manager'
hmkdir ':Utilities'
hcopy -m "$TMP/diskcopy.bin" ':Utilities:Disk Copy'
hcopy -m "$TMP/expander.bin" ':Utilities:StuffIt Expander'
humount
cp "$TMP/out.dsk" "$SYSTEMS/system755.dsk"
python3 -I "$RE/mkscsidisk.py" "$SYSTEMS/system755.dsk" "$DRIVER" "$SYSTEMS/system755.hd"
echo "wrote $SYSTEMS/system755.dsk, system755.hd"
