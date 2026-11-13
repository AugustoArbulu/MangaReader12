#!/usr/bin/env python3
"""EO: read-only, two-copy iOS12 offline baseline review on a HOST computer.

Only extracted full app-data-container copies are accepted. Never connects
to the iPad, writes, repairs, installs, checkpoints SQLite or restores data.
Copies that match are NOT device-attested and never authorize Build71.
"""
import argparse
import json
import os
from pathlib import Path
import sys

from build70_ec_full_container_dual_copy import compare_copies
from build70_ea_external_copy_audit import audit_snapshot
from build70_eh_sqlite_relational_integrity import audit_metadata_relations
from build70_ei_all_downloads_inventory import audit_noncompleted_and_orphans
from build70_ej_recovery_plan_metadata import audit_recovery_plans
from build70_ek_partial_prefix_metadata import audit_partial_prefixes
from build70_ef_offline_payload_triage import review_offline_payloads


class EORejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def fail(code):
    raise EORejected(code)


def guarded_stage(label, callback, *args):
    """Do not disclose exceptions containing private paths or chapter IDs."""
    try:
        result = callback(*args)
    except Exception:
        fail("EO_STOP_" + label + "_FAILED")
    if (type(result) is not dict
            or type(result.get("status")) is not str
            or not result["status"].startswith(label + "_")):
        fail("EO_STOP_" + label + "_INVALID_REPORT")
    return result


def review_stage_or_stop(label, callback, snapshot):
    # One unsafe category must not conceal other findings. Preserve an
    # explicit STOP for independently rejected phases without leaking
    # exception strings, paths, metadata or page content.
    try:
        return guarded_stage(label, callback, snapshot)
    except EORejected:
        return {"status": label + "_STOP_EO_AUDIT_FAILED"}


def review_pair(first: Path, second: Path) -> dict:
    # EC already rejects same/nested roots, nonregular files and symlinks.
    # Its whole-tree hashes include preferences, documents and Downloads.
    baseline = guarded_stage("EC", compare_copies, first, second)
    if (baseline["status"].startswith("EC_STOP_")
            or baseline.get("copiesByteIdenticalHere") is not True):
        fail("EO_STOP_TWO_COPIES_NOT_IDENTICAL")

    steps = (
        ("EA", audit_snapshot),
        ("EH", audit_metadata_relations),
        ("EI", audit_noncompleted_and_orphans),
        ("EJ", audit_recovery_plans),
        ("EK", audit_partial_prefixes),
        ("EF", review_offline_payloads),
    )
    statuses = {"EC": baseline["status"]}
    summaries = {}
    for label, callback in steps:
        value = review_stage_or_stop(label, callback, first)
        statuses[label] = value["status"]
        if label == "EA" and not value["status"].startswith("EA_STOP_"):
            summaries["completedChapterRows"] = value["completedChapters"]
            summaries["completedPageFilesHashed"] = value["pageFilesReadAndHashed"]
            summaries["legacyCompletedChapterRows"] = value["legacyChapters"]
        if label == "EI" and not value["status"].startswith("EI_STOP_EO_"):
            summaries["incompleteDownloadRows"] = value["noncompletedDownloadRows"]
            summaries["orphanChapterFiles"] = value["orphanChapterFiles"]
        if label == "EF" and not value["status"].startswith("EF_STOP_"):
            summaries["unknownPageFormats"] = value["unknownFormats"]
            summaries["invalidPageSignatures"] = (
                value["truncatedOrBrokenSignatures"]
                + value["htmlJsonOrTextResponses"]
            )

    # Other audits may read for minutes; verify both copies have not changed
    # before even describing their temporary, local coherence.
    checked_again = guarded_stage("EC", compare_copies, first, second)
    if (checked_again["status"].startswith("EC_STOP_")
            or checked_again.get("copiesByteIdenticalHere") is not True
            or baseline.get("fullTreeSHA256") is None
            or checked_again.get("fullTreeSHA256") != baseline["fullTreeSHA256"]):
        fail("EO_STOP_TWO_COPIES_CHANGED_DURING_REVIEW")

    flagged = any(value.startswith(label + "_STOP_")
                  for label, value in statuses.items())
    status = (
        "EO_STOP_REQUIRES_HUMAN_REVIEW_OF_COPY"
        if flagged else "EO_TWO_COPIES_COHERENT_NOT_DEVICE_ATTESTED"
    )
    return {
        "status": status,
        "auditStatuses": statuses,
        "observedAggregateCounts": summaries,
        "copiesByteIdenticalAtTwoChecks": True,
        "originalDeviceIdentityAttested": False,
        "snapshotProvenTakenFromSameIPad": False,
        "independentPhysicalCustodyProven": False,
        "allImagesDecodeOnIOS12Proven": False,
        "offlineReadingOfSameChapterProven": False,
        "noUserDataLossAcrossUpgradeProven": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def rejected_report(status):
    return {
        "status": status,
        "originalDeviceIdentityAttested": False,
        "independentPhysicalCustodyProven": False,
        "offlineReadingOfSameChapterProven": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--first", type=Path, required=True,
                   help="first extracted full-container copy, on a host")
    p.add_argument("--second", type=Path, required=True,
                   help="independent second extracted full-container copy")
    args = p.parse_args(argv)
    try:
        result = review_pair(args.first, args.second)
    except EORejected as exc:
        result = rejected_report(exc.code)
    except (OSError, ValueError, TypeError, OverflowError):
        result = rejected_report("EO_STOP_INVALID_INPUT")

    # Intentionally print only statuses and bounded aggregate counts.
    # No original paths, source URLs, chapter titles, IDs or content hashes.
    print(json.dumps(result, sort_keys=True))
    # Even matching copies are not installation authorization. Intentionally
    # return a nonzero gate until independent on-device proof exists.
    return 2


if __name__ == "__main__":
    sys.exit(main())
