#!/bin/bash
# DB4: independent, intentionally unprivileged iOS12 HTTPS headers-only app.
# No WebReader app content, IPA installer, downloaded files or GitHub tokens.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(uname -s)" == "Darwin" ]] || {
  echo "macOS Xcode required" >&2
  exit 2
}
OUT="WebReader-DB4-HTTPS-Only-iOS12-adhoc.ipa"
[[ ! -e "$OUT" && ! -e "$OUT.sha256" ]] || {
  echo "Refusing to overwrite QA artifact" >&2
  exit 2
}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
APP="$TMP/Payload/WRDB4HTTPS.app"
mkdir -p "$APP"

xcrun --sdk iphoneos clang \
  -arch arm64 -miphoneos-version-min=12.0 \
  -fobjc-arc -Os -Wall -Wextra -Werror \
  -framework UIKit -framework Foundation -framework CoreGraphics \
  ci/chimera_db4_https_app_probe/main.m \
  -o "$APP/WRDB4HTTPS"

python3 - "$APP/Info.plist" <<'PY'
from pathlib import Path
import plistlib
import sys

path = Path(sys.argv[1])
info = {
    "CFBundleDevelopmentRegion": "pt_BR",
    "CFBundleExecutable": "WRDB4HTTPS",
    "CFBundleIdentifier": "com.example.WebReaderDB4HTTPSProbe",
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleName": "WebReader DB4 HTTPS",
    "CFBundleDisplayName": "WebReader HTTPS Teste",
    "CFBundlePackageType": "APPL",
    "CFBundleShortVersionString": "1.0",
    "CFBundleVersion": "1",
    "MinimumOSVersion": "12.0",
    "LSRequiresIPhoneOS": True,
    "UIDeviceFamily": [1, 2],
    "UIRequiredDeviceCapabilities": ["arm64"],
}
path.write_bytes(plistlib.dumps(info, sort_keys=True))
PY

codesign --force --sign - --timestamp=none \
  --entitlements ci/chimera_db4_https_app_probe/qa.entitlements "$APP"
codesign --verify --verbose=2 "$APP"
codesign -d --entitlements :- "$APP" > "$TMP/signed-entitlements.plist" 2>/dev/null
python3 - "$TMP/signed-entitlements.plist" <<'PY'
import plistlib
from pathlib import Path
import sys
observed = plistlib.loads(Path(sys.argv[1]).read_bytes())
expected = {"application-identifier":
            "WRTEST0001.com.example.WebReaderDB4HTTPSProbe"}
if observed != expected:
    raise SystemExit("BLOCKED: bad sandbox app entitlement")
print("PASS DB4: independent app identifier, no privileged entitlements")
PY

(
  cd "$TMP"
  /usr/bin/zip -qry "$OLDPWD/$OUT" Payload
)
shasum -a 256 "$OUT" > "$OUT.sha256"
echo "Created $OUT: only an HTTPS status-headers probe, no IPA downloader"
