#!/usr/bin/env python3
"""Read-only structural/identity validation for unsigned WebReader IPA archives.

A package can pass this check and still be malicious: authenticity comes only
from an independently verified signed manifest, a protected signing key, and
the SHA-256 of the downloaded bytes. No app installation is attempted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import posixpath
import re
import stat
import zipfile

BUNDLE_ID = "com.example.MangaReader12"
EXECUTABLE = "MangaReader12"
APP_PREFIX = "Payload/MangaReader12.app/"
MAX_IPA_BYTES = 512 * 1024 * 1024
MAX_ENTRIES = 20000
MAX_ENTRY_UNCOMPRESSED = 512 * 1024 * 1024
MAX_UNCOMPRESSED_TOTAL = 1024 * 1024 * 1024
MAX_INFO_PLIST = 1024 * 1024

class IPARejected(ValueError):
    pass

def _version(string):
    if not isinstance(string, str) or not re.fullmatch(r"\d{1,2}\.\d{1,2}(?:\.\d{1,2})?", string):
        raise IPARejected("invalid iOS version")
    value = tuple(int(x) for x in string.split("."))
    return value + (0,) * (3 - len(value))

def _digest_of(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _check_name(name):
    if (not name or name.startswith("/") or "\\" in name or "\x00" in name or
        any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))):
        raise IPARejected("unsafe ZIP member path")
    if posixpath.normpath(name.rstrip("/")) != name.rstrip("/"):
        raise IPARejected("ZIP path normalization mismatch")
    return name

def validate_ipa(
    path: Path, expected_sha256: str, installed_build: int = 55,
    installed_ios: str = "12.5.8"
) -> dict:
    if not isinstance(expected_sha256, str) or not re.fullmatch("[0-9a-f]{64}", expected_sha256):
        raise IPARejected("invalid expected SHA-256")
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_IPA_BYTES:
        raise IPARejected("missing or oversized IPA")
    actual = _digest_of(path)
    if actual != expected_sha256:
        raise IPARejected("IPA SHA-256 mismatch")
    if not isinstance(installed_build, int) or isinstance(installed_build, bool) or installed_build < 0:
        raise IPARejected("invalid installed build")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_ENTRIES:
                raise IPARejected("too many ZIP entries")
            names = set()
            total = 0
            for info in members:
                _check_name(info.filename)
                if info.filename in names:
                    raise IPARejected("duplicate ZIP member")
                names.add(info.filename)
                if info.flag_bits & 1:
                    raise IPARejected("encrypted ZIP entry")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise IPARejected("ZIP symlink")
                if (info.file_size < 0 or info.file_size > MAX_ENTRY_UNCOMPRESSED
                    or info.compress_size < 0):
                    raise IPARejected("out of bounds ZIP entry")
                total += info.file_size
                if total > MAX_UNCOMPRESSED_TOTAL:
                    raise IPARejected("ZIP exceeds total decompressed limit")
                if info.file_size > 0 and info.compress_size == 0:
                    raise IPARejected("invalid compressed ZIP size")
                if (info.file_size > 0 and info.compress_size > 0 and
                    info.file_size > info.compress_size * 10000):
                    raise IPARejected("implausible ZIP compression ratio")
                if not info.filename.startswith("Payload/"):
                    raise IPARejected("unexpected entry outside Payload")
                if not info.filename.startswith(APP_PREFIX) and info.filename != "Payload/":
                    raise IPARejected("unexpected app bundle")
            plist_path = APP_PREFIX + "Info.plist"
            binary_path = APP_PREFIX + EXECUTABLE
            if plist_path not in names or binary_path not in names:
                raise IPARejected("missing app Info.plist or executable")
            if archive.getinfo(plist_path).file_size > MAX_INFO_PLIST:
                raise IPARejected("oversized Info.plist")
            try:
                info = plistlib.loads(archive.read(plist_path))
            except (ValueError, TypeError, OverflowError, KeyError) as e:
                raise IPARejected("invalid Info.plist") from e
            if not isinstance(info, dict):
                raise IPARejected("Info.plist is not a dictionary")
            if info.get("CFBundleIdentifier") != BUNDLE_ID:
                raise IPARejected("wrong bundle ID")
            if info.get("CFBundleExecutable") != EXECUTABLE:
                raise IPARejected("wrong executable name")
            if info.get("CFBundleDisplayName") != "WebReader":
                raise IPARejected("wrong display name")
            raw_build = info.get("CFBundleVersion")
            if not isinstance(raw_build, str) or not re.fullmatch(r"[1-9]\d{0,9}", raw_build):
                raise IPARejected("invalid build number")
            build = int(raw_build)
            if build <= installed_build:
                raise IPARejected("not a newer build")
            minimum = info.get("MinimumOSVersion")
            if _version(minimum) > _version(installed_ios):
                raise IPARejected("incompatible iOS version")
            if archive.getinfo(binary_path).file_size < 4:
                raise IPARejected("empty app executable")
    except (zipfile.BadZipFile, OSError, EOFError, RuntimeError, OverflowError) as e:
        raise IPARejected("malformed ZIP/IPA") from e

    return {
        "bundleId": BUNDLE_ID,
        "build": build,
        "displayName": "WebReader",
        "minimumIOS": minimum,
        "bytes": path.stat().st_size,
        "sha256": actual,
        "signature_or_origin_verified": False,
        "installation_performed": False
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--sha256-file", required=True, type=Path)
    parser.add_argument("--installed-build", type=int, default=55)
    parser.add_argument("--installed-ios", default="12.5.8")
    opts = parser.parse_args()
    text = opts.sha256_file.read_text().strip()
    fields = text.split()
    if not fields:
        raise IPARejected("missing checksum")
    print(json.dumps(validate_ipa(
        opts.ipa, fields[0], opts.installed_build, opts.installed_ios
    ), indent=2))

if __name__ == "__main__":
    main()
