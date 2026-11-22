#!/usr/bin/env python3
"""EC: compare two EXTRACTED external iOS data-container copies, read-only.

Descriptors anchor directory traversal; no children are followed via symlinks.
Two identical local copies do NOT attest origin, capture time or recoverability.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from build70_ea_external_copy_audit import audit_snapshot, AuditRejected

MAX_FILES = 250_000
MAX_DIRS = 100_000
MAX_BYTES = 128 * 1024**3
MAX_DEPTH = 64
MAX_FILE = 1024**3
CHUNK = 1024 * 1024
DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)


class ECRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def fail(code):
    raise ECRejected(code)


def _directory_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_mtime_ns,
            info.st_ctime_ns)


def _file_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_root(root):
    declared = os.path.abspath(root)
    if stat.S_ISLNK(os.lstat(declared).st_mode):
        fail("EC_STOP_UNSAFE_ROOT")
    # macOS /var is often a system symlink; normalize trusted ancestors.
    # The canonical path is opened component by component, anchored to FDs.
    resolved = os.path.realpath(declared)
    fd = os.open("/", DIR_FLAGS)
    try:
        for segment in Path(resolved).parts[1:]:
            entry = os.stat(segment, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISDIR(entry.st_mode):
                fail("EC_STOP_UNSAFE_ROOT")
            child_fd = os.open(segment, DIR_FLAGS, dir_fd=fd)
            opened = os.fstat(child_fd)
            if (opened.st_dev, opened.st_ino) != (entry.st_dev, entry.st_ino):
                os.close(child_fd)
                fail("EC_STOP_DIRECTORY_CHANGED")
            os.close(fd)
            fd = child_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _hash_file(directory_fd, name, initial, remaining):
    if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:
        fail("EC_STOP_UNSAFE_HARDLINK_OR_FILE")
    size = initial.st_size
    if size < 0 or size > MAX_FILE or size > remaining:
        fail("EC_STOP_FILE_OR_SIZE_LIMIT")
    fd = os.open(name, FILE_FLAGS, dir_fd=directory_fd)
    try:
        if _file_identity(os.fstat(fd)) != _file_identity(initial):
            fail("EC_STOP_FILE_CHANGED")
        h = hashlib.sha256()
        actual = 0
        while True:
            data = os.read(fd, CHUNK)
            if not data:
                break
            actual += len(data)
            if actual > size or actual > remaining:
                fail("EC_STOP_FILE_CHANGED")
            h.update(data)
        if actual != size or _file_identity(os.fstat(fd)) != _file_identity(initial):
            fail("EC_STOP_FILE_CHANGED")
        # A pathname replacement after open must not be silently accepted.
        if _file_identity(os.stat(name, dir_fd=directory_fd,
                                  follow_symlinks=False)) != _file_identity(initial):
            fail("EC_STOP_FILE_CHANGED")
        return h.digest(), actual
    finally:
        os.close(fd)


def audit_tree(root):
    """Hash every regular file, including empty/hidden files, via anchored FDs."""
    h = hashlib.sha256(b"WEBREADER-EC-FULL-COPY-V2\x00")
    totals = {"files": 0, "dirs": 0, "bytes": 0}

    def walk(directory_fd, path_parts, depth):
        if depth > MAX_DEPTH:
            fail("EC_STOP_DEPTH_LIMIT")
        initial = os.fstat(directory_fd)
        if not stat.S_ISDIR(initial.st_mode):
            fail("EC_STOP_UNSAFE_DIRECTORY")
        totals["dirs"] += 1
        if totals["dirs"] > MAX_DIRS:
            fail("EC_STOP_DIRECTORY_LIMIT")
        rel = b"/".join(path_parts)
        h.update(b"D" + len(rel).to_bytes(4, "big") + rel)
        with os.scandir(directory_fd) as entries:
            names = sorted((entry.name for entry in entries), key=os.fsencode)
        if len(names) > MAX_FILES + MAX_DIRS:
            fail("EC_STOP_ENTRY_LIMIT")
        for name in names:
            raw = os.fsencode(name)
            if not raw or len(raw) > 255 or b"/" in raw or b"\x00" in raw:
                fail("EC_STOP_UNSAFE_NAME")
            parts = path_parts + (raw,)
            path = b"/".join(parts)
            if len(path) > 4096:
                fail("EC_STOP_PATH_LIMIT")
            entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISLNK(entry.st_mode):
                fail("EC_STOP_SYMLINK")
            if stat.S_ISDIR(entry.st_mode):
                child_fd = os.open(name, DIR_FLAGS, dir_fd=directory_fd)
                try:
                    if (os.fstat(child_fd).st_dev, os.fstat(child_fd).st_ino) != (
                        entry.st_dev, entry.st_ino
                    ):
                        fail("EC_STOP_DIRECTORY_CHANGED")
                    walk(child_fd, parts, depth + 1)
                    after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                    if _directory_identity(after) != _directory_identity(entry):
                        fail("EC_STOP_DIRECTORY_CHANGED")
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(entry.st_mode):
                totals["files"] += 1
                if totals["files"] > MAX_FILES:
                    fail("EC_STOP_FILE_OR_SIZE_LIMIT")
                digest, size = _hash_file(
                    directory_fd, name, entry, MAX_BYTES - totals["bytes"]
                )
                totals["bytes"] += size
                h.update(b"F" + len(path).to_bytes(4, "big") + path)
                h.update(size.to_bytes(8, "big") + digest)
            else:
                fail("EC_STOP_UNSAFE_ENTRY")
        if _directory_identity(os.fstat(directory_fd)) != _directory_identity(initial):
            fail("EC_STOP_DIRECTORY_CHANGED")

    try:
        fd = _open_root(root)
        try:
            walk(fd, tuple(), 0)
        finally:
            os.close(fd)
    except (OSError, AuditRejected, OverflowError, UnicodeError):
        fail("EC_STOP_UNREADABLE_OR_CHANGED")
    return {"sha256": h.hexdigest(), **totals}


def compare_copies(first, second):
    a = os.path.realpath(os.path.abspath(first))
    b = os.path.realpath(os.path.abspath(second))
    if os.path.commonpath((a, b)) in (a, b):
        fail("EC_STOP_COPIES_NOT_DISTINCT")
    try:
        first_ea = audit_snapshot(first)
        second_ea = audit_snapshot(second)
    except AuditRejected:
        fail("EC_STOP_OFFLINE_COPY_INVALID")
    f1, f2 = audit_tree(first), audit_tree(second)
    match = (
        f1 == f2
        and first_ea["sqliteSHA256"] == second_ea["sqliteSHA256"]
        and first_ea["offlineContentSHA256"] == second_ea["offlineContentSHA256"]
    )
    if not match:
        status = "EC_STOP_EXTERNAL_COPIES_DIFFER"
    elif first_ea["completedChapters"] == 0:
        status = "EC_IDENTICAL_COPIES_ZERO_OFFLINE_NOT_DEVICE_PROOF"
    elif first_ea["legacyChapters"] or first_ea["nonAsciiIdentifierChapters"]:
        status = "EC_IDENTICAL_COPIES_LEGACY_NOT_DEVICE_PROOF"
    else:
        status = "EC_TWO_EXTERNAL_COPIES_IDENTICAL_NOT_DEVICE_PROOF"
    return {
        "status": status,
        "copyFileCounts": [f1["files"], f2["files"]],
        "copyByteCounts": [f1["bytes"], f2["bytes"]],
        "fullTreeSHA256": f1["sha256"] if match else None,
        "copiesByteIdenticalHere": match,
        "originOfEitherCopyAuthenticated": False,
        "originalIPadDataAttested": False,
        "wholeBackupRestorabilityProven": False,
        "offlineImageDecodingVerified": False,
        "ownerReleaseApprovalRecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--first", type=Path, required=True)
    ap.add_argument("--second", type=Path, required=True)
    args = ap.parse_args()
    try:
        result = compare_copies(args.first, args.second)
    except (ECRejected, OSError, ValueError) as exc:
        result = {
            "status": exc.code if isinstance(exc, ECRejected) else "EC_STOP_INVALID_INPUT",
            "installationAuthorized": False,
            "restorationAuthorized": False,
            "readyToDistributeIPA": False,
            "readyToInstallIPA": False,
            "automaticUpdaterEnabled": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    # A structured STOP result is a failed preflight even when the input is
    # syntactically parseable. Do not let shell/CI treat it as success.
    return 2 if result["status"].startswith("EC_STOP_") else 0


if __name__ == "__main__":
    sys.exit(main())
