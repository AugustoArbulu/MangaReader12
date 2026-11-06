#!/usr/bin/env python3
"""Verify the two distinct disposable iOS12 IPA bundles, without running them."""
from pathlib import Path
import hashlib
import plistlib
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "WebReader-Appinst-Disposable-v"
BIN = "Payload/WRDisposable.app/WRDisposable"
INFO = "Payload/WRDisposable.app/Info.plist"
BUNDLE = "com.example.WebReaderAppinstDisposableTest"
SIGNED_APP_ID = "WRQA000001." + BUNDLE
CODESIGN_RESOURCE = "Payload/WRDisposable.app/_CodeSignature/CodeResources"


def executable_code_digest(data: bytes) -> str:
    """Mach-O __TEXT,__text only: versioned Info.plist changes signature bytes."""
    assert data[:4] == b"\xcf\xfa\xed\xfe"
    ncmds = struct.unpack_from("<I", data, 16)[0]
    offset = 32  # mach_header_64
    for _ in range(ncmds):
        command, length = struct.unpack_from("<II", data, offset)
        assert length >= 8 and offset + length <= len(data)
        if command == 0x19:  # LC_SEGMENT_64
            nsects = struct.unpack_from("<I", data, offset + 64)[0]
            for index in range(nsects):
                section = offset + 72 + index * 80
                assert section + 80 <= offset + length
                name = data[section:section + 16].split(b"\0", 1)[0]
                segment = data[section + 16:section + 32].split(b"\0", 1)[0]
                if name == b"__text" and segment == b"__TEXT":
                    size = struct.unpack_from("<Q", data, section + 40)[0]
                    start = struct.unpack_from("<I", data, section + 48)[0]
                    assert 0 < size < len(data) and start + size <= len(data)
                    return hashlib.sha256(data[start:start + size]).hexdigest()
        offset += length
    raise AssertionError("Mach-O missing __TEXT,__text")



def verify(version: int):
    name = f"{PREFIX}{version}-iOS12-adhoc.ipa"
    path = ROOT / name
    checksum = ROOT / (name + ".sha256")
    assert path.is_file() and path.stat().st_size < 2 * 1024 * 1024
    assert checksum.is_file()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert checksum.read_text().strip() == f"{digest}  {name}"
    with zipfile.ZipFile(path) as archive:
        entries = archive.namelist()
        assert len(entries) == len(set(entries))
        assert BIN in entries and INFO in entries and CODESIGN_RESOURCE in entries
        assert len(entries) <= 12
        assert not any(".." in x.split("/") for x in entries)
        assert not any(x.startswith("/") or "\\" in x for x in entries)
        # Validate the exact signed .app bundle before any physical install.
        with tempfile.TemporaryDirectory(prefix="wr-adhoc-audit-") as temp:
            archive.extractall(temp)
            app = Path(temp) / "Payload/WRDisposable.app"
            verified = subprocess.run(
                ["codesign", "--verify", "--verbose", str(app)],
                capture_output=True, text=True
            )
            assert verified.returncode == 0, verified.stdout + verified.stderr
            signed = subprocess.run(
                ["codesign", "-d", "--entitlements", ":-", str(app)],
                capture_output=True
            )
            assert signed.returncode == 0, signed.stderr
            entitlements = plistlib.loads(signed.stdout)
            assert entitlements == {
                "application-identifier": SIGNED_APP_ID
            }, entitlements
            assert not (app / "embedded.mobileprovision").exists()
        info = plistlib.loads(archive.read(INFO))
        executable = archive.read(BIN)
        assert len(executable) > 1000
        assert executable[:4] == b"\xcf\xfa\xed\xfe"  # thin Mach-O ARM64
        assert int.from_bytes(executable[4:8], "little") == 0x0100000C
        assert info["CFBundleIdentifier"] == BUNDLE
        assert info["CFBundleIdentifier"] != "com.example.MangaReader12"
        assert info["CFBundleVersion"] == str(version)
        assert info["MinimumOSVersion"] == "12.0"
        assert info["CFBundleExecutable"] == "WRDisposable"
        assert info["CFBundleDisplayName"] == "WR Appinst Test"
        assert info["UIDeviceFamily"] == [1, 2]
        assert "UIBackgroundModes" not in info
        assert "UIFileSharingEnabled" not in info
        return executable_code_digest(executable), info, digest


def main():
    old, old_info, old_sha = verify(1)
    new, new_info, new_sha = verify(2)
    assert old == new, "v1/v2 must have identical executable code section"
    assert old_info["CFBundleIdentifier"] == new_info["CFBundleIdentifier"]
    assert old_info["CFBundleVersion"] != new_info["CFBundleVersion"]
    assert old_sha != new_sha
    assert "webreader-appinst-disposable-data" in (
        ROOT / "ci/appinst_disposable/main.m"
    ).read_text()
    print("PASS: two ad-hoc signed iOS12 disposable IPAs; same separate Bundle ID")
    print("PASS: both signatures contain identical application-identifier")
    print("PASS: original __TEXT,__text is identical despite signature changes")
    print("PASS: no WebReader executable or production bundle ID")
    print("PASS: v1->v2 can verify UserDefaults persistence on device")
    return 0


if __name__ == "__main__":
    sys.exit(main())
