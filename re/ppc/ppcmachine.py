"""Run routines of a PowerPC (PEF, CodeWarrior) build in Unicorn.

The PPC counterpart of machine.py (68k). Memory layout as Ghidra loads
the PEF (run_ghidra.sh must have run; the work folder holds the .pef,
traceback.txt, data.bin, imports.txt and toc.txt):
  0x10000000  code section
  after it    data section, unpacked and relocated (data.bin), then bss
  after it    imports: one word per imported Toolbox routine (imports.txt)
  0x20000000  stubs: each import's word points to its own stub; a hook
              runs the Python implementation (or fails if there is none)
  0x30000000  heap (NewPtr / NewHandle), 0x3f000000 stack
CodeWarrior calls an import through glue: r12 = TOC slot (the import's
word), ctr = *r12, r2 = *(r12 + 4), bctr; the caller reloads r2 from
0x14(r1) afterwards. A stub only has to set r3 and return to LR.

Usage:
    m = Machine("re/work/ppc")              # names.txt next to it: extra names
    m.stub("SetRect", m.toolbox_setrect)    # most common ones are built in
    m.call("InitTileHotRects")
    m.read(addr, n)
"""
import os
import struct
import sys

from unicorn import Uc, UcError, UC_ARCH_PPC, UC_MODE_PPC32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.ppc_const import UC_PPC_REG_LR, UC_PPC_REG_PC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pef_traceback import code_section, find_pef, read_toc, BASE  # noqa: E402

STUBS = 0x20000000
HEAP = 0x30000000
STACK_TOP = 0x3f000000
RETURN = 0x0fff0000             # LR of the outermost call: stops emulation


def reg(n):
    from unicorn import ppc_const
    return getattr(ppc_const, f"UC_PPC_REG_{n}")


R = [reg(i) for i in range(32)]


class Machine:
    def __init__(self, ppc_dir):
        self.dir = ppc_dir
        pef = open(find_pef(ppc_dir), "rb").read()
        self.toc = read_toc(ppc_dir)
        code = code_section(pef)
        raw = open(os.path.join(ppc_dir, "data.bin"), "rb").read()
        dbase = struct.unpack(">I", raw[:4])[0]
        data = raw[4:]
        self.uc = uc = Uc(UC_ARCH_PPC, UC_MODE_PPC32 | UC_MODE_BIG_ENDIAN)
        from unicorn import ppc_const
        uc.ctl_set_cpu_model(ppc_const.UC_CPU_PPC32_750_V3_1)   # a G3, with FPU
        last_import = max(int(line.split()[0], 16) for line in open(os.path.join(ppc_dir, "imports.txt")))
        uc.mem_map(BASE, (last_import + 4 - BASE + 0xffff) & ~0xffff)    # code + data + bss + imports
        uc.mem_write(BASE, code)
        uc.mem_write(dbase, data)
        self.names = {}
        for line in open(os.path.join(ppc_dir, "traceback.txt")):
            a, _, n = line.split()
            self.names[n.lstrip(".")] = int(a, 16)
        extra = os.path.join(ppc_dir, "names.txt")     # names of routines without traceback
        if os.path.exists(extra):
            for line in open(extra):
                if line.strip() and not line.startswith("#"):
                    a, _, n = line.split()
                    self.names[n] = int(a, 16)
        # imports -> stubs
        self.imports = {}                               # stub address -> name
        uc.mem_map(STUBS, 0x10000)
        for k, line in enumerate(open(os.path.join(ppc_dir, "imports.txt"))):
            a, full = line.split()
            name = full.split("::")[-1]
            stub = STUBS + 4 * k
            uc.mem_write(int(a, 16), struct.pack(">I", stub))
            uc.mem_write(stub, b"\x4e\x80\x00\x20")    # blr
            self.imports[stub] = name
        self.impl = {}
        uc.mem_map(HEAP, 0x01000000)
        self.heap = HEAP
        uc.mem_map(STACK_TOP - 0x100000, 0x100000)
        uc.mem_map(RETURN, 0x1000)
        uc.hook_add(UC_HOOK_CODE, self._stub_hook, begin=STUBS, end=STUBS + 0xffff)
        self.rand_seed = 1
        self.regions = {}
        self.hsize = {}
        self.gworld = 0
        self.ticks = 0
        self.trace_calls = False
        for n, f in (("SetRect", self.tb_setrect), ("Random", self.tb_random),
                     ("TickCount", self.tb_tickcount), ("SectRect", self.tb_sectrect), ("PtInRect", self.tb_ptinrect), ("NewRgn", self.tb_newrgn),
                     ("CopyRgn", self.tb_copyrgn), ("OffsetRgn", self.tb_offsetrgn), ("SectRgn", self.tb_sectrgn),
                     ("EmptyRgn", self.tb_emptyrgn), ("DisposeRgn", self.tb_disposergn),
                     ("NewGWorld", self.tb_newgworld), ("GetGWorldPixMap", self.tb_getgworldpixmap),
                     ("GetPixBaseAddr", self.tb_getpixbaseaddr), ("SetGWorld", self.tb_setgworld),
                     ("GetGWorld", self.tb_getgworld), ("EraseRect", self.tb_eraserect),
                     ("BitMapToRegion", self.tb_bitmaptoregion), ("LockPixels", self.tb_nop),
                     ("UnlockPixels", self.tb_nop), ("DisposeGWorld", self.tb_nop), ("OffsetRect", self.tb_offsetrect), ("SetPt", self.tb_setpt),
                     ("NewPtr", self.tb_newptr), ("NewPtrClear", self.tb_newptr),
                     ("NewHandle", self.tb_newhandle), ("NewHandleClear", self.tb_newhandle),
                     ("HLock", self.tb_nop), ("HUnlock", self.tb_nop), ("MoveHHi", self.tb_nop),
                     ("HLockHi", self.tb_nop), ("PtrToHand", self.tb_ptrtohand), ("GetHandleSize", self.tb_gethandlesize),
                     ("Munger", self.tb_munger), ("BlockMoveData", self.tb_blockmove), ("BlockMove", self.tb_blockmove),
                     ("DisposeHandle", self.tb_nop)):
            self.stub(n, f)

    # --- memory ---
    def read(self, a, n):
        return bytes(self.uc.mem_read(a, n))

    def write(self, a, b):
        self.uc.mem_write(a, bytes(b))

    def r16(self, a):
        return struct.unpack(">h", self.read(a, 2))[0]

    def r32(self, a):
        return struct.unpack(">I", self.read(a, 4))[0]

    def w16(self, a, v):
        self.write(a, struct.pack(">H", v & 0xFFFF))

    def w32(self, a, v):
        self.write(a, struct.pack(">I", v & 0xffffffff))

    def toc_slot(self, off):
        """Value of the TOC slot at r2 + off (off negative)."""
        return self.r32(self.toc + off)

    def alloc(self, n, clear=True):
        a = self.heap
        self.heap += (n + 15) & ~15
        if clear:
            self.write(a, bytes(n))
        return a

    def glob(self, slot):
        """Address a TOC slot points to (CodeWarrior reaches globals this way)."""
        return self.r32(slot)

    def stub_routine(self, f, result=0, log=None):
        """Make a routine of the game return at once with r3 = result
        (a value, or a function of the machine returning one). A later
        stub of the same routine replaces the earlier one.
        log: a list that receives (name, r3, r4, r5, r6) for every call."""
        a = self.addr(f)
        stubs = self.__dict__.setdefault("_stubs", {})
        if a in stubs:
            self.uc.hook_del(stubs.pop(a))
        name = f if isinstance(f, str) else hex(f)

        def hook(uc, address, size, _):
            if log is not None:
                log.append((name,) + tuple(self.get(i) for i in range(3, 7)))
            self.set(3, result(self) if callable(result) else result)
            uc.reg_write(UC_PPC_REG_PC, uc.reg_read(UC_PPC_REG_LR))

        stubs[a] = self.uc.hook_add(UC_HOOK_CODE, hook, begin=a, end=a)

    # --- registers ---
    def get(self, i):
        return self.uc.reg_read(R[i])

    def set(self, i, v):
        self.uc.reg_write(R[i], v & 0xffffffff)

    # --- Toolbox stubs ---
    def stub(self, name, fn):
        self.impl[name] = fn

    def _stub_hook(self, uc, address, size, _):
        name = self.imports.get(address)
        if name not in self.impl:
            uc.emu_stop()
            self.missing = name
            return
        if self.trace_calls:
            print(f"  toolbox {name}({', '.join(hex(self.get(i)) for i in range(3, 8))})")
        res = self.impl[name]()
        if res is not None:
            self.set(3, res)

    def tb_nop(self):
        return None

    def tb_setrect(self):
        r, left, top, right, bottom = (self.get(i) for i in range(3, 8))
        s16 = lambda v: (v & 0xFFFF) - 0x10000 if v & 0x8000 else v & 0xFFFF
        self.write(r, struct.pack(">hhhh", *(s16(v) for v in (top, left, bottom, right))))

    def tb_setpt(self):
        # SetPt(&pt, h, v): Point is {v, h}
        self.w16(self.get(3), self.get(5))
        self.w16(self.get(3) + 2, self.get(4))

    def tb_offsetrect(self):
        r, dh, dv = self.get(3), self.get(4), self.get(5)
        t, l, b, rr = struct.unpack(">hhhh", self.read(r, 8))
        dh = (dh & 0xffff) - (0x10000 if dh & 0x8000 else 0)
        dv = (dv & 0xffff) - (0x10000 if dv & 0x8000 else 0)
        self.write(r, struct.pack(">hhhh", t + dv, l + dh, b + dv, rr + dh))

    def tb_sectrect(self):
        a = struct.unpack(">hhhh", self.read(self.get(3), 8))
        b = struct.unpack(">hhhh", self.read(self.get(4), 8))
        r = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
        if r[2] <= r[0] or r[3] <= r[1]:
            self.write(self.get(5), bytes(8))
            return 0
        self.write(self.get(5), struct.pack(">hhhh", *r))
        return 1

    def tb_ptinrect(self):
        """PtInRect(pt, &r): pt by value (v high, h low); top / left inside,
        bottom / right not."""
        pt = self.get(3)
        v, h = struct.unpack(">hh", struct.pack(">I", pt))
        r = struct.unpack(">hhhh", self.read(self.get(4), 8))
        return int(r[0] <= v < r[2] and r[1] <= h < r[3])

    # --- QuickDraw regions: pixel sets in Python, handle + {rgnSize, rgnBBox}
    # in memory (the game reads rgnBBox directly) ---
    def make_region(self, pixels=()):
        h = self.alloc(4)
        self.w32(h, self.alloc(10))
        self.regions[h] = set(pixels)
        self._region_sync(h)
        return h

    def _region_sync(self, h):
        px = self.regions[h]
        if px:
            xs = [p[0] for p in px]
            ys = [p[1] for p in px]
            box = (min(ys), min(xs), max(ys) + 1, max(xs) + 1)
        else:
            box = (0, 0, 0, 0)
        self.write(self.r32(h), struct.pack(">Hhhhh", 10, *box))

    def tb_newrgn(self):
        return self.make_region()

    def tb_copyrgn(self):
        self.regions[self.get(4)] = set(self.regions[self.get(3)])
        self._region_sync(self.get(4))

    def tb_offsetrgn(self):
        h = self.get(3)
        s16 = lambda v: (v & 0xFFFF) - 0x10000 if v & 0x8000 else v & 0xFFFF
        dh, dv = s16(self.get(4)), s16(self.get(5))
        self.regions[h] = {(x + dh, y + dv) for x, y in self.regions[h]}
        self._region_sync(h)

    def tb_sectrgn(self):
        self.regions[self.get(5)] = self.regions[self.get(3)] & self.regions[self.get(4)]
        self._region_sync(self.get(5))

    def tb_emptyrgn(self):
        return 0 if self.regions[self.get(3)] else 1

    def tb_disposergn(self):
        self.regions.pop(self.get(3), None)

    # --- offscreen GWorlds (enough for BuildMaskRegion): a GWorld is its
    # PixMap handle; PixMap: baseAddr +0, rowBytes +4, bounds +6, pixelSize
    # +0x20. EraseRect fills with 0 (white in clut 8 and in 1-bit).
    def tb_newgworld(self):
        out, depth, rect = self.get(3), self.get(4) & 0xFFFF, self.get(5)
        t, l, b, r = struct.unpack(">hhhh", self.read(rect, 8))
        w, h = r - l, b - t
        row = ((w * depth + 31) // 32) * 4
        base = self.alloc(row * h)
        pm = self.alloc(0x32)
        self.w32(pm, base)
        self.w16(pm + 4, row | (0x8000 if depth > 1 else 0))
        self.write(pm + 6, struct.pack(">hhhh", t, l, b, r))
        self.w16(pm + 0x20, depth)
        handle = self.alloc(4)
        self.w32(handle, pm)
        self.w32(out, handle)
        return 0

    def tb_getgworldpixmap(self):
        return self.get(3)

    def tb_getpixbaseaddr(self):
        return self.r32(self.r32(self.get(3)))

    def tb_setgworld(self):
        self.gworld = self.get(3)

    def tb_getgworld(self):
        self.w32(self.get(3), self.gworld)
        self.w32(self.get(4), 0)

    def tb_eraserect(self):
        pm = self.r32(self.gworld)
        base, row = self.r32(pm), self.r16(pm + 4) & 0x3FFF
        t, l, b, r = struct.unpack(">hhhh", self.read(pm + 6, 8))
        self.write(base, bytes(row * (b - t)))

    def tb_bitmaptoregion(self):
        """QuickDraw: the region of the set bits, most significant bit = left."""
        rgn, bm = self.get(3), self.get(4)
        base, row = self.r32(bm), self.r16(bm + 4) & 0x3FFF
        t, l, b, r = struct.unpack(">hhhh", self.read(bm + 6, 8))
        data = self.read(base, row * (b - t))
        self.regions[rgn] = {(l + x, t + y) for y in range(b - t) for x in range(r - l)
                             if data[y * row + x // 8] & (0x80 >> (x % 8))}
        self._region_sync(rgn)
        return 0

    def tb_random(self):
        # QuickDraw Random: Park-Miller (16807, 2^31 - 1) on randSeed; -32768 -> 0
        self.rand_seed = (self.rand_seed * 16807) % 0x7fffffff
        v = self.rand_seed & 0xffff
        if v == 0x8000:
            v = 0
        return v

    def tb_tickcount(self):
        return self.ticks

    def tb_newptr(self):
        return self.alloc(self.get(3))

    def tb_newhandle(self):
        size = self.get(3)
        h = self.alloc(4)
        self.w32(h, self.alloc(size))
        self.hsize[h] = size
        return h

    def new_handle(self, data):
        """A handle holding these bytes (the Memory Manager's view: hsize)."""
        h = self.alloc(4)
        p = self.alloc(max(len(data), 1))
        self.write(p, data)
        self.w32(h, p)
        self.hsize[h] = len(data)
        return h

    def tb_ptrtohand(self):
        src, dst, n = self.get(3), self.get(4), self.get(5)
        self.w32(dst, self.new_handle(self.read(src, n)))
        return 0

    def tb_gethandlesize(self):
        return self.hsize.get(self.get(3), 0)

    def tb_munger(self):
        """Munger(h, offset, ptr1, len1, ptr2, len2): replace the first ptr1
        from offset with ptr2; the offset after it, or -1."""
        h, off, p1, n1, p2, n2 = (self.get(i) for i in range(3, 9))
        data = self.read(self.r32(h), self.hsize[h])
        key = self.read(p1, n1)
        pos = data.find(key, off)
        if pos < 0:
            return 0xFFFFFFFF
        new = data[:pos] + self.read(p2, n2) + data[pos + n1:]
        p = self.alloc(max(len(new), 1))
        self.write(p, new)
        self.w32(h, p)
        self.hsize[h] = len(new)
        return pos + n2

    def tb_blockmove(self):
        src, dst, n = self.get(3), self.get(4), self.get(5)
        if n:
            self.write(dst, self.read(src, n))
        return 0

    # --- calls ---
    def addr(self, f):
        return self.names[f] if isinstance(f, str) else f

    def call(self, f, *args, limit=50_000_000, regs=None):
        """Call routine f (name or address) with integer args in r3...; return r3.
        regs: other registers to set first ({30: value}) - for routines that
        read a caller's register without setting it."""
        self.missing = None
        for i in range(32):
            self.set(i, 0)
        self.set(1, STACK_TOP - 0x1000)
        self.set(2, self.toc)
        for i, a in enumerate(args):
            self.set(3 + i, a)
        for r, v in (regs or {}).items():
            self.set(r, v)
        self.uc.reg_write(UC_PPC_REG_LR, RETURN)
        from unicorn.ppc_const import UC_PPC_REG_MSR
        self.uc.reg_write(UC_PPC_REG_MSR, self.uc.reg_read(UC_PPC_REG_MSR) | 0x2000)  # MSR[FP]
        try:
            self.uc.emu_start(self.addr(f), RETURN, count=limit)
        except UcError as e:
            pc = self.uc.reg_read(UC_PPC_REG_PC)
            raise RuntimeError(f"{e} at {pc:08x} ({self.where(pc)})") from None
        if self.missing:
            lr = self.uc.reg_read(UC_PPC_REG_LR)
            raise RuntimeError(f"no stub for Toolbox routine {self.missing} (called from {self.where(lr)})")
        return self.get(3)

    def where(self, a):
        best = max((v, k) for k, v in self.names.items() if v <= a) if a >= BASE else (a, "?")
        return f"{best[1]}+{a - best[0]:x}"
