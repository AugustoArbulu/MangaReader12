#!/bin/bash
# Build two unsigned, isolated iOS12 IPAs for appinst persistence QA only.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Requires Xcode macOS iOS SDK" >&2
  exit 2
fi
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT
SDK="$(xcrun --sdk iphoneos --show-sdk-path)"
xcrun --sdk iphoneos clang \
  -arch arm64 -miphoneos-version-min=12.0 \
  -fobjc-arc -Os -Wall -Wextra -Werror \
  -isysroot "$SDK" \
  -framework UIKit -framework Foundation \
  ci/appinst_disposable/main.m \
  -o "$TEMP/WRDisposable"
for VERSION in 1 2; do
  OUT="WebReader-Appinst-Disposable-v$VERSION-iOS12-unsigned.ipa"
  if [[ -e "$OUT" || -e "$OUT.sha256" ]]; then
    echo "Refusing to overwrite $OUT" >&2
    exit 2
  fi
  mkdir -p "$TEMP/Payload/WRDisposable.app"
  cp "$TEMP/WRDisposable" "$TEMP/Payload/WRDisposable.app/WRDisposable"
  python3 - "$TEMP/Payload/WRDisposable.app/Info.plist" "$VERSION" <<'PY'
import plistlib
import sys
from pathlib import Path
path = Path(sys.argv[1])
version = sys.argv[2]
assert version in ("1", "2")
info = {
    "CFBundleDevelopmentRegion": "en",
    "CFBundleExecutable": "WRDisposable",
    "CFBundleIdentifier": "com.example.WebReaderAppinstDisposableTest",
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleName": "WR Appinst Test",
    "CFBundleDisplayName": "WR Appinst Test",
    "CFBundlePackageType": "APPL",
    "CFBundleShortVersionString": "1.0" if version == "1" else "2.0",
    "CFBundleVersion": version,
    "MinimumOSVersion": "12.0",
    "LSRequiresIPhoneOS": True,
    "UIDeviceFamily": [1, 2],
    "UIRequiredDeviceCapabilities": ["arm64"],
}
path.write_bytes(plistlib.dumps(info, sort_keys=True))
PY
  (
    cd "$TEMP"
    /usr/bin/zip -qr "$OLDPWD/$OUT" Payload
  )
  shasum -a 256 "$OUT" > "$OUT.sha256"
  rm -rf "$TEMP/Payload"
  echo "Created disposable test IPA: $OUT"
done
