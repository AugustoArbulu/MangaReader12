#!/bin/bash
# Builds ONE standalone, ad-hoc-signed diagnostic iOS12 IPA; no installation.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Darwin ]]; then
  echo "Needs GitHub Actions macOS with iPhoneOS SDK" >&2
  exit 2
fi
OUTPUT="WebReader-Appinst-Direto-iOS12-adhoc.ipa"
[[ ! -e "$OUTPUT" && ! -e "$OUTPUT.sha256" ]] || {
  echo "Refusing to overwrite existing diagnostic IPA" >&2
  exit 2
}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
APP="$TMP/Payload/WRAppinstDirect.app"
mkdir -p "$APP"
SDK="$(xcrun --sdk iphoneos --show-sdk-path)"
xcrun --sdk iphoneos clang \
  -arch arm64 -miphoneos-version-min=12.0 \
  -fobjc-arc -Os -Wall -Wextra -Werror \
  -isysroot "$SDK" \
  -framework UIKit -framework Foundation -framework CoreGraphics \
  ci/appinst_direct_probe/main.m \
  -o "$APP/WRAppinstDirect"
# Bundled child is a separate ARM64 executable, not an installer.
xcrun --sdk iphoneos clang \
  -arch arm64 -miphoneos-version-min=12.0 \
  -Os -Wall -Wextra -Werror -isysroot "$SDK" \
  ci/appinst_direct_probe/spawn_child.c \
  -o "$APP/WRSpawnChild"
python3 - "$APP/Info.plist" <<'PY'
from pathlib import Path
import plistlib
import sys
path = Path(sys.argv[1])
info = {
    "CFBundleDevelopmentRegion": "pt_BR",
    "CFBundleExecutable": "WRAppinstDirect",
    "CFBundleIdentifier": "com.example.WebReaderAppinstDirectProbe",
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleName": "WR Appinst Direct",
    "CFBundleDisplayName": "WebReader appinst Test",
    "CFBundlePackageType": "APPL",
    "CFBundleShortVersionString": "1.0",
    "CFBundleVersion": "3",
    "MinimumOSVersion": "12.0",
    "LSRequiresIPhoneOS": True,
    "UIDeviceFamily": [1, 2],
    "UIRequiredDeviceCapabilities": ["arm64"],
}
path.write_bytes(plistlib.dumps(info, sort_keys=True))
PY
# Only ad-hoc sign this independent diagnostic; NEVER sign or touch WebReader.
# Sign the nested test child first, then seal the complete app bundle.
/usr/bin/codesign --force --sign - --timestamp=none "$APP/WRSpawnChild"
/usr/bin/codesign --force --sign - --timestamp=none \
  --entitlements ci/appinst_direct_probe/qa.entitlements "$APP"
/usr/bin/codesign --verify --verbose=2 "$APP"
/usr/bin/codesign --verify --verbose=2 "$APP/WRSpawnChild"
(
  cd "$TMP"
  /usr/bin/zip -qry "$OLDPWD/$OUTPUT" Payload
)
shasum -a 256 "$OUTPUT" > "$OUTPUT.sha256"
echo "Created $OUTPUT -- independent ad-hoc diagnostic, no installer invoked by CI"
