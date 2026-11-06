"""Unpack a classic Mac application into the work layout the other scripts
use:

    <work>/rsrc/TYPE_ID.bin     every resource (type with non-alphanumerics
                                as "_", e.g. "snd " -> snd__100.bin)
    <work>/code/segNN.bin       CODE n (n >= 1) without its 4-byte header,
                                so offsets match the jump table
    <work>/resources.txt        type, id, size, name of every resource

CODE 0 (the jump table) stays as rsrc/CODE_0.bin.

The input is the application as
  - MacBinary (e.g. from `hcopy -m` out of a disk image),
  - a file holding only the resource fork (raw), or
  - on macOS a file with a resource fork (read via FILE/..namedfork/rsrc).

For an HFS disk image, copy the application out first (hfsutils):
    cp game.dsk /tmp/copy.dsk && hmount /tmp/copy.dsk && hls -l
    hcopy -m ":Game App" app.bin && humount
(work on a copy: hmount can change the image.)

Usage: python3 unpack_app.py <app> <work dir>
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from macres import parse, safe  # noqa: E402


def read_fork(path):
    data = open(path, "rb").read()
    # MacBinary: byte 0 is 0, name length 1..63, zero at 74 and 82
    if len(data) > 128 and data[0] == 0 and 1 <= data[1] <= 63 and data[74] == 0 and data[82] == 0:
        data_len, rsrc_len = struct.unpack(">II", data[83:91])
        start = 128 + ((data_len + 127) // 128) * 128
        if 0 < rsrc_len and start + rsrc_len <= len(data):
            return data[start:start + rsrc_len], "MacBinary"
    try:
        fork = open(os.path.join(path, "..namedfork", "rsrc"), "rb").read()
        if fork:
            return fork, "resource fork"
    except OSError:
        pass
    return data, "raw resource fork"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    app, work = sys.argv[1], sys.argv[2]
    fork, kind = read_fork(app)
    resources = parse(fork)
    os.makedirs(f"{work}/rsrc", exist_ok=True)
    os.makedirs(f"{work}/code", exist_ok=True)
    lines = []
    for rtype, rid, name, data in sorted(resources, key=lambda r: (r[0], r[1])):
        with open(f"{work}/rsrc/{safe(rtype)}_{rid}.bin", "wb") as f:
            f.write(data)
        if rtype == "CODE" and rid > 0:
            with open(f"{work}/code/seg{rid:02d}.bin", "wb") as f:
                f.write(data[4:])
        lines.append(f"{rtype!r:8} {rid:6} {len(data):8}  {name}")
    with open(f"{work}/resources.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{app}: {kind}, {len(resources)} resources -> {work}")


if __name__ == "__main__":
    main()
