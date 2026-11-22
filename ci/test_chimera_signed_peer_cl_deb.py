#!/usr/bin/env python3
"""Read-only macOS verification of Phase CL's optional CLI-only iOS12 DEB.

Inspects real signed ARM64 Mach-O payloads; never uses dpkg, installs a
package, launches a service, contacts a device, or executes appinst.
"""
import hashlib
from pathlib import Path
import plistlib
import re
import struct
import subprocess

from package_chimera_signed_peer_cl import (
    ROOT, OUT, CHECKSUM, NAMES, INSTALL, RUNNER
)
from test_chimera_persistent_ping_deb import ar_entries, tar_items

HEX40 = re.compile(r"\bCDHash=([0-9a-f]{40})\b")
ENTITLEMENTS = {"com.apple.private.security.no-container": True}
DIRS = ("./usr/", "./usr/local/", "./usr/local/bin/")


def run(*args):
    result = subprocess.run([str(x) for x in args],
                            capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise AssertionError(
            f"native signature audit failed for {args[0]}: {result.stderr[:600]}"
        )
    return result


def codehash(file):
    info = run("codesign", "-d", "--verbose=4", file)
    match = HEX40.findall(info.stdout + info.stderr)
    if len(match) != 1:
        raise AssertionError("missing or ambiguous signed CodeDirectory reference")
    return match[0]


def main():
    raw = OUT.read_bytes()
    assert 4000 < len(raw) < 1_000_000, "unexpected archive bounds"
    assert CHECKSUM.read_text("ascii").strip() == (
        hashlib.sha256(raw).hexdigest() + "  " + OUT.name
    )
    records = ar_entries(raw)
    controls = tar_items(records["control.tar.gz"])
    files = tar_items(records["data.tar.gz"], DIRS)
    assert set(controls) == {"./control"}, "no maintainer scripts or auto startup"
    assert set(files) == set(INSTALL.values()) | {RUNNER}, files.keys()
    assert b"Package: com.example.webreader.peercl\n" in controls["./control"][0]
    assert b"Architecture: iphoneos-arm\n" in controls["./control"][0]
    assert b"postinst" not in controls["./control"][0].lower()
    for kind, name in NAMES.items():
        actual = files[INSTALL[kind]]
        binary = (ROOT / name).read_bytes()
        assert actual[0] == binary, "package did not preserve code signed bytes"
        assert actual[1] == 0o755
        assert binary[:4] == b"\xcf\xfa\xed\xfe"
        assert struct.unpack_from("<I", binary, 4)[0] == 0x0100000C
        for forbidden in (
            b"/usr/bin/appinst", b"WRINST1", b"I-CONFIRM-INSTALL",
            b"launchctl", b"/var/mobile/Documents"
        ):
            assert forbidden not in binary, forbidden
        seal = run("codesign", "--verify", "--verbose=2", ROOT / name)
        ent = subprocess.run(
            ["codesign", "-d", "--entitlements", ":-", str(ROOT / name)],
            capture_output=True, timeout=25
        )
        assert ent.returncode == 0, ent.stderr
        assert plistlib.loads(ent.stdout) == ENTITLEMENTS
        symbols = run("xcrun", "nm", "-u", ROOT / name).stdout
        used = {
            line.strip().split()[-1] for line in symbols.splitlines() if line.strip()
        }
        for forbidden in ("_posix_spawn", "_execve", "_system",
                          "_popen", "_setuid", "_setgid", "_chown"):
            assert forbidden not in used, f"{kind}: {forbidden} linked"
        assert "_dlsym" in used
        otool = run("xcrun", "otool", "-l", ROOT / name).stdout
        assert "minos 12.0" in otool or "version 12.0" in otool
        assert "LC_DYLD_CHAINED_FIXUPS" not in otool

    allowed = codehash(ROOT / NAMES["allowed"])
    foreign = codehash(ROOT / NAMES["foreign"])
    server = codehash(ROOT / NAMES["server"])
    assert len({allowed, foreign, server}) == 3, "not independently signed"
    shell, mode, _, _ = files[RUNNER]
    assert mode == 0o755
    assert b"ALLOWED_PIN=" + allowed.encode() in shell
    assert b"FOREIGN_PIN=" + foreign.encode() in shell
    assert b"REFUSE_ROOT" in shell
    assert b"FINAL_INSTALL_AUTHORIZATION=DENIED" in shell
    assert b"WRINST1" not in shell and b"/usr/bin/appinst" not in shell
    assert b"run_case a " in shell and b"run_case b " in shell
    assert b"run_case c " in shell
    sh = subprocess.run(
        ["/bin/sh", "-n"], input=shell, capture_output=True, timeout=20
    )
    assert sh.returncode == 0, sh.stderr
    print("PASS CL: 3 DISTINCT independently signed iOS12 ARM64 CLI peer executables")
    print("PASS CL: all code seals, minimum iOS12, entitlement, and APK-free .deb")
    print("PASS CL: runner embeds independently extracted allowed/foreign CDHashes")
    print("PASS CL: non-root one-shot UNIX diagnostic only; NO install, IPA, launchd")
    print("SHA256: " + hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
