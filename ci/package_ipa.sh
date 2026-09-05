#!/bin/bash
set -euo pipefail

APP_PATH="${1:?usage: package_ipa.sh /path/to/App.app [output.ipa]}"
OUTPUT="${2:-MangaReader12-unsigned.ipa}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: app bundle not found: $APP_PATH" >&2
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/Payload"
ditto "$APP_PATH" "$TMP/Payload/$(basename "$APP_PATH")"
(
  cd "$TMP"
  /usr/bin/zip -qry "$OLDPWD/$OUTPUT" Payload
)
shasum -a 256 "$OUTPUT" > "$OUTPUT.sha256"
echo "Created $OUTPUT"
cat "$OUTPUT.sha256"
