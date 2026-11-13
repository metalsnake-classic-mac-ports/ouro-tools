#!/bin/sh
# Build the emulators the Ouro ports use:
#   Basilisk II and SheepShaver in the ouro-macemu checkout next to this
#   folder (OURO_MACEMU, default ../ouro-macemu; cloned with branch ouro if
#   missing): BasiliskII/src/Unix/BasiliskII, SheepShaver/src/Unix/SheepShaver
#   (Unix build, SDL2 via sdl2-compat, no JIT);
#   systemless 0.109.0 with its debugger socket into systemless/ here;
#   MAME from Homebrew (bottled; run it with run-mame.sh).
#
# An existing checkout is built as it is (no pull, no branch switch), so
# work in progress there is never touched.
#
# Usage: build-emulators.sh [basilisk|sheepshaver|systemless|mame|all]   (default: all)
# Needs: brew install autoconf automake libtool mpfr gmp sdl2-compat
#        (systemless: a Rust toolchain with cargo)
set -e
cd "$(dirname "$0")"
TOOLS="$(pwd)"
WHAT="${1:-all}"
MACEMU="${OURO_MACEMU:-$(cd .. && pwd)/ouro-macemu}"

checkout() {
    if [ ! -d "$MACEMU/.git" ]; then
        git clone -q -b ouro https://github.com/metalsnake-classic-mac-ports/ouro-macemu.git "$MACEMU"
        git -C "$MACEMU" remote add upstream https://github.com/kanjitalk755/macemu.git
    fi
    echo "building $MACEMU at $(git -C "$MACEMU" rev-parse --abbrev-ref HEAD) $(git -C "$MACEMU" log -1 --format=%h)"
}

# slirp (networking) is K&R C: compile C with gnu89.
export CFLAGS="-O2 -std=gnu89 -Wno-implicit-function-declaration -Wno-int-conversion"
export CPPFLAGS="-I/opt/homebrew/include" LDFLAGS="-L/opt/homebrew/lib"

# The Makefiles have no header dependencies: always build from clean.
if [ "$WHAT" = basilisk ] || [ "$WHAT" = all ]; then
    checkout
    (cd "$MACEMU/BasiliskII/src/Unix" &&
     NO_CONFIGURE=1 ./autogen.sh &&
     ./configure --enable-sdl-video --enable-sdl-audio --without-gtk \
         --disable-jit-compiler --without-mon --without-esd --without-x &&
     make clean >/dev/null && make -j8)
    echo "built $MACEMU/BasiliskII/src/Unix/BasiliskII"
fi
if [ "$WHAT" = sheepshaver ] || [ "$WHAT" = all ]; then
    checkout
    make -C "$MACEMU/SheepShaver" links >/dev/null
    # `make links` replaces a tracked file by a link and adds Windows/m4:
    # keep both out of `git status` so they are not committed by mistake.
    git -C "$MACEMU" update-index --assume-unchanged SheepShaver/src/kpx_cpu/src/cpu/jit/x86/codegen_x86.h
    grep -qx '/SheepShaver/src/Windows/m4' "$MACEMU/.git/info/exclude" 2>/dev/null ||
        echo '/SheepShaver/src/Windows/m4' >> "$MACEMU/.git/info/exclude"
    (cd "$MACEMU/SheepShaver/src/Unix" &&
     NO_CONFIGURE=1 ./autogen.sh &&
     ./configure --enable-sdl-video --enable-sdl-audio --without-gtk \
         --without-mon --without-esd --without-x --disable-jit &&
     make clean >/dev/null && make -j8)
    echo "built $MACEMU/SheepShaver/src/Unix/SheepShaver"
fi
if [ "$WHAT" = systemless ] || [ "$WHAT" = all ]; then
    # Homebrew's systemless has no debugger socket (Harry's re/tools/sl_peek.py needs it).
    cargo install systemless --version 0.109.0 --locked --features debug-server --root "$TOOLS/systemless"
    echo "built $TOOLS/systemless/bin/systemless"
fi
if [ "$WHAT" = mame ] || [ "$WHAT" = all ]; then
    # Hardware-level emulation with a debugger and Lua (README, "MAME").
    command -v mame >/dev/null || brew install mame
    echo "mame $(mame -version)"
fi
