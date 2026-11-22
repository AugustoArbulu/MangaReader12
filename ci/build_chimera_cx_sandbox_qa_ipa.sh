#!/bin/bash
# Phase DA — completely standalone, sandboxed iOS12 check-only client IPA.
# Does not package WebReader, modify the main app or publish any Release.
# The only network destination in source is 127.0.0.1:38973; no helper,
# AppInst, scripts, LSApplicationWorkspace, source runtime or SQLite.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(uname -s)" == "Darwin" ]] || { echo "macOS required" >&2; exit 2; }

OUT="WebReader-CX-Sandbox-DA-iOS12-adhoc.ipa"
[[ ! -e "$OUT" && ! -e "$OUT.sha256" ]] || {
    echo "Refusing to overwrite the preexisting diagnostic artifact" >&2
    exit 2
}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
APP="$TMP/Payload/WRCXSandbox.app"
mkdir -p "$APP"

xcrun --sdk iphoneos clang \
    -arch arm64 -miphoneos-version-min=12.0 \
    -fobjc-arc -Os -Wall -Wextra -Werror \
    -framework UIKit -framework Foundation -framework CoreGraphics \
    ci/chimera_cx_app_probe/main.m \
    ci/chimera_cx_app_probe/cx_client.c \
    -o "$APP/WRCXSandbox"

python3 - "$APP/Info.plist" <<'PY'
import plistlib
from pathlib import Path
import sys
path = Path(sys.argv[1])
info = {
    "CFBundleDevelopmentRegion": "pt_BR",
    "CFBundleExecutable": "WRCXSandbox",
    "CFBundleIdentifier": "com.example.WebReaderCXSandboxProbe",
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleName": "WebReader CX QA",
    "CFBundleDisplayName": "WebReader CX Teste",
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
    --entitlements ci/chimera_cx_app_probe/qa.entitlements "$APP"
codesign --verify --verbose=2 "$APP"
codesign -d --entitlements :- "$APP" > "$TMP/entitlements.plist" 2>/dev/null
python3 - "$TMP/entitlements.plist" <<'PY'
import plistlib
from pathlib import Path
import sys
actual = plistlib.loads(Path(sys.argv[1]).read_bytes())
expected = {
    "application-identifier":
        "WRTEST0001.com.example.WebReaderCXSandboxProbe"
}
if actual != expected:
    raise SystemExit("Denied: sandbox QA has unexpected entitlements")
print("PASS DA: separate sandboxed QA app identity; no helper entitlement")
PY
(
    cd "$TMP"
    /usr/bin/zip -qry "$OLDPWD/$OUT" Payload
)
shasum -a 256 "$OUT" > "$OUT.sha256"
echo "Created $OUT. NO WebReader update, installer or app data involved."
