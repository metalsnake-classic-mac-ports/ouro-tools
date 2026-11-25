# macemu fork check

Last check: 2026-11-25

Once a month the forks of kanjitalk755/macemu are checked for changes worth
taking into [ouro-macemu](https://github.com/metalsnake-classic-mac-ports/ouro-macemu)
(branch `ouro`). A SessionStart hook in Claude Code (`fork-check.sh due`)
reminds when the date above is more than a month old.

## How to check

1. `./fork-check.sh changed` lists every fork branch that is new or moved
   since `fork-heads.tsv` (repository, branch, old head or `new`).
2. For each, read the new commits (`git fetch --filter=blob:none` into a
   scratch clone of ouro-macemu; never build or run fork code without
   asking). Also check kanjitalk755's `master` for new commits and whether
   `ouro` rebases onto it cleanly.
3. Worth taking: fixes in the shared core (CPU, interrupts, timers, sound,
   video, ADB, extfs, disks, prefs) that reach the Unix/SDL build on macOS
   arm64; anything for scripting, headless runs, tracing, recording,
   deterministic time. Not: iOS, Android, Windows-only, JIT, Metal/gfxaccel,
   Mac OS X guests - unless a commit also fixes a generic bug.
4. Look at Ploos-AS/MacSandbox even when quiet (below).
   `changed` never lists a branch that has not moved since it entered
   `fork-heads.tsv`. Every branch that was there on 2026-11-06 was reviewed
   once on 2026-11-16 (below); to repeat that for all branches,
   `./fork-check.sh ahead > ahead.tsv` lists every branch with commits its
   base lacks, and `python3 -I fork-triage.py ahead.tsv SCRATCH` fetches
   them blobless and prints the commits left after dropping upstream
   subjects and paths outside our build.
5. Write the findings into "Open" / "Decided" here, set "Last check", then
   `./fork-check.sh snapshot`, and commit both files.

Taking a change: commit it onto `ouro` (cherry-pick `-x`, or a port with
the source named), add it to ouro-macemu's README list, rebuild with
`build-emulators.sh`, test, push.

## Open (to decide)

| Fork | Commit | What | Note |
|---|---|---|---|
| kanjitalk755/macemu `master` | [`9107beb2`](https://github.com/kanjitalk755/macemu/commit/9107beb2), [`37a86824`](https://github.com/kanjitalk755/macemu/commit/37a86824) | ExtFS: minimal Mac OS 9 fixes ([PR #330](https://github.com/kanjitalk755/macemu/pull/330), replaces the closed #329: buffer bounds in GetVol / GetFInfo / SetFInfo, OpenDF and MakeFSSpec dispatch, stale CNIDs retired); audio_sdl3 shutdown deadlock (#331) | 2026-11-25: `ouro` rebases cleanly onto this master; the rebase drops our cherry-picks of `e2989b65` / `40bbf669` and our extfs `GetFileInfo` fix (RandoOnSteam `9bc0c66f`), which #330 contains. Needs a force-push of `ouro` |
| invariablyafk/macemu `fix-mach-timer-lost-wakeup` | [`c338b1ed`](https://github.com/invariablyafk/macemu/commit/c338b1edab90fa0355134ab71d7f20de9f1819c3) | `timer.cpp`, `PRECISE_TIMING_MACH`: the timer thread could sleep past a wake-up that `PrimeTime()` moved earlier (thread_abort before clock_sleep aborts nothing), so Time Manager tasks went overdue for seconds or for good; now a condition variable under a mutex | 2026-11-25: our macOS build uses exactly this path (no `clock_nanosleep`, so `PRECISE_TIMING_MACH`, Basilisk II and SheepShaver); games that time with the Time Manager can be hit. Recommended; not yet a PR upstream |
| RandoOnSteam/PocketShaver | `dab4f849`, `3d8c410e`, `495096d4`, `4c08ce77` | SoundBase emulation and VIA redirect (behind `MACEMU_USEVIASOUNDBASE`, ~120 lines in `audio.cpp`): sound for games that write the sound buffer and VIA directly (Populous) | watch: would matter if a port's original plays sound through SoundBase; mixed with SFL / SDL3 changes, would need splitting |
| RandoOnSteam/PocketShaver | `41ca2f49` | "a host of stalls, hangs, crashes": the ADB part (`adb.cpp`) may matter, the rest is JIT / CMake | watch; mixed commit, would need splitting |

## Decided

- 2026-11-14, taken onto `ouro` by cherry-pick `-x` (pushed 2026-11-14):
  upstream `e2989b65` (fatal Mach exceptions without GUI teardown) and
  `40bbf669` (`stfiwx`), until `ouro` is next rebased onto `master`; e-z-g
  `4584883c` (`singlemode`, off by default), here also declared as a
  Basilisk II pref. Built and booted headless (SheepShaver / Mac OS 9.0.4,
  Basilisk II / System 7.5) with and without `singlemode`. Headless runs
  cannot show its effect (`SDL_VIDEODRIVER=offscreen` clamps `screen` to the
  dummy display's 1024x768). Tested by hand in a window, Basilisk II /
  System 7.5, `screen win/1200/800`: without `singlemode`, Monitors >
  Options... lists the standard sizes and a size chosen there (800x600)
  lasts through a restart of the Mac, but the next emulator start comes up
  at 1200x800 again; with `singlemode true` it comes up at 1200x800 and
  1200x800 is the only size offered.
- 2026-11-14, not taken: RandoOnSteam `48319f9f` (stops zeroing r28, the
  68k VBR, in `execute_68k`; no reason given beyond a force-quit crash) -
  only if that crash shows up here.
- 2026-11-25, not taken: asvitkine `feat/gfxaccel-*`, `feat/rave-metal`,
  `fix/gfxaccel-*` (gfxaccel / RAVE / Metal backports from PocketShaver;
  `5c8c439b`, which keeps InstallExtFS() from running twice, only matters
  with gfxaccel's accRun sweeps) and `fix/sdl3-recenter-on-resize` (SDL3
  video, we build SDL2); invariablyafk `fix-slirp-syn-template` (slirp TCP,
  networking unused); Cronocide (RAVE / GL); RandoOnSteam (OS X guest, GL
  engine, multi-CPU, SFL, Intel JIT); carbjo / sierra760 PocketShaver
  (iOS, Catalyst); the other invariablyafk and hghpublic branches are old
  kanjitalk755 test branches or match upstream.
- Idea, not code to take: mihaip `77276172` reports every resource load
  from the `CheckLoad` hook to Infinite Mac's worker. The same hook could
  log which resources a game loads (type, id, size) behind an environment
  variable - useful when reverse engineering a port's original.
- 2026-11-16, not taken: billcavalieri `sheepforce` (head `6e90d26c`, 301
  commits, ~137,000 lines, 29 commits behind upstream): its own SheepShaver
  line - New World JIT for arm64, Metal / RAVE, a SwiftUI app with several
  VMs and an MCP server, "SheepBlaster" sound, guest tools (Sheep Shears,
  SheepBench), qcow / CHD images. The fixes that look generic are tied to
  that rework: `e1c6cd69` (lha / lhau) is in its own JIT (`nw_jit.cpp`),
  the `ppc-cpu.cpp` part is logging only; `f69ca9aa` and `b9086202` (crash
  at the end of a sound) depend on its SheepBlaster state. Only `7bbd2aa0`
  stands alone (Disk First Aid lists hard disks and CDs as floppies: the
  disk and CD drivers refuse Control 23 and number drives from 3) - a
  cosmetic Disk First Aid issue, not needed for the games.
- Not taken: e-z-g `be111582` (`[present]` lines every ten seconds without
  a switch); everything Android, iOS / Mac Catalyst, Metal gfxaccel, JIT,
  Mac OS X guests; RandoOnSteam `fea656ee` / `c73ed75d` (ISO / TOAST CD
  images, 64-bit file handling - large, conflicts with Windows files; only
  if a game needs a CD image).
- 2026-11-14, not taken: LoetLuemmel `sdl-clipboard` (`47fcfef3`,
  `78df321c`: SDL clipboard for Linux builds; macOS keeps its own); the
  RandoOnSteam `osxguest*` branches (OS X guest JIT, SFL backend, boot GUI,
  new GL engine; `fd91755c`'s `extfs.cpp` change is SFL-only); sierra760
  (gfxaccel / Metal / DrawSprocket, iOS); tordona (Windows ARM64);
  asvitkine `stfiwx*` (same change as upstream `40bbf669`).
- The emulator monitor's newer commands `deploy`, `find`, `cat`, `fetch`
  (RandoOnSteam `4b4b99db`, `72c4b633`) live in the native client
  (`tools/emumonitor.c`), not in the emulator; `disks` is already in `ouro`.

## Review of the first snapshot (2026-11-16)

The branches already in the first `fork-heads.tsv` (2026-11-06) were never
listed by `changed`. `fork-check.sh ahead` found 284 branches in 113
repositories with commits their base lacks; `fork-triage.py` left 1540
distinct commits after dropping 1008 with an upstream subject and 1307 that
touch only paths outside our build. Nothing worth taking:

- Own projects, most of the commits: rcarmo/macemu-jit and dtseto (68k JIT
  for arm64), sirmick (Unicorn core, WebRTC streaming), mihaip (Infinite Mac,
  Emscripten), billcavalieri (sheepforce, see "Decided"), brnrds /
  rscaboyke / carbjo PocketShaver (iOS), raytran08 (NetBSD wscons),
  audiocontrol-org (MIDI over SCSI), Photosounder (WAHE / Wasm), kwhr0 (its
  own 68020 / PPC interpreters), agranlund (Atari), andyvand (Android),
  PegLeg-Computer and GillesXP `zydeco_rootless` (rootless mode), robxnano
  (Meson, Qt prefs), mylordmonkeyman (libretro), Cronocide (RAVE / GL and
  the arm64 JIT; its test-and-set fix `ad80ac80` is the one `ouro` already
  has from e-z-g).
- Small and generic, but nothing a game run needs: Photosounder `1287f5a2`
  (extfs: clamp file sizes over 2 GB), omega1119 (Z8530 SCC emulation),
  DMJC (SDL joystick as ADB), dbarth (`onclose` pref, UDP tunnel,
  IOSurface screen share), mstevenson (window and cursor scaling, Fn-F
  full screen), robxnano `e2a210ef` (no keyboard shortcuts while the mouse
  is grabbed), Motardo (F3 as power key), mborjesson (`sdl_nofsscale`),
  timothy-fuchs (screen rotation), schinkelg (libslirp).
- cebix-era fixes missing from kanjitalk755's master: SLiRP buffer
  overflows (`d26ae37e`), cxmon prompt buffer (`b04dc5e5`) - networking and
  cxmon are not used in our runs.
- Old kanjitalk755 test branches carried by forks (GillesXP, mattjvw,
  armcknight, DrLex0) and build fixes for older or other systems.

## Ploos-AS/MacSandbox

A Basilisk II fork that records CPU and memory "evidence" (memory writes,
runtime sessions) for malware analysis. State on 2026-11-14 (unchanged since
2026-11-06): last commit 2026-09-12; it does not record the guest's A-line traps (Toolbox calls),
and its event counter stops at 4096. Not usable to trace a game yet;
Classetta's `--trace-traps` and Unicorn remain the tools for that.
