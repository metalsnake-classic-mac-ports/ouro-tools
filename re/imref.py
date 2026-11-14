"""Look things up in Inside Macintosh (the 1992-96 series and its X-Ref
volume) without the internet: a routine's description, a constant, a
record field, a result code, or a full-text search.

  imref.py build [PDF_DIR]     read the books into reference/imref.sqlite
                               (once; PDF_DIR holds the books and X-Ref/,
                               default reference/im-pdf/Inside Macintosh)
  imref.py lookup NAME         where NAME is documented (routine, constant,
                               field; X-Ref index) and the text there
  imref.py search WORDS...     full-text search: book, page, snippet
  imref.py error CODE|NAME     a result code: -43 -> fnfErr, or the reverse
  imref.py page BOOK LABEL     one printed page, e.g. `page Tb 3-120`

The books are Apple's and stay out of git (reference/ is ignored); `build`
needs pdftotext (brew install poppler). Run with python3 -I.
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
    db.commit()


def connect():
    if not os.path.exists(DB):
        sys.exit("no reference/imref.sqlite: run `imref.py build` first")
    return sqlite3.connect(DB)


def page_text(db, book, label):
    row = db.execute("select text, pdf_page from pages where book = ? and label = ?", (book, label)).fetchone()
    return row if row else (None, None)


def lookup(name):
    db = connect()
    rows = db.execute("select kind, name, book, label from entries where name = ? collate nocase "
                      "order by kind, book, label", (name,)).fetchall()
    for code in db.execute("select name, code, meaning from codes where name = ? collate nocase", (name,)):
        print(f"result code {code[0]} = {code[1]}: {code[2]}")
    if not rows:
        print(f"{name}: not in the X-Ref indexes; full-text search:")
        search([name])
        return
    for kind, entry, book, label in rows:
        print(f"{kind} {entry}: {BOOKS[book][0]} ({book}) page {label}")
    # the description: the first reference's page from the line naming it on
    kind, entry, book, label = rows[0]
    text, pdf_page = page_text(db, book, label)
    if text is None:
        return
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if re.search(rf"\b{re.escape(entry)}\b", l)), 0)
    following, _ = db.execute("select text, 0 from pages where book = ? and pdf_page = ?",
                              (book, pdf_page + 1)).fetchone() or ("", 0)
    print(f"\n--- {BOOKS[book][0]}, page {label} ---")
    print("\n".join(lines[start:] + following.splitlines()[:40]).rstrip())


def search(words, limit=12):
    db = connect()
    query = " ".join('"' + w.replace('"', "") + '"' for w in words)
    rows = db.execute("select book, label, snippet(fts, 2, '[', ']', ' ... ', 12) from fts "
                      "where fts match ? order by rank limit ?", (query, limit)).fetchall()
    for book, label, snippet in rows:
        title = BOOKS.get(book, (book,))[0]
        print(f"{book:4} {label:7} {title}: {' '.join(snippet.split())}")
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
