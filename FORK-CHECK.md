# macemu fork check

Last check: 2026-11-14

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
5. Write the findings into "Open" / "Decided" here, set "Last check", then
   `./fork-check.sh snapshot`, and commit both files.

Taking a change: commit it onto `ouro` (cherry-pick `-x`, or a port with
the source named), add it to ouro-macemu's README list, rebuild with
`build-emulators.sh`, test, push.

## Open (to decide)

| Fork | Commit | What | Note |
|---|---|---|---|
| asvitkine/macemu `extfs-macos9-fixes-upstream` | [`88f45de1`](https://github.com/asvitkine/macemu/commit/88f45de1), [`9b9fa73a`](https://github.com/asvitkine/macemu/commit/9b9fa73a) | ExtFS rework (~2000 lines in `extfs.cpp`): Mac OS 9 File Manager / catalog consistency, NavigationLib crash | branch dated 2026-11-14, by the upstream maintainer, [PR #329](https://github.com/kanjitalk755/macemu/pull/329) (open); decided 2026-11-14: wait until it lands on master, then it comes with the rebase. Matters for shared folders under Mac OS 9 |
| RandoOnSteam/PocketShaver | `dab4f849`, `3d8c410e`, `495096d4`, `4c08ce77` | SoundBase emulation and VIA redirect (behind `MACEMU_USEVIASOUNDBASE`, ~120 lines in `audio.cpp`): sound for games that write the sound buffer and VIA directly (Populous) | watch: would matter if a port's original plays sound through SoundBase; mixed with SFL / SDL3 changes, would need splitting |
| RandoOnSteam/PocketShaver | `41ca2f49` | "a host of stalls, hangs, crashes": the ADB part (`adb.cpp`) may matter, the rest is JIT / CMake | watch; mixed commit, would need splitting |

## Decided

- 2026-11-14, taken onto `ouro` by cherry-pick `-x` (not pushed yet):
  upstream `e2989b65` (fatal Mach exceptions without GUI teardown) and
  `40bbf669` (`stfiwx`), until `ouro` is next rebased onto `master`; e-z-g
  `4584883c` (`singlemode`, off by default), here also declared as a
  Basilisk II pref. Built and booted headless (SheepShaver / Mac OS 9.0.4,
  Basilisk II / System 7.5) with and without `singlemode`. Not observed:
  that it shortens the Mac's mode list - under `SDL_VIDEODRIVER=offscreen`
  `screen` is clamped to the dummy display's 1024x768, and with 1000x700
  both settings came up at 1000x700.
- 2026-11-14, not taken: RandoOnSteam `48319f9f` (stops zeroing r28, the
  68k VBR, in `execute_68k`; no reason given beyond a force-quit crash) -
  only if that crash shows up here.
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

## Ploos-AS/MacSandbox

A Basilisk II fork that records CPU and memory "evidence" (memory writes,
runtime sessions) for malware analysis. State on 2026-11-14 (unchanged since
2026-11-06): last commit 2026-09-12; it does not record the guest's A-line traps (Toolbox calls),
and its event counter stops at 4096. Not usable to trace a game yet;
Classetta's `--trace-traps` and Unicorn remain the tools for that.
