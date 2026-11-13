#!/usr/bin/env python3
"""EI: account for ALL copied Downloads files, including interrupted jobs.

Read-only metadata inventory. No IPad access, no writes, no filesystem repair.
Both the copied SQLite and directory tree remain unauthenticated evidence.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

from build70_ea_external_copy_audit import (
    AuditRejected, audit_snapshot, swift_component,
)
from build70_ed_portable_vs_external_library import copied_database, EDRejected

MAX_FILES = 300_000
MAX_DIRS = 120_000
MAX_BYTES = 128 * 1024**3
MAX_DEPTH = 12
DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


class EIRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stop(code):
    raise EIRejected(code)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode,
            info.st_mtime_ns, info.st_ctime_ns)


def _collect_download_tree(root):
    """Depth-first inventory via anchored directory FDs; returns no filenames."""
    summary = {"files": 0, "directories": 0, "totalBytes": 0,
               "filesByChapter": {}, "bytesByChapter": {},
               "unexpectedDepthFiles": 0, "unexpectedDepthDirectories": 0,
               "unexpectedDepthBytes": 0}
    if not root.exists() and not root.is_symlink():
        return summary
    # Check root is not a symlink before any traversal.
    root_info = root.lstat()
    if not stat.S_ISDIR(root_info.st_mode):
        stop("EI_STOP_UNSAFE_DOWNLOAD_ROOT")
    try:
        fd = os.open(root, DIR_FLAGS)
        try:
            if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (
                root_info.st_dev, root_info.st_ino
            ):
                stop("EI_STOP_DOWNLOAD_TREE_CHANGED")

            def walk(folder_fd, parts, depth):
                if depth > MAX_DEPTH:
                    stop("EI_STOP_DEPTH_LIMIT")
                initial = os.fstat(folder_fd)
                summary["directories"] += 1
                if summary["directories"] > MAX_DIRS:
                    stop("EI_STOP_DIRECTORY_LIMIT")
                if depth > 3:
                    summary["unexpectedDepthDirectories"] += 1
                try:
                    names = []
                    with os.scandir(folder_fd) as directory:
                        for entry in directory:
                            names.append(entry.name)
                            # Reject adversarially huge directories BEFORE
                            # allocating an unbounded sorted name list.
                            if len(names) > MAX_FILES + MAX_DIRS:
                                stop("EI_STOP_ENTRY_LIMIT")
                    names.sort(key=os.fsencode)
                except OSError:
                    stop("EI_STOP_DIRECTORY_UNREADABLE")
                for name in names:
                    raw = os.fsencode(name)
                    if (not raw or len(raw) > 255 or b"/" in raw or
                            b"\x00" in raw or name in (".", "..")):
                        stop("EI_STOP_UNSAFE_NAME")
                    if len(b"/".join([os.fsencode(v) for v in parts + (name,)])) > 4096:
                        stop("EI_STOP_PATH_LIMIT")
                    info = os.stat(name, dir_fd=folder_fd, follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        stop("EI_STOP_SYMLINK")
                    child = parts + (name,)
                    if stat.S_ISDIR(info.st_mode):
                        subfd = os.open(name, DIR_FLAGS, dir_fd=folder_fd)
                        try:
                            if (os.fstat(subfd).st_dev, os.fstat(subfd).st_ino) != (
                                info.st_dev, info.st_ino
                            ):
                                stop("EI_STOP_DOWNLOAD_TREE_CHANGED")
                            walk(subfd, child, depth + 1)
                            if _identity(os.stat(
                                name, dir_fd=folder_fd, follow_symlinks=False
                            )) != _identity(info):
                                stop("EI_STOP_DOWNLOAD_TREE_CHANGED")
                        finally:
                            os.close(subfd)
                    elif stat.S_ISREG(info.st_mode):
                        if info.st_nlink != 1 or info.st_size < 0:
                            stop("EI_STOP_UNSAFE_FILE")
                        summary["files"] += 1
                        summary["totalBytes"] += info.st_size
                        if summary["files"] > MAX_FILES or summary["totalBytes"] > MAX_BYTES:
                            stop("EI_STOP_FILE_OR_SIZE_LIMIT")
                        if depth == 3:
                            key = tuple(parts)
                            summary["filesByChapter"][key] = (
                                summary["filesByChapter"].get(key, 0) + 1
                            )
                            summary["bytesByChapter"][key] = (
                                summary["bytesByChapter"].get(key, 0) + info.st_size
                            )
                        else:
                            summary["unexpectedDepthFiles"] += 1
                            summary["unexpectedDepthBytes"] += info.st_size
                    else:
                        stop("EI_STOP_SPECIAL_FILE")
                if _identity(os.fstat(folder_fd)) != _identity(initial):
                    stop("EI_STOP_DOWNLOAD_TREE_CHANGED")

            walk(fd, (), 0)
        finally:
            os.close(fd)
    except OSError:
        stop("EI_STOP_DOWNLOAD_TREE_UNREADABLE")
    return summary


def audit_noncompleted_and_orphans(snapshot):
    try:
        baseline = audit_snapshot(snapshot)
        copied, db_path, first_hash = copied_database(
            snapshot, baseline["sqliteSHA256"]
        )
    except (AuditRejected, EDRejected, sqlite3.Error, OSError, ValueError):
        stop("EI_STOP_EXTERNAL_COPY_INVALID")
    wanted = {}
    collisions = 0
    non_ascii = 0
    total_rows = incomplete_rows = 0
    try:
        sql = """
            SELECT d.state, m.source_id, m.source_manga_id,
                   c.source_chapter_id
            FROM downloads d
            LEFT JOIN chapters c ON c.internal_id = d.chapter_id
            LEFT JOIN manga m ON m.internal_id = c.manga_id
            ORDER BY d.internal_id
        """
        for state, source, manga, chapter in copied.execute(sql):
            total_rows += 1
            if total_rows > MAX_FILES:
                stop("EI_STOP_ROW_LIMIT")
            if any(type(v) is not str for v in (state, source, manga, chapter)):
                stop("EI_STOP_DOWNLOAD_ROW_WITHOUT_ID")
            components = tuple(swift_component(v) for v in (source, manga, chapter))
            if any(not v.isascii() for v in (source, manga, chapter)):
                non_ascii += 1
            if components in wanted:
                collisions += 1
            else:
                wanted[components] = state
            if state != "completed":
                incomplete_rows += 1
        # Bind SQL to the EA hash before filesystem review.
        from build70_ea_external_copy_audit import digest_file, MAX_DATABASE_BYTES
        if digest_file(db_path, MAX_DATABASE_BYTES) != first_hash:
            stop("EI_STOP_COPY_CHANGED")
    except (AuditRejected, sqlite3.Error, UnicodeError, OSError, ValueError):
        stop("EI_STOP_SQLITE_READ_FAILED")
    finally:
        copied.close()
    if collisions:
        stop("EI_STOP_SANITIZED_PATH_COLLISION")
    app = (Path(os.path.abspath(snapshot)) / "Library" /
           "Application Support" / "MangaReader12")
    tree = _collect_download_tree(app / "Downloads")

    # All known rows have a canonical path regardless of current download state.
    # Files that belong to paused, failed or queued jobs matter to preservation.
    known = tree["filesByChapter"]
    partial_files = partial_bytes = 0
    orphan_files = orphan_bytes = orphan_folders = 0
    recorded_folders = 0
    for folder, num in known.items():
        if folder in wanted:
            recorded_folders += 1
            if wanted[folder] != "completed":
                partial_files += num
                partial_bytes += tree["bytesByChapter"][folder]
        else:
            orphan_folders += 1
            orphan_files += num
            orphan_bytes += tree["bytesByChapter"][folder]
    unclassified = tree["unexpectedDepthFiles"]
    # Empty dirs may represent an interrupted job; retain them even if no
    # pages have yet been written. This scan flags content, not empty dirs.
    flagged = orphan_files or unclassified
    if flagged:
        status = "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES"
    elif incomplete_rows or non_ascii:
        status = "EI_NONCOMPLETED_DOWNLOADS_OR_UNICODE_REQUIRE_OWNER_REVIEW"
    elif baseline["completedChapters"] == 0:
        status = "EI_ZERO_COMPLETED_DOWNLOADS_NOT_DEVICE_PROOF"
    else:
        status = "EI_ALL_SCANNED_FILES_ACCOUNTED_NOT_DEVICE_PROOF"
    return {
        "status": status,
        "downloadRows": total_rows,
        "noncompletedDownloadRows": incomplete_rows,
        "downloadRowsWithUnicodeIDs": non_ascii,
        "chapterDirectoriesContainingFiles": len(known),
        "chapterDirectoriesMatchedToRows": recorded_folders,
        "partialJobFiles": partial_files,
        "partialJobBytes": partial_bytes,
        "orphanChapterDirectoriesWithFiles": orphan_folders,
        "orphanChapterFiles": orphan_files,
        "orphanChapterBytes": orphan_bytes,
        "unclassifiedFileCount": unclassified,
        "unclassifiedFileBytes": tree["unexpectedDepthBytes"],
        "nestedUnexpectedDirectoryCount": tree["unexpectedDepthDirectories"],
        "totalRegularFilesWithinDownloads": tree["files"],
        "totalRegularFileBytesWithinDownloads": tree["totalBytes"],
        "contentBytesVerifiedHere": False,
        "noncompletedFilesConfirmedToSurviveUpgrade": False,
        "allUserFilesOffDeviceProven": False,
        "sourceDeviceAttested": False,
        "originalIPadRead": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        result = audit_noncompleted_and_orphans(a.snapshot)
    except (EIRejected, AuditRejected, OSError, ValueError) as exc:
        result = {
            "status": exc.code if isinstance(exc, EIRejected) else "EI_STOP_INVALID_INPUT",
            "readyToDistributeIPA": False,
            "readyToInstallIPA": False,
            "installationAuthorized": False,
            "restorationAuthorized": False,
            "automaticUpdaterEnabled": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"].startswith("EI_STOP_") else 0


if __name__ == "__main__":
    sys.exit(main())
