# TODO

Open work only; remove items when done.

- **Complete System 7.0 and 7.5 test environments for Basilisk II.**
  `system75-sound*.dsk` is the 7.5 "Disk Tools" System Folder (a minimal
  one) and `system70.dsk` / `System70_boot.dsk` are not set up as test
  systems. Wanted: a full install of each (7.5 as 7.5.3 / 7.5.5 if
  available), Sound Manager 3.1, File System Manager 1.2 (for the shared
  folder), and the tools to unpack, pack and mount: StuffIt Expander /
  Deluxe, Disk Copy (4.2 refuses the current 7.5 disk: find out which
  support it misses, or use DiskDup+ / ShrinkWrap), BinHex. Make them
  reproducible like `make-sound-disk.sh`, with clean copies, and list
  them in the README.

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

- **Later (postponed 2026-11-13): record and replay a game's input in the
  emulator.** A hook in ouro-macemu at the game's frame start (one address
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
