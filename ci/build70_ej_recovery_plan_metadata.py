#!/usr/bin/env python3
"""EJ: host-only bounded review of interrupted-download recovery plans.

No device access, no recovery, no modification of pages or SQLite, no URLs,
headers, chapter IDs or plan bodies in JSON output. A plausible plan is NOT
evidence that Swift Codable decoding or iOS12 resume will succeed.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

from build70_ea_external_copy_audit import (
    AuditRejected, audit_snapshot, safe_child, swift_component,
)
from build70_ed_portable_vs_external_library import copied_database, EDRejected
from build70_ei_all_downloads_inventory import (
    audit_noncompleted_and_orphans, EIRejected,
)
from build69_production_release_preflight import (
    _read_external_regular, ProductionPreflightRejected,
)

ACTIVE_STATES = frozenset(("paused", "queued", "downloading"))
MAX_PLAN_BYTES = 16 * 1024 * 1024  # exactly WebReaderOfflineRecoveryPlanReader.maxBytes
MAX_PAGES = 5000                  # exactly WebReaderOfflineResumePrefix.maximumPlannedPages
MAX_ROWS = 300_000


class EJRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stop(code):
    raise EJRejected(code)


def unique_object(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            stop("EJ_STOP_DUPLICATE_JSON_KEY")
        output[key] = value
    return output


def reject_nonfinite(value):
    stop("EJ_STOP_NONFINITE_JSON_NUMBER")


def plausible_plan(raw, source, manga, chapter):
    """Conservative metadata-only check; never expose any plan values."""
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                         parse_constant=reject_nonfinite)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
        stop("EJ_STOP_PLAN_JSON_INVALID")
    if type(obj) is not dict:
        stop("EJ_STOP_PLAN_SHAPE_INVALID")
    if type(obj.get("schemaVersion")) is not int or obj["schemaVersion"] != 1:
        stop("EJ_STOP_PLAN_SCHEMA_INVALID")
    if (type(obj.get("queueOrder")) is not int
            or not 0 <= obj["queueOrder"] <= 2**63 - 1):
        stop("EJ_STOP_PLAN_SHAPE_INVALID")
    # Build70 EN: optional replay flag is always Boolean if present.
    # True prevents treating stale pre-retry pages as a valid prefix.
    if ("requiresFullReplay" in obj
            and type(obj["requiresFullReplay"]) is not bool):
        stop("EJ_STOP_INVALID_REPLAY_FLAG")
    if (obj.get("sourceID") != source
            or type(obj.get("sourceID")) is not str):
        stop("EJ_STOP_PLAN_IDENTITY_MISMATCH")
    for field, expected in (
        ("manga", manga), ("chapter", chapter), ("manifest", source)
    ):
        value = obj.get(field)
        if type(value) is not dict or type(value.get("id")) is not str:
            stop("EJ_STOP_PLAN_SHAPE_INVALID")
        if value["id"] != expected:
            stop("EJ_STOP_PLAN_IDENTITY_MISMATCH")
    pages = obj.get("pages")
    if type(pages) is not list or not (1 <= len(pages) <= MAX_PAGES):
        stop("EJ_STOP_PLAN_PAGE_COUNT_INVALID")
    for index, page in enumerate(pages):
        if type(page) is not dict:
            stop("EJ_STOP_PLAN_PAGE_SHAPE_INVALID")
        if type(page.get("index")) is not int or page["index"] != index:
            stop("EJ_STOP_PLAN_PAGE_ORDER_INVALID")
        if type(page.get("imageUrl")) is not str or not page["imageUrl"]:
            stop("EJ_STOP_PLAN_PAGE_SHAPE_INVALID")
        headers = page.get("headers")
        if (type(headers) is not dict or
                any(type(k) is not str or type(v) is not str
                    for k, v in headers.items())):
            stop("EJ_STOP_PLAN_PAGE_SHAPE_INVALID")
    return len(pages)


def audit_recovery_plans(snapshot):
    try:
        inv = audit_noncompleted_and_orphans(snapshot)
        # Files/folders outside canonical chapter paths must be reviewed
        # before attempting a meaningful recovery-plan classification.
        if inv["status"] == "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES":
            stop("EJ_STOP_UNACCOUNTED_DOWNLOAD_TREE")
        baseline = audit_snapshot(snapshot)
        db, db_path, sha = copied_database(snapshot, baseline["sqliteSHA256"])
    except (EIRejected, AuditRejected, EDRejected, sqlite3.Error, OSError, ValueError):
        stop("EJ_STOP_EXTERNAL_COPY_INVALID")

    missing = malformed = mismatched = active = failed = valid = 0
    planned_pages = stale_completed = rows = 0
    try:
        root = Path(os.path.abspath(snapshot))
        lib = safe_child(root, "Library", directory=True)
        support = safe_child(lib, "Application Support", directory=True)
        app = safe_child(support, "MangaReader12", directory=True)
        downloads = safe_child(app, "Downloads", directory=True, required=False)
        sql = """
            SELECT d.state, m.source_id, m.source_manga_id, c.source_chapter_id
            FROM downloads d
            LEFT JOIN chapters c ON c.internal_id=d.chapter_id
            LEFT JOIN manga m ON m.internal_id=c.manga_id
            ORDER BY d.internal_id
        """
        for state, source, manga, chapter in db.execute(sql):
            rows += 1
            if rows > MAX_ROWS:
                stop("EJ_STOP_TOO_MANY_ROWS")
            if any(type(x) is not str for x in (state, source, manga, chapter)):
                stop("EJ_STOP_UNREADABLE_DOWNLOAD_ROW")
            if state == "completed":
                # Completion should remove this metadata. A leftover plan is
                # material to preserve for owner review, not to auto-delete.
                required = False
            elif state in ACTIVE_STATES:
                active += 1
                required = True
            else:
                failed += 1
                required = False

            folder = downloads
            if folder is not None:
                for raw_id in (source, manga, chapter):
                    folder = safe_child(folder, swift_component(raw_id),
                                        directory=True, required=False)
                    if folder is None:
                        break
            plan = None if folder is None else safe_child(
                folder, "_download-plan.json", required=False)
            if plan is None:
                if required:
                    missing += 1
                continue
            if state == "completed":
                stale_completed += 1
            try:
                binary = _read_external_regular(plan, MAX_PLAN_BYTES)
                count = plausible_plan(binary, source, manga, chapter)
                valid += 1
                planned_pages += count
            except ProductionPreflightRejected:
                malformed += 1
            except EJRejected as err:
                if err.code == "EJ_STOP_PLAN_IDENTITY_MISMATCH":
                    mismatched += 1
                else:
                    malformed += 1
        # Compare DB after all path/plan reads, not just before.
        from build70_ea_external_copy_audit import digest_file, MAX_DATABASE_BYTES
        if digest_file(db_path, MAX_DATABASE_BYTES) != sha:
            stop("EJ_STOP_COPY_CHANGED")
    except (AuditRejected, sqlite3.Error, OSError, UnicodeError, ValueError):
        stop("EJ_STOP_INPUT_CHANGED_OR_UNREADABLE")
    finally:
        db.close()

    if missing or malformed or mismatched or stale_completed:
        status = "EJ_STOP_MISSING_MALFORMED_OR_STALE_RECOVERY_PLANS"
    elif active or failed:
        status = "EJ_STOP_RECOVERY_ROWS_REQUIRE_DEVICE_REVIEW"
    else:
        status = "EJ_NO_PENDING_RECOVERY_ROWS_NOT_DEVICE_PROOF"
    return {
        "status": status,
        "downloadRowsExamined": rows,
        "activeRecoveryRows": active,
        "otherNoncompletedRows": failed,
        "missingRequiredPlans": missing,
        "malformedOrUnsafePlans": malformed,
        "identityMismatchedPlans": mismatched,
        "stalePlansOnCompletedRows": stale_completed,
        "plansWithPlausibleMetadata": valid,
        "sumOfDeclaredPlanPages": planned_pages,
        "fullSwiftCodableDecodePerformed": False,
        "resumabilityProvenOnIOS12": False,
        "headersOrURLsPrinted": False,
        "originalIPadAttested": False,
        "noChangesMadeToCopies": True,
        "ownerReleaseApprovalRecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = audit_recovery_plans(args.snapshot)
    except (EJRejected, OSError, ValueError) as exc:
        result = {
            "status": exc.code if isinstance(exc, EJRejected)
                      else "EJ_STOP_INVALID_INPUT",
            "readyToDistributeIPA": False,
            "readyToInstallIPA": False,
            "installationAuthorized": False,
            "restorationAuthorized": False,
            "automaticUpdaterEnabled": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"].startswith("EJ_STOP_") else 0


if __name__ == "__main__":
    sys.exit(main())
