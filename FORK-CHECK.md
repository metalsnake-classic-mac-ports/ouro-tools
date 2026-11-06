# macemu fork check

Last check: 2026-11-06

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
| RandoOnSteam/PocketShaver | [`48319f9f`](https://github.com/RandoOnSteam/PocketShaver/commit/48319f9fb7ac10e9915e6c5f846b632bd0c9a7c8) | SheepShaver `sheepshaver_glue.cpp`: one line (`gpr(28) = 0` removed) against a crash when a guest app is force-quit | from the cloud run 2026-11-06, not yet read here; cherry-picks cleanly onto `ouro` |
| e-z-g/macemu | [`4584883c`](https://github.com/e-z-g/macemu/commit/4584883c89177c5745e36d9e0de2c1d6650460e9) | pref `singlemode`: offer the Mac only the screen size given | could pin the screen size for scripted runs; not yet read |
| RandoOnSteam/PocketShaver | `41ca2f49` | "a host of stalls, hangs, crashes": the ADB part (`adb.cpp`) may matter, the rest is JIT / CMake | watch; mixed commit, would need splitting |

## Decided

- Not taken: e-z-g `be111582` (`[present]` lines every ten seconds without
  a switch); everything Android, iOS / Mac Catalyst, Metal gfxaccel, JIT,
  Mac OS X guests; RandoOnSteam `fea656ee` / `c73ed75d` (ISO / TOAST CD
  images, 64-bit file handling - large, conflicts with Windows files; only
  if a game needs a CD image).
- The emulator monitor's newer commands `deploy`, `find`, `cat`, `fetch`
  (RandoOnSteam `4b4b99db`, `72c4b633`) live in the native client
  (`tools/emumonitor.c`), not in the emulator; `disks` is already in `ouro`.

## Ploos-AS/MacSandbox

A Basilisk II fork that records CPU and memory "evidence" (memory writes,
runtime sessions) for malware analysis. State on 2026-11-06: last commit
2026-09-12; it does not record the guest's A-line traps (Toolbox calls),
and its event counter stops at 4096. Not usable to trace a game yet;
Classetta's `--trace-traps` and Unicorn remain the tools for that.
