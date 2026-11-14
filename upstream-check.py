#!/usr/bin/env python3
"""Monthly check of the emulators and tools we use or keep an eye on, but do
not fork (see UPSTREAM-CHECK.md; the macemu forks have fork-check.sh): MAME,
DingusPPC, Snow, QEMU, systemless, Unicorn, Capstone, Ghidra, Retro68, the
archive and disk tools, and the projects we may take ideas from.

  upstream-check.py changed    what is new since upstream-state.json: releases,
                               commits (on the watched paths for big
                               repositories), MAME wiki pages, a newer MAME in
                               Homebrew; repositories that went archived
  upstream-check.py snapshot   write upstream-state.json with today's state
  upstream-check.py due        print "due since DATE" when the last check in
                               UPSTREAM-CHECK.md is more than a month old
  upstream-check.py hook       Claude Code SessionStart hook: the same as a
                               context reminder, only under the ports folder

Needs gh (logged in) for the GitHub API; `due` and `hook` work offline.
Run with python3 -I.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "upstream-state.json")
DOC = os.path.join(HERE, "UPSTREAM-CHECK.md")

# What is watched, by group. A project's "paths" are directories or files
# in its repository (only commits touching them count; None = every
# commit); "keep" filters the files of commits under a path (MAME's
# src/mame/apple also holds the Apple II and Lisa); "why" says what to look
# for. Add a project here and to UPSTREAM-CHECK.md's list.
MAC_FILES = re.compile(
    r"src/mame/apple/(mac|cuda|egret|adbmodem|dafb|valkyrie|v8|sonora|iosb|omega|"
    r"djmemc|f108|prav8ckb|pseudovia|bandit|grandcentral|heathrow|mpc106|pippin)")
PROJECTS = {
    # emulators
    "mamedev/mame": {
        "group": "emulator",
        "why": "Mac drivers, 68k / PPC CPUs, Mac chips, debugger, Lua (README, MAME)",
        "paths": [
            "src/mame/apple",                       # the Mac drivers and their chips
            "src/devices/cpu/m68000",               # 68000 ... 68040
            "src/devices/cpu/powerpc",
            "src/devices/sound/asc.cpp",            # Apple Sound Chip
            "src/devices/machine/swim1.cpp", "src/devices/machine/swim2.cpp",
            "src/devices/machine/swim3.cpp", "src/devices/machine/applefdintf.cpp",
            "src/devices/machine/ncr53c90.cpp",     # SCSI of the Quadras
            "src/devices/machine/6522via.cpp",
            "src/devices/bus/nubus",                # video cards
            "src/frontend/mame/luaengine.cpp",      # what drive.lua uses
            "src/frontend/mame/luaengine_debug.cpp",
            "src/emu/debug",                        # the debugger
        ],
        "keep": {"src/mame/apple": MAC_FILES},
    },
    "dingusdev/dingusppc": {
        "group": "emulator",
        "why": "PowerPC Macs at hardware level: screenshots, headless, save states, scripting would make it usable",
    },
    "twvd/snow": {
        "group": "emulator",
        "why": "68000-68030 Macs at hardware level, in Rust, core crate usable as a library",
    },
    "qemu/qemu": {
        "group": "emulator",
        "why": "Quadra 800 (q800) and PowerMac machines; gdb stub, record / replay",
        "paths": ["hw/m68k", "target/m68k", "hw/nubus", "hw/misc/mac_via.c", "hw/ppc/mac_oldworld.c",
                  "hw/ppc/mac_newworld.c"],
    },
    "benletchford/systemless": {
        "group": "emulator",
        "why": "Toolbox reimplementation running 68k / PPC apps; headless play scripts (built here)",
    },
    "theeggcrusher2/Classetta-weekly": {
        "group": "emulator",
        "why": "Python Toolbox runtime for 68k apps (read only, no licence): trap tracing, ideas for stubs",
    },
    # analysis tools we use
    "unicorn-engine/unicorn": {
        "group": "analysis",
        "why": "the differential test harnesses (m68k, ppc, Python bindings)",
        "paths": ["qemu/target/m68k", "qemu/target/ppc", "bindings/python"],
    },
    "capstone-engine/capstone": {
        "group": "analysis",
        "why": "disasm.py, ppcdis.py",
        "paths": ["arch/M68K", "arch/PowerPC"],
    },
    "NationalSecurityAgency/ghidra": {
        "group": "analysis",
        "why": "decompiling 68k and PEF (re/ghidra, re/ppc/ghidra)",
        "paths": ["Ghidra/Processors/68000", "Ghidra/Processors/PowerPC"],
    },
    "autc04/Retro68": {
        "group": "analysis",
        "why": "GCC for classic Macs (build-retro68.sh)",
    },
    # archives and disks
    "MacPaw/XADMaster": {
        "group": "files",
        "why": "unar / lsar (Homebrew): StuffIt, Compact Pro, BinHex ...",
    },
    "adespoton/macextract.py": {
        "group": "files",
        "why": "Python reader for classic archives (fallback when unar fails)",
    },
    "uzTools/MacExtract": {
        "group": "files",
        "why": "the C original of macextract.py",
    },
    "danifunker/rusty-backup": {
        "group": "files",
        "why": "HFS / HFS+ images and the Apple Installer Tome reader (issue 109)",
    },
    "elliotnunn/machfs": {
        "group": "files",
        "why": "Python HFS read / write",
    },
    # ideas and neighbours
    "LoetLuemmel/AppleBridge": {
        "group": "ideas",
        "why": "remote control from inside the guest; a memory read verb or a public Toolbox reference would change the verdict",
    },
    "jorio/Pomme": {
        "group": "ideas",
        "why": "Toolbox subset for source ports: decoders (MACE, IMA4, Cinepak)",
    },
    "adespoton/utmconfigs": {
        "group": "ideas",
        "why": "QEMU configurations for Mac OS 7.1-9.2",
    },
}
COMMITS_SHOWN = 15  # per project; the rest is linked
WIKI_PAGES = ["Driver:Mac 68K", "Driver:Mac PPC"]
WIKI_API = "https://wiki.mamedev.org/api.php"


def gh(path, paginate=True):
    out = subprocess.run(["gh", "api"] + (["--paginate"] if paginate else []) + [path],
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"gh api {path}: {out.stderr.strip()}")
    # --paginate concatenates JSON arrays as "][": join them into one list
    text = out.stdout.strip().replace("]\n[", ",").replace("][", ",")
    return json.loads(text) if text else []


def head(repo):
    return gh(f"repos/{repo}/commits?per_page=1", paginate=False)[0]["sha"]


def releases_since(repo, since):
    found = []
    for rel in gh(f"repos/{repo}/releases?per_page=20", paginate=False):
        if (rel.get("published_at") or "") > since:
            found.append((rel["published_at"][:10], rel["tag_name"], rel.get("name") or ""))
    return found


def commits_since(repo, since, paths, keep):
    """Commits after `since` touching the paths, newest first, with the
    watched files they touch (MAME) - one entry per commit."""
    seen = {}
    for path in paths or [None]:
        query = f"repos/{repo}/commits?since={since}&per_page=100"
        if path:
            query += "&path=" + urllib.parse.quote(path)
        for c in gh(query):
            entry = seen.setdefault(c["sha"], {
                "sha": c["sha"],
                "date": c["commit"]["committer"]["date"][:10],
                "subject": c["commit"]["message"].split("\n")[0],
                "files": set(),
                "paths": set(),
            })
            entry["paths"].add(path)
    for entry in seen.values():
        filters = [keep[p] for p in entry["paths"] if p in keep]
        if filters and entry["paths"] <= set(keep):
            # only under filtered paths: keep it if a watched file changed
            files = commit_files(repo, entry["sha"])
            entry["files"] = {f for f in files if any(r.match(f) for r in filters)}
            entry["drop"] = not entry["files"]
        else:
            entry["files"] = {p for p in entry["paths"] if p}
    return sorted((e for e in seen.values() if not e.get("drop")),
                  key=lambda e: e["date"], reverse=True)


def commit_files(repo, sha):
    out = subprocess.run(["gh", "api", f"repos/{repo}/commits/{sha}", "--jq", ".files[].filename"],
                         capture_output=True, text=True)
    return out.stdout.split()


def wiki_revisions():
    query = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "ids|timestamp",
                                    "titles": "|".join(WIKI_PAGES), "format": "json"})
    try:
        with urllib.request.urlopen(f"{WIKI_API}?{query}", timeout=20) as answer:
            pages = json.load(answer)["query"]["pages"].values()
    except OSError as error:
        print(f"MAME wiki not reachable: {error}")
        return {}
    return {p["title"]: {"revid": p["revisions"][0]["revid"], "date": p["revisions"][0]["timestamp"][:10]}
            for p in pages if "revisions" in p}


def homebrew_mame():
    """(installed version, Homebrew's stable version), None where unknown."""
    try:
        info = json.loads(subprocess.run(["brew", "info", "--json=v2", "mame"],
                                         capture_output=True, text=True).stdout)["formulae"][0]
    except (OSError, ValueError, KeyError, IndexError):
        return None, None
    installed = info["installed"][0]["version"] if info.get("installed") else None
    return installed, info["versions"]["stable"]


def snapshot():
    state = {"date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "heads": {repo: head(repo) for repo in PROJECTS},
             "wiki": wiki_revisions()}
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    print(f"wrote {STATE}")


def changed():
    if not os.path.exists(STATE):
        sys.exit("no upstream-state.json yet: run snapshot")
    state = json.load(open(STATE))
    since = state["date"]
    print(f"Since {since}:")
    group = None
    for repo, spec in PROJECTS.items():
        if spec["group"] != group:
            group = spec["group"]
            print(f"\n######## {group}")
        print(f"\n== {repo} - {spec['why']}")
        if gh(f"repos/{repo}", paginate=False).get("archived"):
            print("  ARCHIVED: nothing more will come; consider dropping it from the list")
        for date, tag, name in releases_since(repo, since):
            print(f"  release {date} {tag} {name}")
        commits = commits_since(repo, since, spec.get("paths"), spec.get("keep", {}))
        for c in commits[:COMMITS_SHOWN]:
            files = ", ".join(sorted(f.rsplit("/", 1)[-1] for f in c["files"]))
            print(f"  {c['date']} {c['sha'][:10]} {c['subject']}" + (f"  [{files}]" if files else ""))
        if len(commits) > COMMITS_SHOWN:
            print(f"  ... and {len(commits) - COMMITS_SHOWN} older ones: https://github.com/{repo}/commits")
        if not commits:
            print("  no commits" + (" on the watched paths" if spec.get("paths") else ""))
    print("\n== MAME wiki")
    for title, rev in wiki_revisions().items():
        old = state.get("wiki", {}).get(title, {}).get("revid")
        if rev["revid"] != old:
            print(f"  {title}: revision {rev['revid']} of {rev['date']} (was {old}); diff: "
                  f"https://wiki.mamedev.org/index.php?diff={rev['revid']}&oldid={old}")
        else:
            print(f"  {title}: unchanged")
    installed, stable = homebrew_mame()
    print(f"\n== MAME in Homebrew: installed {installed}, available {stable}")


def due():
    text = open(DOC).read() if os.path.exists(DOC) else ""
    found = re.search(r"^Last check: (\d{4}-\d{2}-\d{2})", text, re.M)
    if not found:
        return "due (no date in UPSTREAM-CHECK.md)"
    last = datetime.date.fromisoformat(found.group(1))
    today = datetime.date.today()
    # the same day one month earlier (the 28th at most, so every month has it)
    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    month_ago = datetime.date(year, month, min(today.day, 28))
    return f"due since {last}" if last <= month_ago else ""


def hook():
    # Only in sessions under the ports folder (the parent of ouro-tools).
    project = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    if not (project.rstrip("/") + "/").startswith(os.path.dirname(HERE) + "/"):
        return
    message = due()
    if message:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": f"The monthly upstream check of the emulators and tools is {message}. "
                                 f"Tell the user and offer to run it now; how: {DOC}."}}))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "snapshot":
        snapshot()
    elif command == "changed":
        changed()
    elif command == "due":
        message = due()
        if message:
            print(message)
    elif command == "hook":
        hook()
    else:
        sys.exit("usage: upstream-check.py changed|snapshot|due|hook")
