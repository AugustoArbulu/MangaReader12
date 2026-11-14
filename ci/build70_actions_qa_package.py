#!/usr/bin/env python3
"""Build70 CB: one-shot GitHub Actions manual-QA artifact packager.

Owner specifically authorized a single Build70 QA IPA. This *separate* Actions
entry point does not change the default-deny local BK/BY packaging policy.
The trigger must be the sole change in the latest commit on the experiment
branch. No GitHub release, credentials, privileged installer or device installation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile

from build70_unsigned_candidate_audit import inspect_unsigned_candidate
from build70_private_qa_ipa_preflight import preflight_private_qa_ipa
from build66_ipa_preflight import MAX_IPA_BYTES

BRANCH = "feat/chimera-updater-phase1-protocol-audit"
TRIGGER = "ci/build70_owner_approved_qa_trigger.txt"
MARKER = "WEBREADER_BUILD70_OWNER_APPROVED_ONE_SHOT_ACTIONS_QA_IPA_NO_INSTALL"
IPA_NAME = "WebReader-Build70-iOS12-adhoc.ipa"
APP_NAME = "MangaReader12.app"
EXPECTED_ENTITLEMENTS = {
    "application-identifier": "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
}
ROOT = Path(__file__).resolve().parent.parent.resolve()
EXPECTED_WORKFLOW = (
    ".github/workflows/chimera-build70-owner-approved-one-shot-qa.yml"
)


class OneShotQARejected(RuntimeError):
    pass


def _command(args, *, cwd=None, timeout=120):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, check=True,
                              timeout=timeout, text=True).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise OneShotQARejected("native macOS QA command failed") from exc


def _git(*args):
    return _command(["git", "-C", str(ROOT), *args], timeout=15)


def require_owner_approved_actions_context():
    """Checks immutable source event and the one-shot trigger; no app writes."""
    env = os.environ
    if (sys.platform != "darwin" or env.get("GITHUB_ACTIONS") != "true"
            or env.get("GITHUB_EVENT_NAME") != "push"
            or env.get("GITHUB_REF") != "refs/heads/" + BRANCH):
        raise OneShotQARejected("not the approved macOS experiment-branch push")
    workflow_ref = env.get("GITHUB_WORKFLOW_REF", "")
    if not workflow_ref.endswith(
        "/" + EXPECTED_WORKFLOW + "@refs/heads/" + BRANCH
    ):
        raise OneShotQARejected("wrong GitHub Actions workflow")
    sha = env.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise OneShotQARejected("missing immutable Actions SHA")
    if _git("rev-parse", "HEAD") != sha:
        raise OneShotQARejected("checkout differs from triggering commit")
    trigger = ROOT / TRIGGER
    if trigger.is_symlink() or not trigger.is_file():
        raise OneShotQARejected("one-shot owner trigger missing")
    data = trigger.read_text(encoding="utf-8")
    lines = data.splitlines()
    if len(lines) != 2 or lines[0] != MARKER or not re.fullmatch(
        r"[0-9a-f]{40}", lines[1]
    ):
        raise OneShotQARejected("owner authorization marker invalid")
    expected_parent = lines[1]
    if _git("rev-parse", "HEAD^") != expected_parent:
        raise OneShotQARejected("trigger does not directly follow reviewed source")
    if _git("diff", "--name-only", "HEAD^", "HEAD") != TRIGGER:
        raise OneShotQARejected("trigger commit changed non-trigger files")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise OneShotQARejected("checkout modified before QA build")
    return sha


def _hash_regular(path: Path):
    if not hasattr(os, "O_NOFOLLOW") or path.is_symlink():
        raise OneShotQARejected("cannot inspect linked IPA")
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_IPA_BYTES:
            raise OneShotQARejected("QA IPA is not a bounded regular file")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_IPA_BYTES:
                raise OneShotQARejected("QA IPA exceeded size bound")
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        attr = lambda x: (x.st_dev, x.st_ino, x.st_size,
                          x.st_ctime_ns, x.st_mtime_ns)
        if attr(before) != attr(after) or total != before.st_size:
            raise OneShotQARejected("QA IPA changed during hash")
        return (before.st_dev, before.st_ino, total, digest.hexdigest())


def _safe_report(data):
    # Only engineering receipt fields, never titles, library, credentials.
    return json.dumps(data, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def package_one_shot_qa(unsigned_app: Path, output_dir: Path):
    # Call this after the workflow has checked the trigger and built the app.
    source_sha = require_owner_approved_actions_context()
    app = Path(unsigned_app).resolve()
    out = Path(output_dir).resolve()
    if not out.is_dir() or out == ROOT or ROOT in out.parents:
        raise OneShotQARejected("delivery directory must be outside checkout")
    if app.name != APP_NAME or app.is_symlink() or not app.is_dir():
        raise OneShotQARejected("expected unsigned WebReader .app")
    if ROOT in app.parents or app == ROOT:
        raise OneShotQARejected("source app must be isolated from repository")
    from build70_unsigned_candidate_audit import UnsignedCandidateRejected
    try:
        audit = inspect_unsigned_candidate(app)
    except (ValueError, OSError, UnsignedCandidateRejected) as exc:
        raise OneShotQARejected("unsigned app did not pass Build70/iOS12 audit") from exc
    if audit.get("observedAppBuild") != 70 or audit.get("binaryMinimumIOS") != "12.0":
        raise OneShotQARejected("unsigned app not Build70 iOS12")
    ipa = out / IPA_NAME
    checksum = out / (IPA_NAME + ".sha256")
    receipt_path = out / "WebReader-Build70-private-qa-audit.json"
    provenance_path = out / "WebReader-Build70-source-provenance.json"
    finals = (checksum, ipa, receipt_path, provenance_path)
    if any(p.exists() or p.is_symlink() for p in finals):
        raise OneShotQARejected("private QA destination already exists")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise OneShotQARejected("missing Actions run ID")
    with tempfile.TemporaryDirectory(prefix=".wr70-owner-qa-", dir=out) as tmpdir:
        temp = Path(tmpdir)
        payload = temp / "Payload"
        payload.mkdir()
        signed_app = payload / APP_NAME
        _command(["/usr/bin/ditto", str(app), str(signed_app)])
        entitlements = ROOT / "ci/chimera_webreader_qa.entitlements"
        _command([
            "/usr/bin/codesign", "--force", "--sign", "-",
            "--timestamp=none", "--entitlements", str(entitlements),
            str(signed_app)
        ])
        _command(["/usr/bin/codesign", "--verify", "--verbose=2",
                  str(signed_app)])
        signed_entitlements = temp / "entitlements.plist"
        # codesign outputs plist to stdout with this flag on supported macOS.
        try:
            value = subprocess.run(
                ["/usr/bin/codesign", "-d", "--entitlements", ":-",
                 str(signed_app)],
                check=True, capture_output=True, timeout=30
            ).stdout
            actual = plistlib.loads(value)
        except (OSError, ValueError, subprocess.SubprocessError,
                plistlib.InvalidFileException) as exc:
            raise OneShotQARejected("cannot parse QA signed entitlements") from exc
        if actual != EXPECTED_ENTITLEMENTS:
            raise OneShotQARejected("installed application identifier differs")
        info = plistlib.loads((signed_app / "Info.plist").read_bytes())
        if (info.get("CFBundleVersion") != "70"
                or info.get("MinimumOSVersion") != "12.0"
                or info.get("CFBundleIdentifier") != "com.example.MangaReader12"):
            raise OneShotQARejected("signed QA app identity or iOS minimum mismatch")
        staged = temp / IPA_NAME
        _command(["/usr/bin/zip", "-qry", str(staged), "Payload"],
                 cwd=temp, timeout=120)
        original_identity = _hash_regular(staged)
        expected_sha = original_identity[3]
        checksum_bytes = (expected_sha + "  " + IPA_NAME + "\n").encode("ascii")
        staged_checksum = temp / (IPA_NAME + ".sha256")
        staged_checksum.write_bytes(checksum_bytes)
        # Full ZIP, embedded iOS ARM64, ad-hoc codesign, entitlement & CDHash.
        first = preflight_private_qa_ipa(
            staged, checksum_data=checksum_bytes, baseline=69
        )
        if first.get("adHocSignatureIntegrityVerified") is not True:
            raise OneShotQARejected("native QA codesign seal not verified")
        if first.get("installedApplicationIdentifierMatch") is not True:
            raise OneShotQARejected("installed application identifier not verified")
        if first.get("readyForDistribution") is not False:
            raise OneShotQARejected("QA receipt must not claim release authority")
        created = []
        try:
            # Commit checksum first; publish IPA name last.
            os.link(staged_checksum, checksum)
            created.append(checksum)
            os.link(staged, ipa)
            created.append(ipa)
            final_identity = _hash_regular(ipa)
            if (final_identity != original_identity
                    or checksum.read_bytes() != checksum_bytes):
                raise OneShotQARejected("published QA IPA differed from staged bytes")
            final_audit = preflight_private_qa_ipa(
                ipa, checksum_data=checksum.read_bytes(), baseline=69
            )
            if (final_audit.get("ipaSHA256") != expected_sha
                    or final_audit.get("codeDirectoryCDHash") !=
                    first.get("codeDirectoryCDHash")):
                raise OneShotQARejected("published IPA changed after native audit")
            provenance = {
                "sourceCommit": source_sha,
                "parentReviewedCommit": _git("rev-parse", "HEAD^"),
                "githubActionsRun": int(run_id),
                "branch": BRANCH,
                "qaArtifact": IPA_NAME,
                "sha256": expected_sha,
                "ipaBytes": final_identity[2],
                "build": 70,
                "installedBuildReference": 69,
                "distributionChannel": "ACTIONS_QA_ARTIFACT_NOT_PUBLIC_RELEASE",
                "releasePublisherAuthenticated": False,
                "automaticInstallationEnabled": False,
                "deviceInstallTested": False,
                "installationAuthorized": False,
                "installationPerformed": False,
            }
            for target, obj in ((receipt_path, final_audit),
                                (provenance_path, provenance)):
                if target.exists() or target.is_symlink():
                    raise OneShotQARejected("QA receipt destination appeared")
                # Exclusive creation, no overwrites.
                with target.open("xb") as stream:
                    stream.write(_safe_report(obj))
                created.append(target)
        except BaseException:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            raise
    return {
        "status": "OWNER_APPROVED_GITHUB_ACTIONS_QA_ARTIFACT_ONLY",
        "file": IPA_NAME,
        "sha256": expected_sha,
        "sourceCommit": source_sha,
        "ipaBytes": final_identity[2],
        "publishedAsGitHubRelease": False,
        "productionPublisherAuthenticated": False,
        "automaticChimeraInstallationEnabled": False,
        "physicalIOS12QAPassed": False,
    }


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("unsigned_app", type=Path)
    p.add_argument("delivery_dir", type=Path)
    args = p.parse_args()
    print(json.dumps(package_one_shot_qa(args.unsigned_app, args.delivery_dir),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
