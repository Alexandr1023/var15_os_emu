#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  set -- --vfs vfs_examples/minimal.xml
fi

python3 -m src.shell_emulator "$@"
