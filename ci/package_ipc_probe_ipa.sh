#!/bin/bash
# Package a completely separate iOS12 WebReader IPC diagnostic application.
# No helper executable is bundled with the IPA; no install/release action.
set -euo pipefail

APP_PATH="${1:?usage: package_ipc_probe_ipa.sh /path/to/MangaReader12.app [output.ipa]}"
OUTPUT="${2:-WebReader-IPC-Probe-iOS12-unsigned.ipa}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: missing compiled app bundle" >&2
  exit 2
fi
if [[ -e "$OUTPUT" || -e "$OUTPUT.sha256" ]]; then
  echo "ERROR: refusing to overwrite existing output" >&2
  exit 2
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/Payload"
/usr/bin/ditto "$APP_PATH" "$TMP/Payload/MangaReader12.app"

python3 - "$TMP/Payload/MangaReader12.app/Info.plist" <<'PY'
import plistlib
from pathlib import Path
import sys

path = Path(sys.argv[1])
with path.open("rb") as f:
    info = plistlib.load(f)
assert info.get("CFBundleIdentifier") == "com.example.MangaReader12"
assert info.get("CFBundleExecutable") == "MangaReader12"
assert info.get("CFBundleVersion") == "56"
assert info.get("MinimumOSVersion") == "12.0"
# Only dedicated Chimera read-only IPC QA uses build 57/58, so iOS
# replaces the independent test app. Build56/main stays untouched.
import os
probe_build = os.environ.get("WEBREADER_IPC_PROBE_BUILD", "56")
assert probe_build in ("56", "57", "58")
info["CFBundleVersion"] = probe_build
info["CFBundleIdentifier"] = "com.example.MangaReader12.ipcprobe"
info["CFBundleDisplayName"] = "WebReader IPC Test"
info["CFBundleName"] = "WebReaderIPC"
# The diagnostic app does not request background fetch capability.
info.pop("UIBackgroundModes", None)
with path.open("wb") as f:
    plistlib.dump(info, f)
PY

(
  cd "$TMP"
  /usr/bin/zip -qry "$OLDPWD/$OUTPUT" Payload
)
shasum -a 256 "$OUTPUT" > "$OUTPUT.sha256"
echo "Created isolated IPC diagnostic IPA: $OUTPUT"
cat "$OUTPUT.sha256"
