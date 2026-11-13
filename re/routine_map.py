"""Map the routines of two 68k applications built from the same code (a
game and its sequel, two versions): which routine of A is which of B, and
whether it is the same, differs only in constants, is changed, or exists
in one of them only. Also maps A5 globals (A's offset -> B's) by voting
over the matched routines.

Usage: python3 routine_map.py <work A> <work B> [--names A.tsv] [--out map.md]
       [--json map.json]
(work dirs in unpack_app.py's layout; needs capstone; --names: lines
"seg:0xoff<TAB>name" naming A's routines, e.g. from a port's sources)

Routines: every `link a6` and every jump table target starts one; it runs
to the next start (data between routines - names, strings, switch tables -
stays in the routine before it). Each instruction becomes a token:
globals (`-$x(a5)`) and calls (jump table, `bsr`/`jsr` pc-relative) are
placeholders, branches inside the routine "BR", Toolbox traps by name,
everything else as written (immediates included). Two routines are
"same" when their tokens are equal and their globals and callees map
consistently; "constants" when only immediates differ; "changed" when
they are paired by similarity (difflib ratio of the tokens, at least
MIN_RATIO) or by their place in a matched caller's call list.
"""
import collections
import difflib
import json
import re
import struct
import sys

import capstone

# run with python3 -I: this folder is not on the path then
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from disasm import jump_table, trap_name  # noqa: E402

MIN_RATIO = 0.5

IMM = re.compile(r"#\$?-?[0-9a-f]+")
GLOBAL = re.compile(r"-\$([0-9a-f]+)\(a5\)")
JT = re.compile(r"^\$([0-9a-f]+)\(a5\)$")


class Routine:
    def __init__(self, seg, start, end):
        self.seg, self.start, self.end = seg, start, end
        self.tokens = []  # with placeholders
        self.globals = []  # A5 offsets in token order
        self.calls = []  # (seg, offset) targets in order
        self.imms = []  # immediates in order
        self.traps = []

    @property
    def key(self):
        return f"{self.seg}:{self.start:#x}"

    def skeleton(self):
        return [IMM.sub("#", t) for t in self.tokens]


def load(work):
    table = jump_table(work)
    by_seg = collections.defaultdict(set)
    for seg, off in table.values():
        by_seg[seg].add(off)
    md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_020 | capstone.CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    routines = []
    seg = 1
    while True:
        try:
            code = open(f"{work}/code/seg{seg:02d}.bin", "rb").read()
        except FileNotFoundError:
            break
        starts = set(o for o in by_seg[seg] if o < len(code))
        starts |= {i for i in range(0, len(code) - 1, 2) if code[i : i + 2] == b"\x4e\x56"}
        starts = sorted(starts)
        for a, e in zip(starts, starts[1:] + [len(code)]):
            r = Routine(seg, a, e)
            decode(md, code, r, table)
            routines.append(r)
        seg += 1
    return routines


def decode(md, code, r, table):
    at = r.start
    while at < r.end:
        word = struct.unpack(">H", code[at : at + 2])[0]
        if word >> 12 == 0xA:
            name = trap_name(word)
            r.tokens.append("_" + name)
            r.traps.append(name)
            at += 2
            continue
        ins = next(md.disasm(code[at : r.end], at, count=1), None)
        if ins is None:
            r.tokens.append(f"dc.w ${word:04x}")
            at += 2
            continue
        mn, op = ins.mnemonic, ins.op_str
        m = JT.match(op)
        if mn in ("jsr", "jmp", "pea") and m and int(m.group(1), 16) in table:
            r.calls.append(table[int(m.group(1), 16)])
            tok = f"{mn} CALL"
        elif mn in ("bsr.b", "bsr.w", "jsr") and re.fullmatch(r"\$[0-9a-f]+", op):
            r.calls.append((r.seg, int(op[1:], 16)))
            tok = "bsr CALL"
        elif mn.startswith(("b", "db")) and re.search(r"\$[0-9a-f]+$", op) and not mn.startswith(("bchg", "bclr", "bset", "btst", "bf")):
            target = int(re.search(r"\$([0-9a-f]+)$", op).group(1), 16)
            inside = r.start <= target < r.end
            tok = f"{mn} {re.sub(r'[$][0-9a-f]+$', 'BR' if inside else 'OUT', op)}"
        else:
            for g in GLOBAL.findall(op):
                r.globals.append(-int(g, 16))
            op = GLOBAL.sub("G(a5)", op)
            op = re.sub(r"\$[0-9a-f]+\(pc", "X(pc", op)
            r.imms += IMM.findall(op)
            tok = f"{mn} {op}"
        r.tokens.append(tok)
        at += ins.size


def ratio(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < MIN_RATIO or sm.quick_ratio() < MIN_RATIO:
        return 0.0
    return sm.ratio()


def match(A, B):
    pair = {}  # A key -> (B routine, how)
    used = set()
    # 1. unique equal token lists, then unique equal skeletons
    for how, sig in (("tokens", lambda r: tuple(r.tokens)), ("skeleton", lambda r: tuple(r.skeleton()))):
        ia, ib = collections.defaultdict(list), collections.defaultdict(list)
        for r in A:
            if r.key not in pair:
                ia[sig(r)].append(r)
        for r in B:
            if r.key not in used:
                ib[sig(r)].append(r)
        for s, ra in ia.items():
            rb = ib.get(s, [])
            if len(ra) == 1 and len(rb) == 1 and len(s) >= 4:
                pair[ra[0].key] = (rb[0], how)
                used.add(rb[0].key)
    byb = {r.key: r for r in B}
    bya = {r.key: r for r in A}
    starts_a = {(r.seg, r.start): r for r in A}
    starts_b = {(r.seg, r.start): r for r in B}

    # 2. call graph: callees at the same place in matched callers
    def propagate():
        grew = True
        while grew:
            grew = False
            for ka, (rb, _) in list(pair.items()):
                ra = bya[ka]
                if len(ra.calls) != len(rb.calls):
                    continue
                for ca, cb in zip(ra.calls, rb.calls):
                    xa, xb = starts_a.get(ca), starts_b.get(cb)
                    if xa and xb and xa.key not in pair and xb.key not in used:
                        if ratio(xa.skeleton(), xb.skeleton()) >= 0.3:
                            pair[xa.key] = (xb, "calls")
                            used.add(xb.key)
                            grew = True

    propagate()
    # 3. best mutual similarity among the rest
    rest_a = [r for r in A if r.key not in pair]
    rest_b = [r for r in B if r.key not in used]
    cands = []
    for ra in rest_a:
        sa = ra.skeleton()
        for rb in rest_b:
            if not (0.5 <= len(rb.tokens) / max(1, len(ra.tokens)) <= 2):
                continue
            q = ratio(sa, rb.skeleton())
            if q >= MIN_RATIO:
                cands.append((q, ra.key, rb.key))
    for q, ka, kb in sorted(cands, reverse=True):
        if ka not in pair and kb not in used:
            pair[ka] = (byb[kb], f"similar {q:.2f}")
            used.add(kb)
    propagate()
    return pair


def classify(A, B, pair):
    bya = {r.key: r for r in A}
    starts_b = {(r.seg, r.start): r for r in B}
    callee = {}
    for ka, (rb, _) in pair.items():
        ra = bya[ka]
        callee[(ra.seg, ra.start)] = (rb.seg, rb.start)
    votes = collections.defaultdict(collections.Counter)
    for ka, (rb, _) in pair.items():
        ra = bya[ka]
        if ra.skeleton() == rb.skeleton() and len(ra.globals) == len(rb.globals):
            for ga, gb in zip(ra.globals, rb.globals):
                votes[ga][gb] += 1
    gmap = {ga: c.most_common(1)[0][0] for ga, c in votes.items()}
    out = {}
    for ka, (rb, how) in pair.items():
        ra = bya[ka]
        q = ratio(ra.skeleton(), rb.skeleton()) if ra.skeleton() != rb.skeleton() else 1.0
        if ra.skeleton() == rb.skeleton():
            globals_ok = len(ra.globals) == len(rb.globals) and all(gmap.get(a) == b for a, b in zip(ra.globals, rb.globals))
            calls_ok = all(callee.get(a) == b for a, b in zip(ra.calls, rb.calls))
            diff = [(x, y) for x, y in zip(ra.imms, rb.imms) if x != y]
            if diff:
                status = "constants"
            elif globals_ok and calls_ok:
                status = "same"
            else:
                status = "same code, other globals/callees"
        else:
            diff = []
            status = "changed"
        out[ka] = dict(b=rb.key, status=status, how=how, ratio=round(q, 2), consts=diff[:6],
                       size_a=ra.end - ra.start, size_b=rb.end - rb.start)
    return out, gmap


def main():
    args = sys.argv[1:]
    opt = {}
    for flag in ("--names", "--out", "--json"):
        if flag in args:
            i = args.index(flag)
            opt[flag] = args[i + 1]
            del args[i : i + 2]
    wa, wb = args
    names = {}
    if "--names" in opt:
        for line in open(opt["--names"]):
            if "\t" in line:
                k, n = line.rstrip("\n").split("\t", 1)
                names[k] = n
    A, B = load(wa), load(wb)
    pair = match(A, B)
    res, gmap = classify(A, B, pair)
    counts = collections.Counter(v["status"] for v in res.values())
    matched_b = {v["b"] for v in res.values()}
    only_a = [r for r in A if r.key not in res]
    only_b = [r for r in B if r.key not in matched_b]
    size = lambda rs: sum(r.end - r.start for r in rs)
    lines = []
    lines.append(f"A: {wa} ({len(A)} routines, {size(A)} bytes); B: {wb} ({len(B)} routines, {size(B)} bytes)\n")
    lines.append("| status | routines | bytes of A |\n|---|---|---|")
    bya = {r.key: r for r in A}
    for s in ("same", "same code, other globals/callees", "constants", "changed"):
        rs = [bya[k] for k, v in res.items() if v["status"] == s]
        lines.append(f"| {s} | {len(rs)} | {size(rs)} |")
    lines.append(f"| A only | {len(only_a)} | {size(only_a)} |")
    lines.append(f"| B only | {len(only_b)} | ({size(only_b)} bytes of B) |\n")
    lines.append("| A | name | bytes | B | bytes | status | similarity | paired by | constants A→B |\n|---|---|---|---|---|---|---|---|---|")
    for r in A:
        v = res.get(r.key)
        nm = names.get(r.key, "")
        if v:
            consts = ", ".join(f"{x}→{y}" for x, y in v["consts"])
            lines.append(f"| {r.key} | {nm} | {v['size_a']} | {v['b']} | {v['size_b']} | {v['status']} | {v['ratio']} | {v['how']} | {consts} |")
        else:
            lines.append(f"| {r.key} | {nm} | {r.end - r.start} | - | - | A only | | | |")
    lines.append("\n**B only** (traps used, first ones):\n\n| B | bytes | traps |\n|---|---|---|")
    for r in only_b:
        t = ", ".join(dict.fromkeys(r.traps))[:120]
        lines.append(f"| {r.key} | {r.end - r.start} | {t} |")
    text = "\n".join(lines) + "\n"
    if "--out" in opt:
        open(opt["--out"], "w").write(text)
    else:
        sys.stdout.write(text)
    if "--json" in opt:
        json.dump({"pairs": res, "globals": {str(k): v for k, v in sorted(gmap.items())},
                   "a_only": [r.key for r in only_a], "b_only": [r.key for r in only_b]},
                  open(opt["--json"], "w"), indent=1)
    print(dict(counts), "A only", len(only_a), "B only", len(only_b), "globals mapped", len(gmap), file=sys.stderr)


if __name__ == "__main__":
    main()
