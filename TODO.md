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
