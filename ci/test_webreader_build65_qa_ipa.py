#!/usr/bin/env python3
"""Build65 iOS12 QA archive audit: signature + exact installed application ID."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import subprocess
import tempfile
import zipfile

from validate_webreader_ipa import validate_ipa, IPARejected

INSTALLED_APP_ID = "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"

def audit(ipa: Path, checksum: Path):
    digest_parts = checksum.read_text("utf-8").strip().split()
    if len(digest_parts) != 2 or digest_parts[1] != ipa.name:
        raise ValueError("checksum must refer to the exact QA IPA")
    sha256 = digest_parts[0]
    if hashlib.sha256(ipa.read_bytes()).hexdigest() != sha256:
        raise ValueError("SHA256 mismatch")
    report = validate_ipa(ipa, sha256, installed_build=56,
                          installed_ios="12.5.8")
    if report["build"] != 65 or report["bundleId"] != "com.example.MangaReader12":
        raise ValueError("QA build/bundle identity mismatch")
    with zipfile.ZipFile(ipa) as archive:
        name = "Payload/MangaReader12.app/"
        plist = plistlib.loads(archive.read(name + "Info.plist"))
        if plist["CFBundleVersion"] != "65" or plist["MinimumOSVersion"] != "12.0":
            raise ValueError("QA build or minimum iOS mismatch")
        executable = archive.read(name + "MangaReader12")
        if len(executable) < 8 or executable[:4] != b"\xcf\xfa\xed\xfe":
            raise ValueError("not a thin ARM64 Mach-O executable")
        if struct.unpack_from("<I", executable, 4)[0] != 0x0100000C:
            raise ValueError("unexpected Mach-O CPU type")
    with tempfile.TemporaryDirectory(prefix="wr65-fix2-qa-") as directory:
        subprocess.run(
            ["/usr/bin/ditto", "-x", "-k", str(ipa.resolve()), directory],
            check=True, capture_output=True, text=True
        )
        app = Path(directory) / "Payload" / "MangaReader12.app"
        subprocess.run(
            ["codesign", "--verify", "--verbose=2", str(app)],
            check=True, capture_output=True, text=True
        )
        signature = subprocess.run(
            ["codesign", "-d", "--entitlements", ":-", str(app)],
            check=True, capture_output=True
        )
        signed = plistlib.loads(signature.stdout)
        if signed != {"application-identifier": INSTALLED_APP_ID}:
            raise ValueError("application-identifier differs from installed Build56")
    assert report["installation_performed"] is False
    assert report["signature_or_origin_verified"] is False
    return {"status": "PASS", "build": 65,
            "bundleID": report["bundleId"],
            "minimumIOS": report["minimumIOS"],
            "sha256": sha256,
            "bytes": report["bytes"],
            "adHocSignatureVerified": True,
            "applicationIdentifier": INSTALLED_APP_ID,
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
