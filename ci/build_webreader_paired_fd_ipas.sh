#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(uname -s)" == "Darwin" ]] || exit 2
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
root="$PWD"
for role in Target Observer; do
  exe="WRFD$role"
  bundle="com.example.WebReaderPairedFD$role"
  out="WebReader-FD-$role-iOS12.ipa"
  [[ ! -e "$out" && ! -e "$out.sha256" ]] || exit 2
  stage="$tmp/$role"
  app="$stage/Payload/$exe.app"
  mkdir -p "$app"
  flags=()
  if [[ "$role" == Target ]]; then flags=(-DWR_FD_TARGET); fi
  xcrun --sdk iphoneos clang -arch arm64 -miphoneos-version-min=12.0 \
    -fobjc-arc -Os -Wall -Wextra -Werror -framework UIKit -framework Foundation \
    ${flags[@]+"${flags[@]}"} ci/paired_fd_app/main.m -o "$app/$exe"
  python3 - "$app" "$exe" "$bundle" "$role" <<'PY'
import plistlib,sys
from pathlib import Path
app,exe,bundle,role = sys.argv[1:]
title = "WebReader FD " + ("Alvo" if role == "Target" else "Observador")
Path(app, "Info.plist").write_bytes(plistlib.dumps({
    "CFBundleExecutable": exe, "CFBundleIdentifier": bundle,
    "CFBundleName": title, "CFBundleDisplayName": title,
    "CFBundlePackageType": "APPL", "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleVersion": "1", "CFBundleShortVersionString": "1.0",
    "MinimumOSVersion": "12.0", "LSRequiresIPhoneOS": True,
    "UIDeviceFamily": [1, 2], "UIRequiredDeviceCapabilities": ["arm64"],
}))
Path(app).parent.parent.joinpath("entitlements.plist").write_bytes(
    plistlib.dumps({"application-identifier": "WRTEST0001." + bundle}))
PY
  codesign --force --sign - --timestamp=none --entitlements "$stage/entitlements.plist" "$app"
  codesign --verify --verbose=2 "$app"
  codesign -d --entitlements :- "$app" > "$stage/signed.plist" 2>/dev/null
  cmp "$stage/entitlements.plist" "$stage/signed.plist" ||
    python3 -c 'import plistlib,sys; assert plistlib.load(open(sys.argv[1],"rb")) == plistlib.load(open(sys.argv[2],"rb"))' \
      "$stage/entitlements.plist" "$stage/signed.plist"
  xcrun otool -l "$app/$exe" > "$stage/load.txt"
  grep -Eq 'minos 12\.0|version 12\.0' "$stage/load.txt"
  if grep -q LC_DYLD_CHAINED_FIXUPS "$stage/load.txt"; then exit 1; fi
  (cd "$stage" && /usr/bin/zip -qry "$root/$out" Payload)
  shasum -a 256 "$out" > "$out.sha256"
done
