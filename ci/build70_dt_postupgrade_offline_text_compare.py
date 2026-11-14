#!/usr/bin/env python3
"""Build70 DT: UNATTESTED before-70 / after-71 SQLite + offline text comparison.

Existing Build70 DO data and future Build71 clipboard output are compared
without reading chapter images, app containers, IPA files, or performing any
backup, restore or installation.

Matching aggregated counts cannot prove identical titles, records, bytes,
image decodability, publisher identity, preservation or same physical device.
Always outputs explicit negative authority; stop/review on contradictions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build70_dj_continuity_report_compare import (
    AFTER_BUILD, BEFORE_BUILD, DJRejected, IOS_VERSION,
    _read_file_once, compare_reports, parse_continuity_report,
)
from build70_do_preupgrade_baseline_audit import (
    DORejected, audit_build70_baseline, MAX_REPORTS,
)


class DTRejected(ValueError):
    pass


_BEFORE_LINE = f"Build observada: {BEFORE_BUILD} • iOS: {IOS_VERSION}".encode()
_AFTER_LINE = f"Build observada: {AFTER_BUILD} • iOS: {IOS_VERSION}".encode()

FALSE_FIELDS = (
    "inputReportsCryptographicallyAuthenticated",
    "samePhysicalDeviceAndMomentEstablished",
    "installedBuild70CodeIdentityCryptographicallyVerified",
    "physicalBuild71InstallationProven",
    "sqliteRowIdentityOrContentVerified",
    "exactSameOfflineChaptersProven",
    "offlineImagePayloadBytesVerified",
    "offlineImageDecodingVerified",
    "wifiDisabledPhysicalReadingVerified",
    "dataContainerRetentionProven",
    "externalBackupValidated",
    "publisherAuthenticated",
    "installerConsumedApprovedIPABytes",
    "ownerDistributionOrInstallConsentRecorded",
    "helperPeerAuthenticated",
    "automaticUpdaterEnabled",
    "readyToDistributeIPA",
    "readyToInstallIPA",
    "installationAuthorized",
    "installationPerformed",
)


def _canonical_after_as_before(data: bytes) -> bytes:
    """Map ONLY an exact Build71/iOS12 version header to Build70 for DO reuse.

    The DO parser remains fixed to 70; no loose regex or permissive version
    parsing. Every other byte is unchanged and parsed by the existing schema.
    """
    if type(data) is not bytes or not 0 < len(data) <= 4096:
        raise DTRejected("invalid bounded Build71 clipboard text")
    if b"\x00" in data or b"\r" in data:
        raise DTRejected("binary or CR in after report")
    rows = data.split(b"\n")
    if len(rows) < 2 or rows[1] != _AFTER_LINE:
        raise DTRejected("after report is not exactly Build71/iOS12.5.8")
    rows[1] = _BEFORE_LINE
    return b"\n".join(rows)


def compare_dt_upgrade_reports(
    *, before_counts: bytes, after_counts: bytes,
    before_offline: list[bytes], after_offline: list[bytes],
) -> dict:
    if (type(before_offline) is not list or type(after_offline) is not list
        or not 1 <= len(before_offline) <= MAX_REPORTS
        or not 1 <= len(after_offline) <= MAX_REPORTS):
        raise DTRejected("one to 256 ordered offline batches on each side")

    try:
        # DJ enforces exact Build70 + Build71 counts and metadata labels.
        dj = compare_reports(before_counts, after_counts)
        before = audit_build70_baseline(before_counts, before_offline)
        normalized_after_counts = _canonical_after_as_before(after_counts)
        normalized_after_batches = [
            _canonical_after_as_before(data) for data in after_offline
        ]
        after = audit_build70_baseline(
            normalized_after_counts, normalized_after_batches
        )
    except (DJRejected, DORejected, DTRejected) as exc:
        raise DTRejected("invalid Build70/Build71 SQLite/offline text format") from exc

    if dj["status"] not in (
        "DJ_NINE_COUNTS_TEXTUALLY_EQUAL_NOT_OFFLINE_PROOF",
        "DJ_COUNT_DIFFERENCE_REQUIRES_MANUAL_REVIEW",
    ):
        raise DTRejected("unknown DJ cross-build status")
    if before["status"] not in (
        "DO_TEXT_FULL_COVERAGE_NO_IMAGE_BYTE_PROOF",
        "DO_OFFLINE_METADATA_FAILURE_OWNER_REVIEW_REQUIRED",
        "DO_LEGACY_WITHOUT_RECEIPT_NEEDS_PHYSICAL_READING",
        "DO_PARTIAL_SAMPLE_NEEDS_MORE_BATCHES",
        "DO_NO_COMPLETE_OFFLINE_CHAPTERS_IN_TEXT_NOT_DEVICE_PROOF",
    ) or after["status"] not in (
        "DO_TEXT_FULL_COVERAGE_NO_IMAGE_BYTE_PROOF",
        "DO_OFFLINE_METADATA_FAILURE_OWNER_REVIEW_REQUIRED",
        "DO_LEGACY_WITHOUT_RECEIPT_NEEDS_PHYSICAL_READING",
        "DO_PARTIAL_SAMPLE_NEEDS_MORE_BATCHES",
        "DO_NO_COMPLETE_OFFLINE_CHAPTERS_IN_TEXT_NOT_DEVICE_PROOF",
    ):
        raise DTRejected("unknown DO cross-build status")

    fields_to_compare = (
        "totalCompletedRecordsAsText",
        "inspectedChapterRecordsAsText",
        "validSequentialChaptersAsText",
        "sealedChapterReceiptsAsText",
        "legacyWithoutReceiptAsText",
        "missingOrUnsafeChaptersAsText",
        "offlinePageEntriesAsText",
        "remainingRecordsNotInspectedAsText",
    )
    different = [
        key for key in fields_to_compare
        if before[key] != after[key]
    ]
    full = "DO_TEXT_FULL_COVERAGE_NO_IMAGE_BYTE_PROOF"
    bad = "DO_OFFLINE_METADATA_FAILURE_OWNER_REVIEW_REQUIRED"
    legacy = "DO_LEGACY_WITHOUT_RECEIPT_NEEDS_PHYSICAL_READING"
    zero = "DO_NO_COMPLETE_OFFLINE_CHAPTERS_IN_TEXT_NOT_DEVICE_PROOF"

    # Prioritize hard contradictions, never silently accept partial coverage.
    if dj["status"] == "DJ_COUNT_DIFFERENCE_REQUIRES_MANUAL_REVIEW":
        status = "DT_STOP_SQLITE_COUNTS_CHANGED_REVIEW_REQUIRED"
    elif before["status"] == bad or after["status"] == bad:
        status = "DT_STOP_OFFLINE_FILE_METADATA_UNSAFE_REVIEW_REQUIRED"
    elif before["status"] == legacy or after["status"] == legacy:
        status = "DT_REPORTED_LEGACY_CHAPTERS_REQUIRE_REAL_OFFLINE_READING"
    elif before["status"] == zero or after["status"] == zero:
        status = "DT_REPORTED_ZERO_OFFLINE_RECORDS_NOT_PHYSICAL_PROOF"
    elif before["status"] != full or after["status"] != full:
        status = "DT_REPORTED_OFFLINE_BATCHES_INCOMPLETE_REVIEW_REQUIRED"
    elif different:
        status = "DT_STOP_OFFLINE_AGGREGATES_CHANGED_REVIEW_REQUIRED"
    else:
        status = "DT_BEFORE_AFTER_TEXT_AGGREGATES_EQUAL_NOT_DATA_PROOF"

    return {
        "status": status,
        "beforeReportedBuild": BEFORE_BUILD,
        "afterReportedBuild": AFTER_BUILD,
        "targetIOS": IOS_VERSION,
        "beforeOfflineTextStatus": before["status"],
        "afterOfflineTextStatus": after["status"],
        "beforeReportedOfflineBatchCount": before["offlineBatchTextsChecked"],
        "afterReportedOfflineBatchCount": after["offlineBatchTextsChecked"],
        "changedSQLiteCountLabels": dj["differentCountLabels"],
        "changedOfflineAggregateFields": different,
        "allNineSQLiteCountsTextuallyEqual": dj["allNineCountsTextuallyEqual"],
        "beforeCompletedRowsCoveredByTexts": before["allCompletedRowsCoveredByTextSequence"],
        "afterCompletedRowsCoveredByTexts": after["allCompletedRowsCoveredByTextSequence"],
        "offlineAggregateValuesTextuallyEqual": len(different) == 0,
        **dict.fromkeys(FALSE_FIELDS, False),
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--before-counts", type=Path, required=True)
    cli.add_argument("--after-counts", type=Path, required=True)
    cli.add_argument("--before-offline", action="append", type=Path, required=True)
    cli.add_argument("--after-offline", action="append", type=Path, required=True)
    args = cli.parse_args()
    try:
        if len(args.before_offline) > MAX_REPORTS or len(args.after_offline) > MAX_REPORTS:
            raise DTRejected("too many batches")
        receipt = compare_dt_upgrade_reports(
            before_counts=_read_file_once(args.before_counts),
            after_counts=_read_file_once(args.after_counts),
            before_offline=[_read_file_once(x) for x in args.before_offline],
            after_offline=[_read_file_once(x) for x in args.after_offline],
        )
    except (DJRejected, DTRejected, OSError) as exc:
        cli.error("BLOCKED: " + str(exc))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
