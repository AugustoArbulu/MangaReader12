#!/usr/bin/env python3
"""Independently audit optional Build66 iOS12 csops token probe DEB.

No install, extraction into live filesystem, network traffic or iOS execution.
"""
import hashlib
from pathlib import Path
import plistlib
import struct
import subprocess

from test_chimera_persistent_ping_deb import ar_entries, tar_items

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "WebReader-Chimera-CSOpsTokenProbe66-iOS12.deb"
BINARY = ROOT / "WebReader-Build66-CSOpsTokenProbe-iOS12"
CHECKSUM = ROOT / (PACKAGE.name + ".sha256")
EXE = "./usr/local/bin/webreader-csopsprobe66"
EXPECTED_ENTITLEMENTS = {"com.apple.private.security.no-container": True}


def main():
    raw = PACKAGE.read_bytes()
    if not 1000 < len(raw) < 300_000:
        raise AssertionError("unexpected package bounds")
    digest = hashlib.sha256(raw).hexdigest()
    assert CHECKSUM.read_text("ascii").strip() == digest + "  " + PACKAGE.name
    sections = ar_entries(raw)
    assert set(sections) == {"debian-binary", "control.tar.gz", "data.tar.gz"}
    assert sections["debian-binary"] == b"2.0\n"
    control = tar_items(sections["control.tar.gz"])
    data = tar_items(
        sections["data.tar.gz"],
        ("./usr/", "./usr/local/", "./usr/local/bin/")
    )
    assert set(control) == {"./control"}, list(control)
    assert set(data) == {EXE}, list(data)
    assert data[EXE][1] == 0o755
    assert data[EXE][0] == BINARY.read_bytes()
    text = control["./control"][0].decode("utf8")
    for required in (
        "Package: com.example.webreader.csopsprobe66\n",
        "Architecture: iphoneos-arm\n", "Version: 0.1.0\n"
    ):
        assert required in text, required
    for forbidden in ("postinst", "prerm", "launchd", "appinst"):
        assert forbidden not in text.lower(), forbidden
    code = BINARY.read_bytes()
    assert code[:4] == b"\xcf\xfa\xed\xfe", "thin little-endian Mach-O"
    assert struct.unpack_from("<I", code, 4)[0] == 0x0100000C, "ARM64 CPU type"
    for forbidden in (
        b"/usr/bin/appinst", b"WRINST1", b"launchctl", b"I-CONFIRM-INSTALL",
        b"/var/mobile/Documents"
    ):
        assert forbidden not in code, forbidden
    signed = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(BINARY)],
        capture_output=True, timeout=20
    )
    assert signed.returncode == 0, signed.stderr
    assert plistlib.loads(signed.stdout) == EXPECTED_ENTITLEMENTS
    seal = subprocess.run(
        ["codesign", "--verify", "--verbose", str(BINARY)],
        capture_output=True, text=True, timeout=20
    )
    assert seal.returncode == 0, seal.stderr
    symbols = subprocess.run(
        ["xcrun", "nm", "-u", str(BINARY)],
        capture_output=True, text=True, check=True, timeout=20
    )
    used = {
        line.strip().split()[-1] for line in symbols.stdout.splitlines()
        if line.strip()
    }
    for forbidden in ("_execve", "_posix_spawn", "_system", "_popen",
                      "_setuid", "_setgid", "_chown"):
        assert forbidden not in used, forbidden
    assert "_dlsym" in used, "symbol presence only: expected dlsym"
    loads = subprocess.run(
        ["xcrun", "otool", "-l", str(BINARY)],
        capture_output=True, text=True, check=True, timeout=20
    )
    assert "minos 12.0" in loads.stdout or "version 12.0" in loads.stdout
    assert "LC_DYLD_CHAINED_FIXUPS" not in loads.stdout
    print("PASS: Build66 csops token diagnostic IPA-free DEB verified")
    print("PASS: ARM64 / minimum iOS 12, ad-hoc seal, minimal entitlement")
    print("PASS: package has only CLI and explicit parent directories")
    print("PASS: no postinstall script, no daemon, no installer or executable spawn")
    print("SHA256: " + digest)


if __name__ == "__main__":
    main()
