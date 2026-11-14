#!/usr/bin/env python3
"""ED: read-only comparison of SQLite library rows in a portable .mr12backup
and a previously extracted external data-container copy. No device access.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import sys
from build70_ea_external_copy_audit import (
    audit_snapshot, digest_file, AuditRejected, MAX_DATABASE_BYTES,
)
from build69_bf_portable_backup_baseline import (
    read_build68_portable_baseline, PortableBaselineRejected, MAX_BACKUP_BYTES,
    MAX_DATABASE_BYTES as MAX_PORTABLE_DB,
)
from build69_bc_copied_ipa_recheck import _unique_json_object
from build69_production_release_preflight import _read_external_regular

# Exact source-v1 schema columns. Chapters.downloaded is reset in the export.
COLS = {
    "manga": "internal_id source_id source_manga_id title cover description status url last_update date_added",
    "library": "manga_id date_added last_checked",
    "chapters": "internal_id manga_id source_chapter_id name number volume url is_read last_page_read bookmarked downloaded",
    "categories": "internal_id name sort_order",
    "manga_categories": "manga_id category_id",
    "history": "manga_id chapter_id last_read_at",
    "repositories": "internal_id name url enabled last_refresh",
    "source_settings": "source_id key value",
    "migration_map": "internal_id source_manga_id destination_manga_id migrated_at",
}
COLS = {table: tuple(raw.split()) for table, raw in COLS.items()}
MAX_ROWS = 2_000_000
MAX_CELL = 16 * 1024 * 1024


class EDRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stop(code):
    raise EDRejected(code)


def cell_bytes(value):
    if value is None:
        return b"N"
    if type(value) is int:
        return b"I" + str(value).encode("ascii")
    if type(value) is float:
        return b"F" + struct.pack(">d", value)
    if type(value) is str:
        return b"T" + value.encode("utf-8")
    if type(value) is bytes:
        return b"B" + value
    stop("ED_STOP_UNEXPECTED_SQLITE_TYPE")


def digest_rows(db, table):
    cols = tuple(x[1] for x in db.execute('PRAGMA table_info("' + table + '")'))
    if cols != COLS[table]:
        stop("ED_STOP_UNSUPPORTED_SCHEMA")
    selected = tuple(x for x in cols if not (table == "chapters" and x == "downloaded"))
    sql = 'SELECT rowid, ' + ", ".join('"' + x + '"' for x in selected)
    sql += ' FROM "' + table + '" ORDER BY rowid'
    h = hashlib.sha256(b"WEBREADER-ED-LIBRARY-ROWS-V1\x00" + table.encode("ascii"))
    count = 0
    for row in db.execute(sql):
        count += 1
        if count > MAX_ROWS:
            stop("ED_STOP_ROW_LIMIT")
        for value in row:
            data = cell_bytes(value)
            if len(data) > MAX_CELL:
                stop("ED_STOP_CELL_LIMIT")
            h.update(len(data).to_bytes(4, "big"))
            h.update(data)
    return count, h.digest()


def portable_database(raw):
    try:
        # Existing strict format/SQLite/sanitization validation; its legacy
        # Build68 label does not verify the build that actually exported it.
        read_build68_portable_baseline(raw)
        envelope = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object)
        binary = base64.b64decode(envelope["databaseBase64"], validate=True)
        if not 0 < len(binary) <= MAX_PORTABLE_DB:
            stop("ED_STOP_PORTABLE_INVALID")
        db = sqlite3.connect(":memory:")
        try:
            db.deserialize(binary)
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            return db
        except BaseException:
            db.close()
            raise
    except (PortableBaselineRejected, ValueError, KeyError,
            sqlite3.Error, MemoryError):
        stop("ED_STOP_PORTABLE_INVALID")


def copied_database(root, expected_sha256):
    db_path = Path(os.path.abspath(root)) / "Library" / "Application Support" / "MangaReader12" / "library.sqlite"
    # Bind all SQLite queries to exact bytes already checked by EA. Never
    # let SQLite reopen a potentially swapped path.
    raw = _read_external_regular(db_path, MAX_DATABASE_BYTES)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        stop("ED_STOP_COPY_CHANGED")
    db = sqlite3.connect(":memory:")
    try:
        db.deserialize(raw)
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        return db, db_path, bytes.fromhex(expected_sha256)
    except BaseException:
        db.close()
        raise

def compare_portable_to_copy(snapshot, portable_bytes):
    if type(portable_bytes) is not bytes or not 0 < len(portable_bytes) <= MAX_BACKUP_BYTES:
        stop("ED_STOP_PORTABLE_INVALID")
    try:
        observed = audit_snapshot(snapshot)
    except AuditRejected:
        stop("ED_STOP_EXTERNAL_COPY_INVALID")
    portable = portable_database(portable_bytes)
    try:
        try:
            copied, path, initial = copied_database(snapshot, observed["sqliteSHA256"])
        except (AuditRejected, OSError, ValueError, sqlite3.Error):
            stop("ED_STOP_EXTERNAL_COPY_INVALID")
        try:
            mismatches = []
            equal = rows = 0
            for table in COLS:
                a = digest_rows(copied, table)
                b = digest_rows(portable, table)
                rows += a[0]
                if rows > MAX_ROWS:
                    stop("ED_STOP_ROW_LIMIT")
                if a == b:
                    equal += 1
                else:
                    mismatches.append(table)
            if digest_file(path, MAX_DATABASE_BYTES) != initial:
                stop("ED_STOP_COPY_CHANGED")
        finally:
            copied.close()
    except (AuditRejected, sqlite3.Error, OSError, UnicodeError):
        stop("ED_STOP_DATABASE_UNREADABLE")
    finally:
        portable.close()
    return {
        "status": ("ED_LIBRARY_ROWS_EQUAL_NOT_ATTESTED" if not mismatches
                   else "ED_STOP_LIBRARY_ROWS_DIFFER"),
        "tablesCompared": len(COLS),
        "matchingTables": equal,
        "mismatchedTableNames": mismatches,
        "copiedRowsAcrossTables": rows,
        "portableBackupExcludesOfflinePages": True,
        "downloadedFlagAndDownloadRowsExcluded": True,
        "installedSourcesExcludedByPortableSanitizer": True,
        "preferencesNotComparedToUserDefaults": True,
        "physicalDeviceIdentityAttested": False,
        "backupAndCopyFromSameMomentProven": False,
        "portableOriginAuthenticated": False,
        "externalCopyOriginAuthenticated": False,
        "offlineImageDecodingVerified": False,
        "fullBackupRestorabilityProven": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backup", type=Path, required=True)
    p.add_argument("--snapshot", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = compare_portable_to_copy(
            args.snapshot, _read_external_regular(args.backup, MAX_BACKUP_BYTES))
    except (EDRejected, OSError, ValueError) as exc:
        result = {
            "status": exc.code if isinstance(exc, EDRejected)
                      else "ED_STOP_INPUT_UNREADABLE",
            "installationAuthorized": False,
            "restorationAuthorized": False,
            "readyToInstallIPA": False,
            "readyToDistributeIPA": False,
            "automaticUpdaterEnabled": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    # A structured STOP result is a failed preflight even when the input is
    # syntactically parseable. Do not let shell/CI treat it as success.
    return 2 if result["status"].startswith("ED_STOP_") else 0


if __name__ == "__main__":
    sys.exit(main())
