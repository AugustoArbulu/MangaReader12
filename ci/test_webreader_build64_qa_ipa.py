#!/usr/bin/env python3
"""Build64 personal updater QA IPA audit. Offline, read-only, no installation.

Invoke after package_webreader_build64_qa_ipa.sh to validate a real iOS
build, its identity, and a checksum. The test never connects to a device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import zipfile

from validate_webreader_ipa import validate_ipa, IPARejected


def audit(ipa: Path, checksum: Path):
    digest_parts = checksum.read_text("utf-8").strip().split()
    if len(digest_parts) != 2 or digest_parts[1] != ipa.name:
        raise ValueError("checksum must refer to the exact QA IPA")
    sha256 = digest_parts[0]
    expected = hashlib.sha256(ipa.read_bytes()).hexdigest()
    if sha256 != expected:
        raise ValueError("SHA256 mismatch")
    report = validate_ipa(ipa, sha256, installed_build=56,
                          installed_ios="12.5.8")
    if report["build"] != 64 or report["bundleId"] != "com.example.MangaReader12":
        raise ValueError("QA build/bundle identity mismatch")
    with zipfile.ZipFile(ipa) as archive:
        name = "Payload/MangaReader12.app/"
        plist = plistlib.loads(archive.read(name + "Info.plist"))
        if plist["CFBundleVersion"] != "64":
            raise ValueError("QA CFBundleVersion mismatch")
        if plist["MinimumOSVersion"] != "12.0":
            raise ValueError("iOS12 minimum changed")
        executable = archive.read(name + "MangaReader12")
        if len(executable) < 8 or executable[:4] != b"\xcf\xfa\xed\xfe":
            raise ValueError("not a thin arm64 Mach-O application")
        if struct.unpack_from("<I", executable, 4)[0] != 0x0100000C:
            raise ValueError("unexpected Mach-O CPU type")
    assert report["installation_performed"] is False
    assert report["signature_or_origin_verified"] is False
    return {"status": "PASS", "build": 64,
            "bundleID": report["bundleId"],
            "minimumIOS": report["minimumIOS"],
            "sha256": sha256,
            "bytes": report["bytes"],
            "installationPerformed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--sha256-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.ipa, args.sha256_file), indent=2))
    except (ValueError, OSError, KeyError, AssertionError,
            zipfile.BadZipFile, IPARejected) as e:
        parser.error("QA IPA rejected: " + str(e))
