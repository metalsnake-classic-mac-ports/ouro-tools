"""Run a routine of two 68k applications built from the same code (a game
and its sequel, two versions) in lockstep, instruction by instruction, on
the same random data, and report where they part: the evidence that a
routine the routine map (routine_map.py) calls "same" or "constants only"
behaves the same, so a port can share it.

Each run starts both machines (machine.Machine) at the routine with an
empty call frame. Memory is filled lazily: the first time routine A reads
a byte it has not written, it gets a random value; routine B's read in the
same step (the k-th read of the step pairs with A's k-th) gets the same
value at its own address. So tables at other addresses or with other
record sizes in B are covered by the pairing itself - B's code computes its
addresses, A's data goes there. The arguments above the return address
are random the same way. Code, the jump table and the return address are
never filled.

Compared per step: the instruction (mnemonic and operand shape, numbers
masked), the size and value of every write (a 4-byte value pointing into
code, the A5 world or the stack only by what it points into: return
addresses, `pea` of a global). Not compared: registers and
addresses (they may differ by layout). Random values: 0, -1, small and medium numbers, any 16/32 bits, a fresh
pointer for 4 bytes, and often the routine's own immediates (± 1), so
branches on exact sub-states are taken. A run ends when both return, at
a difference, when both fault at the same step (a random pointer into
nowhere: counted apart, not a difference; when only one does on a memory
access, "one memory fault": the layouts put a random pointer's target at a
region's edge on one side - counted and shown, not a difference in logic), or after `steps` instructions
(counted apart: a loop over a random count).

Toolbox traps: give each machine its stubs before (stub_trap / a port's
toolbox.install). A stub's reads and writes through uc.mem_read /
mem_write are routed through the same fill and comparison as the CPU's
(SectRect reads both rects, SetRect's write is compared).

Use:
    from lockstep import compare
    report = compare(ma, (5, 0x5e7a), mb, (5, 0x6336), runs=500, seed=1)
    print(report)

Needs unicorn and capstone; machine.py next to it.
"""
import os
import random
import re
import struct
import sys

import capstone
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_UNMAPPED, UC_HOOK_MEM_WRITE, UC_PROT_ALL
from unicorn.m68k_const import (UC_M68K_REG_A0, UC_M68K_REG_A5, UC_M68K_REG_A7, UC_M68K_REG_D0,
                                UC_M68K_REG_PC)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine import A5, RETURN, SEG_BASE, STACK  # noqa: E402

MD = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_020 | capstone.CS_MODE_BIG_ENDIAN)
NUM = re.compile(r"-?\$?[0-9a-f]+\b")


def shape(uc, pc):
    """The instruction at pc, numbers masked."""
    code = bytes(uc.mem_read(pc, 10))
    if code[0] & 0xF0 == 0xA0:
        return f"trap {code[:2].hex()}"
    ins = next(MD.disasm(code, pc, count=1), None)
    if ins is None:
        return f"dc.w {code[:2].hex()}"
    if ins.mnemonic == "nop":
        return "nop"   # a stubbed trap is a NOP in both
    if ins.mnemonic in ("jsr", "bsr.b", "bsr.w", "bsr"):
        return "call"  # pc-relative in one, through the jump table in the other
    return f"{ins.mnemonic} {NUM.sub('N', ins.op_str)}"


def where(m, pc):
    for n, size in m.segments.items():
        base = m.address(n, 0)
        if base <= pc < base + size:
            return f"{n}:{pc - base:#x}"
    return f"{pc:#x}"


class Side:
    def __init__(self, m):
        self.m = m
        if not hasattr(m, "lazy_pages"):
            m.lazy_pages = set()
        self.owned = set()       # bytes written by the routine (or the frame)
        self.reads = []          # this step: (address, size)
        self.writes = []         # this step: (address, size, value)
        self.fill = None         # this step: function(k, address, size) -> bytes or None
        self.unpaired = False    # this step read memory it may not fill
        self.pair = None         # B: A's reads of this step
        self.tainted = False     # B read unpaired memory in an earlier step of this run
        self.first_mismatch = None
        self.code = [(m.address(n, 0), m.address(n, 0) + s) for n, s in m.segments.items()]
        self.hooks = [
            m.uc.hook_add(UC_HOOK_MEM_READ, self._read),
            m.uc.hook_add(UC_HOOK_MEM_WRITE, self._write),
            m.uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._unmapped),
        ]
        # a trap's Python stub reads and writes through the API: route
        # those through the same fill and comparison as the CPU's accesses
        uc = m.uc
        self._mem_read, self._mem_write = uc.mem_read, uc.mem_write
        self.stepping = False

        def map_pages(a, size):
            for page in range(a & ~0xFFF, (a + size + 0xFFF) & ~0xFFF, 0x1000):
                try:
                    self._mem_read(page, 1)
                except Exception:
                    self._unmapped(uc, 0, page, 1, 0, None)

        def mem_read(a, size):
            if self.stepping:
                map_pages(a, size)
                self._read(uc, 0, a, size, 0, None)
            return self._mem_read(a, size)

        def mem_write(a, data):
            if self.stepping:
                map_pages(a, len(data))
                self._write(uc, 0, a, len(data), int.from_bytes(bytes(data), "big"), None)
            return self._mem_write(a, data)

        uc.mem_read, uc.mem_write = mem_read, mem_write

    def fillable(self, a):
        if a < 0x100 or RETURN <= a < RETURN + 0x8000:
            return False
        if A5 <= a < A5 + 32 + 8 * len(self.m.entries):   # application parameters, jump table
            return False
        return not any(lo <= a < hi for lo, hi in self.code)

    def _read(self, uc, access, a, size, value, _):
        if any(lo <= a < hi for lo, hi in self.code):
            return   # code: an instruction fetch (Unicorn reports them after code was written) or a table in it
        k = len(self.reads)
        self.reads.append((a, size, None, False))
        if self.fill and not self.fillable(a):
            self.unpaired = True
        if self.pair is not None:
            mine = any(a + i in self.owned for i in range(size))
            if k >= len(self.pair) or self.pair[k][3] != mine:
                self.unpaired = True    # one side reads what it wrote, the other not: an index off its table
        if self.fill and self.fillable(a):
            data = self.fill(k, a, size)
            if data is not None:
                mine = [i for i in range(size) if a + i in self.owned]
                if mine:
                    old = bytes(self._mem_read(a, size))
                    data = bytes(old[i] if i in mine else data[i] for i in range(size))
                self._mem_write(a, data)
        self.reads[k] = (a, size, bytes(self._mem_read(a, size)), any(a + i in self.owned for i in range(size)))
        if self.pair is not None and k < len(self.pair) and self.pair[k][2] != self.reads[k][2] and self.first_mismatch is None:
            self.first_mismatch = (hex(self.pair[k][0]), hex(a), self.pair[k][2].hex(), self.reads[k][2].hex(),
                                   self.pair[k][3], self.reads[k][3], self.fillable(a))

    def _write(self, uc, access, a, size, value, _):
        self.writes.append((a, size, value & ((1 << (8 * size)) - 1)))
        self.owned.update(range(a, a + size))

    def _unmapped(self, uc, access, a, size, value, _):
        ok = False
        for page in range(a & ~0xFFF, (a + size + 0xFFF) & ~0xFFF, 0x1000):
            if page >= 0x100000000:
                break
            try:
                uc.mem_map(page, 0x1000, UC_PROT_ALL)
                self.m.lazy_pages.add(page)
                ok = True
            except Exception:
                ok = ok or page in self.m.lazy_pages
        return ok

    def close(self):
        for h in self.hooks:
            self.m.uc.hook_del(h)
        del self.m.uc.mem_read, self.m.uc.mem_write   # back to the class's methods


def kind(m, size, v):
    """A written value as compared: pointers (4 bytes into or near code,
    the A5 world, the stack or a page mapped for a random pointer) by what
    they point into - their numbers differ by layout (another record size
    moves a field) - everything else as it is."""
    if size == 4:
        for n, length in m.segments.items():
            if m.address(n, 0) <= v < m.address(n, 0) + length:
                return "code pointer"
        if A5 - 0x40000 <= v < A5 + 0x10000:
            return "A5 pointer"
        if STACK - 0x20000 <= v < STACK:
            return "stack pointer"
        if any(p - 0x10000 <= v < p + 0x11000 for p in getattr(m, "lazy_pages", ())):
            return "pointer"
    return v


def start(m, at):
    """An empty Pascal call frame: the return address only."""
    sp = STACK - 0x400
    m.uc.mem_write(sp, struct.pack(">I", RETURN))
    for r in range(8):
        m.uc.reg_write(UC_M68K_REG_D0 + r, 0)
    for r in range(5):
        m.uc.reg_write(UC_M68K_REG_A0 + r, 0)
    m.uc.reg_write(UC_M68K_REG_A7, sp)
    m.uc.reg_write(UC_M68K_REG_A5, A5)
    m.uc.reg_write(UC_M68K_REG_PC, m.address(*at))
    return sp


HEAP = 0x01000000   # random pointers point into fresh blocks from here, 64 KB apart


def value(rng, size, blocks=None, consts=()):
    if consts and rng.random() < 0.3:
        v = rng.choice(consts) + rng.choice((0, 0, 0, -1, 1))
        return (v & ((1 << (8 * size)) - 1)).to_bytes(size, "big")
    if size == 4 and blocks is not None and rng.random() < 0.4:
        blocks[0] += 1
        return (HEAP + 0x10000 * blocks[0] + 0x100).to_bytes(4, "big")
    pick = rng.random()
    if pick < 0.25:
        v = 0
    elif pick < 0.35:
        v = (1 << (8 * size)) - 1                 # -1
    elif pick < 0.6:
        v = rng.randint(1, 12)
    elif pick < 0.85:
        v = rng.randint(0, 700)
    else:
        v = rng.getrandbits(8 * size)
    return (v & ((1 << (8 * size)) - 1)).to_bytes(size, "big")


def run(ma, at_a, mb, at_b, rng, steps, setup=None, stubs=(), consts=()):
    """One run; returns (status, detail, executed A addresses). stubs:
    ((segment, offset) in A, (segment, offset) in B, argument bytes) - a
    callee pair known to differ, returned from at once in both (Pascal:
    the return address and the arguments popped, nothing written), so the
    runs go on past it."""
    stub_at = {(ma.address(*a), mb.address(*b)): n for a, b, n in stubs}
    sa, sb = Side(ma), Side(mb)
    # pages mapped for random pointers in earlier runs: the same in both
    for m, other in ((ma, mb), (mb, ma)):
        for page in sorted(other.lazy_pages - m.lazy_pages):
            try:
                m.uc.mem_map(page, 0x1000, UC_PROT_ALL)
                m.lazy_pages.add(page)
            except Exception:
                pass
    done = set()
    try:
        for side, at in ((sa, at_a), (sb, at_b)):
            sp = start(side.m, at)
            side.owned.update(range(sp, sp + 4))
        if setup:
            setup(ma, mb, rng)
        filled = {}
        blocks = [0]

        def fill_a(k, a, size):
            if all(a + i in filled for i in range(size)):
                return None
            data = value(rng, size, blocks, consts)
            for i in range(size):
                filled[a + i] = data[i]
            return data

        sa.fill = fill_a
        for n in range(steps):
            pa = ma.uc.reg_read(UC_M68K_REG_PC)
            pb = mb.uc.reg_read(UC_M68K_REG_PC)
            if pa == RETURN or pb == RETURN:
                if pa != pb:
                    return "differ", f"one returned: A at {where(ma, pa)}, B at {where(mb, pb)}", done
                return "same", "", done
            jumped = False
            for m, side in ((ma, sa), (mb, sb)):
                pc = m.uc.reg_read(UC_M68K_REG_PC)
                if A5 + 32 <= pc < A5 + 32 + 8 * len(m.entries):   # a jump table entry: its JMP
                    side.fill, keep = None, side.fill
                    m.uc.emu_start(pc, 0xFFFFFFFF, count=1)
                    side.fill = keep
                    jumped = True
            if jumped:
                continue
            if (pa, pb) in stub_at:
                for m in (ma, mb):
                    sp = m.uc.reg_read(UC_M68K_REG_A7)
                    ret = struct.unpack(">I", m.uc.mem_read(sp, 4))[0]
                    m.uc.reg_write(UC_M68K_REG_A7, sp + 4 + stub_at[(pa, pb)])
                    m.uc.reg_write(UC_M68K_REG_PC, ret)
                continue
            ka, kb = shape(ma.uc, pa), shape(mb.uc, pb)
            if ka != kb and sb.tainted:
                return "layout", f"step {n}: {where(ma, pa)} / {where(mb, pb)}: B read outside the memory filled before", done
            if ka != kb:
                return "differ", f"step {n}: A {where(ma, pa)} {ka} / B {where(mb, pb)} {kb}", done
            done.add(pa)
            sa.reads, sa.writes, sb.reads, sb.writes = [], [], [], []
            fault_a = None
            sa.stepping = True
            try:
                ma.uc.emu_start(pa, 0xFFFFFFFF, count=1)
            except Exception as e:
                fault_a = e
            sa.stepping = False
            got = list(sa.reads)

            def fill_b(k, a, size, got=got):
                if k < len(got) and got[k][1] == size:
                    return got[k][2]
                return None

            sb.tainted = sb.tainted or sb.unpaired
            sb.unpaired = False

            sb.fill = fill_b
            sb.pair = got
            fault_b = None
            sb.stepping = True
            try:
                mb.uc.emu_start(pb, 0xFFFFFFFF, count=1)
            except Exception as e:
                fault_b = e
            sb.stepping = False
            if fault_a or fault_b:
                if (fault_a is None) != (fault_b is None) and (sb.tainted or sb.unpaired):
                    return "layout", f"step {n}: one faults after B read outside the memory filled", done
                if fault_a and fault_b:
                    return "both fault", f"{where(ma, pa)}: {fault_a}", done
                if "UC_ERR_" in str(fault_a or fault_b) and ("MAP" in str(fault_a or fault_b) or "UNMAPPED" in str(fault_a or fault_b)):
                    return "one memory fault", f"step {n}: only {'A' if fault_a else 'B'} faults at {where(ma, pa)} / {where(mb, pb)}: {fault_a or fault_b} (a random pointer at a region's edge, the layouts differing)", done
                return "differ", f"step {n}: only {'A' if fault_a else 'B'} faults at {where(ma, pa)} / {where(mb, pb)}: {fault_a or fault_b}", done
            if ka.startswith(("pea", "call")):
                wa = [(s, "address") for _, s, v in sa.writes]
                wb = [(s, "address") for _, s, v in sb.writes]
            else:
                wa = [(s, v) for _, s, v in sa.writes]
                wb = [(s, v) for _, s, v in sb.writes]
                if wa != wb:
                    wa = [(s, kind(ma, s, v)) for _, s, v in sa.writes]
                    wb = [(s, kind(mb, s, v)) for _, s, v in sb.writes]
            if wa != wb and (sb.unpaired or sb.tainted):
                return "layout", f"step {n}: {where(ma, pa)} / {where(mb, pb)}: B read outside the memory filled (an index past its table)", done
            if wa != wb:
                if os.environ.get("LOCKSTEP_DEBUG"):
                    print("  first read mismatch (A addr, B addr, A val, B val, A owned, B owned, B fillable):", sb.first_mismatch, file=sys.stderr)
                    print("  A reads", [(hex(a), s, d.hex(), o) for a, s, d, o in sa.reads], file=sys.stderr)
                    print("  B reads", [(hex(a), s, d.hex(), o) for a, s, d, o in sb.reads], file=sys.stderr)
                return "differ", f"step {n}: {where(ma, pa)} / {where(mb, pb)} {ka}: writes A {wa} B {wb}", done
        return "long", f"{steps} steps", done
    finally:
        sa.close()
        sb.close()


def _in_routine(ma, detail, at_a):
    """Is A's address in a difference's detail inside the routine (from its
    start to the next routine start: same segment, at or after it, before
    the next `link a6`)?"""
    m = re.search(r"A (\d+):(0x[0-9a-f]+)|: (\d+):(0x[0-9a-f]+) /", detail)
    if not m:
        return True
    seg = int(m.group(1) or m.group(3))
    off = int(m.group(2) or m.group(4), 16)
    if seg != at_a[0] or off < at_a[1]:
        return False
    code = bytes(ma.uc.mem_read(ma.address(seg, 0), ma.segments[seg]))
    nxt = code.find(b"\x4e\x56", at_a[1] + 2)
    while nxt != -1 and nxt % 2:
        nxt = code.find(b"\x4e\x56", nxt + 1)
    return off < (nxt if nxt != -1 else len(code))


def routine_end(m, at):
    seg, start = at
    code = bytes(m.uc.mem_read(m.address(seg, 0), m.segments[seg]))
    end = code.find(b"\x4e\x56", start + 2)
    while end != -1 and end % 2:
        end = code.find(b"\x4e\x56", end + 1)
    return code, (end if end != -1 else len(code))


def routine_constants(m, at):
    """The immediates the routine compares with or uses (sub-states, limits):
    the fill picks them often, so the branches on exact values are taken."""
    code, end = routine_end(m, at)
    out = set()
    for ins in MD.disasm(code[at[1]:end], at[1]):
        for v in re.findall(r"#\$?(-?[0-9a-f]+)", ins.op_str):
            n = int(v, 16) if "$" in ins.op_str else int(v)
            if -0x8000 <= n < 0x10000:
                out.add(n)
    return sorted(out)


def compare(ma, at_a, mb, at_b, runs=300, seed=1, steps=20000, setup=None, reset=None, stubs=()):
    """Lockstep runs of the routine at at_a in ma and at_b in mb. reset(ma,
    mb) before each run (default: nothing - memory carries over, which is
    fine: every read is filled anew unless the routine wrote it this run).
    Returns a report dict: counts per status, the first details, coverage
    of A's routine (addresses executed)."""
    rng = random.Random(seed)
    counts = {}
    details = []
    lo_a = ma.address(*at_a)
    consts = routine_constants(ma, at_a)
    done = set()
    for _ in range(runs):
        if reset:
            reset(ma, mb)
        status, detail, ex = run(ma, at_a, mb, at_b, rng, steps, setup, stubs, consts)
        if status == "differ" and detail.startswith("step") and not _in_routine(ma, detail, at_a):
            status = "differ in a callee"
        counts[status] = counts.get(status, 0) + 1
        if detail and status not in ("long", "both fault"):
            details.append((not status.startswith("differ"), detail))
        done |= ex
    seg, start = at_a
    code = bytes(ma.uc.mem_read(ma.address(seg, 0), ma.segments[seg]))
    end = code.find(b"\x4e\x56", start + 2)
    while end != -1 and end % 2:
        end = code.find(b"\x4e\x56", end + 1)
    end = end if end != -1 else len(code)
    total = 0
    at = start
    for ins in MD.disasm(code[start:end], ma.address(seg, start)):
        total += 1
    own = sorted(a for a in done if lo_a <= a < ma.address(seg, end))
    details = [d for _, d in sorted(details, key=lambda x: x[0])][:5]
    return {"counts": counts, "details": details, "executed": len(done), "in_routine": len(own),
            "routine_instructions": total}
