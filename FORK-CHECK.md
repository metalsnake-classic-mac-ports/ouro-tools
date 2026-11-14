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
| kanjitalk755/macemu `master` | [`40bbf669`](https://github.com/kanjitalk755/macemu/commit/40bbf669e2be31acab5a59297ceb9ee06ba3e051) | SheepShaver kpx_cpu: implement the PowerPC `stfiwx` instruction (14 lines) | 2026-11-14: generic CPU fix in the interpreter we build; take. `ouro` rebases cleanly onto the new master (needs a force-push of `ouro`, or a merge instead) |
| kanjitalk755/macemu `master` | [`e2989b65`](https://github.com/kanjitalk755/macemu/commit/e2989b6552bb06763f404547048c569190690b0d) | SheepShaver: on a fatal Mach exception don't call `QuitEmulator()` from the exception thread (deadlock / AppKit off the main thread); let the Mach backend forward it | 2026-11-14: reaches macOS arm64; take with the rebase above |
| e-z-g/macemu | [`4584883c`](https://github.com/e-z-g/macemu/commit/4584883c89177c5745e36d9e0de2c1d6650460e9) | pref `singlemode`: offer the Mac only the screen size given | read 2026-11-14: 3 lines in `video_sdl2.cpp` (the backend our build uses) and `prefs_items.cpp`; pins the screen size for scripted runs; recommended |
| RandoOnSteam/PocketShaver | [`48319f9f`](https://github.com/RandoOnSteam/PocketShaver/commit/48319f9fb7ac10e9915e6c5f846b632bd0c9a7c8) | SheepShaver `execute_68k`: no longer zero r28 (the 68k emulator's VBR) | read 2026-11-14: no explanation beyond "crash when force-quitting a guest app"; changes the state every 68k call starts with. Recommended: not taken unless we hit that crash |
| asvitkine/macemu `extfs-macos9-fixes-upstream` | [`88f45de1`](https://github.com/asvitkine/macemu/commit/88f45de1), [`9b9fa73a`](https://github.com/asvitkine/macemu/commit/9b9fa73a) | ExtFS rework (~2000 lines in `extfs.cpp`): Mac OS 9 File Manager / catalog consistency, NavigationLib crash | branch dated 2026-11-14, by the upstream maintainer, likely a pending PR; wait until it lands on master, then it comes with the rebase. Matters for shared folders under Mac OS 9 |
| RandoOnSteam/PocketShaver | `dab4f849`, `3d8c410e`, `495096d4`, `4c08ce77` | SoundBase emulation and VIA redirect (behind `MACEMU_USEVIASOUNDBASE`, ~120 lines in `audio.cpp`): sound for games that write the sound buffer and VIA directly (Populous) | watch: would matter if a port's original plays sound through SoundBase; mixed with SFL / SDL3 changes, would need splitting |
| RandoOnSteam/PocketShaver | `41ca2f49` | "a host of stalls, hangs, crashes": the ADB part (`adb.cpp`) may matter, the rest is JIT / CMake | watch; mixed commit, would need splitting |

## Decided

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
