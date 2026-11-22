#!/bin/bash
# Build two ad-hoc signed, isolated iOS12 IPAs for appinst persistence QA only.
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
  -framework UIKit -framework Foundation -framework CoreGraphics \
  ci/appinst_disposable/main.m \
  -o "$TEMP/WRDisposable"
for VERSION in 1 2; do
  OUT="WebReader-Appinst-Disposable-v$VERSION-iOS12-adhoc.ipa"
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
  # Build60 field QA: unsigned fixture reached MIInstallerErrorDomain Code=3.
  # Sign the WHOLE .app bundle after versioned Info.plist was written.
  # Both versions must have identical app identity entitlement; this is an
  # ad-hoc signature for the user's Chimera + AppSync sandbox, NOT an
  # Apple-trusted profile or a production signing identity.
  APP="$TEMP/Payload/WRDisposable.app"
  codesign --force --sign - --timestamp=none \
    --entitlements ci/chimera_disposable_app.entitlements "$APP"
  codesign --verify --verbose "$APP"
  codesign -d --entitlements :- "$APP" > "$TEMP/signed-$VERSION.plist" 2>/dev/null
  python3 - "$TEMP/signed-$VERSION.plist" "$APP/Info.plist" <<'PY'
import plistlib
import sys
from pathlib import Path
entitlements = plistlib.loads(Path(sys.argv[1]).read_bytes())
info = plistlib.loads(Path(sys.argv[2]).read_bytes())
bundle = "com.example.WebReaderAppinstDisposableTest"
expected = "WRQA000001." + bundle
assert info["CFBundleIdentifier"] == bundle
assert entitlements == {"application-identifier": expected}, entitlements
print("PASS: disposable v" + info["CFBundleVersion"] +
      " has version-matched signed App ID; no extra entitlements")
PY
  (
    cd "$TEMP"
    /usr/bin/zip -qr "$OLDPWD/$OUT" Payload
  )
  shasum -a 256 "$OUT" > "$OUT.sha256"
  rm -rf "$TEMP/Payload"
  echo "Created disposable test IPA: $OUT"
done
