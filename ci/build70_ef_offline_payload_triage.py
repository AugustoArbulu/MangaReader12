#!/usr/bin/env python3
"""EF: conservative READ-ONLY payload-type triage for EXTRACTED offline pages.

Headers/trailers are only sanity checks, NEVER an image decode or iPad proof.
The original pages and their paths remain private and unmodified.
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
from build70_ea_external_copy_audit import (
    audit_snapshot, AuditRejected, safe_child, no_link, swift_component,
    MAX_PAGE_BYTES,
)
from build70_ed_portable_vs_external_library import copied_database, EDRejected

PNG = b"\x89PNG\r\n\x1a\n"
PNG_IEND = b"\x00\x00\x00\x00IEND\xaeB\x60\x82"
GIFS = (b"GIF87a", b"GIF89a")
PAGE = re.compile(r"page-[0-9]{5}\.bin\Z", re.ASCII)
SNIFF = 96
MAX_PAGES = 1_000_000


class EFRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stop(code):
    raise EFRejected(code)


def classify_page_bytes(start: bytes, end: bytes, size: int):
    """Return recognized *plausible* signature, or a fail/unknown category."""
    stripped = start.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if (stripped.startswith((b"<!doctype html", b"<html", b"<?xml",
                             b"<script", b"{", b"["))
            or stripped.startswith(b"access denied")
            or stripped.startswith(b"error ")):
        return "nonImageResponse"
    if start.startswith(PNG):
        return "pngPlausible" if size >= 45 and end.endswith(PNG_IEND) else "truncated"
    if start.startswith(b"\xff\xd8\xff"):
        # Mirror the bounded EOI check in ChapterDownloadImageValidator.
        return ("jpegPlausible" if size >= 4 and b"\xff\xd9" in end[-64:]
                else "truncated")
    if start.startswith(b"RIFF") and start[8:12] == b"WEBP":
        if size < 20 or len(start) < 20:
            return "truncated"
        declared = int.from_bytes(start[4:8], "little")
        if (declared != size - 8 or declared % 2 != 0 or
                start[12:16] not in (b"VP8 ", b"VP8L", b"VP8X")):
            return "truncated"
        return "webpPlausible"
    if start.startswith(GIFS):
        return "gifPlausible" if size >= 14 and end.endswith(b"\x3b") else "truncated"
    if start.startswith(b"\x89PNG") or start.startswith(b"\xff\xd8"):
        return "truncated"
    if start.startswith(b"RIFF") and b"WEBP" in start[:16]:
        return "truncated"
    if start.startswith(b"GIF8"):
        return "truncated"
    return "unknownNeedsDeviceReading"


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def inspect_one_page(path):
    before = no_link(path)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        stop("EF_STOP_UNSAFE_FILE")
    if not 0 < before.st_size <= MAX_PAGE_BYTES:
        stop("EF_STOP_UNSAFE_FILE")
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) |
                     getattr(os, "O_NONBLOCK", 0))
        if _identity(os.fstat(fd)) != _identity(before):
            stop("EF_STOP_FILE_CHANGED")
        first = os.pread(fd, SNIFF, 0)
        last = os.pread(fd, SNIFF, max(0, before.st_size-SNIFF))
        if (_identity(os.fstat(fd)) != _identity(before)
                or _identity(os.lstat(path)) != _identity(before)):
            stop("EF_STOP_FILE_CHANGED")
    except OSError:
        stop("EF_STOP_FILE_UNREADABLE_OR_CHANGED")
    finally:
        if fd is not None:
            os.close(fd)
    return classify_page_bytes(first, last, before.st_size)


def review_offline_payloads(snapshot):
    try:
        ea = audit_snapshot(snapshot)
        copied, path, first_hash = copied_database(
            snapshot, ea["sqliteSHA256"]
        )
    except (AuditRejected, EDRejected, sqlite3.Error, OSError, ValueError):
        stop("EF_STOP_EXTERNAL_COPY_INVALID")
    counts = {key: 0 for key in (
        "jpegPlausible", "pngPlausible", "webpPlausible",
        "gifPlausible", "unknownNeedsDeviceReading", "truncated",
        "nonImageResponse",
    )}
    chapters = pages = 0
    app = (Path(os.path.abspath(snapshot)) / "Library" /
           "Application Support" / "MangaReader12")
    try:
        query = """
            SELECT m.source_id,m.source_manga_id,c.source_chapter_id
            FROM downloads d
            JOIN chapters c ON c.internal_id=d.chapter_id
            JOIN manga m ON m.internal_id=c.manga_id
            WHERE d.state='completed' ORDER BY d.internal_id
        """
        for source, manga, chapter in copied.execute(query):
            chapters += 1
            folder = app / "Downloads"
            for name in (source, manga, chapter):
                folder = safe_child(folder, swift_component(name),
                                    directory=True)
            with os.scandir(folder) as iterator:
                names = sorted(e.name for e in iterator if PAGE.fullmatch(e.name))
            for name in names:
                counts[inspect_one_page(safe_child(folder, name))] += 1
                pages += 1
                if pages > MAX_PAGES:
                    stop("EF_STOP_TOO_MANY_PAGES")
    except (AuditRejected, sqlite3.Error, OSError, ValueError):
        stop("EF_STOP_EXTERNAL_COPY_CHANGED_OR_UNREADABLE")
    finally:
        copied.close()
    if pages != ea["pageFilesReadAndHashed"] or chapters != ea["completedChapters"]:
        stop("EF_STOP_EXTERNAL_COPY_CHANGED_OR_UNREADABLE")
    # Do not call this an image decode. The app validates and decodes formats
    # on iOS 12, with an independent libwebp path.
    failing = counts["nonImageResponse"] + counts["truncated"]
    status = (
        "EF_STOP_HTML_OR_TRUNCATED_OFFLINE_FILES" if failing
        else "EF_UNKNOWN_FORMATS_REQUIRE_REAL_IOS12_READ" if counts["unknownNeedsDeviceReading"]
        else "EF_KNOWN_IMAGE_SIGNATURES_PLAUSIBLE_NOT_DECODED"
    )
    return {
        "status": status,
        "completedChapterRowsChecked": chapters,
        "pageFileHeadersAndTrailersRead": pages,
        "plausibleJPEG": counts["jpegPlausible"],
        "plausiblePNG": counts["pngPlausible"],
        "plausibleWebP": counts["webpPlausible"],
        "plausibleGIF": counts["gifPlausible"],
        "unknownFormats": counts["unknownNeedsDeviceReading"],
        "truncatedOrBrokenSignatures": counts["truncated"],
        "htmlJsonOrTextResponses": counts["nonImageResponse"],
        "fullImageDecodeAttempted": False,
        "iOS12ImageDecodeVerified": False,
        "sourceDeviceAttested": False,
        "originalImageBytesComparedWithIPad": False,
        "allUserFilesBackedUpProven": False,
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
        result = review_offline_payloads(args.snapshot)
    except (EFRejected, OSError, ValueError) as exc:
        result = {
            "status": exc.code if isinstance(exc, EFRejected)
                      else "EF_STOP_INVALID_INPUT",
            "readyToDistributeIPA": False, "readyToInstallIPA": False,
            "installationAuthorized": False, "restorationAuthorized": False,
            "automaticUpdaterEnabled": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    # A structured STOP result is a failed preflight even when the input is
    # syntactically parseable. Do not let shell/CI treat it as success.
    return 2 if result["status"].startswith("EF_STOP_") else 0


if __name__ == "__main__":
    sys.exit(main())
