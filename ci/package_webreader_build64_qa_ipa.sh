#!/bin/bash
# Build64 personal WebReader IPA for explicit Filza QA only.
# This package is never published as a GitHub Release or installed by CI.
# The repository's stable Build56 metadata is not modified.
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
info["CFBundleVersion"] = "64"
path.write_bytes(plistlib.dumps(info, sort_keys=True))
PY

(
  cd "$TMP"
  /usr/bin/zip -qry "$OLDPWD/$OUTPUT" Payload
)
shasum -a 256 "$OUTPUT" > "$OUTPUT.sha256"
echo "Build64 QA-only IPA created; unchanged bundle identity, no installer"
echo "SHA256 manifest: $OUTPUT.sha256"
