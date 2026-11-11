#!/usr/bin/env python3
"""Build71 DY: owner-trigger-only, one-shot macOS QA artifact packaging.

This code is INERT until a separate explicitly owner-approved single-file
trigger commit; no trigger is created by development work. The user must
approve the particular delivery before changing that file.

The output is a private GitHub Actions QA artifact, not a public Release,
publisher-authenticated update, signed production feed or device installer.
Identities reported by synthetic DR/DS input are not measurements of an iPad.
No library or downloaded images are read, backed up, restored, or modified.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import sys
import tempfile

from build70_dh_unsigned_build71_preview import inspect_dh_unsigned_app
from build70_di_build71_private_qa_preflight import (
    QA_FILENAME, preflight_di_build71_private_qa,
)
from build70_ds_candidate_evidence_gate import (
    inspect_ds_preupgrade_candidate,
)
from build70_dl_full_app_signed_shadow import (
    _synthetic_dq_installed_claim,
    _synthetic_library_with_three_downloads,
    _synthetic_offline_three_downloads,
)
from build66_code_signature_gate import INSTALLED_APPLICATION_IDENTIFIER

REPOSITORY = "AugustoArbulu/MangaReader12"
BRANCH = "feat/chimera-updater-phase1-protocol-audit"
WORKFLOW = ".github/workflows/chimera-build71-owner-approved-one-shot-qa.yml"
TRIGGER = "ci/build71_owner_approved_qa_trigger.txt"
MARKER = "WEBREADER_BUILD71_OWNER_APPROVED_ONE_SHOT_ACTIONS_QA_IPA_NO_INSTALL"
APP_NAME = "MangaReader12.app"
IPA_NAME = QA_FILENAME
QA_BUILD = 71
PREVIOUS_BUILD_REFERENCE = 70
MAX_IPA_BYTES = 512 * 1024 * 1024
ROOT = Path(__file__).resolve().parent.parent.resolve()
EXPECTED_ENTITLEMENTS = {
    "application-identifier": INSTALLED_APPLICATION_IDENTIFIER
}


class DYRejected(RuntimeError):
    pass


def _run(args, *, cwd=None, timeout=120) -> bytes:
    if not args or any(type(arg) is not str or not arg or "\x00" in arg for arg in args):
        raise DYRejected("unsafe native command")
    try:
        return subprocess.run(
            args, cwd=cwd, capture_output=True, check=True, timeout=timeout
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise DYRejected("native QA operation failed; no artifact admitted") from exc


def _git(*args) -> str:
    try:
        return _run(["git", "-C", str(ROOT), *args], timeout=20).decode("utf-8").strip()
    except UnicodeError as exc:
        raise DYRejected("invalid source Git metadata") from exc


def require_explicit_single_commit_trigger() -> tuple[str, str, Path]:
    """Review CI event and triggering source snapshot; not owner cryptography."""
    env = os.environ
    if (sys.platform != "darwin"
            or env.get("GITHUB_ACTIONS") != "true"
            or env.get("GITHUB_REPOSITORY") != REPOSITORY
            or env.get("GITHUB_EVENT_NAME") != "push"
            or env.get("GITHUB_REF") != "refs/heads/" + BRANCH
            or env.get("GITHUB_WORKFLOW_REF") !=
               REPOSITORY + "/" + WORKFLOW + "@refs/heads/" + BRANCH):
        raise DYRejected("Build71 QA workflow context not explicitly allowed")
    sha = env.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise DYRejected("missing immutable reviewed source SHA")
    if _git("rev-parse", "HEAD") != sha:
        raise DYRejected("checkout differs from triggering source commit")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise DYRejected("source checkout has unreviewed files")
    trigger = ROOT / TRIGGER
    if trigger.is_symlink() or not trigger.is_file():
        raise DYRejected("owner-approved trigger file absent")
    data = trigger.read_bytes()
    if len(data) > 256:
        raise DYRejected("oversized authorization marker")
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise DYRejected("noncanonical authorization marker") from exc
    if (len(lines) != 2 or lines[0] != MARKER
            or re.fullmatch(r"[0-9a-f]{40}", lines[1]) is None):
        raise DYRejected("invalid owner-authorization marker format")
    parent = lines[1]
    if _git("rev-parse", "HEAD^") != parent:
        raise DYRejected("trigger commit parent differs from reviewed commit")
    if _git("diff", "--name-only", "HEAD^", "HEAD") != TRIGGER:
        raise DYRejected("trigger commit must change ONLY authorization marker")
    if re.fullmatch(r"[0-9]{1,20}", env.get("GITHUB_RUN_ID", "")) is None:
        raise DYRejected("missing exact GitHub Actions run ID")

    raw_temp = env.get("RUNNER_TEMP", "")
    root = Path(raw_temp)
    if (
        not raw_temp or not root.is_absolute() or root.is_symlink()
        or not root.is_dir() or ROOT == root.resolve()
        or ROOT in root.resolve().parents or root.resolve() in ROOT.parents
    ):
        raise DYRejected("runner temp root unsafe")
    return sha, parent, root.resolve()


def _hash_regular(path: Path) -> tuple[int, int, int, str]:
    if not hasattr(os, "O_NOFOLLOW") or path.is_symlink():
        raise DYRejected("cannot hash linked or unsafe QA IPA")
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            first = os.fstat(stream.fileno())
            if not stat.S_ISREG(first.st_mode) or not 0 < first.st_size <= MAX_IPA_BYTES:
                raise DYRejected("not a bounded regular QA IPA")
            digest = hashlib.sha256()
            length = 0
            while True:
                part = stream.read(1024 * 1024)
                if not part:
                    break
                length += len(part)
                if length > MAX_IPA_BYTES:
                    raise DYRejected("QA IPA exceeded size limit")
                digest.update(part)
            last = os.fstat(stream.fileno())
            identity = lambda obj: (
                obj.st_dev, obj.st_ino, obj.st_size, obj.st_mtime_ns, obj.st_ctime_ns
            )
            if identity(first) != identity(last) or length != first.st_size:
                raise DYRejected("QA IPA changed while being hashed")
            return first.st_dev, first.st_ino, length, digest.hexdigest()
    except OSError as exc:
        raise DYRejected("unable to read QA IPA with no-follow descriptor") from exc


def _receipt_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _check_di(receipt, sha: str, size: int) -> None:
    expected = {
        "status": "DI_SIGNED_QA_SNAPSHOT_HOST_ONLY_NOT_DISTRIBUTABLE",
        "expectedInstalledPhysicalBuild": PREVIOUS_BUILD_REFERENCE,
        "candidateBuild": QA_BUILD,
        "bundleID": "com.example.MangaReader12",
        "iosMinimumDeclared": "12.0",
        "iosMinimumFromExecutable": "12.0",
        "architecture": "arm64",
        "ipaSHA256": sha,
        "ipaBytes": size,
        "adHocCodeSealIntegrityVerifiedOnHost": True,
        "historicalApplicationIdentifierMatches": True,
        "historicalApplicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
        "readyForPrivateQADistribution": False,
        "installationAuthorized": False,
        "installationPerformed": False,
        "publisherCryptographicallyAuthenticated": False,
        "physicalBuild70AppIdentityNewlyAttested": False,
        "actualDeviceInstallabilityProven": False,
    }
    if type(receipt) is not dict:
        raise DYRejected("missing DI receipt")
    for key, value in expected.items():
        if key not in receipt or type(receipt[key]) is not type(value) or receipt[key] != value:
            raise DYRejected("host-only DI receipt unexpected: " + key)
    if re.fullmatch(r"[0-9a-f]{40}", receipt.get("staticCodeDirectoryCDHash", "")) is None:
        raise DYRejected("malformed static CodeDirectory hash")


def _check_ds(receipt, sha: str, size: int, cdhash: str) -> None:
    expected = {
        "status": "DS_HOST_TEXT_AND_SIGNED_CANDIDATE_COHERENT_NOT_INSTALLABLE",
        "candidateIPAStaticSHA256": sha,
        "candidateIPABytes": size,
        "candidateStaticCDHash": cdhash,
        "ipaAdHocSealCheckedOnHost": True,
        "physicalDeviceAndReportOriginAuthenticated": False,
        "physicalInstalledBuild70IdentityCryptographicallyVerified": False,
        "localAppDataContainerRetentionProven": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
    }
    if type(receipt) is not dict:
        raise DYRejected("missing synthetic DS receipt")
    for key, value in expected.items():
        if key not in receipt or type(receipt[key]) is not type(value) or receipt[key] != value:
            raise DYRejected("synthetic DS receipt unexpectedly elevated: " + key)


def _inspect_signed_qa(path: Path, checksum_bytes: bytes):
    size = path.stat().st_size
    sha = _hash_regular(path)[3]
    receipt = preflight_di_build71_private_qa(
        path, checksum_data=checksum_bytes, installed_build=PREVIOUS_BUILD_REFERENCE,
    )
    _check_di(receipt, sha, size)
    linked = inspect_ds_preupgrade_candidate(
        dq_report=_synthetic_dq_installed_claim(),
        sqlite_count_report=_synthetic_library_with_three_downloads(),
        offline_reports=[_synthetic_offline_three_downloads()],
        ipa_path=path, checksum_data=checksum_bytes,
    )
    _check_ds(linked, sha, size, receipt["staticCodeDirectoryCDHash"])
    if _hash_regular(path)[3] != sha:
        raise DYRejected("QA IPA changed after code-signature validation")
    return receipt, linked


def package_one_shot_build71_qa(unsigned_app: Path, output_dir: Path) -> dict:
    sha, parent, temp_root = require_explicit_single_commit_trigger()
    app = Path(unsigned_app)
    out = Path(output_dir)
    if (app.name != APP_NAME or app.is_symlink() or not app.is_dir()
            or out.is_symlink() or not out.is_dir()):
        raise DYRejected("missing isolated unsigned app or output directory")
    app = app.resolve()
    out = out.resolve()
    if (temp_root not in app.parents or temp_root not in out.parents
            or out == app or out in app.parents or app in out.parents):
        raise DYRejected("input/output not isolated in runner temp")
    try:
        unsigned = inspect_dh_unsigned_app(app, source_root=ROOT)
    except (ValueError, OSError) as exc:
        raise DYRejected("full unsigned WebReader Build71 metadata refused") from exc
    if (unsigned.get("status") != "DH_UNSIGNED_APP_METADATA_ONLY_NOT_INSTALLABLE"
            or unsigned.get("observedCompiledBuild") != QA_BUILD
            or unsigned.get("actualExecutableMinimumIOS") != "12.0"
            or unsigned.get("compiledBinaryArchitecture") != "arm64"
            or unsigned.get("installationAuthorized") is not False
            or unsigned.get("ownerDistributionApprovalRecorded") is not False):
        raise DYRejected("not a valid full unsigned iOS12 Build71 app")

    output_files = {
        "checksum": out / (IPA_NAME + ".sha256"),
        "ipa": out / IPA_NAME,
        "audit": out / "WebReader-Build71-private-qa-audit.json",
        "second": out / "WebReader-Build71-second-preflight.json",
        "provenance": out / "WebReader-Build71-source-provenance.json",
    }
    if any(p.exists() or p.is_symlink() for p in output_files.values()):
        raise DYRejected("destination must be empty; no overwrite of QA files")

    ent = ROOT / "ci/chimera_webreader_qa.entitlements"
    if ent.is_symlink() or plistlib.loads(ent.read_bytes()) != EXPECTED_ENTITLEMENTS:
        raise DYRejected("historical QA entitlement fixture changed")
    with tempfile.TemporaryDirectory(prefix=".wr71-dy-owner-qa-", dir=out) as directory:
        temp = Path(directory)
        payload = temp / "Payload"
        payload.mkdir(mode=0o700)
        signed = payload / APP_NAME
        _run(["/usr/bin/ditto", str(app), str(signed)])
        _run(["/usr/bin/codesign", "--force", "--sign", "-", "--timestamp=none",
              "--entitlements", str(ent), str(signed)])
        _run(["/usr/bin/codesign", "--verify", "--verbose=2", str(signed)])
        signed_ent = plistlib.loads(_run(
            ["/usr/bin/codesign", "-d", "--entitlements", ":-", str(signed)]
        ))
        if signed_ent != EXPECTED_ENTITLEMENTS:
            raise DYRejected("signed QA application identifier changed")
        info = plistlib.loads((signed / "Info.plist").read_bytes())
        if (info.get("CFBundleVersion") != "71"
                or info.get("CFBundleIdentifier") != "com.example.MangaReader12"
                or info.get("MinimumOSVersion") != "12.0"):
            raise DYRejected("signed Build71 bundle identity mismatch")
        staged = temp / IPA_NAME
        _run(["/usr/bin/zip", "-qry", str(staged), "Payload"], cwd=temp)
        snapshot_id = _hash_regular(staged)
        digest = snapshot_id[3]
        checksum_bytes = (digest + "  " + IPA_NAME + "\n").encode("ascii")
        first, _ = _inspect_signed_qa(staged, checksum_bytes)
        staged_checksum = temp / (IPA_NAME + ".sha256")
        staged_checksum.write_bytes(checksum_bytes)

        created = []
        try:
            # Stage the two immutable QA asset names without overwrites.
            # GitHub upload occurs ONLY in the separate trigger-gated workflow.
            for origin, dest in (
                (staged_checksum, output_files["checksum"]),
                (staged, output_files["ipa"]),
            ):
                os.link(origin, dest)
                created.append(dest)
            second_id = _hash_regular(output_files["ipa"])
            if (second_id != snapshot_id
                    or output_files["checksum"].read_bytes() != checksum_bytes):
                raise DYRejected("published QA source bytes differ from audited snapshot")
            second, ds = _inspect_signed_qa(output_files["ipa"], checksum_bytes)
            if (second["ipaSHA256"] != first["ipaSHA256"]
                    or second["staticCodeDirectoryCDHash"] !=
                       first["staticCodeDirectoryCDHash"]):
                raise DYRejected("final QA code signature changed after staging")
            provenance = {
                "channel": "OWNER_ONE_SHOT_ACTIONS_PRIVATE_QA_NOT_RELEASE",
                "sourceCommit": sha,
                "reviewedSourceParent": parent,
                "githubActionsRun": int(os.environ["GITHUB_RUN_ID"]),
                "candidateBuild": 71,
                "expectedPreviousPhysicalBuild": 70,
                "bundleID": "com.example.MangaReader12",
                "ipaFilename": IPA_NAME,
                "ipaSHA256": digest,
                "ipaBytes": snapshot_id[2],
                "codeDirectoryCDHash": first["staticCodeDirectoryCDHash"],
                "syntheticDQAndOfflineDataUsedForHostGate": True,
                "physicalInstalledBuild70IdentityAttested": False,
                "physicalLibraryAndOfflinePreservationVerified": False,
                "publisherCryptographicallyAuthenticated": False,
                "automaticUpdaterEnabled": False,
                "ownerTriggerFileWasOnlyChangedFile": True,
                "ownerIdentityCryptographicallyAuthenticatedByTrigger": False,
                "installationAuthorized": False,
                "installationPerformed": False,
                "githubReleasePublished": False,
            }
            for key, obj in (
                ("audit", first), ("second", second), ("provenance", provenance),
            ):
                dest = output_files[key]
                with dest.open("xb") as stream:
                    stream.write(_receipt_bytes(obj))
                created.append(dest)
        except BaseException:
            for file in reversed(created):
                file.unlink(missing_ok=True)
            raise
    return {
        "status": "DY_QA_ARTIFACT_BUILT_AFTER_EXPLICIT_TRIGGER_NOT_INSTALLED",
        "ipaFilename": IPA_NAME,
        "ipaSHA256": digest,
        "ipaBytes": snapshot_id[2],
        "codeDirectoryCDHash": first["staticCodeDirectoryCDHash"],
        "sourceCommit": sha,
        "githubActionsRun": int(os.environ["GITHUB_RUN_ID"]),
        "ownerIdentityCryptographicallyAuthenticatedByTrigger": False,
        "releasePublished": False,
        "physicalDeviceUpgradeVerified": False,
        "automaticUpdaterEnabled": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    import argparse
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("unsigned_app", type=Path)
    cli.add_argument("delivery_dir", type=Path)
    args = cli.parse_args()
    result = package_one_shot_build71_qa(args.unsigned_app, args.delivery_dir)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
