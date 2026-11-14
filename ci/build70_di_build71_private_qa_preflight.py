#!/usr/bin/env python3
"""WebReader Build70/DI — READ-ONLY private Build71 QA IPA receipt.

Explicit baseline 70 -> candidate 71. NEVER constructs/signs an IPA, executes
appinst, uploads files, issues a Release, or grants owner distribution consent.

The archived Build70/BB preflight is fixed at baseline69 -> Build70; never
change its constants to silently claim compatibility with a newer device.
This gate consumes the actual bytes read through a single O_NOFOLLOW file
descriptor and then checks a native macOS *ad-hoc* code seal on that immutable
snapshot. Ad-hoc code signing IS NOT publisher authentication. The previously
reported entitlement identity is historical, not a fresh device attestation.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path
import plistlib
import zipfile

from build66_ipa_preflight import AdmissionDenied, inspect_ipa
from build66_code_signature_gate import (
    CodeSignatureRejected, audit_code_signature_snapshot,
    INSTALLED_APPLICATION_IDENTIFIER,
)
from build70_unsigned_candidate_audit import (
    UnsignedCandidateRejected, _macho_ios_minimum,
)
from build69_production_release_preflight import _read_external_regular

QA_BUILD = 71
PHYSICAL_BASELINE_BUILD = 70
BUNDLE = "com.example.MangaReader12"
QA_FILENAME = "WebReader-Build71-iOS12-adhoc.ipa"
EXECUTABLE_IN_ZIP = "Payload/MangaReader12.app/MangaReader12"
INFO_PLIST_IN_ZIP = "Payload/MangaReader12.app/Info.plist"


class DIPrivateQARejected(ValueError):
    pass


def parse_di_checksum(value: bytes) -> str:
    """One exact SHA256+fixed-name line, source provenance NOT authenticated."""
    if type(value) is not bytes or not 0 < len(value) <= 512:
        raise DIPrivateQARejected("missing bounded QA checksum")
    try:
        raw = value.decode("ascii")
    except UnicodeError as exc:
        raise DIPrivateQARejected("checksum must be ASCII") from exc
    match = re.fullmatch(
        r"([0-9a-f]{64})  " + re.escape(QA_FILENAME) + r"\n", raw
    )
    if match is None:
        raise DIPrivateQARejected("invalid/ambiguous checksum or wrong QA filename")
    return match.group(1)


def preflight_di_build71_private_qa(
    path: Path, *, checksum_data: bytes,
    installed_build: int = PHYSICAL_BASELINE_BUILD,
) -> dict:
    """Return host-only QA audit; cannot authorize distribution or installation.

    All tests that need native codesign run on macOS. Never accept an IPA
    extracted by the user into a mutable dir as proof of the same bytes
    that a later installer will consume.
    """
    if type(installed_build) is not int or installed_build != PHYSICAL_BASELINE_BUILD:
        raise DIPrivateQARejected("physical baseline must be exactly Build70")
    candidate = Path(path)
    if candidate.name != QA_FILENAME or candidate.is_symlink():
        raise DIPrivateQARejected("wrong Build71 QA filename or symlink")
    digest = parse_di_checksum(checksum_data)
    try:
        size = candidate.stat().st_size
        checked = inspect_ipa(
            candidate, digest, size, installed_build,
            require_exact_identity=True, return_snapshot=True
        )
        snapshot = checked.pop("ipa_snapshot")
        if (
            checked["build"] != QA_BUILD
            or checked["minimum_ios"] != "12.0"
            or checked["bundle"] != BUNDLE
        ):
            raise DIPrivateQARejected("wrong Build71 bundle/version/minimum iOS")
        with zipfile.ZipFile(io.BytesIO(snapshot)) as archive:
            exe = archive.read(EXECUTABLE_IN_ZIP)
            actual_minimum = _macho_ios_minimum(exe[:1024 * 1024 + 32])
            info = plistlib.loads(archive.read(INFO_PLIST_IN_ZIP))
            if (
                info.get("CFBundleVersion") != str(QA_BUILD)
                or info.get("CFBundleIdentifier") != BUNDLE
                or info.get("CFBundleDisplayName") != "WebReader"
                or info.get("MinimumOSVersion") != "12.0"
            ):
                raise DIPrivateQARejected("wrong embedded Build71 identity")
        signature = audit_code_signature_snapshot(
            snapshot, checked["sha256"], checked["ipa_size"]
        )
    except (
        AdmissionDenied, CodeSignatureRejected, UnsignedCandidateRejected,
        OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile,
        plistlib.InvalidFileException, RuntimeError
    ) as exc:
        if isinstance(exc, DIPrivateQARejected):
            raise
        raise DIPrivateQARejected(
            "Build71 private QA refused: exact signed snapshot not verified"
        ) from exc
    if (
        signature.get("adHocSignatureIntegrityVerified") is not True
        or signature.get("thinArm64ExecutableVerified") is not True
        or signature.get("installedApplicationIdentifierMatch") is not True
        or signature.get("applicationIdentifier") != INSTALLED_APPLICATION_IDENTIFIER
        or not re.fullmatch(
            r"[0-9a-f]{40}",
            signature.get("approvedArtifactStaticCodeDirectoryCDHash", "")
        )
    ):
        raise DIPrivateQARejected("ad-hoc code identity / signature mismatch")

    # Each true item is a HOST-only observation of this fixed byte snapshot.
    # The historical application-identifier string is necessary but does not
    # prove the installed physical Build70 identity or future OS admission.
    return {
        "status": "DI_SIGNED_QA_SNAPSHOT_HOST_ONLY_NOT_DISTRIBUTABLE",
        "expectedInstalledPhysicalBuild": PHYSICAL_BASELINE_BUILD,
        "candidateBuild": QA_BUILD,
        "bundleID": BUNDLE,
        "iosMinimumDeclared": checked["minimum_ios"],
        "iosMinimumFromExecutable": actual_minimum,
        "architecture": "arm64",
        "ipaSHA256": checked["sha256"],
        "ipaBytes": checked["ipa_size"],
        "checksumMatchesProvidedFile": True,
        "checksumSourceIndependentlyAuthenticated": False,
        "adHocCodeSealIntegrityVerifiedOnHost": True,
        "historicalApplicationIdentifierMatches": True,
        "historicalApplicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
        "staticCodeDirectoryCDHash": signature[
            "approvedArtifactStaticCodeDirectoryCDHash"
        ],
        "physicalBuild70AppIdentityNewlyAttested": False,
        "actualDeviceInstallabilityProven": False,
        "finalInstallerConsumedSameBytesProven": False,
        "publisherCryptographicallyAuthenticated": False,
        "productionEditorialTrustConfigured": False,
        "liveHelperPeerAuthenticated": False,
        "libraryBackupValidated": False,
        "libraryFavoritesProgressPreservedOnDevice": False,
        "offlineChaptersVerifiedAfterUpgrade": False,
        "ownerQADistributionApprovalRecorded": False,
        "readyForPrivateQADistribution": False,
        "readyForProductionRelease": False,
        "githubReleasePublished": False,
        "mainModified": False,
        "automaticUpdaterEnabled": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--checksum-file", type=Path, required=True)
    parser.add_argument("--installed-build", type=int, default=70)
    args = parser.parse_args()
    try:
        receipt = preflight_di_build71_private_qa(
            args.ipa,
            checksum_data=_read_external_regular(args.checksum_file, 512),
            installed_build=args.installed_build,
        )
    except (DIPrivateQARejected, ValueError, OSError) as exc:
        parser.error("BLOCKED: " + str(exc))
    print(json.dumps(receipt, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
