# Upstream check: MAME and DingusPPC

Last check: 2026-11-14

Once a month the emulators we use but do not fork are checked for changes
worth having: [MAME](https://github.com/mamedev/mame) (only its Mac
drivers, the 68k and PowerPC CPUs, the Mac chips, its debugger and Lua)
and [DingusPPC](https://github.com/dingusdev/dingusppc). A SessionStart
hook in Claude Code (`upstream-check.py hook`) reminds when the date above
is more than a month old. The macemu forks have their own check
(`FORK-CHECK.md`).

## How to check

1. `python3 -I upstream-check.py changed` lists what is new since
   `upstream-state.json`: releases, commits on the watched paths (MAME:
   with the files they touch), new revisions of the MAME wiki's Mac pages
   (with a diff link), and whether Homebrew has a newer MAME than the one
   installed. The watched paths are at the top of the script.
2. Read what sounds relevant (`gh api repos/mamedev/mame/commits/SHA`, or
   the pull request). Worth having:
   - MAME: fixes to the machines we use (Quadra 700 / 630 / 900, IIci,
     SE/30, Plus, Classic; `pmac6100`, `pwrmacg3`), the 68040 (timing,
     FPU, MMU), ASC sound, SCSI, floppy, ADB, video; anything for Lua,
     the debugger, save states, headless runs; new working machines.
   - DingusPPC: anything that makes it scriptable (screenshots, headless,
     save states, a debugger over a socket), the 68k debugging context,
     deterministic mode, fixes to the 7500 / 6100 / G3, more Mac OS
     versions booting.
   - Not: other systems' drivers, networking cards, BeBox / Model 3.
3. Write the findings into "Open" / "Decided", set "Last check", run
   `python3 -I upstream-check.py snapshot` and commit both files.

Taking a change: MAME comes from Homebrew (`brew upgrade mame` when a new
release is there; `build-emulators.sh mame`); a fix we need before a
release would mean building MAME from source (large: ask first). After an
update, run the S.C.Out check in the README ("MAME") again. DingusPPC is
not built here yet (README, "DingusPPC"): build it when we need it.

## Open (to decide)

| Project | Commits | What | Note |
|---|---|---|---|
| MAME 0.290 (not released yet; 0.289 of 2026-07-30 is current) | `d0f88216fa`, `bbaf9fff54` | Cuda: MAME exits when the Mac shuts down; PRAM kept across a reset | would let scripts end with Special > Shut Down: clean disks without deleting `Shutdown Check` (Cuda machines only: Quadra 630, PowerMacs; not the Quadra 700). Wait for the release |
| MAME 0.290 | `b7695f673a` | save state fixes (PowerPC DRC, MPC106, PCI, Cuda) | our save state hang was on the Quadra 700 (no Cuda): try again after the update |
| MAME 0.290 | `146a66f90c`, `1bb1bd00f6`, `cd157c9c6a`, `b850d81a30` | 68k MMU state across reset; ASC interrupt on FIFO status write; four 53C96 SCSI differences; VIA PB7 | general accuracy, comes with the update |
| MAME 0.290 | (wiki, Driver:Mac PPC) | Beige G3 working, more PowerMacs | for PPC games, next to SheepShaver and DingusPPC |

## Decided

- 2026-11-14: first check, from 2026-10-14. Nothing to do before MAME
  0.290 is released and in Homebrew. DingusPPC: a month of display, MacIO
  interrupt and timer fixes; nothing that changes the README's verdict
  (no screenshots or headless runs yet).
