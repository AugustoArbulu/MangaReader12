#!/bin/bash
set -euo pipefail

APP_PATH="${1:?usage: verify_binary.sh /path/to/App.app}"
BIN="$APP_PATH/MangaReader12"

if [[ ! -f "$BIN" ]]; then
  echo "ERROR: executable not found: $BIN" >&2
  exit 2
fi

printf '== Architectures ==\n'
lipo -info "$BIN"

printf '\n== Mach-O minimum OS ==\n'
otool -l "$BIN" | awk '
  /LC_BUILD_VERSION/ {in_build=1; print; next}
  in_build && /platform|sdk|minos/ {print}
  in_build && /ntools/ {print; in_build=0}
'

if ! otool -l "$BIN" | grep -A8 LC_BUILD_VERSION | grep -q 'minos 12\.0'; then
  echo "ERROR: binary does not advertise minos 12.0" >&2
  exit 3
fi

echo "PASS: Mach-O minimum OS is iOS 12.0."
