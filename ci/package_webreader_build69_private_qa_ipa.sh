#!/bin/bash
# Build69 BK: PRIVATE, owner-triggered QA packaging from an ALREADY built
# unsigned iOS12 arm64 WebReader Build69 .app. This is NOT a release pipeline.
# Nothing executes by default, and no GitHub upload or device install exists.
set -euo pipefail
umask 077

CONSENT="I-APPROVE-BUILD69-PRIVATE-QA-PACKAGING"
if [[ "${WR69_PRIVATE_QA_PACKAGE_APPROVAL:-}" != "$CONSENT" ]]; then
  echo "BLOCKED: explicit owner approval to create private QA IPA is required." >&2
  exit 2
fi
if [[ $# -ne 2 ]]; then
  echo "usage: WR69_PRIVATE_QA_PACKAGE_APPROVAL=... $0 BUILT_APP EXTERNAL_OUTPUT_IPA" >&2
  exit 2
fi
if [[ "$EUID" -eq 0 ]]; then
  echo "BLOCKED: QA IPA packaging must not run as root." >&2
  exit 2
fi
# Never allow the automated GitHub runner to produce/distribute a real QA IPA.
if [[ -n "${GITHUB_ACTIONS:-}" || -n "${CI:-}" ]]; then
  echo "BLOCKED: private QA packaging is not permitted in automation." >&2
  exit 2
fi
for tool in /usr/bin/ditto /usr/bin/codesign /usr/bin/zip; do
  if [[ ! -x "$tool" ]]; then
    echo "BLOCKED: native macOS signing tool unavailable." >&2
    exit 2
  fi
done

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
APP_PATH="$1"
OUTPUT="$2"
EXPECTED_NAME="WebReader-Build69-iOS12-adhoc.ipa"
[[ -d "$APP_PATH" && ! -L "$APP_PATH" ]] || {
  echo "BLOCKED: no real source .app directory." >&2; exit 2;
}
[[ "$(basename "$APP_PATH")" == "MangaReader12.app" ]] || {
  echo "BLOCKED: unexpected application bundle name." >&2; exit 2;
}
[[ "$(basename "$OUTPUT")" == "$EXPECTED_NAME" ]] || {
  echo "BLOCKED: wrong private QA asset filename." >&2; exit 2;
}
OUTPUT_DIR="$(cd "$(dirname "$OUTPUT")" && pwd -P)"
case "$OUTPUT_DIR/" in
  "$ROOT/"*) echo "BLOCKED: never create IPA in the source tree." >&2; exit 2 ;;
esac
OUTPUT="$OUTPUT_DIR/$EXPECTED_NAME"
[[ ! -e "$OUTPUT" && ! -L "$OUTPUT" && ! -e "$OUTPUT.sha256" ]] || {
  echo "BLOCKED: the output already exists (no overwrites)." >&2; exit 2;
}

# This is a deliberate human guard, not cryptographic authentication.
# Do not use this marker as publisher trust or authorization to install.
if [[ -n "${GITHUB_REF:-}" ]]; then
  [[ "$GITHUB_REF" == "refs/heads/feat/chimera-updater-phase1-protocol-audit" ]] || {
    echo "BLOCKED: private QA packaging is experimental-branch only." >&2; exit 2;
  }
else
  [[ "$(git -C "$ROOT" branch --show-current)" == "feat/chimera-updater-phase1-protocol-audit" ]] || {
    echo "BLOCKED: checkout must be the experimental branch." >&2; exit 2;
  }
fi

# BX: exact independently reviewed commit and clean checkout are required.
# This is source hygiene only, NOT proof that the .app came from this SHA.
if [[ ! "${WR69_PRIVATE_QA_REVIEWED_COMMIT:-}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "BLOCKED: owner-reviewed full Git commit SHA is required." >&2
  exit 2
fi
python3 "$ROOT/ci/build69_bx_reviewed_source_gate.py" \
  --checkout "$ROOT" --reviewed-commit "$WR69_PRIVATE_QA_REVIEWED_COMMIT" >/dev/null

# The source branch remains at version56; only isolated xcodebuild override69
# is permitted. This exact .app must already be produced by the owner.
python3 "$ROOT/ci/build69_ba_unsigned_candidate_audit.py" "$APP_PATH" >/dev/null
# Stage the archive in the DESTINATION filesystem. An interrupted archive
# cannot appear under the final .ipa name. mktemp ensures a private directory.
TMP="$(mktemp -d "$OUTPUT_DIR/.wr69-private-qa.XXXXXXXX")"
cleanup() {
  rm -rf "$TMP"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "$TMP/Payload"
STAGED_IPA="$TMP/$EXPECTED_NAME"
/usr/bin/ditto "$APP_PATH" "$TMP/Payload/MangaReader12.app"
APP="$TMP/Payload/MangaReader12.app"
ENTITLEMENTS="$ROOT/ci/chimera_webreader_qa.entitlements"

# Sign ONLY the ephemeral copy. Never write to Xcode project/main/device.
/usr/bin/codesign --force --sign - --timestamp=none \
  --entitlements "$ENTITLEMENTS" "$APP"
/usr/bin/codesign --verify --verbose=2 "$APP"
/usr/bin/codesign -d --entitlements :- "$APP" \
  > "$TMP/entitlements.plist" 2>/dev/null
python3 - "$TMP/entitlements.plist" "$APP/Info.plist" <<'PY'
from pathlib import Path
import plistlib
import sys
signed = plistlib.loads(Path(sys.argv[1]).read_bytes())
info = plistlib.loads(Path(sys.argv[2]).read_bytes())
assert signed == {
    "application-identifier": "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
}
assert info["CFBundleIdentifier"] == "com.example.MangaReader12"
assert info["CFBundleDisplayName"] == "WebReader"
assert info["CFBundleExecutable"] == "MangaReader12"
assert info["CFBundleVersion"] == "69"
assert info["MinimumOSVersion"] == "12.0"
PY

(
  cd "$TMP"
  /usr/bin/zip -qry "$STAGED_IPA" Payload
)

# Verify exactly the final IPA bytes with the native ad-hoc code-seal auditor.
# This is NOT an independent SHA channel or a production editor signature.
PYTHONPATH="$ROOT/ci" python3 - "$STAGED_IPA" <<'PY'
from pathlib import Path
import hashlib
import sys
from build66_ipa_preflight import inspect_ipa
from build66_code_signature_gate import (
    audit_code_signature_snapshot, INSTALLED_APPLICATION_IDENTIFIER
)
ipa = Path(sys.argv[1])
from build66_ipa_preflight import MAX_IPA_BYTES
size = ipa.stat().st_size
assert 0 < size <= MAX_IPA_BYTES, "QA IPA exceeds maximum size"
with ipa.open("rb") as stream:
    sha = hashlib.sha256()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        sha.update(chunk)
digest = sha.hexdigest()
report = inspect_ipa(
    ipa, digest, size, 68,
    require_exact_identity=True, return_snapshot=True
)
snapshot = report.pop("ipa_snapshot")
assert report["build"] == 69 and report["minimum_ios"] == "12.0"
seal = audit_code_signature_snapshot(snapshot, digest, size)
assert seal["adHocSignatureIntegrityVerified"]
assert seal["installedApplicationIdentifierMatch"]
assert seal["applicationIdentifier"] == INSTALLED_APPLICATION_IDENTIFIER
assert seal["thinArm64ExecutableVerified"]
print("PASS: Build69 QA archive and ad-hoc CodeDirectory verified (host only).")
print("LIMIT: no publisher authentication, distribution or installation approval.")
PY
(
  cd "$TMP"
  /usr/bin/shasum -a 256 "$EXPECTED_NAME" > "$EXPECTED_NAME.sha256"
)
# Publish in two phases using exclusive hard links on the same filesystem.
# The final IPA name is created LAST, after SHA, ZIP and ad-hoc audits pass.
# os.link fails if any destination already exists (no overwrite), including
# symlinks; interrupted work leaves no partly written final .ipa.
python3 - "$STAGED_IPA" "$OUTPUT" <<'PY'
import os
from pathlib import Path
import sys
staged, final = map(Path, sys.argv[1:3])
checksum_staged = Path(str(staged) + ".sha256")
checksum_final = Path(str(final) + ".sha256")
created = []
try:
    if final.exists() or final.is_symlink() or checksum_final.exists() or checksum_final.is_symlink():
        raise RuntimeError("QA output appeared after initial preflight")
    os.link(checksum_staged, checksum_final)
    created.append(checksum_final)
    os.link(staged, final)
    created.append(final)
except BaseException:
    for path in reversed(created):
        path.unlink(missing_ok=True)
    raise
PY
echo "PASS: private QA asset created only at caller's external local path."
echo "IPA: $OUTPUT"
echo "LOCAL_CHECKSUM: $OUTPUT.sha256 (verify through an independent channel)"
echo "NOT_DONE: no GitHub upload, release, main change, or Chimera installation"
