#!/usr/bin/env python3
"""Build66 fail-closed *preflight* for an IPA. Not a code-signature verifier.

The installer must independently verify signature, publisher and immutable bytes.
This module performs only bounded archive and Info.plist checks; it never installs.
"""
import hashlib
import io
import os
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


def inspect_ipa(path, expected_sha256, expected_size, min_build, *,
                require_exact_identity=False, return_snapshot=False):
    """Inspect one O_NOFOLLOW-opened, hash-verified in-memory IPA snapshot.

    require_exact_identity adds fixed WebReader archive-layout and executable
    checks. The caller must not treat this as proof of iOS code signing.
    """
    if type(require_exact_identity) is not bool or type(return_snapshot) is not bool:
        raise AdmissionDenied("invalid identity policy")
    path = Path(path)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise AdmissionDenied("invalid digest")
    if type(expected_size) is not int or not 0 < expected_size <= MAX_IPA_BYTES:
        raise AdmissionDenied("invalid size")
    if type(min_build) is not int or min_build < 0:
        raise AdmissionDenied("invalid baseline")
    # Open once with O_NOFOLLOW and inspect the actual descriptor. The bytes
    # validated here are an in-memory snapshot, never a mutable path to install.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | os.O_NONBLOCK
    if not hasattr(os, "O_NOFOLLOW"):
        raise AdmissionDenied("platform cannot reject symlinks atomically")
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise AdmissionDenied("cannot securely open IPA") from exc
    digest = hashlib.sha256()
    payload = io.BytesIO()
    try:
        with os.fdopen(fd, "rb") as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
                raise AdmissionDenied("size mismatch or nonregular file")
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
                payload.write(block)
                if payload.tell() > MAX_IPA_BYTES:
                    raise AdmissionDenied("oversized IPA")
            after = os.fstat(source.fileno())
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                    before.st_ctime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
                    after.st_ctime_ns):
                raise AdmissionDenied("IPA changed during preflight")
            if payload.tell() != expected_size:
                raise AdmissionDenied("size changed during read")
    except OSError as exc:
        raise AdmissionDenied("IPA read failed") from exc
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
                if require_exact_identity:
                    if entry.flag_bits & 1:
                        raise AdmissionDenied("encrypted ZIP member")
                    if entry.file_size > 512 * 1024 * 1024:
                        raise AdmissionDenied("oversized ZIP entry")
                    if entry.file_size and (
                        entry.compress_size == 0 or
                        entry.file_size > entry.compress_size * 10000
                    ):
                        raise AdmissionDenied("invalid ZIP compression ratio")
                    if entry.filename != "Payload/" and not entry.filename.startswith(
                        "Payload/MangaReader12.app/"
                    ):
                        raise AdmissionDenied("unexpected file outside WebReader bundle")
                name = entry.filename
                if (name.startswith("/") or "\\" in name or
                        any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))):
                    raise AdmissionDenied("unsafe ZIP path")
                mode = (entry.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise AdmissionDenied("ZIP symlink")
            infos = [e for e in entries if re.fullmatch(
                r"Payload/[^/]+\.app/Info\.plist", e.filename
            )]
            if len(infos) != 1 or infos[0].file_size > 1024 * 1024:
                raise AdmissionDenied("missing or ambiguous Info.plist")
            if require_exact_identity:
                if infos[0].filename != "Payload/MangaReader12.app/Info.plist":
                    raise AdmissionDenied("unexpected app container")
                executable_name = "Payload/MangaReader12.app/MangaReader12"
                if executable_name not in {entry.filename for entry in entries}:
                    raise AdmissionDenied("missing executable")
                if archive.getinfo(executable_name).file_size < 4:
                    raise AdmissionDenied("empty executable")
            metadata = plistlib.loads(archive.read(infos[0]))
            if not isinstance(metadata, dict):
                raise AdmissionDenied("invalid Info.plist document")
            if metadata.get("CFBundleIdentifier") != BUNDLE_ID:
                raise AdmissionDenied("wrong bundle")
            if require_exact_identity and (
                metadata.get("CFBundleExecutable") != "MangaReader12" or
                metadata.get("CFBundleDisplayName") != "WebReader"
            ):
                raise AdmissionDenied("wrong app executable or display name")
            build_text = metadata.get("CFBundleVersion")
            if not isinstance(build_text, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", build_text):
                raise AdmissionDenied("invalid build")
            build = int(build_text)
            if build <= min_build:
                raise AdmissionDenied("downgrade")
            minimum = metadata.get("MinimumOSVersion")
            if not isinstance(minimum, str) or not re.fullmatch(r"[0-9]{1,2}\.[0-9]{1,2}(\.[0-9]{1,2})?", minimum):
                raise AdmissionDenied("invalid iOS minimum")
            parts = tuple(int(x) for x in minimum.split("."))
            if (parts + (0,) * (3 - len(parts))) > (12, 5, 8):
                raise AdmissionDenied("incompatible iOS")
            result = {"build": build, "bundle": BUNDLE_ID, "minimum_ios": minimum,
                      "sha256": digest.hexdigest(), "ipa_size": len(payload.getbuffer())}
            # Host QA can pass this exact immutable snapshot to codesign without
            # reopening the original untrusted path. Never return it by default.
            if return_snapshot:
                result["ipa_snapshot"] = payload.getvalue()
            return result
    except (zipfile.BadZipFile, zipfile.LargeZipFile, plistlib.InvalidFileException,
            KeyError, ValueError, TypeError, EOFError, RuntimeError, OSError,
            OverflowError) as exc:
        if isinstance(exc, AdmissionDenied):
            raise
        raise AdmissionDenied("malformed IPA") from exc


# IMPORTANT: this is NOT sufficient to authorize installation. A privileged
# helper must independently validate signed provenance, entitlements and the
# exact immutable file descriptor used by appinst.
