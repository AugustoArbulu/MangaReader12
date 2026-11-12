#!/usr/bin/env python3
"""EC: compare all files in two EXTRACTED off-device data-container copies.

Read-only host tool. Agreement is not device attestation or backup proof.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from build70_ea_external_copy_audit import audit_snapshot, digest_file, AuditRejected

MAX_FILES = 250000
MAX_DIRS = 100000
MAX_BYTES = 128 * 1024**3
MAX_DEPTH = 64
MAX_FILE = 1024**3

class ECRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def fail(code):
    raise ECRejected(code)

def audit_tree(root):
    root = Path(os.path.abspath(root))
    if root.is_symlink() or not root.is_dir():
        fail("EC_STOP_UNSAFE_ROOT")
    h = hashlib.sha256(b"WEBREADER-EC-FULL-COPY-V1\x00")
    stats = {"files": 0, "dirs": 0, "bytes": 0}
    def walk(folder, parts, depth):
        if depth > MAX_DEPTH:
            fail("EC_STOP_DEPTH_LIMIT")
        before = folder.lstat()
        if not stat.S_ISDIR(before.st_mode):
            fail("EC_STOP_UNSAFE_DIRECTORY")
        stats["dirs"] += 1
        if stats["dirs"] > MAX_DIRS:
            fail("EC_STOP_DIRECTORY_LIMIT")
        rel = b"/".join(parts)
        h.update(b"D" + len(rel).to_bytes(4, "big") + rel)
        with os.scandir(folder) as entries:
            names = sorted((e.name for e in entries), key=os.fsencode)
        for name in names:
            item = folder / name
            raw = os.fsencode(name)
            if not raw or b"/" in raw or b"\x00" in raw or len(raw) > 255:
                fail("EC_STOP_UNSAFE_NAME")
            entry = item.lstat()
            if stat.S_ISLNK(entry.st_mode):
                fail("EC_STOP_SYMLINK")
            child = parts + (raw,)
            if len(b"/".join(child)) > 4096:
                fail("EC_STOP_PATH_LIMIT")
            if stat.S_ISDIR(entry.st_mode):
                walk(item, child, depth + 1)
            elif stat.S_ISREG(entry.st_mode):
                stats["files"] += 1
                size = entry.st_size
                if stats["files"] > MAX_FILES or size > MAX_FILE or stats["bytes"] + size > MAX_BYTES:
                    fail("EC_STOP_FILE_OR_SIZE_LIMIT")
                digest = digest_file(item, MAX_FILE)
                stats["bytes"] += size
                relpath = b"/".join(child)
                h.update(b"F" + len(relpath).to_bytes(4, "big") + relpath)
                h.update(size.to_bytes(8, "big") + digest)
            else:
                fail("EC_STOP_UNSAFE_ENTRY")
        after = folder.lstat()
        if (before.st_dev, before.st_ino, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_mtime_ns
        ):
            fail("EC_STOP_DIRECTORY_CHANGED")
    try:
        walk(root, (), 0)
    except (OSError, AuditRejected, OverflowError, UnicodeError):
        fail("EC_STOP_UNREADABLE_OR_CHANGED")
    return {"sha256": h.hexdigest(), **stats}

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
    return 0

if __name__ == "__main__":
    sys.exit(main())
