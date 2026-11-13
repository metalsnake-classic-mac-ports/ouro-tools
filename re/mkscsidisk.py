"""Turn a raw HFS volume (a Basilisk II / SheepShaver .dsk) into a bootable
SCSI hard disk image for MAME's 68k Macs.

A real Mac boots from SCSI only from a disk with a driver descriptor
(block 0), an Apple partition map and a driver partition; the ROM loads the
driver and the driver mounts the Apple_HFS partition. Basilisk II does not
need any of that (its disk images are bare volumes), MAME does.

The driver is Apple HD SC Setup's resource 'scsi' 128 (HD SC Setup 7.0.1 is
on the System 7.0 boot floppy); dump it with
`macres.py dump "HD SC Setup.bin" out/` → out/scsi_128.bin.

Usage: python3 -I mkscsidisk.py <volume.dsk> <driver.bin> <out.hd>
The output is a raw block image; MAME takes it as `-hard1 out.hd`.
"""
import struct
import sys

BLOCK = 512
MAP_START, MAP_BLOCKS = 1, 63
DRIVER_START = MAP_START + MAP_BLOCKS  # 64
DRIVER_BLOCKS = 64  # room for larger drivers


def checksum(data):
    """Partition Manager boot code checksum: add, then rotate left by one."""
    s = 0
    for b in data:
        s = (s + b) & 0xFFFF
        s = ((s << 1) | (s >> 15)) & 0xFFFF
    return s


def entry(count, start, blocks, name, ptype, status, boot_size=0, boot_sum=0):
    e = bytearray(BLOCK)
    struct.pack_into(">2sHIII32s32sIII", e, 0, b"PM", 0, count, start, blocks,
                     name.encode(), ptype.encode(), 0, blocks, status)
    if boot_size:
        # pmLgBootStart, pmBootSize, pmBootAddr, pmBootAddr2, pmBootEntry,
        # pmBootEntry2, pmBootCksum, pmProcessor
        struct.pack_into(">IIIIIII16s", e, 0x5C, 0, boot_size, 0, 0, 0, 0,
                         boot_sum, b"68000")
    return bytes(e)


def main():
    vol_path, drv_path, out_path = sys.argv[1:4]
    vol = open(vol_path, "rb").read()
    drv = open(drv_path, "rb").read()
    if len(vol) % BLOCK:
        sys.exit("volume size is not a multiple of 512")
    if vol[1024:1026] != b"BD":
        sys.exit("not an HFS volume (no 'BD' at offset 1024)")
    drv_blocks = (len(drv) + BLOCK - 1) // BLOCK
    if drv_blocks > DRIVER_BLOCKS:
        sys.exit("driver too large")
    hfs_start = DRIVER_START + DRIVER_BLOCKS
    hfs_blocks = len(vol) // BLOCK
    total = hfs_start + hfs_blocks

    ddm = bytearray(BLOCK)
    # sbSig, sbBlkSize, sbBlkCount, sbDevType, sbDevId, sbData, sbDrvrCount,
    # ddBlock, ddSize, ddType
    struct.pack_into(">2sHIHHIHIHH", ddm, 0, b"ER", BLOCK, total, 1, 1, 0, 1,
                     DRIVER_START, drv_blocks, 1)
    count = 3
    pm = (entry(count, MAP_START, MAP_BLOCKS, "Apple", "Apple_partition_map", 0x37)
          + entry(count, DRIVER_START, DRIVER_BLOCKS, "Macintosh", "Apple_Driver", 0x7F,
                  len(drv), checksum(drv))
          + entry(count, hfs_start, hfs_blocks, "MacOS", "Apple_HFS", 0x37))
    with open(out_path, "wb") as f:
        f.write(ddm)
        f.write(pm.ljust(MAP_BLOCKS * BLOCK, b"\0"))
        f.write(drv.ljust(DRIVER_BLOCKS * BLOCK, b"\0"))
        f.write(vol)
    print(f"{out_path}: {total} blocks, driver {len(drv)} bytes at {DRIVER_START}, "
          f"HFS at {hfs_start}")


if __name__ == "__main__":
    main()
