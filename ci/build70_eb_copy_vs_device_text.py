#!/usr/bin/env python3
"""EB: host-only crosscheck of Build70 clipboard totals and copied offline bytes.

Unauthenticated texts; agreement NEVER proves device origin or authorizes IPA.
"""
import argparse
import json
from pathlib import Path
import sys

from build70_ea_external_copy_audit import AuditRejected, audit_snapshot
from build70_do_preupgrade_baseline_audit import (
    DORejected, MAX_REPORTS, audit_build70_baseline,
)
from build70_dj_continuity_report_compare import DJRejected, _read_file_once


class EBRejected(ValueError):
    pass


def audit_eb(snapshot: Path, counts: bytes, batches: list[bytes]) -> dict:
    try:
        observed = audit_build70_baseline(counts, batches)
    except (DORejected, DJRejected) as exc:
        raise EBRejected("EB_STOP_NONCANONICAL_BUILD70_REPORT_TEXT") from exc
    try:
        copied = audit_snapshot(snapshot)
    except AuditRejected as exc:
        raise EBRejected("EB_STOP_EXTERNAL_COPY_UNSAFE_OR_INCOMPLETE") from exc

    text_count = observed["totalCompletedRecordsAsText"]
    copied_count = copied["completedChapters"]
    complete = observed["allCompletedRowsCoveredByTextSequence"]
    failures = observed["missingOrUnsafeChaptersAsText"]
    same_counts = (
        observed["validSequentialChaptersAsText"] == copied_count
        and observed["sealedChapterReceiptsAsText"] == copied["receiptVerifiedChapters"]
        and observed["legacyWithoutReceiptAsText"] == copied["legacyChapters"]
        and observed["offlinePageEntriesAsText"] == copied["pageFilesReadAndHashed"]
    )

    if failures:
        status = "EB_STOP_DEVICE_TEXT_REPORTS_MISSING_OR_UNSAFE_PAGES"
    elif text_count != copied_count:
        status = "EB_STOP_COMPLETED_CHAPTER_COUNTS_DIFFER"
    elif not complete:
        status = "EB_PARTIAL_DEVICE_TEXT_BATCHES_NOT_COMPARABLE"
    elif not same_counts:
        status = "EB_STOP_PAGE_OR_RECEIPT_COUNTS_DIFFER"
    elif copied_count == 0:
        status = "EB_ZERO_DOWNLOADS_REPORTED_NOT_DEVICE_PROOF"
    elif copied["legacyChapters"] or copied["nonAsciiIdentifierChapters"]:
        status = "EB_LEGACY_OR_UNICODE_REQUIRES_PHYSICAL_READING"
    else:
        status = "EB_COPIED_BYTES_AND_DEVICE_TEXT_TOTALS_AGREE_NOT_ATTESTED"

    return {
        "status": status,
        "reportedCompletedChapters": text_count,
        "copiedCompletedChapters": copied_count,
        "reportedPageFileEntries": observed["offlinePageEntriesAsText"],
        "copiedPageFilesReadAndHashed": copied["pageFilesReadAndHashed"],
        "reportedReceiptCount": observed["sealedChapterReceiptsAsText"],
        "copiedReceiptCount": copied["receiptVerifiedChapters"],
        "reportedMissingOrUnsafeCount": failures,
        "allBuild70TextBatchesPresent": complete,
        "comparisonsOnlyOfAggregateCounts": True,
        "reportsAuthenticatedAsPhysicalDeviceData": False,
        "copyProvenToComeFromSameDevice": False,
        "copyProvenToHaveBeenTakenAtSameMoment": False,
        "originalOfflineImageBytesCompared": False,
        "offlineImagesDecodedOrReadOnIOS12": False,
        "fullDataContainerExternallyBackedUp": False,
        "ownerDistributionApprovalRecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "installationPerformed": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--counts", type=Path, required=True)
    parser.add_argument("--offline", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    try:
        if len(args.offline) > MAX_REPORTS:
            raise EBRejected("EB_STOP_TOO_MANY_REPORT_BATCHES")
        result = audit_eb(
            args.snapshot,
            _read_file_once(args.counts),
            [_read_file_once(path) for path in args.offline],
        )
    except (EBRejected, OSError, DJRejected) as exc:
        status = (str(exc) if isinstance(exc, EBRejected)
                  else "EB_STOP_INVALID_OR_INACCESSIBLE_REPORT_INPUT")
        result = {
            "status": status,
            "installationAuthorized": False, "installationPerformed": False,
            "readyToDistributeIPA": False, "readyToInstallIPA": False,
            "restorationAuthorized": False, "automaticUpdaterEnabled": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
