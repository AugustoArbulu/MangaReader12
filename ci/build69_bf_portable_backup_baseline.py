#!/usr/bin/env python3
"""Build69 BF: Build68 portable-backup counts BEFORE Build69 exists.

Build68 cannot run Build69's new SQLite snapshot UI. Instead the owner may
export an EXISTING .mr12backup and examine a copy entirely on their own host.

CAUTION: The portable backup deliberately DELETES downloads and zeroes
chapters.downloaded, so offline image preservation CANNOT be inferred.
Reports never print titles, IDs, URLs, preferences, file paths or image bytes.
The caller—not the script—must establish that the backup came from Build68.
"""
import argparse
import base64
import binascii
import json
from pathlib import Path
import re
import sqlite3

from build69_be_compare_upgrade_counts import (
    METRICS, ContinuityReportRejected, parse_continuity_report
)
from build69_bc_copied_ipa_recheck import _unique_json_object
from build69_production_release_preflight import _read_external_regular

MAX_BACKUP_BYTES = 128 * 1024 * 1024
MAX_DATABASE_BYTES = 64 * 1024 * 1024

QUERIES = (
    "SELECT COUNT(*) FROM library;",
    "SELECT COUNT(*) FROM chapters;",
    "SELECT COUNT(*) FROM chapters WHERE is_read = 1;",
    "SELECT COUNT(*) FROM chapters WHERE last_page_read > 0;",
    "SELECT COUNT(*) FROM chapters WHERE bookmarked = 1;",
    None,  # Downloads: not present in a portable backup.
    "SELECT COUNT(*) FROM history;",
    "SELECT COUNT(*) FROM categories;",
    "SELECT COUNT(*) FROM manga_categories;",
)


class PortableBaselineRejected(ValueError):
    pass


def _read_counts_from_sqlite(raw: bytes):
    if not raw.startswith(b"SQLite format 3\x00"):
        raise PortableBaselineRejected("backup does not contain SQLite database")
    try:
        db = sqlite3.connect(":memory:")
        try:
            # Never open the user library in write mode or create a file.
            # Deserialize this bounded copy into a throwaway in-memory DB.
            db.deserialize(raw)
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            row = db.execute("PRAGMA user_version").fetchone()
            if not row or row[0] != 1:
                raise PortableBaselineRejected("unsupported library schema")
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise PortableBaselineRejected("corrupt backup SQLite snapshot")
            results = {}
            for name, sql in zip(METRICS, QUERIES):
                if sql is None:
                    results[name] = None
                    continue
                row = db.execute(sql).fetchone()
                if not row or type(row[0]) is not int or row[0] < 0:
                    raise PortableBaselineRejected("invalid SQLite count query")
                results[name] = row[0]
            return results
        finally:
            db.close()
    except (sqlite3.DatabaseError, sqlite3.OperationalError,
            sqlite3.NotSupportedError, MemoryError) as exc:
        raise PortableBaselineRejected("unreadable or unsupported portable SQLite backup") from exc


def read_build68_portable_baseline(backup: bytes) -> dict:
    if type(backup) is not bytes or not 0 < len(backup) <= MAX_BACKUP_BYTES:
        raise PortableBaselineRejected("missing or oversized portable backup")
    try:
        envelope = json.loads(
            backup.decode("utf-8"), object_pairs_hook=_unique_json_object
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise PortableBaselineRejected("invalid or duplicated JSON backup") from exc
    if (type(envelope) is not dict
            or set(envelope) != {
                "formatVersion", "createdAt", "databaseBase64", "preferences"
            } or type(envelope.get("formatVersion")) is not int
            or envelope["formatVersion"] != 1
            or type(envelope.get("databaseBase64")) is not str
            or type(envelope.get("preferences")) is not dict):
        raise PortableBaselineRejected("unsupported backup envelope")
    encoded = envelope["databaseBase64"]
    if len(encoded) > (MAX_DATABASE_BYTES * 4 // 3 + 8):
        raise PortableBaselineRejected("oversized base64 SQLite payload")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PortableBaselineRejected("malformed SQLite base64") from exc
    if not 0 < len(raw) <= MAX_DATABASE_BYTES:
        raise PortableBaselineRejected("oversized or missing SQLite data")
    counts = _read_counts_from_sqlite(raw)
    return {
        "status": "PORTABLE_LIBRARY_COUNTS_NOT_OFFLINE_CHAPTER_BASELINE",
        "backupFormatVersion": 1,
        "librarySchemaVersion": 1,
        "assumedInstalledBuildAtExport": 68,
        "buildAtExportAuthenticatedByTool": False,
        "metrics": counts,
        "missingDownloadCount": True,
        "offlineChapterImagesIncluded": False,
        "offlinePagesPreservedByBackup": False,
        "sensitiveValuesPrinted": False,
        "userLibraryModified": False,
        "restorationPerformed": False,
        "readyToInstall": False,
        "physicalUpgradeVerified": False,
    }


def compare_portable_baseline_to_build69(backup: bytes, after_report: bytes) -> dict:
    baseline = read_build68_portable_baseline(backup)
    try:
        after = parse_continuity_report(after_report)
    except ContinuityReportRejected as exc:
        raise PortableBaselineRejected("invalid post-upgrade iOS12 count report") from exc
    if after["build"] != 69 or after["ios"] != "12.5.8":
        raise PortableBaselineRejected("comparison requires Build69 on iOS 12.5.8")
    rows = []
    lost = changed = 0
    for name in METRICS:
        before_count = baseline["metrics"][name]
        after_count = after["counts"][name]
        if before_count is None:
            rows.append({
                "metric": name, "before": None, "after": after_count,
                "delta": None, "reason": "NOT_INCLUDED_IN_PORTABLE_BACKUP"
            })
            continue
        delta = after_count - before_count
        lost += int(delta < 0)
        changed += int(delta != 0)
        rows.append({
            "metric": name, "before": before_count,
            "after": after_count, "delta": delta
        })
    status = (
        "POTENTIAL_LIBRARY_LOSS_STOP_REVIEW" if lost else
        "LIBRARY_COUNTS_CHANGED_REVIEW" if changed else
        "LIBRARY_COUNTS_MATCH_OFFLINE_NOT_VERIFIED"
    )
    return {
        "status": status,
        "baselineBackupFormat": 1,
        "newBuild": 69,
        "ios": "12.5.8",
        "counts": rows,
        "decreasedLibraryMetricCount": lost,
        "changedLibraryMetricCount": changed,
        "offlineDownloadedPagesVerified": False,
        "downloadRecordCountComparable": False,
        "portableBackupContainsOfflinePages": False,
        "backupOriginAuthenticatedByTool": False,
        "physicalUpdateVerified": False,
        "ownerReviewCompleted": False,
        "installationAuthorized": False,
        "installationPerformed": False,
        "networkUsed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--after-report", type=Path,
                        help="only after manual Build69 QA and copied count report")
    args = parser.parse_args()
    raw = _read_external_regular(args.backup, MAX_BACKUP_BYTES)
    if args.after_report:
        result = compare_portable_baseline_to_build69(
            raw, _read_external_regular(args.after_report, 4096)
        )
    else:
        result = read_build68_portable_baseline(raw)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
