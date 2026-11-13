# TODO

Open work only; remove items when done.

- **Test systems: what is left.** `system755.dsk` / `system711.dsk` are
  full installs with MacsBug, StuffIt Expander and Disk Copy (7.5.5) and
  boot in Basilisk II and MAME. Open: whether 7.5.5 plays sound in
  Basilisk II (it has Sound Manager 3.x built in; not listened to yet) -
  then `system75-sound*.dsk` can go and the ports' run scripts move to
  `system755.dsk`; the games installed on it per port (`system755-<game>`);
  MacsBug on the 7.1.1 disk (6.2.2); BinHex. MacsBug cannot be entered by
  key in MAME (Cmd+Power does nothing) - it still catches crashes and
  `_Debugger`.

- **Check the harnesses against the emulator, not only the ports against
  the harnesses.** A harness that emulates the Toolbox or SANE wrongly
  records a wrong "original", and the differential tests then agree with
  a wrong port (Quagmire, 2026-11-12: lost condition codes made the
  rounding look like truncation; only a video of the emulated game showed
  it). Wanted: a half-automatic check per port - a few scenarios run in
  Basilisk II / SheepShaver through the emulator monitor (keys, then
  screenshots per frame or the memory of a few globals), positions
  measured and compared with the harness's dump. Needs a way to reach a
  level or state in the original quickly (patched start level, a saved
  state, or memory reads/writes in the monitor) - a patched New Game in
  Quagmire went black and hung in level 8.
  MAME does most of this already (README, "MAME"): `re/mame/drive.lua`
  sends keys and dumps globals at emulated times; S.C.Out's level 1 map
  from the running original matched the harness's `emu_level1.json`
  (2026-11-13). Left: the same for Harry and Quagmire, and per-frame
  dumps (a breakpoint at the game's frame start instead of times).

- **Later (postponed 2026-11-13): record and replay a game's input in the
  emulator.** (MAME may be the easier place: Lua at a breakpoint can read
  and write memory without changing the emulator.) A hook in ouro-macemu at the game's frame start (one address
  per game; probably needs the interpreter, not the JIT) writes what the
  game reads each frame - the key map, mouse and button, `TickCount` -
  and `RandSeed` at the start into a file, in the format of the ports'
  input recordings (Ouro-Quagmire/TODO.md, "Later"). Gain: a recording
  made by playing the original fits the original, so the port and the
  Unicorn harness must follow it frame by frame to the level's end, and
  every difference is surely their bug; it also checks a harness against
  the real system (the item above). The same hook writing the recorded
  values into memory before the game reads them replays it exactly in the
  emulator (sending keys from outside does not: the emulator is not in
  step with the game's frames, and the original seeds its random numbers
  from the clock) - mostly useful to watch a difference found in Unicorn.
  To find out per game: which traps and low-memory globals it reads its
  input from. Effort medium to high, so postponed; a recording option in
  a port is the cheaper first step.

- **MAME: open points.** Quadra 700 with 20M RAM hangs in the ROM at
  start-up (4M / 8M work; 36M / 68M untried). The PRAM byte for 8-bit
  video is known for the Quadra 700 only (other machines: change it once
  in the Monitors control panel and compare the nvram files). System 7.1.1
  is there (`make-system711-disk.sh`); a System 6 disk for the compact
  Macs is missing (the images the MAME wiki links on
  rbelmont.mameworld.info are gone, NXDOMAIN 2026-11-13).
