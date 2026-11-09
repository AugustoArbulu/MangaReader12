#!/bin/bash
# Build69 BY: opt-in, macOS-only private QA candidate from one reviewed Git commit.
# Never executed by CI. Builds in an isolated git archive, then calls the gated
# BK/BL packager on the already built app. NO release, upload or installation.
set -euo pipefail
umask 077

CONSENT="I-APPROVE-BUILD69-PRIVATE-QA-PACKAGING"
if [[ "${WR69_PRIVATE_QA_PACKAGE_APPROVAL:-}" != "$CONSENT" ]]; then
  echo "BLOCKED: explicit owner approval for a PRIVATE QA IPA is required." >&2
  exit 2
fi
if [[ -n "${CI:-}" || -n "${GITHUB_ACTIONS:-}" ]]; then
  echo "BLOCKED: a real private QA IPA must never be created by CI." >&2
  exit 2
fi
if [[ "$EUID" -eq 0 ]]; then
  echo "BLOCKED: private QA candidate must not run as root." >&2
  exit 2
fi
if [[ $# -ne 1 ]]; then
  echo "usage: WR69_PRIVATE_QA_PACKAGE_APPROVAL=... WR69_PRIVATE_QA_REVIEWED_COMMIT=... $0 EXTERNAL_OUTPUT_IPA" >&2
  exit 2
fi
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "BLOCKED: an actual iOS12 QA IPA can only be built on macOS." >&2
  exit 2
fi
for tool in git python3 xcodebuild cmake curl sips xcrun; do
  if ! command -v "$tool" >/dev/null; then
    echo "BLOCKED: missing native source-build tool: $tool" >&2
    exit 2
  fi
done
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
OUTPUT="$1"
EXPECTED_NAME="WebReader-Build69-iOS12-adhoc.ipa"
if [[ "$(basename "$OUTPUT")" != "$EXPECTED_NAME" ]]; then
  echo "BLOCKED: unexpected private QA output name." >&2
  exit 2
fi
OUTPUT_DIR="$(cd "$(dirname "$OUTPUT")" && pwd -P)"
if [[ "$OUTPUT_DIR/" == "$ROOT/"* ]]; then
  echo "BLOCKED: QA output must be outside source checkout." >&2
  exit 2
fi
OUTPUT="$OUTPUT_DIR/$EXPECTED_NAME"
if [[ -e "$OUTPUT" || -L "$OUTPUT" || -e "$OUTPUT.sha256" || -L "$OUTPUT.sha256" ]]; then
  echo "BLOCKED: existing QA IPA or checksum must never be overwritten." >&2
  exit 2
fi
REVIEWED_COMMIT="${WR69_PRIVATE_QA_REVIEWED_COMMIT:-}"
if [[ ! "$REVIEWED_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "BLOCKED: independently reviewed full Git commit is required." >&2
  exit 2
fi
python3 "$ROOT/ci/build69_bx_reviewed_source_gate.py" \
  --checkout "$ROOT" --reviewed-commit "$REVIEWED_COMMIT" >/dev/null

# Git archive, not a copy of mutable local working files, is the build input.
# Icon generation, pinned libwebp download, derived data and Xcode outputs
# stay in disposable directories, leaving the owner's reviewed checkout clean.
TMP="$(mktemp -d "${TMPDIR:-/tmp}/wr69-by-isolated-source.XXXXXXXX")"
cleanup() {
  rm -rf "$TMP"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
SOURCE="$TMP/Source"
mkdir -p "$SOURCE"
git -C "$ROOT" archive --format=tar "$REVIEWED_COMMIT" |
  /usr/bin/tar -xf - -C "$SOURCE"

(
  cd "$SOURCE"
  python3 ci/prepare_webreader_icons.py
  bash ci/prepare_libwebp_ios.sh
  xcodebuild -project MangaReader12.xcodeproj \
    -scheme MangaReader12 -configuration Release \
    -sdk iphoneos -destination 'generic/platform=iOS' \
    -derivedDataPath "$TMP/DerivedData" \
    CURRENT_PROJECT_VERSION=69 \
    CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO clean build
)
APP="$TMP/DerivedData/Build/Products/Release-iphoneos/MangaReader12.app"
python3 "$ROOT/ci/build69_ba_unsigned_candidate_audit.py" "$APP" >/dev/null
python3 "$ROOT/ci/build69_bx_reviewed_source_gate.py" \
  --checkout "$ROOT" --reviewed-commit "$REVIEWED_COMMIT" >/dev/null

# Only the BK packager may sign a disposable app copy and publish the QA IPA.
# It rechecks source/build identity, the exact bytes, CodeDirectory and
# installed application-identifier, then emits IPA and sidecar atomically.
bash "$ROOT/ci/package_webreader_build69_private_qa_ipa.sh" "$APP" "$OUTPUT"
echo "PASS: locally prepared private QA candidate from reviewed Git archive."
echo "LIMIT: this is NOT editorial signing, a distribution permit or physical QA."
echo "NOT_DONE: no GitHub release/upload, appinst/Chimera installation or main merge."
