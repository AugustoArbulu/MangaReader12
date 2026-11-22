#!/usr/bin/env python3
"""Check ONE self-contained iOS12 test IPA does not replace WebReader.

The bundled helper must be precisely the CI-compiled read-only PING helper,
not the appinst installer bridge. Does not install or execute the IPA.
"""
import hashlib
from pathlib import Path
import plistlib
import struct
import sys
import zipfile

BASE_IPA = Path("WebReader-iOS12-unsigned.ipa")
TEST_IPA = Path("WebReader-Chimera-Test-iOS12-unsigned.ipa")
PING_BINARY = Path("WebReader-Helper-Ping-iOS12")
APP_PREFIX = "Payload/MangaReader12.app/"
HELPER = APP_PREFIX + "WebReaderEmbeddedPing"
INFO = APP_PREFIX + "Info.plist"
EXECUTABLE = APP_PREFIX + "MangaReader12"


def extract(path):
    with zipfile.ZipFile(path) as arc:
        names = arc.namelist()
        assert len(names) == len(set(names)), "duplicated entries"
        assert HELPER not in names if path == BASE_IPA else True
        assert INFO in names and EXECUTABLE in names
        return set(names), plistlib.loads(arc.read(INFO)), arc.read(EXECUTABLE), (
            arc.read(HELPER) if HELPER in names else None
        )


def test():
    stable_names, stable, stable_binary, _ = extract(BASE_IPA)
    test_names, metadata, binary, helper = extract(TEST_IPA)
    assert stable["CFBundleIdentifier"] == "com.example.MangaReader12"
    assert metadata["CFBundleIdentifier"] == "com.example.MangaReader12.chimeraoneapp"
    assert metadata["CFBundleDisplayName"] == "WebReader Chimera Test"
    assert metadata["CFBundleVersion"] == stable["CFBundleVersion"] == "56"
    assert metadata["MinimumOSVersion"] == stable["MinimumOSVersion"] == "12.0"
    assert metadata["CFBundleExecutable"] == stable["CFBundleExecutable"] == "MangaReader12"
    assert "UIBackgroundModes" not in metadata
    assert set(test_names) == set(stable_names) | {HELPER}, "unexpected extra IPA files"
    assert binary == stable_binary, "original application executable was modified"
    assert helper is not None
    assert hashlib.sha256(helper).digest() == hashlib.sha256(PING_BINARY.read_bytes()).digest()
    assert helper[:4] == b"\xcf\xfa\xed\xfe"
    assert struct.unpack_from("<I", helper, 4)[0] == 0x0100000C
    sha = hashlib.sha256(TEST_IPA.read_bytes()).hexdigest()
    expected = TEST_IPA.with_name(TEST_IPA.name + ".sha256").read_text().strip()
    assert expected == sha + "  " + TEST_IPA.name
    source = Path("ci/webreader_helper_probe.c").read_text()
    for forbidden in ("appinst", "install-confirmed", "posix_spawn", "system("):
        assert forbidden not in source, "embedded helper source cannot install"
    print("PASS: one-IPA Chimera test is separate, iOS12 ARM64, non-installer only")
    print("PASS: primary WebReader executable unchanged; helper byte-identical to CI PING")


if __name__ == "__main__":
    test()
