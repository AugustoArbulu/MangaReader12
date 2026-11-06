#!/usr/bin/env python3
"""Audit the single GitHub Actions download for the Chimera bridge PING test.

The bundle is the independent IPC diagnostic app, and the external helper
is compiled without ANY installation functions. No apps are installed.
"""
import hashlib
from pathlib import Path
import plistlib
import struct
import subprocess
import zipfile

IPA = Path("WebReader-IPC-Probe-iOS12-unsigned.ipa")
HELPER = Path("WebReader-Chimera-Mobile-Ping-iOS12")
PLIST = "Payload/MangaReader12.app/Info.plist"
MACHO = "Payload/MangaReader12.app/MangaReader12"


def validate_hash(path):
    checksum = path.with_name(path.name + ".sha256")
    assert path.is_file() and checksum.is_file(), path
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert checksum.read_text().strip() == f"{digest}  {path.name}"
    return digest


def main():
    validate_hash(IPA)
    validate_hash(HELPER)
    with zipfile.ZipFile(IPA) as archive:
        paths = archive.namelist()
        assert len(paths) == len(set(paths)), "duplicate entries"
        assert PLIST in paths and MACHO in paths
        info = plistlib.loads(archive.read(PLIST))
        executable = archive.read(MACHO)
        assert info["CFBundleIdentifier"] == "com.example.MangaReader12.ipcprobe"
        assert info["CFBundleIdentifier"] != "com.example.MangaReader12"
        assert info["CFBundleDisplayName"] == "WebReader IPC Test"
        assert info["CFBundleVersion"] == "56"
        assert info["MinimumOSVersion"] == "12.0"
        assert "UIBackgroundModes" not in info
        assert executable[:4] == b"\xcf\xfa\xed\xfe"
        assert struct.unpack_from("<I", executable, 4)[0] == 0x0100000C
    helper = HELPER.read_bytes()
    assert helper[:4] == b"\xcf\xfa\xed\xfe"
    assert struct.unpack_from("<I", helper, 4)[0] == 0x0100000C
    assert b"/usr/bin/appinst" not in helper
    assert b"WEBREADER_PING_ONLY" in helper
    nm = subprocess.run(
        ["xcrun", "nm", "-u", str(HELPER)], check=True,
        capture_output=True, text=True
    )
    assert "posix_spawn" not in nm.stdout
    assert "installApplication" not in nm.stdout
    print("PASS: isolated iOS12 IPC IPA + external PING-only helper")
    print("PASS: helper has no appinst path or process launcher")
    print("PASS: matches locally generated checksums; no install performed")


if __name__ == "__main__":
    main()
