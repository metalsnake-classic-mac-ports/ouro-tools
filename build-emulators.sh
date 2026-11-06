#!/bin/sh
# Build the emulators the Ouro ports use, into this folder:
#   basilisk/     Basilisk II  } from metalsnake-classic-mac-ports/ouro-macemu,
#   sheepshaver/  SheepShaver  } branch ouro (Unix build, SDL2 via sdl2-compat, no JIT)
#   systemless/   systemless 0.109.0 with its debugger socket
#
# Usage: build-emulators.sh [basilisk|sheepshaver|systemless|all]   (default: all)
# Needs: brew install autoconf automake libtool mpfr gmp sdl2-compat
#        (systemless: a Rust toolchain with cargo)
set -e
cd "$(dirname "$0")"
TOOLS="$(pwd)"
WHAT="${1:-all}"
URL=https://github.com/metalsnake-classic-mac-ports/ouro-macemu.git

checkout() {   # DIR: clone or update the ouro branch
    if [ -d "$1/.git" ]; then
        git -C "$1" checkout -q ouro
        git -C "$1" pull -q --ff-only
    else
        git clone -q -b ouro "$URL" "$1"
    fi
}

# slirp (networking) is K&R C: compile C with gnu89.
export CFLAGS="-O2 -std=gnu89 -Wno-implicit-function-declaration -Wno-int-conversion"
export CPPFLAGS="-I/opt/homebrew/include" LDFLAGS="-L/opt/homebrew/lib"

# The Makefiles have no header dependencies: always build from clean.
if [ "$WHAT" = basilisk ] || [ "$WHAT" = all ]; then
    checkout basilisk
    (cd basilisk/BasiliskII/src/Unix &&
     NO_CONFIGURE=1 ./autogen.sh &&
     ./configure --enable-sdl-video --enable-sdl-audio --without-gtk \
         --disable-jit-compiler --without-mon --without-esd --without-x &&
     make clean >/dev/null && make -j8)
    echo "built $TOOLS/basilisk/BasiliskII/src/Unix/BasiliskII"
fi
if [ "$WHAT" = sheepshaver ] || [ "$WHAT" = all ]; then
    checkout sheepshaver
    make -C sheepshaver/SheepShaver links >/dev/null
    (cd sheepshaver/SheepShaver/src/Unix &&
     NO_CONFIGURE=1 ./autogen.sh &&
     ./configure --enable-sdl-video --enable-sdl-audio --without-gtk \
         --without-mon --without-esd --without-x --disable-jit &&
     make clean >/dev/null && make -j8)
    echo "built $TOOLS/sheepshaver/SheepShaver/src/Unix/SheepShaver"
fi
if [ "$WHAT" = systemless ] || [ "$WHAT" = all ]; then
    # Homebrew's systemless has no debugger socket (Harry's re/tools/sl_peek.py needs it).
    cargo install systemless --version 0.109.0 --locked --features debug-server --root systemless
    echo "built $TOOLS/systemless/bin/systemless"
fi
