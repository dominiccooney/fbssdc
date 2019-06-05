#!/bin/bash
set -e
./cpp_codegen.py | clang -x c++ -fsyntax-only /dev/stdin
