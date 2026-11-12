#!/usr/bin/env python3
"""EA: read-only audit of an EXTRACTED, externally copied iOS app data container.

Does not copy, repair, checkpoint, install, restore or publish anything.
An internally consistent copy is NOT evidence of origin, off-device retention,
iOS code-signing identity or successful physical offline reading.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
from urllib.parse import quote

MAX_DATABASE_BYTES = 256 * 1024 * 1024
MAX_CHAPTERS = 100_000
MAX_TOTAL_PAGES = 1_000_000
MAX_PAGE_BYTES = 64 * 1024 * 1024
RECEIPT = ".webreader-completion-v1"
PAGE = re.compile(r"page-([0-9]{5})\.bin\Z", re.ASCII)
CHUNK = 1024 * 1024


class AuditRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def reject(code):
    raise AuditRejected(code)


def no_link(path: Path, directory=False, required=True):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if not required:
            return None
        reject("EA_STOP_REQUIRED_FILE_MISSING")
    except OSError:
        reject("EA_STOP_PATH_INACCESSIBLE")
    if stat.S_ISLNK(info.st_mode):
        reject("EA_STOP_SYMLINK")
    if directory and not stat.S_ISDIR(info.st_mode):
        reject("EA_STOP_INVALID_DIRECTORY")
    if not directory and not stat.S_ISREG(info.st_mode):
        reject("EA_STOP_INVALID_FILE")
    return info


def safe_child(parent: Path, child: str, directory=False, required=True):
    if not child or child in (".", "..") or "/" in child or "\\" in child:
        reject("EA_STOP_INVALID_COMPONENT")
    dest = parent / child
    return dest if no_link(dest, directory=directory, required=required) else None


def swift_component(value):
    """Approximate Foundation CharacterSet.alphanumerics scalar-wise.

    Non-ASCII IDs may have platform-dependent classification; do not claim
    iOS-path equivalence for them without a physical reading check.
    """
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 2048 or "\x00" in value:
        reject("EA_STOP_INVALID_DATABASE_ID")
    result = "".join(c if (c.isalnum() or c in "._-") else "_" for c in value)
    return "item" if result in ("", ".", "..") else result


def digest_file(path: Path, byte_limit: int):
    before = no_link(path)
    if before.st_size < 1 or before.st_size > byte_limit or before.st_nlink != 1:
        reject("EA_STOP_FILE_SIZE_OR_LINKS")
    h = hashlib.sha256()
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino, opened.st_size) != (
                before.st_dev, before.st_ino, before.st_size
            ):
                reject("EA_STOP_FILE_CHANGED")
            count = 0
            while True:
                data = os.read(fd, CHUNK)
                if not data:
                    break
                count += len(data)
                if count > byte_limit:
                    reject("EA_STOP_FILE_SIZE_OR_LINKS")
                h.update(data)
            after = os.fstat(fd)
        finally:
            os.close(fd)
        if count != before.st_size or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
        ):
            reject("EA_STOP_FILE_CHANGED")
    except OSError:
        reject("EA_STOP_FILE_READ_FAILED")
    return h.digest()


def inspect_pages(folder: Path, content_hash):
    names = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                name = entry.name
                if name.startswith("page-"):
                    if not PAGE.fullmatch(name):
                        reject("EA_STOP_INVALID_PAGE_FILENAME")
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        reject("EA_STOP_UNSAFE_PAGE")
                    names.append(name)
                elif name == RECEIPT and (entry.is_symlink() or not entry.is_file(follow_symlinks=False)):
                    reject("EA_STOP_UNSAFE_RECEIPT")
    except OSError:
        reject("EA_STOP_FOLDER_READ_FAILED")
    names.sort()
    if not names or len(names) > 99_999:
        reject("EA_STOP_MISSING_OR_TOO_MANY_PAGES")
    sealed = safe_child(folder, RECEIPT, required=False)
    for index, name in enumerate(names):
        if name != f"page-{index:05d}.bin":
            reject("EA_STOP_SPARSE_PAGES")
        page = safe_child(folder, name)
        file_hash = digest_file(page, MAX_PAGE_BYTES)
        content_hash.update(name.encode("ascii"))
        content_hash.update(file_hash)
    if sealed is not None:
        receipt_info = no_link(sealed)
        if receipt_info.st_size < 1 or receipt_info.st_size > 64:
            reject("EA_STOP_BAD_RECEIPT")
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(sealed, flags)
            try:
                if os.fstat(fd).st_ino != receipt_info.st_ino:
                    reject("EA_STOP_RECEIPT_CHANGED")
                raw = os.read(fd, 65)
            finally:
                os.close(fd)
        except OSError:
            reject("EA_STOP_BAD_RECEIPT")
        if raw != f"WR-OFFLINE-COMPLETE-V1:{len(names)}\n".encode("ascii"):
            reject("EA_STOP_BAD_RECEIPT")
    return len(names), sealed is not None


def audit_snapshot(snapshot: Path):
    root = Path(os.path.abspath(snapshot))
    no_link(root, directory=True)
    lib = safe_child(root, "Library", directory=True)
    support = safe_child(lib, "Application Support", directory=True)
    app = safe_child(support, "MangaReader12", directory=True)
    db_path = safe_child(app, "library.sqlite")
    db_info = no_link(db_path)
    if db_info.st_size < 1 or db_info.st_size > MAX_DATABASE_BYTES:
        reject("EA_STOP_DATABASE_SIZE")
    wal = safe_child(app, "library.sqlite-wal", required=False)
    if wal is not None and no_link(wal).st_size != 0:
        # immutable=1 would IGNORE uncheckpointed transactions. Never fake a
        # complete snapshot by disregarding a copied nonempty WAL.
        reject("EA_STOP_NONEMPTY_WAL_NEEDS_CONSISTENT_SQLITE_SNAPSHOT")
    # Fingerprint the exact DB file examined; reject in-place mutation.
    db_hash = digest_file(db_path, MAX_DATABASE_BYTES)
    uri = "file:" + quote(str(db_path), safe="/") + "?mode=ro&immutable=1"
    try:
        db = sqlite3.connect(uri, uri=True, timeout=0.1)
        try:
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            if db.execute("PRAGMA user_version").fetchone() != (1,):
                reject("EA_STOP_UNSUPPORTED_SCHEMA")
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                reject("EA_STOP_CORRUPT_DATABASE")
            total = db.execute("SELECT COUNT(*) FROM downloads WHERE state='completed'").fetchone()[0]
            if not isinstance(total, int) or total < 0 or total > MAX_CHAPTERS:
                reject("EA_STOP_TOO_MANY_CHAPTERS")
            query = """
                SELECT m.source_id, m.source_manga_id, c.source_chapter_id
                FROM downloads d
                JOIN chapters c ON c.internal_id=d.chapter_id
                JOIN manga m ON m.internal_id=c.manga_id
                WHERE d.state='completed'
                ORDER BY d.internal_id
            """
            rows = db.execute(query)
            downloads = safe_child(app, "Downloads", directory=True, required=total > 0)
            if total and downloads is None:
                reject("EA_STOP_DOWNLOADS_MISSING")
            content_hash = hashlib.sha256(b"WEBREADER-EA-PAGES-V1\x00")
            seen = set()
            pages = sealed_count = chapters = non_ascii = 0
            for source, manga, chapter in rows:
                components = tuple(swift_component(v) for v in (source, manga, chapter))
                if any(not v.isascii() for v in (source, manga, chapter)):
                    non_ascii += 1
                if components in seen:
                    reject("EA_STOP_SANITIZED_PATH_COLLISION")
                seen.add(components)
                parent = downloads
                for name in components:
                    parent = safe_child(parent, name, directory=True)
                for original in (source, manga, chapter):
                    raw = original.encode("utf-8")
                    content_hash.update(len(raw).to_bytes(4, "big"))
                    content_hash.update(raw)
                amount, sealed = inspect_pages(parent, content_hash)
                pages += amount
                sealed_count += int(sealed)
                chapters += 1
                if pages > MAX_TOTAL_PAGES:
                    reject("EA_STOP_TOO_MANY_PAGES")
            if chapters != total:
                reject("EA_STOP_COMPLETED_ROW_JOIN_MISMATCH")
        finally:
            db.close()
    except sqlite3.Error:
        reject("EA_STOP_DATABASE_UNREADABLE")
    if digest_file(db_path, MAX_DATABASE_BYTES) != db_hash:
        reject("EA_STOP_DATABASE_CHANGED")
    return {
        "status": (
            "EA_NO_COMPLETED_DOWNLOADS_NOT_DEVICE_PROOF" if not total else
            "EA_LEGACY_OR_NONASCII_IDS_REQUIRE_DEVICE_READING" if sealed_count != total or non_ascii else
            "EA_COPIED_SQLITE_AND_OFFLINE_BYTES_COHERENT_NOT_DEVICE_PROOF"
        ),
        "completedChapters": total,
        "receiptVerifiedChapters": sealed_count,
        "legacyChapters": total - sealed_count,
        "nonAsciiIdentifierChapters": non_ascii,
        "pageFilesReadAndHashed": pages,
        "sqliteSHA256": db_hash.hex(),
        "offlineContentSHA256": content_hash.hexdigest(),
        "copyIsCryptographicallyProvenToBeFromIPad": False,
        "copyRetainedOffDeviceIndependentlyProven": False,
        "physicalOfflineReadingVerified": False,
        "completeUserDataBackupProven": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True,
                        help="EXTRACTED app data container copy on a separate computer")
    args = parser.parse_args(argv)
    try:
        result = audit_snapshot(args.snapshot)
    except AuditRejected as exc:
        result = {
            "status": exc.code, "installationAuthorized": False,
            "restorationAuthorized": False, "automaticUpdaterEnabled": False,
            "completeUserDataBackupProven": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
