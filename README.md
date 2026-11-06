# ouro-tools

Tools shared by the [Ouro ports](https://github.com/metalsnake-classic-mac-ports)
(Ouro-S.C.Out, Ouro-Harry-the-Handsome-Executive, ...): the emulators
that run the original games, the analysis library that reads, disassembles
and runs their code (`re/`), and the place for the Mac ROMs and system
disks they need. The ports find this folder as `../ouro-tools` from their
repository root, or through the environment variable `OURO_TOOLS`.

This repository holds only the scripts and this description. **ROMs and
system software are Apple's and are not here** - bring your own; the
emulator checkouts and builds are made by `build-emulators.sh`.
`.gitignore` keeps all of them out of git.

## Setup

    git clone https://github.com/metalsnake-classic-mac-ports/ouro-tools.git
    brew install autoconf automake libtool mpfr gmp sdl2-compat
    ouro-tools/build-emulators.sh          # or: basilisk | sheepshaver | systemless

The emulators come from
[ouro-macemu](https://github.com/metalsnake-classic-mac-ports/ouro-macemu),
branch `ouro`: kanjitalk755's Basilisk II and SheepShaver with fixes
collected from other forks (arm64 spinlocks, an extfs overflow), runs
without a window, and an emulator monitor that takes clicks, keys and
screenshots over a local socket. Its README lists every difference from
kanjitalk755/macemu and where it comes from.

## Layout

| Path | What | Source |
|---|---|---|
| `../ouro-macemu/` | the [ouro-macemu](https://github.com/metalsnake-classic-mac-ports/ouro-macemu) checkout next to this folder (`OURO_MACEMU`): Basilisk II (68k Macs) is `BasiliskII/src/Unix/BasiliskII`, SheepShaver (PowerPC Macs) `SheepShaver/src/Unix/SheepShaver` | `build-emulators.sh` (clones it if missing) |
| `systemless/bin/systemless` | [systemless](https://github.com/benletchford/systemless) 0.109.0 (a reimplemented Toolbox that runs 68k / PPC apps without ROM or System), built with its debugger socket - Homebrew's build has none | `build-emulators.sh` (needs cargo) |
| `roms/PERFORMA.ROM` | a 68040 Mac ROM for Basilisk II, e.g. Performa 630 (1 MB) | yours |
| `roms/newworld86.rom` | a New World ROM for SheepShaver | yours |
| `systems/System70_boot.dsk` | System 7.0 boot floppy | yours |
| `systems/system75-sound.dsk` | System 7.5 "Disk Tools" System Folder + Sound Manager 3.1, 20 MB (Basilisk II plays sound only through Sound Manager 3.x) | `make-sound-disk.sh MacOS75.ZIP Sound_Manager_3.1.sea_.hqx` (both were free Apple downloads; `brew install unar hfsutils`) |
| `systems/macos904.iso` | a Mac OS 9.0.4 install CD | yours |
| `systems/macos9-clean.dsk` | Mac OS 9.0.4 freshly installed on a 2 GB Mac OS Extended image ("Update Apple Hard Disk Drivers" off) | installed in SheepShaver |

Boot disks a game changes (an extension its installer adds) get the
game's name, e.g. `systems/system75-sound-harry.dsk`,
`systems/macos9-harry.dsk`; start them from a clean copy, then install
the game. A game's own disks and the emulator settings
(`basilisk.prefs`, `sheepshaver.prefs`, xpram) stay in its port's
`re/work/emu*`, which is not in git either.

## Running

From a port's repository root:

    # Harry, 68k build in System 7.5
    ../ouro-macemu/BasiliskII/src/Unix/BasiliskII --config re/work/emu/basilisk.prefs
    # Harry, PowerPC build in Mac OS 9
    ../ouro-macemu/SheepShaver/src/Unix/SheepShaver --config "$PWD/re/work/emu-ppc/sheepshaver.prefs"
    # S.C.Out (writes its settings, then starts Basilisk II)
    re/tools/emulator/run.sh

Without a window, driven from a script:

    SDL_VIDEODRIVER=offscreen SDL_AUDIODRIVER=dummy EMULATOR_MONITOR_PORT=19840 \
      ../ouro-macemu/BasiliskII/src/Unix/BasiliskII --config re/work/emu/basilisk.prefs &
    python3 ../ouro-macemu/tools/emumonitor.py shot /tmp/mac.png
    python3 ../ouro-macemu/tools/emumonitor.py click 20 10

Notes that cost time:
- Basilisk II's default `frameskip 6` shows 10 images per second; the
  ports set 1.
- With host input (osascript, cliclick) Basilisk II needs press - pause
  (100–150 ms) - release clicks; the monitor's `click` does that itself.
- SheepShaver after a fresh Mac OS 9 install has no sound output
  selected in the Sound control panel: games that open a sound channel
  quit until it is selected.
- The monitor's `quit` ends the emulator without shutting the Mac down:
  the next Mac OS 9 boot shows "did not shut down properly" (click Done).

## Analysis library (`re/`)

General tools for reverse engineering a classic Mac game; a port's
`re/tools/` adds only what is the game's and finds this folder as
`../ouro-tools` (or `OURO_TOOLS`). Python 3 with `capstone` and `unicorn`
in a venv, run with `python3 -I`.

| Script | What |
|---|---|
| `unpack_app.py` | application (MacBinary / resource fork / raw) → a work layout: `code/segNN.bin`, `rsrc/` |
| `macres.py` | list / dump the resources of a MacBinary file |
| `disasm.py` | 68k disassembly with Toolbox trap names and jump table targets |
| `xref.py` | callers of a 68k routine across segments |
| `thinkc_globals.py` | THINK C globals from DATA / ZERO / DREL |
| `macsbug_syms.py` | 68k routine names from MacsBug symbols (CodeWarrior, MPW) |
| `pict.py`, `topng.py` | PICT v2 (8-bit) → PNG; raw pixels + `pltt` → PNG |
| `machine.py` | 68k code in Unicorn for differential tests: segments, A5 globals, jump table, trap stubs |
| `ghidra/` | 68k: replace A-line traps, decompile all segments headless |
| `ppc/pef_traceback.py` | PEF: routine starts and names from traceback tables |
| `ppc/run_ghidra.sh`, `ppc/ghidra/` | PEF into Ghidra: names, TOC, TVectors, globals, a struct; decompile everything |
| `ppc/ppcdis.py`, `ppc/ppc_switch.py` | PowerPC disassembly with names; CodeWarrior switch tables |
| `ppc/ppcmachine.py` | PowerPC code in Unicorn for differential tests |

The method around them (how to find a game's loop, how to build a
differential test) is in the classic-mac-port skill, which is not
published yet.

## Fork check

Once a month the forks of kanjitalk755/macemu are checked for changes
worth taking into ouro-macemu: `FORK-CHECK.md` holds the date of the last
check, the procedure and the open candidates; `fork-check.sh changed` lists
the fork branches that moved since `fork-heads.tsv`. In Claude Code a
SessionStart hook (`fork-check.sh hook`, in the user settings) reminds when
the check is due.

## Working on the emulators

`../ouro-macemu` is an ordinary working copy (remotes: `origin` the
fork, `upstream` kanjitalk755): change it on branch `ouro`, commit, push,
then `build-emulators.sh` builds both emulators from it as it is (no pull,
no branch switch). The SheepShaver build's `make links` replaces a tracked
file by a link; the script hides that from `git status`
(`--assume-unchanged`), so it is not committed by mistake. Keep the branch on top of kanjitalk755's `master`
(`git rebase`) and its README's list of differences current. The
Makefiles have no header dependencies: build from clean after changing a
header (the script always does).
