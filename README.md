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
    ouro-tools/build-emulators.sh          # or: basilisk | sheepshaver | systemless | mame

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
| `retro68-build/toolchain/` | [Retro68](https://github.com/autc04/Retro68) (GCC for classic Macs, 68k only), for small programs the ports run on the Mac itself; source in `retro68/` | `build-retro68.sh` (about an hour; `brew install boost cmake gmp mpfr libmpc bison texinfo ninja`) |
| `roms/PERFORMA.ROM` | a 68040 Mac ROM for Basilisk II, e.g. Performa 630 (1 MB) | yours |
| `roms/newworld86.rom` | a New World ROM for SheepShaver | yours |
| `roms/mame/` | MAME's ROM sets (zip per machine and per device, e.g. `macqd700.zip`, `cuda.zip`), from a MAME 0.289 set | yours |
| `systems/System70_boot.dsk` | System 7.0 boot floppy | yours |
| `systems/system75-sound.dsk` | System 7.5 "Disk Tools" System Folder + Sound Manager 3.1, 20 MB (Basilisk II plays sound only through Sound Manager 3.x) | `make-sound-disk.sh MacOS75.ZIP Sound_Manager_3.1.sea_.hqx` (both were free Apple downloads; `brew install unar hfsutils`) |
| `systems/system711.dsk`, `system711.hd`, `scsi-driver-722.bin` | System 7.1.1 (System 7 Pro, Easy Install, PowerTalk removed) on an 80 MB volume: bare for Basilisk II, as a bootable SCSI disk for MAME (Quadra 700, IIci, SE/30 tested), and HD SC Setup 7.2.2's driver for `re/mkscsidisk.py` | `make-system711-disk.sh SSW-7-Pro-Disk-Images.sit` (the 12 floppy images; installs in MAME, about 3 minutes) |
| `systems/system755.dsk`, `system755.hd` | System 7.5.5 (7.5.3 Easy Install for the Quadra 700 + the 7.5.5 Update) on a 160 MB volume with MacsBug 6.5.3, File System Manager 1.2, `Utilities:` Disk Copy 6.3.3 and StuffIt Expander 4.0.2: bare for Basilisk II (shared folder works), as a SCSI disk for MAME | `make-system755-disk.sh SYSTEM_7-5-3-RETAIL.ISO Apple-Legacy-Feb_2000.iso MacsBug_6.5.3.sit stuffit_expander_4.0.2.sea_.bin` (installs in MAME, about 6 minutes; needs `scsi-driver-722.bin` and the FSM from `system75-sound-harry.dsk`) |
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
- Basilisk II shows the shared folder ("Unix") only with the File System
  Manager 1.2 or newer (`extfs.cpp` asks Gestalt; otherwise the log says
  "FSM <1.2 found, disabling ExtFS"). System 7.5.0 has an older one:
  `system75-sound-harry.dsk` has the "File System Manager" 1.2 extension
  (from Apple's File System Manager 1.2 SDK, user's download) in its
  Extensions folder since 2026-11-08 (before: `system75-sound-harry.before-fsm12.dsk`);
  `system75-sound.dsk` does not yet. Without it: put files onto a disk
  image with hfsutils while the emulator is off
  (`retro68-build/toolchain/bin/hmount DISK; hcopy -m FILE.bin :Name`,
  `hcopy -b` for BinHex; `humount`). hcopy takes MacBinary II only (a
  MacBinary I header needs the version bytes 129 and the CRC); a host
  archive unpacked with `unar -forks fork` keeps forks and Finder info.
- Disk Copy 4.2 does not run on the System 7.5 disk ("will not run on this
  kind of Macintosh since certain required support is not provided").
- The monitor's `quit` ends the emulator without shutting the Mac down:
  the next Mac OS 9 boot shows "did not shut down properly" (click Done).

## MAME

[MAME](https://www.mamedev.org/) emulates the Macs at the hardware level
(the real ROM, VIA, ASC sound, SCSI, the video chips, the ADB / Egret /
Cuda microcontrollers) at their clock, where Basilisk II and SheepShaver
patch the ROM and run as fast as the host. Use it next to them, not
instead:

- **reading the running original**: the Lua script `re/mame/drive.lua`
  sends keys, takes screenshots, dumps the application's globals and
  prints registers and the call chain at given emulated times; MAME's
  debugger (`-debug`) has breakpoints, watchpoints and `trace`. Basilisk
  II has none of this beyond the monitor socket.
- timing and sound as on a given model (a game that is not limited by
  `TickCount` runs at that Mac's speed); save states (F6 / F7);
- Macs Basilisk II cannot run: compact Macs (Plus, SE, Classic), System 6.

It is slower to set up: no shared folder (files go onto disk images with
hfsutils while MAME is off), disks need a partition map and a driver
(`re/mkscsidisk.py`), and every machine needs its microcontroller ROMs.
PowerPC (`pmac6100`, `pwrmacg3`) is young in MAME (0.290 made the G3
"working"); SheepShaver stays the tool for PowerPC games.

Install: `build-emulators.sh mame` (Homebrew's bottle, 0.289). ROMs: the
zips of the machines and devices into `roms/mame/` (`mame -rompath
roms/mame -verifyroms 'mac*'` tells what is missing). With the 0.289 set
every 68k Mac and `pmac6100`, `pwrmacg3`, `imac` verify as good;
`macpb100`, `macprtb` and `mac2bios` run with "best available" (chips no one
has dumped). Our Basilisk ROM `PERFORMA.ROM` is MAME's `06684214.bin`
(Quadra 630 / LC 580).

A boot disk from a Basilisk II volume (System 7.5 here; the driver is
HD SC Setup 7.0.1's, which is on `System70_boot.dsk`):

    H=retro68-build/toolchain/bin
    $H/hmount systems/System70_boot.dsk && $H/hcopy -m ':Apple HD SC Setup' /tmp/hdsc.bin && $H/humount
    python3 -I re/macres.py dump /tmp/hdsc.bin /tmp/hdsc        # -> /tmp/hdsc/scsi_128.bin
    cp systems/system75-sound.dsk WORK/sys75.dsk                # add the game: hcopy -m into
                                                                # ':System Folder:Startup Items:'
    python3 -I re/mkscsidisk.py WORK/sys75.dsk /tmp/hdsc/scsi_128.bin WORK/boot.hd
    ./run-mame.sh macqd700 WORK -ramsize 8M -hard1 WORK/boot.hd

`run-mame.sh <machine> <work dir> [options]` sets the ROM path and keeps
PRAM, settings and screenshots in the work dir; `MAME_HEADLESS=1` runs
without window and sound at full speed (6-10× real time), `MAME_DRIVE`
loads `re/mame/drive.lua` (its header lists the verbs). Example: S.C.Out
(set to "system display", see Ouro-S.C.Out NOTES.md) from Startup Items to
level 1 and its map (`A5-0x6546`) dumped:

    MAME_HEADLESS=1 MAME_DRIVE="35 key return; 46 key cmd+g; 52 key return; 56 dump -0x6546,1920,map.bin; 57 exit" \
      ./run-mame.sh macqd700 WORK -ramsize 8M -hard1 WORK/boot.hd

Notes that cost time:
- For the older Macs (IIci, SE/30, LC, ...: less memory, no 7.5)
  `systems/system711.hd` is ready made (`make-system711-disk.sh`). It also
  shows how to drive an installer: `drive.lua`'s `feed` changes the
  floppies. `systems/system755.hd` (`make-system755-disk.sh`) is the
  full 7.5.5 with MacsBug; its script shows an install from CD and an
  update from a folder per disk (the Installer takes a folder named like
  a disk for the disk), and `click` for buttons without a key.
- Apple's Legacy Recovery CD (2000) has every system from 1.0 to 8.1,
  the updates and Disk Tools per model, as NDIF images (`re/ndif.py`);
  System 6.0.8 from it boots the Mac Plus and Classic. MPW's `ROM Maps`
  (MPW 3.5) name the ROM routines of 24 models, Quadra 700 included.
- Quadra 700 (`macqd700`) with System 7.5 on the disk above works;
  `-ramsize` takes only the listed sizes (`mame -listxml macqd700 | grep
  ramoption`; 4M default, 8M works; 20M hung in the ROM at start-up).
  Quadra 630 boots the same disk on its SCSI bus
  (`-f108:ata:0 "" -f108:scsi:0 harddisk -hard boot.hd`); `-hard1` there
  is the ATA disk, which needs an ATA driver.
- System 7.0 (`System70_boot.dsk`) on the Quadra 700 starts programs but
  S.C.Out hung in a system list walk after Game → Play; the Quadra 700
  shipped with 7.0.1. Use 7.5.
- The built-in video starts in black and white. The depth is in the slot
  PRAM: in `WORK/nvram/macqd700/rtc` (256 bytes of PRAM, written when MAME
  quits) byte 0x48 is the mode, 0x80 = 1 bit … 0x83 = 8 bit; with MAME
  off: `printf '\x83' | dd of=WORK/nvram/macqd700/rtc bs=1 seek=72 conv=notrunc`.
- The second floppy drive needs `-fdc:1 35hd` (then `-flop2`); a floppy
  mounts about 20 s later than in Basilisk II.
- `drive.lua` reads memory through the MMU (`readv_*`); CurrentA5 is the
  running application's A5, the A5 register may belong to the system.

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
| `pict.py`, `topng.py` | PICT v1/v2 (all bitmap opcodes, 1-8 bit, regions) → PNG; raw pixels + `pltt` → PNG |
| `ppat.py` | colour pixel pattern (`ppat`) → PNG |
| `ndif.py` | Disk Copy 6 image (NDIF, `rohd`/`hdro`, ADC compressed: the Legacy Recovery CD, Apple's downloads) → raw disk image; hdiutil no longer reads NDIF. hfsutils mounts only images of 800K or more: pad smaller ones |
| `tomacbinary.py` | a macOS file with resource fork and Finder info (`unar -forks fork`) → MacBinary II for `hcopy -m` |
| `mkscsidisk.py` | a bare HFS volume (a Basilisk II disk) → a bootable SCSI disk for MAME: driver descriptor, partition map, driver, Apple_HFS |
| `mame/drive.lua` | MAME: timed keys, screenshots, globals dumps, registers and call chain (`run-mame.sh`, `MAME_DRIVE`) |
| `machine.py` | 68k code in Unicorn for differential tests: segments, A5 globals, jump table, trap stubs; condition codes from stubs only through `set_ccr` (SR writes are refused: Unicorn loses them, checked at start-up) |
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
