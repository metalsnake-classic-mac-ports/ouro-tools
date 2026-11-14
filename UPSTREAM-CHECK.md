# Upstream check: emulators and tools

Last check: 2026-11-14

Once a month the emulators and tools we use or keep an eye on - but do not
fork - are checked for changes worth having. The list, with what to look
for in each project, is `PROJECTS` at the top of `upstream-check.py`
(groups: emulators, analysis tools, archive and disk tools, ideas); to
watch another project, add it there. A SessionStart hook in Claude Code
(`upstream-check.py hook`) reminds when the date above is more than a
month old. The macemu forks (Basilisk II, SheepShaver) have their own
check, `FORK-CHECK.md`.

## How to check

1. `python3 -I upstream-check.py changed` lists, per project, what is new
   since `upstream-state.json`: releases, commits (big repositories only on
   the watched paths, with the files they touch; at most 15 shown, the
   rest linked), a repository that went archived, new revisions of the
   MAME wiki's Mac pages (with a diff link), and whether Homebrew has a
   newer MAME than the one installed.
2. Read what sounds relevant (`gh api repos/OWNER/REPO/commits/SHA`, or the
   pull request). Worth having, by group:
   - **Emulators**: fixes to the machines and CPUs we use (MAME: Quadra
     700 / 630 / 900, IIci, SE/30, Plus, Classic, `pmac6100`,
     `pwrmacg3`; the 68040's timing, FPU, MMU; ASC sound, SCSI, floppy,
     ADB, video); anything for scripting, headless runs, screenshots,
     save states, debugging, deterministic runs; new working machines.
     DingusPPC and Snow: what would make them usable here (see their
     notes in the README and the skill's related-projects.md).
   - **Analysis tools** (Unicorn, Capstone, Ghidra, Retro68): fixes to
     m68k / PowerPC emulation, disassembly or decompilation - a Unicorn
     fix can change what a harness records, so rerun the differential
     tests after updating it; breaking API changes.
   - **Archive and disk tools**: new formats (Tomes, Apple Backup,
     DiskDoubler / StuffIt methods), fixes to forks or Finder info.
   - **Ideas**: whatever changes the verdict written next to the project.
   - Not: other systems, networking, BeBox / Model 3, iOS / Android.
3. Write the findings into "Open" / "Decided", set "Last check", run
   `python3 -I upstream-check.py snapshot` and commit both files.

Taking a change: MAME comes from Homebrew (`brew upgrade mame` when a new
release is there; `build-emulators.sh mame`); a fix we need before a
release would mean building MAME from source (large: ask first). After an
update, run the S.C.Out check in the README ("MAME") again. Python tools
(unicorn, capstone) are updated in the venv - then run the ports'
differential tests. DingusPPC and Snow are not built here yet: build them
when we need them.

## Open (to decide)

| Project | Commits | What | Note |
|---|---|---|---|
| MAME 0.290 (not released yet; 0.289 of 2026-07-30 is current) | `d0f88216fa`, `bbaf9fff54` | Cuda: MAME exits when the Mac shuts down; PRAM kept across a reset | would let scripts end with Special > Shut Down: clean disks without deleting `Shutdown Check` (Cuda machines only: Quadra 630, PowerMacs; not the Quadra 700). Wait for the release |
| MAME 0.290 | `b7695f673a` | save state fixes (PowerPC DRC, MPC106, PCI, Cuda) | our save state hang was on the Quadra 700 (no Cuda): try again after the update |
| MAME 0.290 | `146a66f90c`, `1bb1bd00f6`, `cd157c9c6a`, `b850d81a30` | 68k MMU state across reset; ASC interrupt on FIFO status write; four 53C96 SCSI differences; VIA PB7 | general accuracy, comes with the update |
| MAME 0.290 | (wiki, Driver:Mac PPC) | Beige G3 working, more PowerMacs | for PPC games, next to SheepShaver and DingusPPC |

## Decided

- 2026-11-14: the list widened from MAME and DingusPPC to all emulators
  and tools we use or watch (Snow, QEMU, systemless, Classetta, Unicorn,
  Capstone, Ghidra, Retro68, XADMaster, macextract.py / MacExtract,
  rusty-backup, machfs, AppleBridge, Pomme, utmconfigs); their baseline is
  this date. Not watched: MacWolfSDL (archived), Mini vMac (not on
  GitHub), hfsutils (unmaintained, Homebrew).

- 2026-11-14: first check, from 2026-10-14. Nothing to do before MAME
  0.290 is released and in Homebrew. DingusPPC: a month of display, MacIO
  interrupt and timer fixes; nothing that changes the README's verdict
  (no screenshots or headless runs yet).
