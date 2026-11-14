#!/usr/bin/env python3
"""DZ: disposable macOS rehearsal of exact DY one-shot QA packager.

Rehearses the complete SIGN -> ZIP -> DI -> DS -> hardlink -> rehash -> DI/DS
path against the actual full unsigned Build71 .app from Xcode. Test doubles
ONLY the owner-trigger guard inside a short-lived scoped unittest.mock.patch.

This is explicitly NOT a real owner authorization, artifact, release, install,
iPad identity check or an offline backup. No IPA/ZIP is retained or uploaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from unittest.mock import patch

import build71_owner_approved_actions_qa_package as dy

ROOT = Path(__file__).resolve().parent.parent.resolve()
WORKFLOW = (
    "AugustoArbulu/MangaReader12/.github/workflows/"
    "chimera-build70-phase-dz-build71-package-rehearsal.yml"
)
BRANCH_REF = "refs/heads/feat/chimera-updater-phase1-protocol-audit"

EXPECTED_FILES = {
    dy.IPA_NAME,
    dy.IPA_NAME + ".sha256",
    "WebReader-Build71-private-qa-audit.json",
    "WebReader-Build71-second-preflight.json",
    "WebReader-Build71-source-provenance.json",
}


class DZRejected(RuntimeError):
    pass


def _git(*args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, timeout=20, check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DZRejected("rehearsal must be at exact clean reviewed SHA") from exc
    return proc.stdout.strip()


def require_ephemeral_dz_runner(unsigned: Path) -> tuple[Path, str]:
    env = os.environ
    if (
        sys.platform != "darwin"
        or env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != dy.REPOSITORY
        or env.get("GITHUB_REF") != BRANCH_REF
        or env.get("GITHUB_EVENT_NAME") not in ("push", "workflow_dispatch")
        or env.get("GITHUB_WORKFLOW_REF") !=
            WORKFLOW + "@" + BRANCH_REF
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or re.fullmatch(r"[0-9]{1,20}", env.get("GITHUB_RUN_ID", "")) is None
    ):
        raise DZRejected("disposable test must run only in reviewed macOS DZ CI")
    sha = env.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None or _git("rev-parse", "HEAD") != sha:
        raise DZRejected("source HEAD is not exact CI commit")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise DZRejected("source checkout not clean")
    if (ROOT/dy.TRIGGER).exists() or (ROOT/dy.TRIGGER).is_symlink():
        raise DZRejected("real owner trigger must be ABSENT during rehearsal")

    path = env.get("RUNNER_TEMP", "")
    root = Path(path)
    if (
        not path or not root.is_absolute() or root.is_symlink()
        or not root.is_dir()
        or ROOT == root.resolve()
        or ROOT in root.resolve().parents
        or root.resolve() in ROOT.parents
    ):
        raise DZRejected("invalid external runner temporary directory")
    candidate = Path(unsigned)
    if (
        candidate.name != dy.APP_NAME
        or candidate.is_symlink() or not candidate.is_dir()
        or root.resolve() not in candidate.resolve().parents
    ):
        raise DZRejected("unsigned app must be in isolated runner temp")
    return root.resolve(), sha


def run_disposable_package_rehearsal(unsigned_app: Path) -> dict:
    root, source_sha = require_ephemeral_dz_runner(unsigned_app)
    # This is the *only* bypass: the true DY owner trigger is not created.
    # It exists only during the invocation of the real packaging function,
    # and all signed data is deleted by TemporaryDirectory on exit.
    context_parent = "0" * 40
    temporary_path = None
    with tempfile.TemporaryDirectory(prefix="wr71-dz-DISCARD-", dir=root) as folder:
        temporary_path = Path(folder)
        output = temporary_path / "delivery"
        output.mkdir(mode=0o700)
        with patch.object(
            dy, "require_explicit_single_commit_trigger",
            return_value=(source_sha, context_parent, root),
        ):
            receipt = dy.package_one_shot_build71_qa(unsigned_app, output)

        if {p.name for p in output.iterdir()} != EXPECTED_FILES:
            raise DZRejected("rehearsal output file set unexpected")
        ipa = output / dy.IPA_NAME
        sha = hashlib.sha256(ipa.read_bytes()).hexdigest()
        checksum = (output / (dy.IPA_NAME + ".sha256")).read_bytes()
        if checksum != (sha + "  " + dy.IPA_NAME + "\n").encode("ascii"):
            raise DZRejected("packager-produced SHA256 checksum mismatch")

        def read_receipt(name: str) -> dict:
            return json.loads((output / name).read_text("utf-8"))
        provenance = read_receipt("WebReader-Build71-source-provenance.json")
        audits = (
            read_receipt("WebReader-Build71-private-qa-audit.json"),
            read_receipt("WebReader-Build71-second-preflight.json"),
        )
        for audited in audits:
            if (
                audited.get("ipaSHA256") != sha
                or audited.get("candidateBuild") != 71
                or audited.get("expectedInstalledPhysicalBuild") != 70
                or audited.get("adHocCodeSealIntegrityVerifiedOnHost") is not True
                or audited.get("installationAuthorized") is not False
                or audited.get("installationPerformed") is not False
            ):
                raise DZRejected("host-only signed QA evidence inconsistent")
        if (
            receipt.get("status") !=
                "DY_QA_ARTIFACT_BUILT_AFTER_EXPLICIT_TRIGGER_NOT_INSTALLED"
            or receipt.get("ipaSHA256") != sha
            or provenance.get("ipaSHA256") != sha
            or provenance.get("candidateBuild") != 71
            or provenance.get("reviewedSourceParent") != context_parent
            or provenance.get("syntheticDQAndOfflineDataUsedForHostGate") is not True
            or provenance.get("physicalInstalledBuild70IdentityAttested") is not False
            or provenance.get("ownerIdentityCryptographicallyAuthenticatedByTrigger") is not False
            or provenance.get("installationAuthorized") is not False
            or provenance.get("installationPerformed") is not False
            or receipt.get("releasePublished") is not False
            or receipt.get("physicalDeviceUpgradeVerified") is not False
            or receipt.get("installationAuthorized") is not False
        ):
            raise DZRejected("simulated packaging did not retain all denials")
        counts = len(EXPECTED_FILES)
        bytes_count = ipa.stat().st_size
        cdhash = receipt.get("codeDirectoryCDHash")
        if not isinstance(cdhash, str) or re.fullmatch(r"[0-9a-f]{40}", cdhash) is None:
            raise DZRejected("signed CodeDirectory hash unavailable")
        print("PASS DZ: ephemeral full-app DY signing/ZIP/two native audits completed")
    if temporary_path is None or temporary_path.exists():
        raise DZRejected("disposable rehearsal directory not destroyed")
    return {
        "status": "DZ_FULL_APP_OWNER_PACKAGER_REHEARSED_AND_DESTROYED",
        "candidateBuild": 71,
        "previousBuildReference": 70,
        "sourceCommit": source_sha,
        "ephemeralIPABytes": bytes_count,
        "ephemeralIPASHA256": sha,
        "ephemeralStaticCodeDirectoryCDHash": cdhash,
        "ephemeralFilesInspectedThenDeleted": counts,
        "actualOwnerTriggerUsed": False,
        "temporaryMockOwnerContextUsed": True,
        "deliverableRetained": False,
        "artifactUploaded": False,
        "releasePublished": False,
        "realInstalledDeviceIdentityAttested": False,
        "physicalLibraryAndOfflinePreservationProven": False,
        "automaticUpdaterEnabled": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unsigned-app", type=Path, required=True)
    args = parser.parse_args()
    result = run_disposable_package_rehearsal(args.unsigned_app)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
