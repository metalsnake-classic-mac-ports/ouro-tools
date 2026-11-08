#!/bin/sh
# Builds Retro68 (https://github.com/autc04/Retro68), the GCC toolchain for
# classic Mac programs, 68k only, for tools the ports run on the Mac itself
# (e.g. Harry's re/tools/debug-switch). Source: retro68/ (a clone with its
# submodules), build: retro68-build/ (toolchain in retro68-build/toolchain);
# both are gitignored. Takes about an hour.
#   brew install boost cmake gmp mpfr libmpc bison texinfo ninja
set -e
cd "$(dirname "$0")"
[ -d retro68 ] || git clone --recursive https://github.com/autc04/Retro68.git retro68
mkdir -p retro68-build
cd retro68-build
PATH="$(brew --prefix bison)/bin:$PATH" ../retro68/build-toolchain.bash --no-ppc --no-carbon
