#!/bin/bash
# Produce a separately installed, unsigned iOS12 HTTPS diagnostic build.
# Never replace the production WebReader IPA or Bundle ID in the build tree.
set -euo pipefail

APP_PATH="${1:?usage: package_tls_probe_ipa.sh /path/to/MangaReader12.app [output.ipa]}"
OUTPUT="${2:-WebReader-TLS-Probe-iOS12-unsigned.ipa}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: missing compiled iOS app" >&2
  exit 2
fi
if [[ -e "$OUTPUT" || -e "$OUTPUT.sha256" ]]; then
  echo "ERROR: output exists; refuse overwrite" >&2
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/Payload"
ditto "$APP_PATH" "$TMP/Payload/MangaReader12.app"

python3 - "$TMP/Payload/MangaReader12.app/Info.plist" <<'PY'
import plistlib
import sys
from pathlib import Path

p = Path(sys.argv[1])
with p.open("rb") as f:
    info = plistlib.load(f)
if info.get("CFBundleIdentifier") != "com.example.MangaReader12":
    raise SystemExit("unexpected base bundle ID")
if info.get("CFBundleExecutable") != "MangaReader12":
    raise SystemExit("unexpected executable")
if info.get("CFBundleVersion") != "56":
    raise SystemExit("expected original Build 56; this is a separate test app")
if info.get("MinimumOSVersion") != "12.0":
    raise SystemExit("unexpected minimum iOS")
info["CFBundleIdentifier"] = "com.example.MangaReader12.httpsprobe"
info["CFBundleDisplayName"] = "WebReader TLS Test"
info["CFBundleName"] = "WebReaderTLS"
with p.open("wb") as f:
    plistlib.dump(info, f)
PY

(
  cd "$TMP"
  /usr/bin/zip -qry "$OLDPWD/$OUTPUT" Payload
)
shasum -a 256 "$OUTPUT" > "$OUTPUT.sha256"
echo "Created isolated TLS diagnostic IPA: $OUTPUT"
cat "$OUTPUT.sha256"
