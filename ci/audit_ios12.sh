#!/bin/bash
set -euo pipefail

PROJECT="MangaReader12.xcodeproj"
SCHEME="MangaReader12"

printf '== Toolchain ==\n'
xcodebuild -version
xcrun --sdk iphoneos --show-sdk-version
swiftc --version

XCODE_VERSION="$(xcodebuild -version | awk 'NR==1 {print $2}')"

if [[ "$XCODE_VERSION" != 15.4* ]]; then
  echo "ERROR: canonical CI requires Xcode 15.4; got $XCODE_VERSION" >&2
  exit 10
fi

printf '\n== Build setting audit ==\n'

SETTINGS="$(
  xcodebuild \
    -project "$PROJECT" \
    -scheme "$SCHEME" \
    -configuration Release \
    -sdk iphoneos \
    -showBuildSettings
)"

echo "$SETTINGS" | grep -E \
  '^[[:space:]]*(IPHONEOS_DEPLOYMENT_TARGET|SWIFT_VERSION|SDKROOT|SUPPORTED_PLATFORMS|TARGETED_DEVICE_FAMILY) ='

DEPLOYMENT_TARGET="$(
  echo "$SETTINGS" |
  awk -F' = ' \
    '/^[[:space:]]*IPHONEOS_DEPLOYMENT_TARGET =/ {print $2; exit}'
)"

if [[ "$DEPLOYMENT_TARGET" != "12.0" ]]; then
  echo "ERROR: deployment target drifted to $DEPLOYMENT_TARGET" >&2
  exit 11
fi

printf '\n== Framework audit ==\n'

if grep -R \
  --line-number \
  --include='*.swift' \
  -E '^[[:space:]]*import[[:space:]]+(SwiftUI|Combine)([[:space:]]|$)' \
  MangaReader12
then
  echo "ERROR: SwiftUI or Combine import detected." >&2
  exit 12
fi

printf '\n== Swift concurrency audit ==\n'

if grep -R \
  --line-number \
  --include='*.swift' \
  -E \
  'func[[:space:]].*\)[[:space:]]+async([[:space:]]|throws)|\)[[:space:]]+async[[:space:]]*\{|\bawait[[:space:]]+[A-Za-z_][A-Za-z0-9_.]*[[:space:]]*\(' \
  MangaReader12
then
  echo "ERROR: async/await syntax detected." >&2
  exit 13
fi

echo
echo "PASS: source/build settings remain pinned to iOS 12.0 and Swift 5 language mode."
