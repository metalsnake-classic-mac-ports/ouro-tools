"""Look things up in Inside Macintosh without the internet: the 1992-96
series with its X-Ref volume, the 1985 volumes I-III (book IM85), and the
A-line trap words from MPW's C interfaces (Universal Interfaces 3.4): a
routine's description, a trap, a constant, a record field, a result code,
or a full-text search.

  imref.py build [PDF_DIR]     read the books into reference/imref.sqlite
                               (once; PDF_DIR holds the books and X-Ref/,
                               default reference/im-pdf/Inside Macintosh)
  imref.py lookup NAME|TRAP    where NAME is documented (routine, constant,
                               field; X-Ref index, IM85 headings), its trap
                               word, and the text there; TRAP (A976, _A976,
                               0xA976) lists the routines on that trap
  imref.py search WORDS...     full-text search: book, page, snippet
  imref.py error CODE|NAME     a result code: -43 -> fnfErr, or the reverse
  imref.py page BOOK LABEL     one printed page, e.g. `page Tb 3-120`

Sources, all Apple's and out of git (reference/ is ignored):
  reference/im-pdf/Inside Macintosh/   the 1992-96 PDFs with X-Ref/
  reference/im-1985/Inside Macintosh Volume I, II, III - 1985.pdf  (OCR text)
  reference/mpw/.../Interfaces/CIncludes/*.h   (MPW, CR line endings)
`build` needs pdftotext (brew install poppler). Run with python3 -I.
"""
import os
import re
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REFERENCE = os.path.join(os.path.dirname(HERE), "reference")
DB = os.path.join(REFERENCE, "imref.sqlite")
DEFAULT_PDFS = os.path.join(REFERENCE, "im-pdf", "Inside Macintosh")
IM85_PDF = os.path.join(REFERENCE, "im-1985", "Inside Macintosh Volume I, II, III - 1985.pdf")
MPW_DIR = os.path.join(REFERENCE, "mpw")
IM85_TITLE = "Inside Macintosh I-III (1985)"

# The X-Ref volume's abbreviations and the PDF file of each book.
BOOKS = {
    "AI": ("AOCE Application Interfaces", "AOCE Application Interfaces.pdf"),
    "AM": ("AOCE Service Access Modules", "AOCE Service Access Modules.pdf"),
    "D": ("Devices", "Devices.pdf"),
    "F": ("Files", "Files.pdf"),
    "Im": ("Imaging With QuickDraw", "Imaging With QuickDraw.pdf"),
    "IC": ("Interapplication Communication", "Interapplication Comm.pdf"),
    "M": ("Memory", "Memory.pdf"),
    "MTb": ("More Macintosh Toolbox", "More Macintosh TB.pdf"),
    "N": ("Networking", "Networking.pdf"),
    "O": ("Overview", "Overview.pdf"),
    "Pr": ("Processes", "Processes.pdf"),
    "PN": ("PowerPC Numerics", "PPC Numerics.pdf"),
    "PS": ("PowerPC System Software", "PPC System Software.pdf"),
    "Q": ("QuickTime", "QuickTime.pdf"),
    "QC": ("QuickTime Components", "QuickTime Components.pdf"),
    "S": ("Sound", "Sound.pdf"),
    "Tb": ("Macintosh Toolbox Essentials", "Macintosh TB Essentials.pdf"),
    "Tx": ("Text", "Text.pdf"),
    "U": ("Operating System Utilities", "Operating System Utils.pdf"),
    "XD": ("QuickDraw GX Printing Extensions and Drivers", "QD GX Printing Ext & Drvrs.pdf"),
    "XG": ("QuickDraw GX Graphics", "QD GX Graphics.pdf"),
    "XO": ("QuickDraw GX Objects", "QD GX Objects.pdf"),
    "XP": ("QuickDraw GX Printing", "QD GX Printing.pdf"),
    "XT": ("QuickDraw GX Typography", "QD GX Typography.pdf"),
    "XU": ("QuickDraw GX Environment and Utilities", "QD GX Environment & Utils.pdf"),
}
# the other X-Ref files (Glossary and the index parts) are searched as text
EXTRA = {"Glossary": "X-Ref/Glossary.pdf", "HIG": "Human Interface Guidelines.pdf"}
INDEXES = {"routine": "X-Ref/Index of Routines.pdf", "constant": "X-Ref/Index of Constants.pdf",
           "field": "X-Ref/Index of Field Names.pdf"}
LABEL = re.compile(r"^\s*(\d+-\d+|[A-Z]-\d+)\s")       # "3-120  Menu Manager Reference"
LABEL_RIGHT = re.compile(r"\s(\d+-\d+|[A-Z]-\d+)\s*$")  # "Menu Manager Reference  3-121"
REF = re.compile(r"^\d+-\d+$")


def pdf_pages(path):
    """The pages of a PDF as text (layout kept)."""
    out = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"pdftotext {path}: {out.stderr.strip()}")
    return out.stdout.split("\f")


def page_label(text):
    """The printed page number ("3-120") from a page's first or last lines."""
    lines = [l for l in text.splitlines() if l.strip()]
    for line in lines[-3:] + lines[:3]:
        for pattern in (LABEL, LABEL_RIGHT):
            found = pattern.search(line)
            if found:
                return found.group(1)
    return None


def parse_index(pages):
    """X-Ref index entries: (name, book abbreviation, page label). A column
    reads "name ABBR 1-2, 3-4, ABBR2 5-6"; the abbreviation carries over."""
    entries = []
    for text in pages:
        for line in text.splitlines():
            for column in re.split(r"\s{3,}", line.strip()):
                tokens = column.replace(",", " ").split()
                # the name ends where the first "ABBR label" pair starts
                for start in range(1, len(tokens) - 1):
                    if tokens[start] in BOOKS and REF.match(tokens[start + 1]):
                        break
                else:
                    continue
                name, book = " ".join(tokens[:start]), None
                for token in tokens[start:]:
                    if token in BOOKS:
                        book = token
                    elif REF.match(token) and book:
                        entries.append((name, book, token))
    return entries


def parse_result_codes(pages):
    """(name, code, meaning) from X-Ref's Result Codes; a long name may sit
    alone on its line with the code on the next."""
    codes, pending = [], None
    line_re = re.compile(r"^(\S+)?\s+([–-]?\d+)(?:\s{2,}(.*))?$")
    for text in pages:
        for line in text.splitlines():
            if not line.strip() or "Inside Macintosh X-Ref" in line:
                continue
            found = line_re.match(line)
            if found and (found.group(1) or pending):
                name = found.group(1) or pending
                codes.append([name, int(found.group(2).replace("–", "-")), found.group(3) or ""])
                pending = None
            elif re.match(r"^\S+$", line.strip()) and not line.startswith(" "):
                pending = line.strip()
            elif codes and line.startswith(" ") and not found:
                codes[-1][2] += " " + line.strip()  # meaning continued
    return codes


def im85_label(text):
    """The 1985 volume's page label ("I-110", "II-332", "III-197") from its
    OCR text, where I and 1 (and l) are mixed up in the volume and O and I
    in the number."""
    lines = [l for l in text.splitlines() if l.strip()]
    for line in lines[:2] + lines[-2:]:
        found = re.search(r"(?:^|\s)([I1l]{1,3})-([0-9IlO]{1,3})(?:\s|$)", line)
        if found:
            volume = "I" * len(found.group(1))
            number = found.group(2).translate(str.maketrans("IlO", "110"))
            return f"{volume}-{int(number)}"
    return None


def im85_headings(text):
    """Routine names from the 1985 volume's PROCEDURE / FUNCTION headings."""
    return re.findall(r"^\s*(?:PROCEDURE|FUNCTION)\s+([A-Za-z][A-Za-z0-9]+)", text, re.M)


INLINE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*?\)\s*"
                    r"(?:ONE|TWO|THREE|FOUR|FIVE|SIX)WORDINLINE\(([^)]*)\)")


def selector(words):
    """The selector that the instruction right before the trap puts into D0 or
    onto the stack: moveq #n,d0 (0x70nn), move.w #n,d0 (0x303C n),
    move.l #n,d0 (0x203C hi lo), move.w #n,-(sp) (0x3F3C n, the Pack
    traps), clr.w -(sp) (0x4267, selector 0)."""
    if len(words) >= 3 and words[-3] == 0x203C:
        return words[-2] << 16 | words[-1]
    if len(words) >= 2 and words[-2] in (0x303C, 0x3F3C):
        return words[-1]
    if words and words[-1] == 0x4267:
        return 0
    if words and words[-1] >> 8 == 0x70:
        value = words[-1] & 0xFF
        return value - 0x100 if value & 0x80 else value
    return None


def mpw_traps(mpw_dir):
    """(name, trap word, selector, header, inline words) for every routine
    an MPW C interface declares with an A-line trap in its inline code."""
    found = []
    for root, _, files in os.walk(mpw_dir):
        if os.path.basename(root) != "CIncludes":
            continue
        for file in sorted(files):
            if not file.endswith(".h"):
                continue
            text = open(os.path.join(root, file), "rb").read().decode("mac_roman").replace("\r", "\n")
            for name, inline in INLINE.findall(text):
                words = [int(w, 16) for w in re.findall(r"0x([0-9A-Fa-f]{1,4})", inline)]
                traps = [i for i, w in enumerate(words) if w & 0xF000 == 0xA000]
                if not traps:
                    continue
                i = traps[-1]
                found.append((name, f"{words[i]:04X}", selector(words[:i]), file,
                              " ".join(f"{w:04X}" for w in words)))
    return found


def build(pdf_dir):
    if os.path.exists(DB):
        os.remove(DB)
    os.makedirs(REFERENCE, exist_ok=True)
    db = sqlite3.connect(DB)
    db.executescript("""
        create table pages(book text, pdf_page integer, label text, text text);
        create virtual table fts using fts5(book unindexed, label unindexed, text);
        create table entries(kind text, name text, book text, label text);
        create table codes(name text, code integer, meaning text);
        create table traps(name text, trap text, selector integer, header text, inline text);
        create index traps_name on traps(name collate nocase);
        create index traps_trap on traps(trap);
        create index entries_name on entries(name collate nocase);
    """)
    for abbr, (title, file) in list(BOOKS.items()) + [(k, (k, f)) for k, f in EXTRA.items()]:
        path = os.path.join(pdf_dir, file)
        if not os.path.exists(path):
            print(f"missing: {file}")
            continue
        for number, text in enumerate(pdf_pages(path), 1):
            label = page_label(text)
            db.execute("insert into pages values (?, ?, ?, ?)", (abbr, number, label, text))
            db.execute("insert into fts values (?, ?, ?)", (abbr, label or f"pdf {number}", text))
        print(f"{abbr:4} {title}")
    for kind, file in INDEXES.items():
        entries = parse_index(pdf_pages(os.path.join(pdf_dir, file)))
        db.executemany("insert into entries values (?, ?, ?, ?)", [(kind,) + e for e in entries])
        print(f"{len(entries)} {kind} references")
    codes = parse_result_codes(pdf_pages(os.path.join(pdf_dir, "X-Ref/Result Codes.pdf")))
    db.executemany("insert into codes values (?, ?, ?)", codes)
    print(f"{len(codes)} result codes")
    if os.path.exists(IM85_PDF):
        headings = 0
        for number, text in enumerate(pdf_pages(IM85_PDF), 1):
            label = im85_label(text)
            db.execute("insert into pages values ('IM85', ?, ?, ?)", (number, label, text))
            db.execute("insert into fts values ('IM85', ?, ?)", (label or f"pdf {number}", text))
            # summaries repeat every heading: index the chapters' own pages
            if label and "Summary of" not in text[:400]:
                for name in im85_headings(text):
                    db.execute("insert into entries values ('routine', ?, 'IM85', ?)", (name, label))
                    headings += 1
        print(f"IM85 {IM85_TITLE}: {headings} routine headings")
    else:
        print(f"missing: {IM85_PDF}")
    traps = mpw_traps(MPW_DIR)
    db.executemany("insert into traps values (?, ?, ?, ?, ?)", traps)
    print(f"{len(traps)} trap declarations from MPW's C interfaces")
    db.commit()


def title(book):
    return IM85_TITLE if book == "IM85" else BOOKS.get(book, (book,))[0]


def connect():
    if not os.path.exists(DB):
        sys.exit("no reference/imref.sqlite: run `imref.py build` first")
    return sqlite3.connect(DB)


def page_text(db, book, label):
    row = db.execute("select text, pdf_page from pages where book = ? and label = ?", (book, label)).fetchone()
    return row if row else (None, None)


def lookup(name):
    db = connect()
    trap = re.fullmatch(r"(?:_|0x)?([Aa][0-9A-Fa-f]{3})", name.strip())
    if trap:
        word = int(trap.group(1), 16)
        rows = db.execute("select name, selector, header, inline from traps where trap = ? "
                          "order by selector, name", (f"{word:04X}",)).fetchall()
        if not rows and word < 0xA800:
            # OS traps: bits 9 and 10 are flags (SYS, CLEAR / IMMED, ASYNC);
            # the headers may declare only one variant
            base = word & 0xF9FF
            rows = db.execute("select name, selector, header, inline from traps where "
                              "trap in (?, ?, ?, ?) order by trap, name",
                              tuple(f"{base | flags:04X}" for flags in (0, 0x200, 0x400, 0x600))).fetchall()
            if rows:
                print(f"_{word:04X} not declared; the same OS trap with other flag bits:")
        for routine, sel, header, inline in rows:
            print(f"_{trap.group(1).upper()}" + (f" selector {sel}" if sel is not None else "")
                  + f": {routine}  ({header}: {inline})")
        if not rows:
            print("no routine on this trap in MPW's C interfaces")
        if len({r[0] for r in rows}) == 1:
            print()
            name = rows[0][0]
        else:
            return
    for routine, trap_word, sel, header, inline in db.execute(
            "select name, trap, selector, header, inline from traps where name = ? collate nocase", (name,)):
        print(f"trap _{trap_word}" + (f" selector {sel}" if sel is not None else "")
              + f": {routine}  ({header}: {inline})")
    rows = db.execute("select kind, name, book, label from entries where name = ? collate nocase "
                      "order by kind, book = 'IM85', book, label", (name,)).fetchall()
    for code in db.execute("select name, code, meaning from codes where name = ? collate nocase", (name,)):
        print(f"result code {code[0]} = {code[1]}: {code[2]}")
    if not rows:
        print(f"{name}: not in the indexes; full-text search:")
        search([name])
        return
    for kind, entry, book, label in rows:
        print(f"{kind} {entry}: {title(book)} ({book}) page {label}")
    # the description: the first reference's page from the line naming it on
    kind, entry, book, label = rows[0]
    text, pdf_page = page_text(db, book, label)
    if text is None:
        return
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if re.search(rf"\b{re.escape(entry)}\b", l)), 0)
    following, _ = db.execute("select text, 0 from pages where book = ? and pdf_page = ?",
                              (book, pdf_page + 1)).fetchone() or ("", 0)
    print(f"\n--- {title(book)}, page {label} ---")
    print("\n".join(lines[start:] + following.splitlines()[:40]).rstrip())


def search(words, limit=12):
    db = connect()
    query = " ".join('"' + w.replace('"', "") + '"' for w in words)
    rows = db.execute("select book, label, snippet(fts, 2, '[', ']', ' ... ', 12) from fts "
                      "where fts match ? order by rank limit ?", (query, limit)).fetchall()
    for book, label, snippet in rows:
        print(f"{book:4} {label:7} {title(book)}: {' '.join(snippet.split())}")
    if not rows:
        print("nothing found")


def error(value):
    db = connect()
    value = value.replace("–", "-")
    if re.match(r"^-?\d+$", value):
        rows = db.execute("select name, code, meaning from codes where code = ?", (int(value),)).fetchall()
    else:
        rows = db.execute("select name, code, meaning from codes where name = ? collate nocase",
                          (value,)).fetchall()
    for name, code, meaning in rows:
        print(f"{code:7} {name}  {meaning}")
    if not rows:
        print("not in X-Ref's result codes")


def page(book, label):
    text, _ = page_text(connect(), book, label)
    print(text if text else "no such page")


if __name__ == "__main__":
    command, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if command == "build":
        build(args[0] if args else DEFAULT_PDFS)
    elif command == "lookup" and args:
        lookup(" ".join(args))
    elif command == "search" and args:
        search(args)
    elif command == "error" and args:
        error(args[0])
    elif command == "page" and len(args) == 2:
        page(*args)
    else:
        sys.exit(__doc__)
