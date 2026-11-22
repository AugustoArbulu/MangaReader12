#!/usr/bin/env python3
"""Build69 BA: audit an ISOLATED, unsigned Xcode .app preview (no IPA).

An application bundle built with command-line CURRENT_PROJECT_VERSION=69 is
NOT an installable IPA, not ad-hoc signed, not a trusted publisher, and not
proof of preservation on an actual iOS device. This program only reads local
bundle metadata and thin ARM64 Mach-O load commands; no signing, packing,
network access, installation, or writes. Expects iOS 12.0 compatibility.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import struct

from build69_az_candidate_readiness import (
    CandidateConfigurationRejected, inspect_future_candidate_source
)

ROOT = Path(__file__).resolve().parent.parent.resolve()
BUNDLE_ID = "com.example.MangaReader12"
BUNDLE_NAME = "WebReader"
EXECUTABLE = "MangaReader12"
EXPECTED_BUILD = 69
MACHO_MAGIC_64_LE = b"\xcf\xfa\xed\xfe"
CPU_TYPE_ARM64 = 0x0100000C
MH_EXECUTE = 2
LC_BUILD_VERSION = 0x32
LC_VERSION_MIN_IPHONEOS = 0x25
PLATFORM_IOS = 2


class UnsignedCandidateRejected(ValueError):
    pass


def _bounded_regular_file(path: Path, *, max_bytes: int) -> bytes:
    if path.is_symlink():
        raise UnsignedCandidateRejected("symbolic links are not allowed")
    try:
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= max_bytes:
            raise UnsignedCandidateRejected("invalid or oversized candidate file")
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            data = stream.read(max_bytes + 1)
            after = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ) or len(data) != before.st_size:
            raise UnsignedCandidateRejected("candidate file changed during inspection")
        return data
    except OSError as exc:
        raise UnsignedCandidateRejected("candidate file unavailable") from exc


def _macho_ios_minimum(binary_header: bytes) -> str:
    if len(binary_header) < 32 or binary_header[:4] != MACHO_MAGIC_64_LE:
        raise UnsignedCandidateRejected("expected thin little-endian 64-bit Mach-O")
    _, cputype, _subtype, filetype, ncmds, sizeofcmds, _flags, _reserved = struct.unpack_from(
        "<IiiIIIII", binary_header, 0
    )
    if cputype != CPU_TYPE_ARM64 or filetype != MH_EXECUTE:
        raise UnsignedCandidateRejected("expected iOS ARM64 executable")
    if not 0 < ncmds <= 4096 or not 8 <= sizeofcmds <= 1024 * 1024:
        raise UnsignedCandidateRejected("invalid Mach-O load command bounds")
    end = 32 + sizeofcmds
    if end > len(binary_header):
        raise UnsignedCandidateRejected("truncated Mach-O load commands")
    cursor, observed = 32, []
    for _ in range(ncmds):
        if cursor + 8 > end:
            raise UnsignedCandidateRejected("truncated Mach-O load command")
        command, cmdsize = struct.unpack_from("<II", binary_header, cursor)
        if cmdsize < 8 or cursor + cmdsize > end:
            raise UnsignedCandidateRejected("invalid Mach-O command length")
        if command == LC_BUILD_VERSION:
            if cmdsize < 24:
                raise UnsignedCandidateRejected("truncated LC_BUILD_VERSION")
            platform, minimum = struct.unpack_from("<II", binary_header, cursor + 8)
            if platform != PLATFORM_IOS:
                raise UnsignedCandidateRejected("non-iOS Mach-O platform")
            observed.append(minimum)
        elif command == LC_VERSION_MIN_IPHONEOS:
            if cmdsize < 16:
                raise UnsignedCandidateRejected("truncated LC_VERSION_MIN_IPHONEOS")
            observed.append(struct.unpack_from("<I", binary_header, cursor + 8)[0])
        cursor += cmdsize
    if cursor != end or len(observed) != 1:
        raise UnsignedCandidateRejected("missing/ambiguous iOS deployment load command")
    encoded = observed[0]
    minimum = (encoded >> 16, (encoded >> 8) & 0xff, encoded & 0xff)
    if minimum != (12, 0, 0):
        raise UnsignedCandidateRejected("candidate binary must target iOS 12.0")
    return "12.0"


def inspect_unsigned_candidate(app_directory: Path, *, source_root: Path = ROOT) -> dict:
    """Read a local candidate; never claim signing or install compatibility."""
    app = Path(app_directory)
    if app.name != "MangaReader12.app" or app.is_symlink() or not app.is_dir():
        raise UnsignedCandidateRejected("expected real MangaReader12.app directory")
    try:
        source_status = inspect_future_candidate_source(source_root)
    except (CandidateConfigurationRejected, OSError) as exc:
        raise UnsignedCandidateRejected("source safety invariants changed") from exc
    if (source_status["sourceBuildVersion"] != 56
            or source_status["targetVersionMatched"]
            or source_status["signedProductionTrustProvisioned"]
            or source_status["chimeraLiveInstallationEnabled"]):
        raise UnsignedCandidateRejected("preview no longer isolated from baseline project")

    info_bytes = _bounded_regular_file(app / "Info.plist", max_bytes=1024 * 1024)
    try:
        info = plistlib.loads(info_bytes)
    except (ValueError, TypeError, OverflowError) as exc:
        raise UnsignedCandidateRejected("invalid app Info.plist") from exc
    if not isinstance(info, dict):
        raise UnsignedCandidateRejected("invalid app plist root")
    expected = {
        "CFBundleVersion": str(EXPECTED_BUILD),
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": EXECUTABLE,
        "CFBundleDisplayName": BUNDLE_NAME,
        "CFBundleName": BUNDLE_NAME,
        "MinimumOSVersion": "12.0",
    }
    for key, val in expected.items():
        if info.get(key) != val:
            raise UnsignedCandidateRejected("app metadata mismatch: " + key)
    if info.get("CFBundlePackageType") != "APPL":
        raise UnsignedCandidateRejected("app is not an application bundle")
    icons = info.get("CFBundleIcons")
    primary_icon = icons.get("CFBundlePrimaryIcon") if isinstance(icons, dict) else None
    if not isinstance(primary_icon, dict) or primary_icon.get("CFBundleIconName") != "AppIcon":
        raise UnsignedCandidateRejected("approved application icon missing")
    _bounded_regular_file(app / "Assets.car", max_bytes=128 * 1024 * 1024)
    binary = _bounded_regular_file(app / EXECUTABLE, max_bytes=256 * 1024 * 1024)
    binary_ios_minimum = _macho_ios_minimum(binary[:1024 * 1024 + 32])

    return {
        "status": "ISOLATED_UNSIGNED_APP_PREVIEW_ONLY",
        "sourceProjectBuild": 56,
        "observedAppBuild": int(info["CFBundleVersion"]),
        "baselineInstalledBuild": 68,
        "bundleIdentifier": BUNDLE_ID,
        "executable": EXECUTABLE,
        "binaryArchitecture": "arm64",
        "binaryMinimumIOS": binary_ios_minimum,
        "binarySHA256": hashlib.sha256(binary).hexdigest(),
        "projectFilesModifiedForBuild": False,
        "productionTrustProvisioned": False,
        "chimeraInstallationEnabled": False,
        "installableIPAProduced": False,
        "appAdHocCodeSignatureVerified": False,
        "installedApplicationIdentifierVerified": False,
        "onDeviceLibraryPreserved": False,
        "onDeviceOfflineChaptersPreserved": False,
        "physicalQAPassed": False,
        "ownerDistributionApprovalRecorded": False,
        "githubReleasePublished": False,
        "mainModified": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_directory", type=Path,
                        help="already-compiled isolated unsigned .app bundle")
    arguments = parser.parse_args()
    print(json.dumps(inspect_unsigned_candidate(arguments.app_directory),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
