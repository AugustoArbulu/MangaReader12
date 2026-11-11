#!/usr/bin/env python3
"""WebReader Build70/DL — signed FULL-app QA shadow test, macOS CI ONLY.

This is NOT an owner-authorized distribution pipeline. It inspects an
unsigned, full WebReader Build71 Release .app from a trusted *test runner*,
makes a temporary ad-hoc-signed copy, packages it in a temporary IPA, and
audits the exact bytes with DI and DK. All temp files are destroyed on exit.

There is deliberately NO upload, GitHub Release, install, appinst, network
transfer or persistent IPA. This workflow DOES NOT prove current Build70
on-device entitlement, data preservation, installer consumption, publisher
authenticity, consent, or helper isolation. The DJ baseline is SYNTHETIC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

from build66_code_signature_gate import INSTALLED_APPLICATION_IDENTIFIER
from build70_dh_unsigned_build71_preview import inspect_dh_unsigned_app
from build70_di_build71_private_qa_preflight import (
    QA_FILENAME, preflight_di_build71_private_qa,
)
from build70_dk_qa_evidence_bridge import audit_dk_qa_evidence
from build70_dj_continuity_report_compare import (
    COUNT_LABELS, HEADER, NOTE, DB_HEALTH, FOOTER, IOS_VERSION
)

ROOT = Path(__file__).resolve().parent.parent.resolve()
BRANCH = "feat/chimera-updater-phase1-protocol-audit"
WORKFLOW = ".github/workflows/chimera-build70-phase-dl-full-app-shadow.yml"
EXPECTED_REPOSITORY = "AugustoArbulu/MangaReader12"
EXPECTED_ENTITLEMENTS = {
    "application-identifier": INSTALLED_APPLICATION_IDENTIFIER
}
MAX_IPA_SIZE = 512 * 1024 * 1024


class DLShadowRejected(RuntimeError):
    pass


def require_dl_ephemeral_runner() -> Path:
    """CI identity check is a workflow safeguard, NOT cryptographic identity."""
    env = os.environ
    if (sys.platform != "darwin" or env.get("GITHUB_ACTIONS") != "true"
            or env.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY
            or env.get("GITHUB_REF") != "refs/heads/" + BRANCH
            or env.get("GITHUB_EVENT_NAME") not in ("push", "workflow_dispatch")):
        raise DLShadowRejected("DL may only run on the designated macOS branch CI")
    workflow_ref = env.get("GITHUB_WORKFLOW_REF", "")
    if not workflow_ref.endswith(
        "/" + WORKFLOW + "@refs/heads/" + BRANCH
    ):
        raise DLShadowRejected("DL invoked by another workflow")
    source_sha = env.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise DLShadowRejected("no immutable CI commit identity")
    temp_env = env.get("RUNNER_TEMP", "")
    if not temp_env:
        raise DLShadowRejected("missing runner temporary root")
    root = Path(temp_env)
    if not root.is_dir() or root.is_symlink() or not root.is_absolute():
        raise DLShadowRejected("invalid runner temporary storage")
    resolved = root.resolve()
    if ROOT == resolved or ROOT in resolved.parents or resolved in ROOT.parents:
        raise DLShadowRejected("runner temporary root overlaps checkout")
    return resolved


def _command(args: list[str], *, cwd: Path | None = None, timeout=90) -> None:
    if any(type(s) is not str or not s or "\x00" in s for s in args):
        raise DLShadowRejected("invalid native command")
    try:
        subprocess.run(
            args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DLShadowRejected(
            "native ad-hoc shadow command failed; no package retained"
        ) from exc


def _synthetic_baseline() -> bytes:
    # Zero counts are deliberately synthetic and do not pretend a user's
    # actual Build70 library is empty. This only exercises DJ report framing.
    lines = [
        HEADER, "Build observada: 70 • iOS: " + IOS_VERSION, NOTE,
        DB_HEALTH,
    ] + [name + ": 0" for name in COUNT_LABELS] + list(FOOTER)
    return "\n".join(lines).encode("utf-8")


def _audit_shadow_unsigned_candidate(app: Path) -> None:
    if app.name != "MangaReader12.app" or app.is_symlink() or not app.is_dir():
        raise DLShadowRejected("expected unsigned full WebReader .app")
    candidate = inspect_dh_unsigned_app(app, source_root=ROOT)
    if (candidate.get("status") != "DH_UNSIGNED_APP_METADATA_ONLY_NOT_INSTALLABLE"
            or candidate.get("observedCompiledBuild") != 71
            or candidate.get("compiledBinaryArchitecture") != "arm64"
            or candidate.get("actualExecutableMinimumIOS") != "12.0"
            or candidate.get("ownerDistributionApprovalRecorded") is not False
            or candidate.get("installationAuthorized") is not False
            or candidate.get("installableIPAProduced") is not False):
        raise DLShadowRejected("unsigned full-app source/metadata gate failed")
    # The Xcode app is kept under the temporary runner and not inside source.
    temp_root = require_dl_ephemeral_runner()
    app_resolved = app.resolve()
    if temp_root not in app_resolved.parents:
        raise DLShadowRejected("unsigned app is not isolated in runner temporary")


def run_shadow_validation(unsigned_app: Path) -> dict:
    temp_root = require_dl_ephemeral_runner()
    _audit_shadow_unsigned_candidate(Path(unsigned_app))
    entitlement_file = ROOT / "ci/chimera_webreader_qa.entitlements"
    if entitlement_file.is_symlink():
        raise DLShadowRejected("unexpected entitlement symlink")
    try:
        claims = plistlib.loads(entitlement_file.read_bytes())
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        raise DLShadowRejected("historical QA entitlement fixture invalid") from exc
    if claims != EXPECTED_ENTITLEMENTS:
        raise DLShadowRejected("app identity fixture differs from historical baseline")
    with tempfile.TemporaryDirectory(prefix="wr-dl-full-app-shadow-",
                                     dir=temp_root) as temporary:
        temp = Path(temporary)
        payload = temp / "Payload"
        payload.mkdir(mode=0o700)
        shadow_app = payload / "MangaReader12.app"
        _command(["/usr/bin/ditto", str(unsigned_app), str(shadow_app)], timeout=120)
        _command(
            ["/usr/bin/codesign", "--force", "--sign", "-", "--timestamp=none",
             "--entitlements", str(entitlement_file), str(shadow_app)],
            timeout=120,
        )
        _command(
            ["/usr/bin/codesign", "--verify", "--verbose=2", str(shadow_app)],
            timeout=90,
        )
        # Compare what codesign really embedded, not just the *source* plist.
        try:
            result = subprocess.run(
                ["/usr/bin/codesign", "-d", "--entitlements", ":-",
                 str(shadow_app)],
                check=True, capture_output=True, timeout=45,
            )
            signed_entitlements = plistlib.loads(result.stdout)
        except (OSError, ValueError, subprocess.SubprocessError,
                plistlib.InvalidFileException) as exc:
            raise DLShadowRejected("unable to verify signed ad-hoc entitlements") from exc
        if signed_entitlements != EXPECTED_ENTITLEMENTS:
            raise DLShadowRejected("signed entitlements do not match historical claim")
        info = plistlib.loads((shadow_app / "Info.plist").read_bytes())
        if (
            info.get("CFBundleVersion") != "71"
            or info.get("CFBundleIdentifier") != "com.example.MangaReader12"
            or info.get("MinimumOSVersion") != "12.0"
        ):
            raise DLShadowRejected("signed WebReader Build71 identity mismatched")

        ipa = temp / QA_FILENAME
        _command(
            ["/usr/bin/zip", "-qry", str(ipa), "Payload"],
            cwd=temp, timeout=120,
        )
        if ipa.is_symlink() or not ipa.is_file():
            raise DLShadowRejected("ad-hoc shadow IPA missing")
        # One in-memory checksum line for the exact bytes verified by DI/DK.
        # This is NOT an external, owner-trusted checksum.
        size = ipa.stat().st_size
        if not 0 < size <= MAX_IPA_SIZE:
            raise DLShadowRejected("unbounded full-app shadow IPA")
        digest = hashlib.sha256(ipa.read_bytes()).hexdigest()
        checksum = (digest + "  " + QA_FILENAME + "\n").encode("ascii")
        package = preflight_di_build71_private_qa(
            ipa, checksum_data=checksum, installed_build=70
        )
        if (
            package.get("status") != "DI_SIGNED_QA_SNAPSHOT_HOST_ONLY_NOT_DISTRIBUTABLE"
            or package.get("ipaSHA256") != digest
            or package.get("ipaBytes") != size
            or package.get("adHocCodeSealIntegrityVerifiedOnHost") is not True
            or package.get("historicalApplicationIdentifierMatches") is not True
            or package.get("readyForPrivateQADistribution") is not False
            or package.get("installationAuthorized") is not False
        ):
            raise DLShadowRejected("full-app signed snapshot rejected by DI")
        linked = audit_dk_qa_evidence(
            ipa_path=ipa, checksum_data=checksum,
            before_report=_synthetic_baseline()
        )
        if (
            linked.get("status") !=
                "DK_HOST_PACKAGE_CHECKED_BASELINE_TEXT_ONLY_NO_DISTRIBUTION"
            or linked.get("hostIPALocalHash") != digest
            or linked.get("hostStaticCodeDirectoryCDHash") !=
                package.get("staticCodeDirectoryCDHash")
            or linked.get("baselineCountReportFormatAccepted") is not True
            or linked.get("readyToDistributePrivateIPA") is not False
            or linked.get("installationAuthorized") is not False
            or linked.get("installationPerformed") is not False
            or linked.get("offlinePageFilesVerified") is not False
        ):
            raise DLShadowRejected("full-app signed snapshot rejected by DK")

        # Only a technical receipt survives. All actual IPA bytes and
        # temporary code-signing output disappear before this function returns.
        return {
            "status": "DL_FULL_APP_SHADOW_SIGNED_AND_AUDITED_HOST_ONLY",
            "candidateBuild": 71,
            "installedPhysicalBuildReference": 70,
            "bundleID": "com.example.MangaReader12",
            "minimumIOS": "12.0",
            "architecture": "arm64",
            "hostShadowIPABytes": size,
            "hostShadowIPA256": digest,
            "hostStaticCodeDirectoryCDHash":
                package["staticCodeDirectoryCDHash"],
            "appleAdHocSealVerifiedOnTemporaryFullApp": True,
            "realFullWebReaderUICompiled": True,
            "staticSourceHardStopsVerified": True,
            "baselineReportWasSynthetic": True,
            "physicalLibraryCountsCaptured": False,
            "physicalOfflineReadingVerified": False,
            "physicalBuild70AppIdentifierReattested": False,
            "realDeviceIOS12ExecutionVerified": False,
            "realDeviceInstallationCompatibilityProven": False,
            "publisherCryptographicallyAuthenticated": False,
            "helperIdentityAuthenticated": False,
            "editorialProductionKeyConfigured": False,
            "ownerDistributionApprovalRecorded": False,
            "readyToDistributeIPA": False,
            "readyToInstallIPA": False,
            "installationAuthorized": False,
            "installationPerformed": False,
            "persistentIPAProduced": False,
            "artifactUploaded": False,
            "releasePublished": False,
            "mainModified": False,
        }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--unsigned-app", required=True, type=Path)
    args = cli.parse_args()
    try:
        receipt = run_shadow_validation(args.unsigned_app)
    except (DLShadowRejected, ValueError, RuntimeError, OSError) as exc:
        cli.error("BLOCKED: " + str(exc))
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
