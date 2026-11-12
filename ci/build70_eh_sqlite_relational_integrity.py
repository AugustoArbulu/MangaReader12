#!/usr/bin/env python3
"""EH: host-only full SQLite integrity + relational metadata audit.

Uses a copied, hashed SQLite image loaded in memory. NEVER repairs rows.
Fail-closed results do not authorize an IPA, restore, or automatic updater.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

from build70_ea_external_copy_audit import AuditRejected, audit_snapshot, MAX_DATABASE_BYTES
from build70_ed_portable_vs_external_library import copied_database, EDRejected


class EHRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stop(code):
    raise EHRejected(code)


def _scalar(db, sql):
    value = db.execute(sql).fetchone()
    if (not value or type(value[0]) is not int or value[0] < 0):
        stop("EH_STOP_BAD_DATABASE_RESULT")
    return value[0]


def audit_metadata_relations(snapshot):
    try:
        baseline = audit_snapshot(snapshot)
        db, path, fingerprint = copied_database(
            snapshot, baseline["sqliteSHA256"]
        )
    except (AuditRejected, EDRejected, sqlite3.Error, OSError, ValueError):
        stop("EH_STOP_EXTERNAL_COPY_INVALID")

    try:
        if db.execute("PRAGMA user_version").fetchone() != (1,):
            stop("EH_STOP_UNSUPPORTED_SCHEMA")
        # quick_check misses foreign-key relationship problems, so run both
        # full integrity_check and foreign_key_check (without disclosing rowids).
        integrity = db.execute("PRAGMA integrity_check").fetchall()
        if integrity != [("ok",)]:
            stop("EH_STOP_SQLITE_INTEGRITY_FAILED")
        violations = db.execute("PRAGMA foreign_key_check").fetchmany(1)
        if violations:
            stop("EH_STOP_FOREIGN_KEY_VIOLATIONS")
        # Production DownloadRepository.setState sets chapters.downloaded to
        # 1 iff the state is completed. Do not infer that missing rows are safe.
        out_of_sync = _scalar(db, """
            SELECT COUNT(*) FROM chapters c
            WHERE COALESCE(c.downloaded, -1) NOT IN (0,1)
               OR (c.downloaded = 1) <> EXISTS(
                    SELECT 1 FROM downloads d
                    WHERE d.chapter_id = c.internal_id AND d.state = 'completed'
                  )
        """)
        bad_completed_progress = _scalar(db, """
            SELECT COUNT(*) FROM downloads
            WHERE state='completed' AND (progress IS NULL OR progress != 1)
        """)
        bad_chapter_markers = _scalar(db, """
            SELECT COUNT(*) FROM chapters
            WHERE is_read IS NULL OR is_read NOT IN (0,1)
               OR bookmarked IS NULL OR bookmarked NOT IN (0,1)
               OR last_page_read IS NULL OR last_page_read < 0
        """)
        if out_of_sync:
            status = "EH_STOP_DOWNLOAD_FLAG_STATE_MISMATCH"
        elif bad_completed_progress:
            status = "EH_STOP_COMPLETED_DOWNLOAD_PROGRESS_MISMATCH"
        elif bad_chapter_markers:
            status = "EH_STOP_CHAPTER_MARKER_OUT_OF_RANGE"
        else:
            status = "EH_COPIED_SQLITE_METADATA_CONSISTENT_NOT_DEVICE_ATTESTED"
        # Rehash the path before describing any success: the in-memory DB
        # is not proof that the copied file did not change in parallel.
        from build70_ea_external_copy_audit import digest_file
        if digest_file(path, MAX_DATABASE_BYTES) != fingerprint:
            stop("EH_STOP_COPY_CHANGED")
    except (sqlite3.Error, UnicodeError, OverflowError):
        stop("EH_STOP_SQLITE_QUERY_FAILED")
    finally:
        db.close()

    return {
        "status": status,
        "foreignKeysChecked": True,
        "fullSQLiteIntegrityChecked": True,
        "chaptersWithDownloadFlagMismatch": out_of_sync,
        "completedDownloadsWithInvalidProgress": bad_completed_progress,
        "chaptersWithInvalidReadMarkers": bad_chapter_markers,
        "countsAreAggregateOnly": True,
        "repairAttempted": False,
        "rowsChanged": False,
        "snapshotOriginAttested": False,
        "consistencyOfSourceIPadProven": False,
        "originalDataContainerBackupProven": False,
        "iOS12OfflineReadingVerified": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_metadata_relations(args.snapshot)
    except (EHRejected, OSError, ValueError) as exc:
        report = {
            "status": exc.code if isinstance(exc, EHRejected)
                      else "EH_STOP_INPUT_INVALID",
            "readyToDistributeIPA": False,
            "readyToInstallIPA": False,
            "installationAuthorized": False,
            "restorationAuthorized": False,
            "automaticUpdaterEnabled": False,
        }
        print(json.dumps(report, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 2 if report["status"].startswith("EH_STOP_") else 0


if __name__ == "__main__":
    sys.exit(main())
