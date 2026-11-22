#!/usr/bin/env python3
"""Build69 BN: REAL compiled app -> ephemeral ad-hoc codesign REVIEW ONLY.

This is a macOS CI/owner rehearsal on the unsigned Build69 .app, NOT a QA IPA.
It signs a disposable ditto copy, audits entitlements, then destroys the copy.
NO ZIP, upload, GitHub release, publisher key, installation or source mutation.
Neither an ad-hoc code seal nor a passing receipt authorizes distribution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

from build69_ba_unsigned_candidate_audit import (
    UnsignedCandidateRejected, inspect_unsigned_candidate
)
from build66_code_signature_gate import INSTALLED_APPLICATION_IDENTIFIER

ROOT = Path(__file__).resolve().parent.parent.resolve()
ENTITLEMENTS = ROOT / "ci/chimera_webreader_qa.entitlements"
APP_NAME = "MangaReader12.app"


class SignedPreviewRejected(ValueError):
    pass


def _sha256_regular(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise SignedPreviewRejected("missing or linked app source file")
    size = path.stat().st_size
    if not 0 < size <= 256 * 1024 * 1024:
        raise SignedPreviewRejected("app source file size is not bounded")
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(part)
    return sha.hexdigest()


def _run_mac(args):
    result = subprocess.run(
        args, timeout=90, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise SignedPreviewRejected("native ad-hoc signing rehearsal rejected")
    return result


def audit_real_signed_app_preview(unsigned_app: Path) -> dict:
    if sys.platform != "darwin":
        raise SignedPreviewRejected("macOS only; no Linux IPA signing")
    app = Path(unsigned_app)
    if app.name != APP_NAME or app.is_symlink() or not app.is_dir():
        raise SignedPreviewRejected("unexpected unsigned app bundle location")
    try:
        unsigned_receipt = inspect_unsigned_candidate(app)
    except (OSError, ValueError, UnsignedCandidateRejected) as exc:
        raise SignedPreviewRejected("isolated source app failed version69 preflight") from exc
    before = {
        name: _sha256_regular(app / name)
        for name in ("Info.plist", "MangaReader12", "Assets.car")
    }
    with tempfile.TemporaryDirectory(prefix="wr69-bn-signed-app-only-") as td:
        disposable_app = Path(td) / APP_NAME
        _run_mac(["/usr/bin/ditto", str(app), str(disposable_app)])
        if disposable_app.is_symlink() or not disposable_app.is_dir():
            raise SignedPreviewRejected("unsafe disposable app copy")
        for name, original_digest in before.items():
            if _sha256_regular(disposable_app / name) != original_digest:
                raise SignedPreviewRejected("ditto copy differed from source app")
        _run_mac([
            "/usr/bin/codesign", "--force", "--sign", "-",
            "--timestamp=none", "--entitlements", str(ENTITLEMENTS),
            str(disposable_app)
        ])
        _run_mac(["/usr/bin/codesign", "--verify", "--verbose=2",
                  str(disposable_app)])
        printed = _run_mac([
            "/usr/bin/codesign", "-d", "--entitlements", ":-",
            str(disposable_app)
        ])
        try:
            entitlements = plistlib.loads(printed.stdout)
        except (plistlib.InvalidFileException, ValueError, TypeError) as exc:
            raise SignedPreviewRejected("unreadable ad-hoc entitlements") from exc
        if entitlements != {"application-identifier": INSTALLED_APPLICATION_IDENTIFIER}:
            raise SignedPreviewRejected("incompatible installed application identifier")
        detail = _run_mac([
            "/usr/bin/codesign", "-dv", "--verbose=4",
            str(disposable_app)
        ]).stderr.decode("utf-8", errors="replace")
        if "Signature=adhoc" not in detail:
            raise SignedPreviewRejected("not an ad-hoc code seal")
        match = re.search(r"\bCDHash=([0-9a-fA-F]{40})\b", detail)
        if not match:
            raise SignedPreviewRejected("native CodeDirectory digest unavailable")
        if list(Path(td).rglob("*.ipa")):
            raise SignedPreviewRejected("a forbidden IPA was created")
        static_cdhash = match.group(1).lower()

    # Verify that signing only touched the disposable copy, never the source.
    if any(_sha256_regular(app / name) != digest for name, digest in before.items()):
        raise SignedPreviewRejected("source app changed during signing rehearsal")
    return {
        "status": "REAL_APP_ADHOC_SIGNED_PREVIEW_ONLY_NOT_AN_IPA",
        "observedBuild": unsigned_receipt["observedAppBuild"],
        "sourceProjectBuild": unsigned_receipt["sourceProjectBuild"],
        "minimumIOS": unsigned_receipt["binaryMinimumIOS"],
        "architecture": unsigned_receipt["binaryArchitecture"],
        "bundleIdentifier": unsigned_receipt["bundleIdentifier"],
        "installedApplicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
        "temporaryCodeDirectoryCDHash": static_cdhash,
        "adHocCodeSealVerifiedInMacOSTemporaryCopy": True,
        "originalUnsignedAppUnchanged": True,
        "temporarySignedAppDeleted": True,
        "installableIPAProduced": False,
        "githubArtifactUploaded": False,
        "githubReleasePublished": False,
        "editorialPublisherAuthenticated": False,
        "qaDistributionAuthorized": False,
        "deviceCompatibilityProven": False,
        "physicalOfflineQAPassed": False,
        "chimeraInstallationEnabled": False,
        "installationAuthorized": False,
        "installationPerformed": False,
        "mainModified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unsigned-app", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_real_signed_app_preview(args.unsigned_app),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
