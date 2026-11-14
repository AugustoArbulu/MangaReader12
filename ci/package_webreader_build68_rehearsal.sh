#!/bin/bash
# Branch-only Build68 unsigned-source -> ad-hoc QA IPA rehearsal (host macOS).
# No release publishing, no appinst, no device connection, no installation.
# The installed app's ad-hoc entitlement is PRESERVED for compatibility,
# but an ad-hoc code seal IS NOT publisher authentication or user consent.
set -euo pipefail
umask 077

if [[ $# -ne 2 ]]; then
  echo "usage: package_webreader_build68_rehearsal.sh APP_PATH OUTPUT_IPA" >&2
  exit 2
fi
APP_PATH="$1"
OUTPUT="$2"
if [[ ! -d "$APP_PATH" || -e "$OUTPUT" || -e "$OUTPUT.sha256" ]]; then
  echo "Missing app or destination already exists" >&2
  exit 2
fi
if [[ "$(basename "$OUTPUT")" != "WebReader-Build68-iOS12-adhoc.ipa" ]]; then
  echo "Refusing ambiguous release artifact naming" >&2
  exit 3
fi
if [[ "$EUID" -eq 0 ]]; then
  echo "Rehearsal must not run as root" >&2
  exit 4
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/Payload"
/usr/bin/ditto "$APP_PATH" "$TMP/Payload/MangaReader12.app"
APP="$TMP/Payload/MangaReader12.app"
python3 - "$APP/Info.plist" "$APP/MangaReader12" <<'PY'
from pathlib import Path
import plistlib
import struct
import sys
plist_path, binary_path = map(Path, sys.argv[1:3])
info = plistlib.loads(plist_path.read_bytes())
assert info.get("CFBundleIdentifier") == "com.example.MangaReader12"
assert info.get("CFBundleDisplayName") == "WebReader"
assert info.get("CFBundleExecutable") == "MangaReader12"
assert info.get("MinimumOSVersion") == "12.0"
# The project remains at build 56 to avoid changing the stable application.
assert info.get("CFBundleVersion") == "56"
with binary_path.open("rb") as stream:
    head = stream.read(8)
assert head[:4] == b"\xcf\xfa\xed\xfe" and len(head) == 8
assert struct.unpack_from("<I", head, 4)[0] == 0x0100000C
info["CFBundleVersion"] = "68"
plist_path.write_bytes(plistlib.dumps(info, sort_keys=True))
PY

ENTITLEMENTS="$(cd "$(dirname "$0")/.." && pwd)/ci/chimera_webreader_qa.entitlements"
codesign --force --sign - --timestamp=none --entitlements "$ENTITLEMENTS" "$APP"
codesign --verify --verbose=2 "$APP"
codesign -d --entitlements :- "$APP" > "$TMP/signed-entitlements.plist" 2>/dev/null
python3 - "$TMP/signed-entitlements.plist" "$APP/Info.plist" <<'PY'
from pathlib import Path
import plistlib
import sys
signed = plistlib.loads(Path(sys.argv[1]).read_bytes())
info = plistlib.loads(Path(sys.argv[2]).read_bytes())
assert info["CFBundleVersion"] == "68"
assert info["MinimumOSVersion"] == "12.0"
assert signed == {
    "application-identifier":
        "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
}
print("PASS: Build68 QA identity/entitlement match installed Build66")
print("LIMIT: this does not authenticate the release publisher")
PY
(
  cd "$TMP"
  /usr/bin/zip -qry "$OLDPWD/$OUTPUT" Payload
)
shasum -a 256 "$OUTPUT" > "$OUTPUT.sha256"
echo "PASS Build68 ad-hoc QA archive produced locally; no install performed."
echo "ARCHIVE_SHA256_FILE=$OUTPUT.sha256"
