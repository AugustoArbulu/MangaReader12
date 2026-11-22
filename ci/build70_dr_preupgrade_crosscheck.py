#!/usr/bin/env python3
"""Build70 DR: reconcile TWO independent, UNATTESTED pre-upgrade text formats.

DQ: user-supplied read-only installed-bundle metadata claim.
DO: user-supplied read-only SQLite/offline sample claims from Build70.

This is a fail-closed HOST consistency filter, NOT device attestation,
signature verification, install eligibility check, backup, or release gate.
The two reports could come from different dates, apps, or devices.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build70_dq_installed_bundle_report import DQReportRejected, inspect_dq_text
from build70_do_preupgrade_baseline_audit import DORejected, audit_build70_baseline
from build70_dj_continuity_report_compare import DJRejected, _read_file_once


class DRRejected(ValueError):
    pass


IDENTITY_MATCH = "DQ_REPORTED_MATCH_HISTORICAL_METADATA_NOT_ATTESTED"
IDENTITY_UNAVAILABLE = "DQ_REPORTED_INSTALLED_IDENTITY_FIELDS_UNAVAILABLE"
IDENTITY_MISMATCH = "DQ_REPORTED_BUNDLE_VERSION_OR_ENTITLEMENT_MISMATCH_STOP_QA"

OFFLINE_FULL = "DO_TEXT_FULL_COVERAGE_NO_IMAGE_BYTE_PROOF"
OFFLINE_INCOMPLETE = "DO_PARTIAL_SAMPLE_NEEDS_MORE_BATCHES"
OFFLINE_LEGACY = "DO_LEGACY_WITHOUT_RECEIPT_NEEDS_PHYSICAL_READING"
OFFLINE_BAD = "DO_OFFLINE_METADATA_FAILURE_OWNER_REVIEW_REQUIRED"
OFFLINE_EMPTY = "DO_NO_COMPLETE_OFFLINE_CHAPTERS_IN_TEXT_NOT_DEVICE_PROOF"


def audit_dr_preupgrade(
    installed_bundle_text: bytes,
    sqlite_count_text: bytes,
    offline_sample_texts: list[bytes],
) -> dict:
    """Never return install authority, even when both sets textually agree."""
    try:
        identity = inspect_dq_text(installed_bundle_text)
        offline = audit_build70_baseline(sqlite_count_text, offline_sample_texts)
    except (DQReportRejected, DORejected, DJRejected) as exc:
        raise DRRejected("invalid or noncanonical DQ/DO report") from exc

    identity_status = identity["status"]
    offline_status = offline["status"]
    if identity_status not in (IDENTITY_MATCH, IDENTITY_UNAVAILABLE, IDENTITY_MISMATCH):
        raise DRRejected("unknown DQ status")
    if offline_status not in (
        OFFLINE_FULL, OFFLINE_INCOMPLETE, OFFLINE_LEGACY, OFFLINE_BAD, OFFLINE_EMPTY,
    ):
        raise DRRejected("unknown DO status")

    # Explicit contradictions outrank unavailable or partial observations.
    if identity_status == IDENTITY_MISMATCH:
        status = "DR_REPORTED_IDENTITY_MISMATCH_STOP_QA"
    elif offline_status == OFFLINE_BAD:
        status = "DR_REPORTED_OFFLINE_METADATA_FAILURE_STOP_QA"
    elif identity_status == IDENTITY_UNAVAILABLE:
        status = "DR_REPORTED_INSTALLED_IDENTITY_UNAVAILABLE_NOT_READY"
    elif offline_status == OFFLINE_LEGACY:
        status = "DR_REPORTED_LEGACY_OFFLINE_NEEDS_REAL_READING"
    elif offline_status == OFFLINE_INCOMPLETE:
        status = "DR_REPORTED_OFFLINE_BATCHES_INCOMPLETE"
    elif offline_status == OFFLINE_EMPTY:
        status = "DR_REPORTED_NO_COMPLETED_OFFLINE_METADATA_NOT_DEVICE_PROOF"
    else:
        status = "DR_PREUPGRADE_TEXT_COHERENT_NOT_ATTESTED_NOT_INSTALLABLE"

    coherent = identity_status == IDENTITY_MATCH and offline_status == OFFLINE_FULL
    return {
        "status": status,
        "scope": "HOST_TEXT_CROSSCHECK_READ_ONLY_NO_INSTALL",
        "dqTextStatus": identity_status,
        "doTextStatus": offline_status,
        "reportedInstalledBundle": identity["reportedBundleID"],
        "reportedInstalledBuild": identity["reportedInstalledBuild"],
        "reportedApplicationIdentifier": identity["reportedApplicationIdentifierEntitlement"],
        "reportedCompletedChapterRecords": offline["totalCompletedRecordsAsText"],
        "reportedInspectedChapterRecords": offline["inspectedChapterRecordsAsText"],
        "reportedMissingUnsafeChapters": offline["missingOrUnsafeChaptersAsText"],
        "reportedLegacyChapters": offline["legacyWithoutReceiptAsText"],
        "reportedRemainingUninspectedChapters": offline["remainingRecordsNotInspectedAsText"],
        "bothReportFormatsTextuallyCoherent": coherent,
        "reportOriginsCryptographicallyAuthenticated": False,
        "sameDeviceAndSameMomentProven": False,
        "installedBuild70NativeSignatureValidated": False,
        "installedBuild70EntitlementAttested": False,
        "build71IPABytesSuppliedOrValidatedHere": False,
        "build71IOSInstallationCompatibilityProven": False,
        "publisherAuthenticated": False,
        "backupOutsideDeviceValidated": False,
        "libraryAndFavoritesContentsVerified": False,
        "offlineImageBytesDecodedAndReadWithoutWifi": False,
        "dataContainerSurvivalAcrossUpgradeProven": False,
        "ownerPrivateQADistributionConsentRecorded": False,
        "productionTrustProvisioned": False,
        "helperPeerAuthenticated": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "automaticUpdaterEnabled": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--dq", type=Path, required=True,
                     help="Optional installed-bundle DQ text")
    cli.add_argument("--counts", type=Path, required=True,
                     help="Build70 nine-count clipboard text")
    cli.add_argument("--offline", type=Path, action="append", required=True,
                     help="Build70 offline batch; repeat in order")
    args = cli.parse_args()
    try:
        if len(args.offline) > 256:
            raise DRRejected("too many offline batches")
        receipt = audit_dr_preupgrade(
            _read_file_once(args.dq),
            _read_file_once(args.counts),
            [_read_file_once(path) for path in args.offline],
        )
    except (DRRejected, DJRejected, OSError) as exc:
        cli.error("BLOCKED: " + str(exc))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
