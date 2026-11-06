# ouro-tools

Tools shared by the [Ouro ports](https://github.com/metalsnake-classic-mac-ports)
(Ouro-S.C.Out, Ouro-Harry-the-Handsome-Executive, ...): the emulators
that run the original games, and the place for the Mac ROMs and system
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
| `basilisk/` | Basilisk II (68k Macs); the program is `basilisk/BasiliskII/src/Unix/BasiliskII` | `build-emulators.sh` |
| `sheepshaver/` | SheepShaver (PowerPC Macs); the program is `sheepshaver/SheepShaver/src/Unix/SheepShaver` | `build-emulators.sh` |
| `systemless/bin/systemless` | [systemless](https://github.com/benletchford/systemless) 0.109.0 (a reimplemented Toolbox that runs 68k / PPC apps without ROM or System), built with its debugger socket - Homebrew's build has none | `build-emulators.sh` (needs cargo) |
| `roms/PERFORMA.ROM` | a 68040 Mac ROM for Basilisk II, e.g. Performa 630 (1 MB) | yours |
| `roms/newworld86.rom` | a New World ROM for SheepShaver | yours |
| `systems/System70_boot.dsk` | System 7.0 boot floppy | yours |
| `systems/system75-sound.dsk` | System 7.5 "Disk Tools" System Folder + Sound Manager 3.1, 20 MB (Basilisk II plays sound only through Sound Manager 3.x) | Ouro-S.C.Out's `re/tools/emulator/make-sound-disk.sh`, from the System 7.5 floppy and Sound Manager 3.1 |
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
    ../ouro-tools/basilisk/BasiliskII/src/Unix/BasiliskII --config re/work/emu/basilisk.prefs
    # Harry, PowerPC build in Mac OS 9
    ../ouro-tools/sheepshaver/SheepShaver/src/Unix/SheepShaver --config "$PWD/re/work/emu-ppc/sheepshaver.prefs"
    # S.C.Out (writes its settings, then starts Basilisk II)
    re/tools/emulator/run.sh

Without a window, driven from a script:

    SDL_VIDEODRIVER=offscreen SDL_AUDIODRIVER=dummy EMULATOR_MONITOR_PORT=19840 \
      ../ouro-tools/basilisk/BasiliskII/src/Unix/BasiliskII --config re/work/emu/basilisk.prefs &
    python3 ../ouro-tools/basilisk/tools/emumonitor.py shot /tmp/mac.png
    python3 ../ouro-tools/basilisk/tools/emumonitor.py click 20 10

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

## Fork check

Once a month the forks of kanjitalk755/macemu are checked for changes
worth taking into ouro-macemu: `FORK-CHECK.md` holds the date of the last
check, the procedure and the open candidates; `fork-check.sh changed` lists
the fork branches that moved since `fork-heads.tsv`. In Claude Code a
SessionStart hook (`fork-check.sh hook`, in the user settings) reminds when
the check is due.

## Working on the emulators

Change `ouro-macemu` in `basilisk/` (branch `ouro`), commit, push; then
`build-emulators.sh sheepshaver` pulls the same branch into
`sheepshaver/`. Keep the branch on top of kanjitalk755's `master`
(`git rebase`) and its README's list of differences current. The
Makefiles have no header dependencies: build from clean after changing a
header (the script always does).
