#!/usr/bin/env python3
"""Build66 fail-closed *preflight* for an IPA. Not a code-signature verifier.

The installer must independently verify signature, publisher and immutable bytes.
This module performs only bounded archive and Info.plist checks; it never installs.
"""
import hashlib
import io
import plistlib
import re
import stat
import zipfile
from pathlib import Path

MAX_IPA_BYTES = 512 * 1024 * 1024
MAX_FILES = 20000
MAX_UNCOMPRESSED = 1024 * 1024 * 1024
BUNDLE_ID = "com.example.MangaReader12"


class AdmissionDenied(ValueError):
    pass


def inspect_ipa(path, expected_sha256, expected_size, min_build):
    path = Path(path)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise AdmissionDenied("invalid digest")
    if type(expected_size) is not int or not 0 < expected_size <= MAX_IPA_BYTES:
        raise AdmissionDenied("invalid size")
    if type(min_build) is not int or min_build < 0:
        raise AdmissionDenied("invalid baseline")
    # A path is not a security boundary: reject symlinks and nonregular files.
    if path.is_symlink() or not path.is_file():
        raise AdmissionDenied("not a regular IPA")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
        raise AdmissionDenied("size mismatch")
    digest = hashlib.sha256()
    payload = io.BytesIO()
    with path.open("rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            payload.write(block)
            if payload.tell() > MAX_IPA_BYTES:
                raise AdmissionDenied("oversized IPA")
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise AdmissionDenied("IPA changed during preflight")
    if digest.hexdigest() != expected_sha256:
        raise AdmissionDenied("SHA-256 mismatch")
    try:
        with zipfile.ZipFile(payload) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_FILES:
                raise AdmissionDenied("invalid archive count")
            if len({e.filename for e in entries}) != len(entries):
                raise AdmissionDenied("duplicate ZIP entries")
            if sum(e.file_size for e in entries) > MAX_UNCOMPRESSED:
                raise AdmissionDenied("oversized extracted content")
            for entry in entries:
                name = entry.filename
                if (name.startswith("/") or "\\" in name or
                        any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))):
                    raise AdmissionDenied("unsafe ZIP path")
                mode = (entry.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise AdmissionDenied("ZIP symlink")
            infos = [e for e in entries if re.fullmatch(
                r"Payload/[^/]+\\.app/Info\\.plist", e.filename
            )]
            if len(infos) != 1 or infos[0].file_size > 1024 * 1024:
                raise AdmissionDenied("missing or ambiguous Info.plist")
            metadata = plistlib.loads(archive.read(infos[0]))
            if metadata.get("CFBundleIdentifier") != BUNDLE_ID:
                raise AdmissionDenied("wrong bundle")
            build_text = metadata.get("CFBundleVersion")
            if not isinstance(build_text, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", build_text):
                raise AdmissionDenied("invalid build")
            build = int(build_text)
            if build <= min_build:
                raise AdmissionDenied("downgrade")
            minimum = metadata.get("MinimumOSVersion")
            if not isinstance(minimum, str) or not re.fullmatch(r"[0-9]{1,2}\\.[0-9]{1,2}(\\.[0-9]{1,2})?", minimum):
                raise AdmissionDenied("invalid iOS minimum")
            parts = tuple(int(x) for x in minimum.split("."))
            if (parts + (0,) * (3 - len(parts))) > (12, 5, 8):
                raise AdmissionDenied("incompatible iOS")
            return {"build": build, "bundle": BUNDLE_ID, "minimum_ios": minimum,
                    "sha256": digest.hexdigest()}
    except (zipfile.BadZipFile, plistlib.InvalidFileException, KeyError, ValueError) as exc:
        if isinstance(exc, AdmissionDenied):
            raise
        raise AdmissionDenied("malformed IPA") from exc


# IMPORTANT: this is NOT sufficient to authorize installation. A privileged
# helper must independently validate signed provenance, entitlements and the
# exact immutable file descriptor used by appinst.
