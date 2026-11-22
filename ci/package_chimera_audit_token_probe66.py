#!/usr/bin/env python3
"""Build66 Phase D: package an optional, nonroot, one-shot CLI observation.

A DEB is only a file container here. No postinst, root daemon, launchd,
installer helper, IPA, network client or automatic startup is bundled.
"""
import hashlib
from pathlib import Path
from package_chimera_persistent_ping_deb import pack_tar, ar_member

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / "WebReader-Build66-AuditTokenProbe-iOS12"
OUTPUT = ROOT / "WebReader-Chimera-AuditTokenProbe66-iOS12.deb"
EXECUTABLE = "./usr/local/bin/webreader-auditprobe66"

CONTROL = """Package: com.example.webreader.auditprobe66
Name: WebReader Build66 Audit Token Capability Probe
Version: 0.1.0
Architecture: iphoneos-arm
Section: Development
Priority: optional
Maintainer: Personal WebReader QA
Description: Optional iOS12 non-root audit-token capability observation. Never installs IPA.
"""


def main():
    if OUTPUT.exists() or (ROOT / (OUTPUT.name + ".sha256")).exists():
        raise RuntimeError("refusing existing artifact overwrite")
    binary = BINARY.read_bytes()
    if binary[:4] != b"\xcf\xfa\xed\xfe":
        raise RuntimeError("expected thin Apple Mach-O")
    if len(binary) < 1500 or len(binary) > 300_000:
        raise RuntimeError("unexpected probe binary size")
    for expected in (
        b"WEBREADER_BUILD66_AUDITTOKEN_CAPABILITY",
        b"FINAL_INSTALL_AUTHORIZATION=DENIED",
        b"SecCodeCreateWithAuditToken",
        b"SecCodeCopyGuestWithAttributes",
        b"UNIX_PEERTOKEN"
    ):
        if expected not in binary:
            raise RuntimeError("required read-only diagnostic marker missing")
    for forbidden in (
        b"/usr/bin/appinst", b"WRINST1", b"launchctl", b"INSTALL_REQUEST",
        b"I-CONFIRM-INSTALL", b"/var/mobile/Documents"
    ):
        if forbidden in binary:
            raise RuntimeError("installation or personal-path marker forbidden")

    archive = (
        b"!<arch>\n"
        + ar_member("debian-binary", b"2.0\n")
        + ar_member("control.tar.gz", pack_tar([
            ("./control", CONTROL.encode(), 0o644)
        ]))
        + ar_member("data.tar.gz", pack_tar([
            ("./usr/", None, 0o755),
            ("./usr/local/", None, 0o755),
            ("./usr/local/bin/", None, 0o755),
            (EXECUTABLE, binary, 0o755),
        ]))
    )
    OUTPUT.write_bytes(archive)
    digest = hashlib.sha256(archive).hexdigest()
    (ROOT / (OUTPUT.name + ".sha256")).write_text(
        digest + "  " + OUTPUT.name + "\n", encoding="ascii"
    )
    print("PASS: Build66 CLI-only audit-token .deb built")
    print("NO postinst, no persistent service, no appinst, no automatic execution")
    print("SHA256: " + digest)


if __name__ == "__main__":
    main()
