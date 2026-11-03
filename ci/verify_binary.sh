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

# Derive the expected version from both Xcode target configurations.
# A hardcoded check would reject every legitimate future build increment.
PROJECT="MangaReader12.xcodeproj/project.pbxproj"
CONFIG_VERSIONS="$(sed -n 's/.*CURRENT_PROJECT_VERSION = \\([0-9][0-9]*\\);/\\1/p' "$PROJECT")"
CONFIG_COUNT="$(printf '%s\\n' "$CONFIG_VERSIONS" | wc -l | tr -d ' ')"
EXPECTED_VERSION="$(printf '%s\\n' "$CONFIG_VERSIONS" | sort -u)"
if [[ "$CONFIG_COUNT" != "2" || ! "$EXPECTED_VERSION" =~ ^[0-9]+$ ]]; then
  echo "ERROR: Debug/Release CURRENT_PROJECT_VERSION is missing or inconsistent" >&2
  exit 4
fi
VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$APP_PATH/Info.plist")
if [[ "$VERSION" != "$EXPECTED_VERSION" ]]; then
  echo "ERROR: wrong embedded CFBundleVersion: $VERSION (expected $EXPECTED_VERSION)" >&2
  exit 4
fi
echo "PASS: embedded CFBundleVersion is $EXPECTED_VERSION."
