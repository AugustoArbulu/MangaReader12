#!/usr/bin/env python3
"""macOS HOST-ONLY Build66 ad-hoc code-signature compatibility audit.

A signed update manifest authenticates IPA bytes only relative to a separately
trusted release public key. An Apple 'ad hoc' code signature verifies integrity
and entitlements, NOT publisher/team provenance. Neither gate authorizes appinst.

This audit consumes ONLY the exact hash-checked IPA snapshot returned by the
signed-release verifier. It never reopens the untrusted IPA path or installs.
"""
import hashlib
import io
import os
import plistlib
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from build66_signed_release_preflight import (
    SignedReleaseRejected, verify_signed_release,
)

EXPECTED_BUNDLE = "com.example.MangaReader12"
# Recorded by Filza for the already-installed WebReader on iOS 12.5.8.
# Matching this string is NECESSARY, not SUFFICIENT, for in-place upgrade.
INSTALLED_APPLICATION_IDENTIFIER = (
    "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
)
MAX_IPA_BYTES = 512 * 1024 * 1024
MAX_ENTRIES = 20000
MAX_UNPACKED_BYTES = 1024 * 1024 * 1024
BUNDLE_PATH = "Payload/MangaReader12.app/"


class CodeSignatureRejected(ValueError):
    pass


def _safe_member_name(name):
    if (not name or name.startswith("/") or "\\" in name or "\x00" in name
            or any(p in ("", ".", "..") for p in name.rstrip("/").split("/"))
            or not (name == "Payload/" or name.startswith(BUNDLE_PATH))):
        raise CodeSignatureRejected("unsafe archive member")


def _extract_verified_snapshot(snapshot, root):
    # Do not use extractall/ditto on a caller-controlled path.
    with zipfile.ZipFile(io.BytesIO(snapshot)) as archive:
        entries = archive.infolist()
        if not entries or len(entries) > MAX_ENTRIES:
            raise CodeSignatureRejected("invalid ZIP entry count")
        total = 0
        names = set()
        for entry in entries:
            name = entry.filename
            _safe_member_name(name)
            if name in names or entry.flag_bits & 1:
                raise CodeSignatureRejected("ambiguous or encrypted ZIP member")
            names.add(name)
            mode = (entry.external_attr >> 16) & 0o170000
            if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise CodeSignatureRejected("nonregular archive member")
            if entry.file_size > 512 * 1024 * 1024:
                raise CodeSignatureRejected("oversized ZIP member")
            if entry.file_size and (
                entry.compress_size == 0 or
                entry.file_size > entry.compress_size * 10000
            ):
                raise CodeSignatureRejected("implausible compression ratio")
            total += entry.file_size
            if total > MAX_UNPACKED_BYTES:
                raise CodeSignatureRejected("oversized expanded IPA")
            if name.endswith("/") and entry.file_size:
                raise CodeSignatureRejected("directory has file data")

            target = root.joinpath(*name.rstrip("/").split("/"))
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            # 'xb' fails closed on duplicate/case-normalized collisions.
            with target.open("xb") as destination:
                with archive.open(entry, "r") as source:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
            permissions = 0o755 if (entry.external_attr >> 16) & 0o111 else 0o644
            target.chmod(permissions)


def _codesign(args):
    try:
        result = subprocess.run(
            ["/usr/bin/codesign", *args],
            capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CodeSignatureRejected("native codesign unavailable") from exc
    if result.returncode != 0:
        raise CodeSignatureRejected("code signature verification failed")
    return result.stdout


def audit_code_signature_snapshot(snapshot, expected_sha256, expected_size):
    """Read-only integrity and installed-app entitlement comparison on macOS."""
    if sys.platform != "darwin":
        raise CodeSignatureRejected("native Apple code signing requires macOS")
    if not isinstance(snapshot, bytes):
        raise CodeSignatureRejected("snapshot must be immutable bytes")
    if (not isinstance(expected_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or type(expected_size) is not int
        or not 0 < expected_size <= MAX_IPA_BYTES
        or len(snapshot) != expected_size
        or hashlib.sha256(snapshot).hexdigest() != expected_sha256):
        raise CodeSignatureRejected("signed-release bytes mismatch")

    try:
        with tempfile.TemporaryDirectory(prefix="wr66-codesign-readonly-") as tmp:
            root = Path(tmp)
            _extract_verified_snapshot(snapshot, root)
            app = root / "Payload" / "MangaReader12.app"
            if not app.is_dir():
                raise CodeSignatureRejected("missing expected application bundle")
            info = plistlib.loads((app / "Info.plist").read_bytes())
            if (not isinstance(info, dict)
                or info.get("CFBundleIdentifier") != EXPECTED_BUNDLE
                or info.get("CFBundleExecutable") != "MangaReader12"):
                raise CodeSignatureRejected("application bundle identity mismatch")
            binary = app / "MangaReader12"
            if not binary.is_file():
                raise CodeSignatureRejected("missing signed executable")
            _codesign(["--verify", "--verbose=2", str(app)])
            signed_entitlements = plistlib.loads(
                _codesign(["-d", "--entitlements", ":-", str(app)])
            )
            if signed_entitlements != {
                "application-identifier": INSTALLED_APPLICATION_IDENTIFIER
            }:
                raise CodeSignatureRejected("installed entitlement identity mismatch")
    except (OSError, ValueError, EOFError, RuntimeError,
            zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        if isinstance(exc, CodeSignatureRejected):
            raise
        raise CodeSignatureRejected("IPA extraction or identity audit failed") from exc

    return {
        "adHocSignatureIntegrityVerified": True,
        "installedApplicationIdentifierMatch": True,
        "applicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
        "publisherAuthenticatedByCodeSignature": False,
        "deviceInstallationCompatibilityProven": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def audit_signed_release_with_code_signature(
    envelope_json, pinned_public_key_pem, ipa_path,
    installed_build=65, installed_ios="12.5.8"
):
    """Combine signed bytes with native codesign on the SAME snapshot."""
    try:
        report = verify_signed_release(
            envelope_json, pinned_public_key_pem, ipa_path,
            installed_build=installed_build, installed_ios=installed_ios,
            include_snapshot=True,
        )
    except SignedReleaseRejected as exc:
        raise CodeSignatureRejected("signed release preflight rejected") from exc
    # Never return or persist the whole IPA in reports.
    snapshot = report.pop("ipa_snapshot")
    identity = audit_code_signature_snapshot(
        snapshot, report["sha256"], report["ipaSize"]
    )
    return {**report, **identity}
