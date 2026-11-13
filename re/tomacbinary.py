"""A macOS file with resource fork and Finder info (as `unar -forks fork`
writes them) -> MacBinary II, which hfsutils' `hcopy -m` puts onto an HFS
disk with type, creator and both forks.

Usage: python3 -I tomacbinary.py <file> <out.bin> [mac name]
"""
import os
import struct
import subprocess
import sys


def crc16(data):
    """CRC-16/XMODEM, as MacBinary II uses it for the header."""
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc


def macbinary(path, name=None):
    data = open(path, "rb").read()
    rsrc_path = path + "/..namedfork/rsrc"
    rsrc = open(rsrc_path, "rb").read() if os.path.exists(rsrc_path) else b""
    out = subprocess.run(["xattr", "-px", "com.apple.FinderInfo", path],
                         capture_output=True, text=True)
    info = bytes.fromhex("".join(out.stdout.split())) if out.returncode == 0 else bytes(32)
    n = (name or os.path.basename(path)).encode("mac_roman")[:63]
    h = bytearray(128)
    h[1] = len(n)
    h[2:2 + len(n)] = n
    h[65:73] = info[0:8]  # type, creator
    h[73] = info[8]  # Finder flags (high byte)
    h[83:87] = struct.pack(">I", len(data))
    h[87:91] = struct.pack(">I", len(rsrc))
    h[101] = info[9]  # Finder flags (low byte)
    h[122] = h[123] = 0x81  # MacBinary II
    h[124:126] = struct.pack(">H", crc16(h[:124]))

    def pad(b):
        return b + bytes(-len(b) % 128)
    return bytes(h) + pad(data) + pad(rsrc)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    open(sys.argv[2], "wb").write(macbinary(sys.argv[1], sys.argv[3] if len(sys.argv) == 4 else None))
