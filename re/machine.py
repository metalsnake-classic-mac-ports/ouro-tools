"""Run routines of a classic Mac application (68k, THINK C style) in Unicorn,
without the Mac: the base for differential tests ("the original computes X
from Y; does the port compute the same?").

What it sets up, from the work layout of unpack_app.py:
  - every CODE segment at SEG_BASE + n * SEG_SIZE (segN.bin, no header)
  - the jump table above A5, resolved: each entry is `JMP abs.l target`,
    so `jsr d16(a5)` lands in the right segment
  - the application globals below A5 from DATA / ZERO / DREL (THINK C;
    see thinkc_globals.py) - other compilers lay this out differently
  - a stack, a return address that stops the emulation, an RTS stub

What it does not do: the Toolbox. A-line traps raise, with the address,
so you see which ones a routine needs; replace them with `stub_trap`
(e.g. Random) or stop the routine before it gets there. A stub that
gives condition codes (a comparison, a Boolean tested by flags) sets them
with `set_ccr`, never by writing SR: Unicorn loses such a write after a
flag-setting instruction in the same block, so the guard refuses SR
writes and the constructor checks that `set_ccr` works. Jump table
entries that draw, play sound or read the keyboard can be stubbed out
(`stub_entries`) or replaced by Python (`hook_entry`).

Typical use:

    m = Machine("work", stub_entries={601, 602})
    m.stub_random()                       # Toolbox Random as Park-Miller
    m.call(5, 0x1B54)                     # an init routine
    m.g16(-0x6546, 3)                     # poke a global
    m.call(9, 0x23FA)                     # one frame of something
    print(m.g32(-0x5396))                 # read the result

Calling conventions: THINK C pushes arguments right to left as longs
(`call`); Pascal routines push left to right and the callee pops them, a
function result slot first (`call_pascal`). Check the routine's `rtd` /
`unlk; move.l (a7)+, a0; addq.l #n, a7` and how callers push.

Needs: pip install unicorn  (python3 -I with a venv is fine)
"""
import glob
import os
import struct
import sys

from unicorn import UC_ARCH_M68K, UC_HOOK_CODE, UC_HOOK_INTR, UC_MODE_BIG_ENDIAN, Uc
from unicorn.m68k_const import (
    UC_CPU_M68K_M68020,
    UC_M68K_REG_A5,
    UC_M68K_REG_A7,
    UC_M68K_REG_D0,
    UC_M68K_REG_D1,
    UC_M68K_REG_PC,
    UC_M68K_REG_SR,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from thinkc_globals import expand  # noqa: E402

A5 = 0x800000
SEG_BASE = 0x100000
SEG_SIZE = 0x10000
STACK = 0x700000
RETURN = 0x0F0000
STUB = 0x0F1000  # RTS
FLAGS = 0x0F4000  # per condition code value: MOVE #ccr, CCR; RTS (set_ccr)
LOW_MEMORY = 0x1000  # Mac low memory globals live below this
CCR_PROBE = FLAGS + 0x800  # set_ccr's start-up check


def guard_sr(uc):
    """Refuse SR writes on this Unicorn: its m68k keeps the condition codes
    apart from SR (QEMU's lazy flags), so after a flag-setting instruction
    in the same translated block an SR written from a hook never reaches
    the next Bcc - silently: a stubbed comparison never branches (Quagmire's
    rounding read as truncation). Use Machine.set_ccr; for a deliberate SR
    write (supervisor or interrupt bits) uc.raw_sr_write. (Uc() returns an
    arch subclass, so the guard goes on the instance.)"""
    write = uc.reg_write

    def reg_write(reg_id, value):
        if reg_id == UC_M68K_REG_SR:
            raise RuntimeError("SR written through Unicorn: the condition codes may not reach the "
                               "next Bcc - use Machine.set_ccr (or uc.raw_sr_write)")
        return write(reg_id, value)

    uc.reg_write = reg_write
    uc.raw_sr_write = lambda value: write(UC_M68K_REG_SR, value)
    return uc


class Machine:
    def __init__(self, work, stub_entries=(), cpu=UC_CPU_M68K_M68020):
        self.work = work
        uc = guard_sr(Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, cpu))
        self.uc = uc
        uc.mem_map(0, LOW_MEMORY)
        uc.mem_map(RETURN, 0x2000)
        uc.mem_write(STUB, b"\x4e\x75")
        uc.mem_map(FLAGS, 0x1000)
        for ccr in range(32):
            uc.mem_write(FLAGS + 8 * ccr, struct.pack(">HHH", 0x44FC, ccr, 0x4E75))
        uc.mem_map(STACK - 0x20000, 0x20000)
        uc.mem_map(A5 - 0x40000, 0x50000)
        self.segments = {}
        for path in sorted(glob.glob(f"{work}/code/seg*.bin")):
            n = int(os.path.basename(path)[3:-4])
            code = open(path, "rb").read()
            uc.mem_map(self.address(n, 0), max(SEG_SIZE, (len(code) + 0xFFF) & ~0xFFF))
            uc.mem_write(self.address(n, 0), code)
            self.segments[n] = len(code)
        self.entries = self._jump_table(set(stub_entries))
        self._globals()
        uc.hook_add(UC_HOOK_INTR, self._on_exception)
        self.seed = 1
        self._check_set_ccr()

    def _check_set_ccr(self):
        """Make sure set_ccr works with this Unicorn: a hook at a NOP after
        a flag-setting instruction in the same block sets C, a BCS after
        it must branch (and must not with C clear). Raises otherwise, so a
        Unicorn update cannot quietly bring back the lost flags."""
        # moveq #0,d1 (C clear) / moveq #-1,d1 / nop (hook) / bcs.s +4 /
        # moveq #0,d0 / bra.s +2 / moveq #1,d0
        uc = self.uc
        for first, ccr, want in ((0x7200, 0x01, 1), (0x72FF, 0x00, 0), (0x72FF, 0x09, 1)):
            uc.mem_write(CCR_PROBE, struct.pack(">7H", first, 0x4E71, 0x6504, 0x7000, 0x6002, 0x7001, 0x4E75))
            uc.reg_write(UC_M68K_REG_D0, 9)
            uc.reg_write(UC_M68K_REG_D1, 5)
            uc.reg_write(UC_M68K_REG_A7, STACK - 0x80)
            h = uc.hook_add(UC_HOOK_CODE, lambda _uc, a, s, _: self.set_ccr(ccr), begin=CCR_PROBE + 2, end=CCR_PROBE + 2)
            try:
                uc.emu_start(CCR_PROBE, CCR_PROBE + 12, count=20)
            finally:
                uc.hook_del(h)
            got = uc.reg_read(UC_M68K_REG_D0)
            if got != want:
                raise RuntimeError(f"set_ccr does not work with this Unicorn (ccr {ccr:#x}: "
                                   f"BCS gave {got}, wanted {want}) - stubbed comparisons would be wrong")

    def address(self, segment, offset):
        return SEG_BASE + segment * SEG_SIZE + offset

    def _jump_table(self, stubbed):
        """Write the loaded jump table: [segment word][JMP abs.l target]."""
        c0 = open(f"{self.work}/rsrc/CODE_0.bin", "rb").read()
        jt_len = struct.unpack(">I", c0[8:12])[0]
        entries = []
        for k in range(jt_len // 8):
            off, _, seg, _ = struct.unpack(">HHHH", c0[16 + k * 8:24 + k * 8])
            target = STUB if k in stubbed else self.address(seg, off)
            self.uc.mem_write(A5 + 32 + 8 * k, struct.pack(">HHI", seg, 0x4EF9, target))
            entries.append((seg, off))
        return entries

    def _globals(self):
        """THINK C: DATA expanded with ZERO below A5, DREL pointers made absolute."""
        rsrc = f"{self.work}/rsrc"
        if not os.path.exists(f"{rsrc}/DATA_0.bin"):
            return
        data = open(f"{rsrc}/DATA_0.bin", "rb").read()
        zero = open(f"{rsrc}/ZERO_0.bin", "rb").read()
        g = bytearray(expand(data, zero))
        if os.path.exists(f"{rsrc}/DREL_0.bin"):
            drel = open(f"{rsrc}/DREL_0.bin", "rb").read()
            for i in range(0, len(drel), 2):
                at = len(g) + struct.unpack(">h", drel[i:i + 2])[0]
                v = struct.unpack(">I", g[at:at + 4])[0]
                g[at:at + 4] = struct.pack(">I", (v + A5) & 0xFFFFFFFF)
        self.uc.mem_write(A5 - len(g), bytes(g))

    def entry_offset(self, k):
        """The A5 offset `jsr d16(a5)` uses for jump table entry k."""
        return 32 + 8 * k + 2

    def _on_exception(self, uc, number, _):
        pc = uc.reg_read(UC_M68K_REG_PC)
        word = struct.unpack(">H", uc.mem_read(pc, 2))[0] if pc else 0
        raise RuntimeError(f"exception {number} at {pc:#x} (word {word:04x}): "
                           "an A-line trap means a Toolbox call - stub it or stop earlier")

    # --- replacing the Mac -------------------------------------------------

    def stub_trap(self, segment, offset, handler):
        """Replace the A-line trap at (segment, offset) by a NOP and call
        handler(machine) there instead (it reads/writes the stack itself)."""
        addr = self.address(segment, offset)
        word = self.uc.mem_read(addr, 2)
        assert word[0] & 0xF0 == 0xA0, f"no A-line trap at {addr:#x}: {word.hex()}"
        self.uc.mem_write(addr, b"\x4e\x71")
        self.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, _: handler(self), begin=addr, end=addr)

    def set_ccr(self, ccr):
        """From a stub_trap handler: the condition codes (X N Z V C, bits
        4-0) the code after the trap sees. Writing SR from a hook does not
        do it: Unicorn's m68k keeps the flags apart from SR (QEMU's lazy
        flags), so a Bcc after the hook would test the old ones - SANE
        comparisons then never branch. Instead the hook goes through MOVE
        #ccr, CCR; RTS, with the address after the trap pushed for the RTS.
        Call it last in the handler, after any stack changes."""
        pc = self.uc.reg_read(UC_M68K_REG_PC)
        sp = self.uc.reg_read(UC_M68K_REG_A7) - 4
        self.uc.mem_write(sp, struct.pack(">I", pc + 2))
        self.uc.reg_write(UC_M68K_REG_A7, sp)
        self.uc.reg_write(UC_M68K_REG_PC, FLAGS + 8 * (ccr & 0x1F))

    def stub_random(self, sites=None):
        """Toolbox Random (A861) as on a real Mac: Park-Miller with the seed
        in self.seed (QuickDraw randSeed starts at 1); the result word goes on
        the stack. sites: (segment, offset) list, default: every A861 at an
        even offset - check those with disasm.py first, data tables can hold
        the same bytes, and patching them corrupts the data."""
        if sites is None:
            sites = [(n, i) for n in self.segments for i in self.find(n, b"\xa8\x61")]

        def random(m):
            m.seed = m.seed * 16807 % 0x7FFFFFFF
            value = m.seed & 0xFFFF
            if value == 0x8000:
                value = 0
            m.uc.mem_write(m.uc.reg_read(UC_M68K_REG_A7), struct.pack(">H", value))

        for segment, offset in sites:
            self.stub_trap(segment, offset, random)

    def hook_entry(self, k, handler):
        """Run handler(machine) instead of jump table entry k, then return
        (each entry gets its own RTS, so hooks do not fire for each other)."""
        stub = STUB + 0x10 + 2 * k
        self.uc.mem_write(stub, b"\x4e\x75")
        self.uc.mem_write(A5 + 32 + 8 * k, struct.pack(">HHI", 0, 0x4EF9, stub))
        self.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, _: handler(self), begin=stub, end=stub)

    def find(self, segment, pattern):
        """Even offsets of a byte pattern in a segment (a linear search can
        hit data; check the hits with disasm.py)."""
        code = self.uc.mem_read(self.address(segment, 0), self.segments[segment])
        hits, i = [], code.find(pattern)
        while i != -1:
            if i % 2 == 0:
                hits.append(i)
            i = code.find(pattern, i + 1)
        return hits

    # --- running -----------------------------------------------------------

    def call(self, segment, offset, *args, count=50_000_000):
        """Call a C routine: long arguments, right to left; returns d0."""
        sp = STACK - 0x100
        frame = struct.pack(">I", RETURN) + b"".join(struct.pack(">i", a) for a in args)
        sp -= len(frame)
        self.uc.mem_write(sp, frame)
        self.uc.reg_write(UC_M68K_REG_A7, sp)
        self.uc.reg_write(UC_M68K_REG_A5, A5)
        self.uc.emu_start(self.address(segment, offset), RETURN, count=count)
        return self.uc.reg_read(UC_M68K_REG_D0)

    def call_pascal(self, segment, offset, args, result=0, count=50_000_000):
        """Call a Pascal routine: args is a list of (format, value) pushed left
        to right (e.g. (">h", 3), (">I", ptr)); result is the size of the
        function result slot pushed first (0, 2 or 4). Returns the slot."""
        payload = b"".join(struct.pack(f, v) for f, v in reversed(args))
        sp = STACK - 0x100 - result
        frame = struct.pack(">I", RETURN) + payload
        sp -= len(frame)
        self.uc.mem_write(sp, frame)
        self.uc.reg_write(UC_M68K_REG_A7, sp)
        self.uc.reg_write(UC_M68K_REG_A5, A5)
        self.uc.emu_start(self.address(segment, offset), RETURN, count=count)
        return bytes(self.uc.mem_read(STACK - 0x100 - result, result)) if result else None

    # --- globals -----------------------------------------------------------

    def g8(self, off, value=None):
        return self._global(off, ">b", value)

    def g16(self, off, value=None):
        return self._global(off, ">h", value)

    def g32(self, off, value=None):
        return self._global(off, ">i", value)

    def _global(self, off, fmt, value):
        size = struct.calcsize(fmt)
        if value is None:
            return struct.unpack(fmt, self.uc.mem_read(A5 + off, size))[0]
        self.uc.mem_write(A5 + off, struct.pack(fmt, value))
        return value

    def read(self, off, size):
        return bytes(self.uc.mem_read(A5 + off, size))

    def write(self, off, data):
        self.uc.mem_write(A5 + off, bytes(data))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 machine.py <work dir>   (loads it and prints a summary)")
    m = Machine(sys.argv[1])
    print(f"{len(m.segments)} segments, {len(m.entries)} jump table entries, A5 = {A5:#x}")
