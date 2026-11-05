#!/usr/bin/env python3
"""Verify the two distinct disposable iOS12 IPA bundles, without running them."""
from pathlib import Path
import hashlib
import plistlib
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "WebReader-Appinst-Disposable-v"
BIN = "Payload/WRDisposable.app/WRDisposable"
INFO = "Payload/WRDisposable.app/Info.plist"
BUNDLE = "com.example.WebReaderAppinstDisposableTest"


def verify(version: int):
    name = f"{PREFIX}{version}-iOS12-unsigned.ipa"
    path = ROOT / name
    checksum = ROOT / (name + ".sha256")
    assert path.is_file() and path.stat().st_size < 2 * 1024 * 1024
    assert checksum.is_file()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert checksum.read_text().strip() == f"{digest}  {name}"
    with zipfile.ZipFile(path) as archive:
        entries = archive.namelist()
        assert len(entries) == len(set(entries))
        assert BIN in entries and INFO in entries
        assert len(entries) <= 8
        assert not any(".." in x.split("/") for x in entries)
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
        return hashlib.sha256(executable).hexdigest(), info, digest


def main():
    old, old_info, old_sha = verify(1)
    new, new_info, new_sha = verify(2)
    assert old == new, "Updating must preserve the same app executable"
    assert old_info["CFBundleIdentifier"] == new_info["CFBundleIdentifier"]
    assert old_info["CFBundleVersion"] != new_info["CFBundleVersion"]
    assert old_sha != new_sha
    assert "webreader-appinst-disposable-data" in (
        ROOT / "ci/appinst_disposable/main.m"
    ).read_text()
    print("PASS: two distinct iOS12 disposable IPAs; same separate Bundle ID")
    print("PASS: no WebReader executable or production bundle ID")
    print("PASS: v1->v2 can verify UserDefaults persistence on device")
    return 0


if __name__ == "__main__":
    sys.exit(main())
