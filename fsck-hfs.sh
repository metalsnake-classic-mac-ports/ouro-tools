#!/bin/sh
# Check an HFS / HFS+ disk image read-only with Apple's fsck_hfs (part of
# macOS, /sbin/fsck_hfs; source: apple-oss-distributions/hfs). The image is
# attached as a device without mounting it, checked, and detached again.
#
# Usage: fsck-hfs.sh IMAGE [IMAGE ...]
#   IMAGE: a bare volume (.dsk) or a disk with a partition map (.hd); for
#   the latter the HFS partition at block 128 (re/mkscsidisk.py) is checked.
# Prints each image's findings and "OK" / "damaged" / "not verified";
# exits 1 when any image is not OK.
#
# What the findings mean (2026-11-14):
# - "Reserved fields in the catalog record have incorrect data" and
#   "Unused node is not erased": what hfsutils (hcopy, hdel) leaves; the
#   Mac does not mind. Reported as "OK (cosmetic)".
# - "Invalid allocation block size": fsck_hfs wants allocation blocks of at
#   least 512 * n, n the smallest with (all sectors of the volume / n) <=
#   65535 (fsck_hfs' SVerify1.c); hformat counts without the volume's
#   management blocks and may pick one size less (128 MB: 2048 against
#   2560; 160 MB: 2560 against 3072). The Mac mounts such volumes, fsck_hfs
#   checks nothing further. Pick sizes a little below a boundary (80 MB:
#   1536, 120 MB: 2048).
# - Anything else (block counts, extents, the bitmap, the hierarchy) is
#   real damage.
status=0
for image in "$@"; do
    work="$(mktemp -d)"
    case "$image" in
    *.hd) dd if="$image" of="$work/volume" bs=512 skip=128 2>/dev/null ;;
    *) cp "$image" "$work/volume" ;;
    esac
    chmod u+w "$work/volume"
    device=$(hdiutil attach -nomount -readonly -imagekey diskimage-class=CRawDiskImage \
        "$work/volume" | awk 'NR==1 {print $1}')
    report=$(/sbin/fsck_hfs -n -f "$device" 2>&1)
    hdiutil detach "$device" >/dev/null
    rm -rf "$work"
    findings=$(printf '%s\n' "$report" | grep -v -E \
        'Permission denied|NO WRITE|cacheBlockSize|Executing fsck_hfs|^\*\* (Checking|/dev)|volume name is|^\(' |
        sort | uniq -c | sed 's/^ *//')
    cosmetic='Reserved fields in the catalog record|Unused node is not erased|found corrupt and needs to be repaired'
    if printf '%s\n' "$report" | grep -q 'appears to be OK'; then
        verdict=OK
    elif printf '%s\n' "$report" | grep -q 'could not be verified'; then
        verdict="not verified"; status=1
    elif ! printf '%s\n' "$findings" | grep -v -E "$cosmetic" | grep -q .; then
        verdict="OK (cosmetic)"
    else
        verdict=damaged; status=1
    fi
    echo "$image: $verdict"
    [ "$verdict" = OK ] || printf '%s\n' "$findings" | sed 's/^/    /'
done
exit $status
