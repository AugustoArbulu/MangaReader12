#!/usr/bin/env python3
"""Build70/DK — join DI package preflight and DJ library-count evidence.

READ-ONLY macOS HOST audit for a possible private Build70 -> Build71 QA.
Never generates, signs, uploads, distributes or installs an IPA. Does not
authenticate report authors, consent, publisher or installed Build70 identity.

A signed ad-hoc IPA inspected by DI plus two printable SQLite count reports
is insufficient to prove offline image bytes, in-place OS installation,
backup integrity, a real helper or editorial trust. All authority flags
remain false regardless of the host observations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from build69_production_release_preflight import _read_external_regular
from build70_dh_unsigned_build71_preview import (
    DHPreviewRejected, inspect_dh_source,
)
from build70_di_build71_private_qa_preflight import (
    DIPrivateQARejected, PHYSICAL_BASELINE_BUILD, QA_BUILD,
    preflight_di_build71_private_qa, parse_di_checksum,
)
from build70_dj_continuity_report_compare import (
    DJRejected, COUNT_LABELS, BEFORE_BUILD, AFTER_BUILD,
    IOS_VERSION, check_before_report, compare_reports, _read_file_once,
)


class DKEvidenceRejected(ValueError):
    pass


_DI_MUST_BE_FALSE = (
    "checksumSourceIndependentlyAuthenticated",
    "physicalBuild70AppIdentityNewlyAttested",
    "actualDeviceInstallabilityProven",
    "finalInstallerConsumedSameBytesProven",
    "publisherCryptographicallyAuthenticated",
    "productionEditorialTrustConfigured",
    "liveHelperPeerAuthenticated",
    "libraryBackupValidated",
    "libraryFavoritesProgressPreservedOnDevice",
    "offlineChaptersVerifiedAfterUpgrade",
    "ownerQADistributionApprovalRecorded",
    "readyForPrivateQADistribution",
    "readyForProductionRelease",
    "githubReleasePublished",
    "mainModified",
    "automaticUpdaterEnabled",
    "installationAuthorized",
    "installationPerformed",
)


def _check_di_receipt(receipt: dict, expected_sha: str) -> None:
    if type(receipt) is not dict:
        raise DKEvidenceRejected("DI package preflight receipt missing")
    required = {
        "status": "DI_SIGNED_QA_SNAPSHOT_HOST_ONLY_NOT_DISTRIBUTABLE",
        "expectedInstalledPhysicalBuild": PHYSICAL_BASELINE_BUILD,
        "candidateBuild": QA_BUILD,
        "bundleID": "com.example.MangaReader12",
        "iosMinimumDeclared": "12.0",
        "iosMinimumFromExecutable": "12.0",
        "architecture": "arm64",
        "ipaSHA256": expected_sha,
        "checksumMatchesProvidedFile": True,
        "adHocCodeSealIntegrityVerifiedOnHost": True,
        "historicalApplicationIdentifierMatches": True,
    }
    for key, value in required.items():
        if key not in receipt or type(receipt[key]) is not type(value) or receipt[key] != value:
            raise DKEvidenceRejected("DI identity/integrity mismatch: " + key)
    if type(receipt.get("ipaBytes")) is not int or not 0 < receipt["ipaBytes"] <= 512*1024*1024:
        raise DKEvidenceRejected("DI bounded IPA size invalid")
    if not isinstance(receipt.get("historicalApplicationIdentifier"), str) or (
        receipt["historicalApplicationIdentifier"] !=
        "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
    ):
        raise DKEvidenceRejected("historical identity inconsistent")
    cdhash = receipt.get("staticCodeDirectoryCDHash")
    if type(cdhash) is not str or re.fullmatch(r"[0-9a-f]{40}", cdhash) is None:
        raise DKEvidenceRejected("DI static code hash invalid")
    for key in _DI_MUST_BE_FALSE:
        if receipt.get(key) is not False:
            raise DKEvidenceRejected("DI would confer unapproved authority: " + key)


def audit_dk_qa_evidence(
    *, ipa_path: Path, checksum_data: bytes,
    before_report: bytes, after_report: bytes | None = None,
) -> dict:
    if PHYSICAL_BASELINE_BUILD != BEFORE_BUILD or QA_BUILD != AFTER_BUILD:
        raise DKEvidenceRejected("DI/DJ build chain mismatch")
    # Parse reports and source first. No IPA data or native code is involved
    # until both inputs have been validated as *syntactically* canonical.
    try:
        expected_sha = parse_di_checksum(checksum_data)
        before = check_before_report(before_report)
        comparison = (
            compare_reports(before_report, after_report)
            if after_report is not None else None
        )
        source = inspect_dh_source()
    except (DIPrivateQARejected, DJRejected, DHPreviewRejected, OSError) as exc:
        raise DKEvidenceRejected("baseline/report/source invalid") from exc

    if (
        source.get("projectSourceBuild") != 56
        or source.get("physicallyApprovedInstalledBuildReference") != 70
        or source.get("proposedQABuild") != 71
        or source.get("selfOnlyReportWired") is not True
        or source.get("identityClaimMatchesHistoricalQAFile") is not True
        or source.get("ownerDistributionApprovalRecorded") is not False
        or source.get("installationAuthorized") is not False
    ):
        raise DKEvidenceRejected("DH source audit does not match intended QA")
    if (before.get("status") != "DJ_BASELINE_COUNT_TEXT_ACCEPTED_UNATTESTED"
        or before.get("installationAuthorized") is not False):
        raise DKEvidenceRejected("DJ baseline is not an unauthenticated count receipt")
    if comparison is not None and (
        comparison.get("expectedInstalledBuild") != 70
        or comparison.get("candidateQABuild") != 71
        or comparison.get("originalReportsAuthenticated") is not False
        or comparison.get("offlinePageImageBytesVerified") is not False
        or comparison.get("installationAuthorized") is not False
        or comparison.get("readyToInstallIPA") is not False
    ):
        raise DKEvidenceRejected("DJ comparison unexpectedly asserts authority")
    try:
        di = preflight_di_build71_private_qa(
            ipa_path, checksum_data=checksum_data, installed_build=70
        )
    except (DIPrivateQARejected, OSError) as exc:
        raise DKEvidenceRejected("real exact-byte DI signed IPA audit rejected") from exc
    _check_di_receipt(di, expected_sha)

    if comparison is None:
        status = "DK_HOST_PACKAGE_CHECKED_BASELINE_TEXT_ONLY_NO_DISTRIBUTION"
        changes: list[str] = []
        equal = False
    elif comparison.get("status") == "DJ_COUNT_DIFFERENCE_REQUIRES_MANUAL_REVIEW":
        status = "DK_STOP_COUNT_DIFFERENCE_OWNER_REVIEW_REQUIRED"
        changes = comparison["differentCountLabels"]
        equal = False
    elif comparison.get("status") == "DJ_NINE_COUNTS_TEXTUALLY_EQUAL_NOT_OFFLINE_PROOF":
        status = "DK_EQUAL_COUNT_TEXT_NOT_OFFLINE_OR_INSTALL_PROOF"
        changes = []
        equal = True
    else:
        raise DKEvidenceRejected("unknown DJ report status")
    if (type(changes) is not list or len(changes) > len(COUNT_LABELS)
        or any(x not in COUNT_LABELS for x in changes)):
        raise DKEvidenceRejected("unexpected count comparison")

    return {
        "status": status,
        "expectedInstalledBuild": 70,
        "candidateBuild": 71,
        "targetIOS": IOS_VERSION,
        "bundleID": "com.example.MangaReader12",
        "hostIPALocalHash": di["ipaSHA256"],
        "hostIPABytes": di["ipaBytes"],
        "hostStaticCodeDirectoryCDHash": di["staticCodeDirectoryCDHash"],
        "hostAdHocSealVerified": True,
        "hostSourceHardStopsVerified": True,
        "baselineCountReportFormatAccepted": True,
        "afterCountReportFormatAccepted": comparison is not None,
        "nineCountsTextuallyEqual": equal,
        "changedCountLabels": changes,
        "reportsIndependentlyAuthenticated": False,
        "deviceBuild70IdentityAttestedNow": False,
        "actualBuild71InstallationProven": False,
        "libraryContentsVerified": False,
        "offlinePageFilesVerified": False,
        "physicalOfflineChapterOpened": False,
        "beforeAfterReportsGenuinelyCapturedOnDevice": False,
        "backupPreservedOutsideDevice": False,
        "sameIPABytesConsumedByAppleInstaller": False,
        "publisherIdentityTrusted": False,
        "helperIPCAuthenticated": False,
        "productionEditorialTrustConfigured": False,
        "ownerDistributionApprovalRecorded": False,
        "readyToDistributePrivateIPA": False,
        "readyToInstall": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--ipa", type=Path, required=True)
    cli.add_argument("--checksum-file", type=Path, required=True)
    cli.add_argument("--before-report", type=Path, required=True)
    cli.add_argument("--after-report", type=Path)
    args = cli.parse_args()
    try:
        receipt = audit_dk_qa_evidence(
            ipa_path=args.ipa,
            checksum_data=_read_external_regular(args.checksum_file, 512),
            before_report=_read_file_once(args.before_report),
            after_report=(
                _read_file_once(args.after_report)
                if args.after_report is not None else None
            ),
        )
    except (DKEvidenceRejected, ValueError, OSError) as exc:
        cli.error("BLOCKED: " + str(exc))
    print(json.dumps(receipt, sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
