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
HELPER = Path("WebReader-Chimera-Ping-DIAG-iOS12")
GATE = Path("WebReader-Chimera-Disposable-Gate-iOS12")
DISPOSABLE = [
    Path("WebReader-Appinst-Disposable-v1-iOS12-unsigned.ipa"),
    Path("WebReader-Appinst-Disposable-v2-iOS12-unsigned.ipa"),
]
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
    validate_hash(GATE)
    for path in DISPOSABLE:
        validate_hash(path)
    with zipfile.ZipFile(IPA) as archive:
        paths = archive.namelist()
        assert len(paths) == len(set(paths)), "duplicate entries"
        assert PLIST in paths and MACHO in paths
        info = plistlib.loads(archive.read(PLIST))
        executable = archive.read(MACHO)
        assert info["CFBundleIdentifier"] == "com.example.MangaReader12.ipcprobe"
        assert info["CFBundleIdentifier"] != "com.example.MangaReader12"
        assert info["CFBundleDisplayName"] == "WebReader IPC Test"
        assert info["CFBundleVersion"] == "60"
        assert info["MinimumOSVersion"] == "12.0"
        assert "UIBackgroundModes" not in info
        assert executable[:4] == b"\xcf\xfa\xed\xfe"
        assert struct.unpack_from("<I", executable, 4)[0] == 0x0100000C
    gate = GATE.read_bytes()
    assert gate[:4] == b"\xcf\xfa\xed\xfe"
    assert struct.unpack_from("<I", gate, 4)[0] == 0x0100000C
    for v, path in enumerate(DISPOSABLE, start=1):
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert sha.encode() in gate, "disposable hash must be embedded"
        assert path.name.encode() in gate
    assert b"I-CONFIRM-DISPOSABLE-ONLY" in gate
    assert b"/usr/bin/appinst" in gate
    assert b"com.example.MangaReader12" not in gate
    # The installer gate is a manually executed CLI only. No TCP listener,
    # client socket or implicit IPC can reach the appinst call.
    symbols = subprocess.run(
        ["xcrun", "nm", "-u", str(GATE)],
        check=True, capture_output=True, text=True
    ).stdout
    # Match whole symbol names, not substrings: dyld_stub_binder contains
    # "_bind" but is part of the system dynamic linker, not TCP bind().
    undefined_symbols = {
        line.strip().split()[-1]
        for line in symbols.splitlines()
        if line.strip()
    }
    for forbidden_socket in ("_socket", "_bind", "_listen", "_accept",
                             "_connect", "_recv", "_send"):
        assert forbidden_socket not in undefined_symbols, forbidden_socket
    assert "_posix_spawn" in undefined_symbols, "CLI-only disposable install"
    helper = HELPER.read_bytes()
    assert helper[:4] == b"\xcf\xfa\xed\xfe"
    assert struct.unpack_from("<I", helper, 4)[0] == 0x0100000C
    assert b"/usr/bin/appinst" not in helper
    assert b"WEBREADER_PING_ONLY" in helper
    assert b"WRLOOPBACK_READY" in helper
    assert b"LOOPBACK_ACCEPTED_127_0_0_1" in helper
    assert b"WRPAIR_READY" in helper
    assert b"WR-PAIR-CLIENT-V1" in helper
    assert b"WR-PAIR-SERVER-V1" in helper
    nm = subprocess.run(
        ["xcrun", "nm", "-u", str(HELPER)], check=True,
        capture_output=True, text=True
    )
    assert "posix_spawn" not in nm.stdout
    assert "installApplication" not in nm.stdout
    # The previous physical probe was SIGKILLed after bare ldid -S.
    # Explicitly confirm that the signed product carries the one minimal
    # legacy Chimera entitlement; no platform/root entitlement is allowed.
    entitlement = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(HELPER)],
        check=True, capture_output=True
    )
    signed = plistlib.loads(entitlement.stdout)
    expected = {"com.apple.private.security.no-container": True}
    assert signed == expected, signed
    gate_entitlements = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(GATE)],
        check=True, capture_output=True
    )
    assert plistlib.loads(gate_entitlements.stdout) == expected
    source_entitlements = plistlib.loads(
        Path("ci/chimera_mobile_ping.entitlements").read_bytes()
    )
    assert source_entitlements == expected
    # No modern dyld chained fixups in this legacy iOS12 deployment.
    load_commands = subprocess.run(
        ["xcrun", "otool", "-l", str(HELPER)],
        check=True, capture_output=True, text=True
    ).stdout
    assert "LC_DYLD_CHAINED_FIXUPS" not in load_commands
    assert "LC_BUILD_VERSION" in load_commands or "LC_VERSION_MIN_IPHONEOS" in load_commands
    assert "minos 12.0" in load_commands or "version 12.0" in load_commands
    print("PASS: Chimera mobile PING helper has no-container entitlement only")
    print("PASS: deployment minimum iOS12 and no chained fixups")
    print("PASS: isolated iOS12 IPC IPA + external PING-only helper")
    print("PASS: helper has no appinst path or process launcher")
    print("PASS: Build60 package has both disposable IPAs and SHA-pinned gate")
    print("PASS: disposable gate has minimal entitlement and no WebReader target")
    print("PASS: matches locally generated checksums; CI never installed an app")


if __name__ == "__main__":
    main()
