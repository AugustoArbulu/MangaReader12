#!/bin/bash
# One standalone iOS12 Chimera experiment IPA, no terminal or helper download.
# The only embedded executable is the existing read-only PING/PONG program.
# Never change stable WebReader's bundle ID or invoke appinst.
set -euo pipefail
if [[ $# -lt 2 ]]; then
  echo "usage: package_chimera_oneapp_ipa.sh APP_PATH PING_HELPER [OUTPUT]" >&2
  exit 2
fi
APP_PATH="$1"
HELPER_PATH="$2"
OUTPUT="WebReader-Chimera-Test-iOS12-unsigned.ipa"
if [[ $# -ge 3 ]]; then OUTPUT="$3"; fi
[[ -d "$APP_PATH" && -f "$HELPER_PATH" ]] || {
  echo "Missing compiled app or read-only ping helper" >&2
  exit 2
}
if [[ -e "$OUTPUT" || -e "$OUTPUT.sha256" ]]; then
  echo "Refusing to overwrite diagnostic IPA" >&2
  exit 2
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/Payload"
/usr/bin/ditto "$APP_PATH" "$TMP/Payload/MangaReader12.app"
APP="$TMP/Payload/MangaReader12.app"
cp "$HELPER_PATH" "$APP/WebReaderEmbeddedPing"
chmod 0755 "$APP/WebReaderEmbeddedPing"
/usr/bin/codesign --verify "$APP/WebReaderEmbeddedPing"

python3 - "$APP/Info.plist" <<'PY'
from pathlib import Path
import plistlib
import sys
path = Path(sys.argv[1])
info = plistlib.loads(path.read_bytes())
assert info.get("CFBundleIdentifier") == "com.example.MangaReader12"
assert info.get("CFBundleExecutable") == "MangaReader12"
assert info.get("CFBundleVersion") == "56"
assert info.get("MinimumOSVersion") == "12.0"
info["CFBundleIdentifier"] = "com.example.MangaReader12.chimeraoneapp"
info["CFBundleDisplayName"] = "WebReader Chimera Test"
info["CFBundleName"] = "WRChimeraTest"
info.pop("UIBackgroundModes", None)
path.write_bytes(plistlib.dumps(info, sort_keys=True))
PY

(
  cd "$TMP"
  /usr/bin/zip -qry "$OLDPWD/$OUTPUT" Payload
)
shasum -a 256 "$OUTPUT" > "$OUTPUT.sha256"
echo "Created ONE separate read-only Chimera diagnostic IPA: $OUTPUT"
