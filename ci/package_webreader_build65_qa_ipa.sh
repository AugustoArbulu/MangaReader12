#!/bin/bash
# Build65 personal WebReader IPA for explicit Filza QA only; no in-app install.
# Preserve main and stable Build56; do not sign the repository source tree.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "usage: package_webreader_build64_qa_ipa.sh APP_PATH OUTPUT_IPA" >&2
  exit 2
fi
APP_PATH="$1"
OUTPUT="$2"
if [[ ! -d "$APP_PATH" || -e "$OUTPUT" || -e "$OUTPUT.sha256" ]]; then
  echo "Missing app or output already exists" >&2
  exit 2
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/Payload"
/usr/bin/ditto "$APP_PATH" "$TMP/Payload/MangaReader12.app"
APP="$TMP/Payload/MangaReader12.app"
python3 - "$APP/Info.plist" <<'PY'
from pathlib import Path
import plistlib
import sys
path = Path(sys.argv[1])
info = plistlib.loads(path.read_bytes())
assert info.get("CFBundleIdentifier") == "com.example.MangaReader12"
assert info.get("CFBundleDisplayName") == "WebReader"
assert info.get("CFBundleExecutable") == "MangaReader12"
assert info.get("MinimumOSVersion") == "12.0"
assert info.get("CFBundleVersion") == "56"
assert (path.parent / "MangaReader12").is_file()
info["CFBundleVersion"] = "65"
path.write_bytes(plistlib.dumps(info, sort_keys=True))
PY
# FILZA rejects upgrade if this string differs from the installed app's
# application-identifier entitlement; AppSync alone does not correct that.
ENTITLEMENTS="$(cd "$(dirname "$0")/.." && pwd)/ci/chimera_webreader_qa.entitlements"
codesign --force --sign - --timestamp=none --entitlements "$ENTITLEMENTS" "$APP"
codesign --verify --verbose=2 "$APP"
codesign -d --entitlements :- "$APP" > "$TMP/entitlements.plist" 2>/dev/null
python3 - "$TMP/entitlements.plist" "$APP/Info.plist" <<'PY'
import plistlib
from pathlib import Path
import sys
signed = plistlib.loads(Path(sys.argv[1]).read_bytes())
info = plistlib.loads(Path(sys.argv[2]).read_bytes())
expected = "AR5SFJC432." + info["CFBundleIdentifier"] + ".AR5SFJC432"
assert info["CFBundleVersion"] == "65"
assert signed == {"application-identifier": expected}, signed
print("PASS: candidate application-identifier equals installed Build56 Filza string")
PY
(
  cd "$TMP"
  /usr/bin/zip -qry "$OLDPWD/$OUTPUT" Payload
)
shasum -a 256 "$OUTPUT" > "$OUTPUT.sha256"
echo "Build65 QA manual QA IPA signed; installer inactive."
echo "SHA256 manifest: $OUTPUT.sha256"
