#!/usr/bin/env python3
"""Read-only appinst .deb provenance/contents audit, Python 3 standard library.

This DOES NOT attest to official origin. A SHA-256 published by an untrusted
mirror only proves equality to that mirror's file; it is not a trust anchor.

Usage:
  python3 ci/audit_appinst_deb.py /path/to/ai.akemi.appinst_2.1.1_iphoneos-arm.deb

Never invokes appinst, dpkg installation, or maintainer scripts. Never
extracts any package file to disk. Contents can be attacker-controlled.
"""
import argparse
import hashlib
import io
import json
import posixpath
from pathlib import Path
import re
import tarfile

MAX_DEB_BYTES = 32 * 1024 * 1024
MAX_AR_PARTS = 12
MAX_TAR_ENTRIES = 10000
MAX_TAR_ENTRY_SIZE = 32 * 1024 * 1024
MAX_TAR_LOGICAL_SIZE = 96 * 1024 * 1024
MAX_CONTROL_FILE_SIZE = 65536

# Observed in Legacy-Me/repo/Packages. NOT an independently authenticated
# official digest. Used for mirror byte-for-byte identification only.
OBSERVED_MIRROR_IPHONEOS_ARM_SHA256 = (
    "5997771183c39eb8b5e13fc2bb511b1dfcb7eb39d3f10c9092ab088ec34aae09"
)
REQUIRED_CONTROL = {
    "Package": "ai.akemi.appinst",
    "Version": "2.1.1",
    "Architecture": "iphoneos-arm",
}
ALLOWED_AR_NAMES = {
    "debian-binary", "control.tar.gz", "control.tar.xz",
    "control.tar.bz2", "control.tar", "data.tar.gz",
    "data.tar.xz", "data.tar.bz2", "data.tar", "data.tar.zst"
}
SCRIPT_NAMES = {"preinst", "postinst", "prerm", "postrm", "config", "templates"}


class PackageRejected(ValueError):
    """Malformed or policy-incompatible archive (never execute it)."""


def parse_ar(data: bytes) -> dict:
    if not data.startswith(b"!<arch>\n"):
        raise PackageRejected("not a Debian ar archive")
    pos = 8
    parts = {}
    while pos < len(data):
        if len(parts) >= MAX_AR_PARTS or len(data) - pos < 60:
            raise PackageRejected("invalid or excessive ar members")
        hdr = data[pos:pos + 60]
        if hdr[58:] != b"\x60\n":
            raise PackageRejected("invalid ar trailer")
        try:
            filename = hdr[:16].decode("ascii").strip().rstrip("/")
            size = int(hdr[48:58].decode("ascii").strip())
        except (UnicodeError, ValueError) as e:
            raise PackageRejected("invalid ar header") from e
        pos += 60
        if size < 0 or size > MAX_DEB_BYTES or pos + size > len(data):
            raise PackageRejected("ar member outside archive")
        if filename in parts or filename not in ALLOWED_AR_NAMES:
            raise PackageRejected("unexpected or duplicate ar member: " + repr(filename[:32]))
        parts[filename] = data[pos:pos + size]
        pos += size + (size % 2)
    if pos != len(data):
        raise PackageRejected("invalid ar alignment")
    if parts.get("debian-binary") != b"2.0\n":
        raise PackageRejected("unsupported Debian archive format")
    controls = [k for k in parts if k.startswith("control.tar")]
    payloads = [k for k in parts if k.startswith("data.tar")]
    if len(controls) != 1 or len(payloads) != 1:
        raise PackageRejected("expected one control and one data tar")
    return parts


def normalize_entry_path(name: str) -> str:
    if not isinstance(name, str) or not name or name.startswith("/"):
        raise PackageRejected("absolute or missing tar member path")
    normalized = posixpath.normpath(name)
    if normalized == ".." or normalized.startswith("../"):
        raise PackageRejected("tar traversal path")
    if "\x00" in normalized or "\\" in normalized:
        raise PackageRejected("invalid tar member path")
    return normalized


def inspect_tar(data: bytes, control_archive: bool) -> tuple:
    entries, controls, scripts, total = [], {}, [], 0
    visited = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r|*") as tf:
            for member in tf:
                if len(entries) >= MAX_TAR_ENTRIES:
                    raise PackageRejected("too many tar members")
                name = normalize_entry_path(member.name)
                if name == ".":
                    continue
                if name in visited:
                    raise PackageRejected("duplicate tar member")
                visited.add(name)
                if member.size < 0 or member.size > MAX_TAR_ENTRY_SIZE:
                    raise PackageRejected("tar member too large")
                total += member.size
                if total > MAX_TAR_LOGICAL_SIZE:
                    raise PackageRejected("tar logical size too large")
                if member.issym() or member.islnk():
                    # Link targets are not followed. Reject to keep analysis
                    # and subsequent use limited to real regular files.
                    raise PackageRejected("symlink/hardlink in package")
                if not member.isdir() and not member.isfile():
                    raise PackageRejected("special device or non-file tar member")
                if member.mode & 0o6000:
                    raise PackageRejected("setuid/setgid tar member")
                entries.append(name)
                if control_archive and member.isfile():
                    if name in SCRIPT_NAMES:
                        scripts.append(name)
                    if name == "control":
                        if member.size > MAX_CONTROL_FILE_SIZE:
                            raise PackageRejected("oversized control metadata")
                        stream = tf.extractfile(member)
                        if stream is None:
                            raise PackageRejected("missing control content")
                        controls["control"] = stream.read(MAX_CONTROL_FILE_SIZE + 1)
                        if len(controls["control"]) != member.size:
                            raise PackageRejected("control metadata length mismatch")
    except (OSError, EOFError, tarfile.TarError, ValueError, OverflowError) as error:
        if isinstance(error, PackageRejected):
            raise
        raise PackageRejected("malformed compressed tar") from error
    return entries, controls, scripts


def control_fields(raw: bytes) -> dict:
    try:
        text = raw.decode("utf-8")
    except UnicodeError as error:
        raise PackageRejected("control is not UTF-8") from error
    fields = {}
    for line in text.splitlines():
        if line.startswith((" ", "\t")):
            continue
        if ": " not in line:
            raise PackageRejected("malformed package control")
        key, value = line.split(": ", 1)
        if key in fields or not re.fullmatch("[A-Za-z][A-Za-z0-9-]{0,80}", key):
            raise PackageRejected("duplicate or invalid control key")
        fields[key] = value.strip()
    return fields


def audit_bytes(data: bytes) -> dict:
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_DEB_BYTES:
        raise PackageRejected("package too large or empty")
    digest = hashlib.sha256(data).hexdigest()
    parts = parse_ar(data)
    control_member = next(k for k in parts if k.startswith("control.tar"))
    payload_member = next(k for k in parts if k.startswith("data.tar"))
    control_entries, controls, scripts = inspect_tar(parts[control_member], True)
    data_entries, _, _ = inspect_tar(parts[payload_member], False)
    if "control" not in controls:
        raise PackageRejected("no Debian control file")
    fields = control_fields(controls["control"])
    for key, expected in REQUIRED_CONTROL.items():
        if fields.get(key) != expected:
            raise PackageRejected(f"wrong {key}")
    if "usr/bin/appinst" not in data_entries:
        raise PackageRejected("no expected rootful /usr/bin/appinst")
    return {
        "package": fields["Package"],
        "version": fields["Version"],
        "architecture": fields["Architecture"],
        "bytes": len(data),
        "sha256": digest,
        "matches_observed_mirror_sha256": digest == OBSERVED_MIRROR_IPHONEOS_ARM_SHA256,
        "control_entries": control_entries,
        "data_entries": data_entries,
        "maintainer_scripts": scripts,
        "installed_appinst_path": "usr/bin/appinst",
        "official_origin_verified": False,
        "eligible_for_privileged_installation": False,
        "notice": (
            "This is a read-only structural audit. An untrusted mirror hash "
            "cannot prove original publisher authenticity. No appinst was run."
        ),
    }


def audit_file(filename: Path) -> dict:
    if not filename.is_file() or filename.stat().st_size > MAX_DEB_BYTES:
        raise PackageRejected("missing or oversized file")
    return audit_bytes(filename.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deb", type=Path, help="Local .deb file to inspect without installation")
    args = parser.parse_args()
    print(json.dumps(audit_file(args.deb), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
