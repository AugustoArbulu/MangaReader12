#!/usr/bin/env python3
"""Package opt-in, non-root, no-installer CX read-only check-only service.

Rootful iOS12 Chimera package. This file BUILDS a .deb in CI only;
it does not install anything on a device or execute launchctl.
Uses the Build61 FIX1 archive implementation that physically fixed
missing-parent-directory failures on Chimera.
"""
import hashlib
import plistlib
from pathlib import Path

from package_chimera_persistent_ping_deb import pack_tar, ar_member

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / "WebReader-Chimera-CheckOnly-CX-iOS12"
PLIST = ROOT / "ci/com.example.webreader.checkonlylab.plist"
OUT = ROOT / "WebReader-Chimera-CheckOnly-CX-iOS12-QA.deb"
PROGRAM_PATH = "./usr/local/libexec/webreader-checkonly"
LAUNCH_PATH = "./Library/LaunchDaemons/com.example.webreader.checkonlylab.plist"
PKG = "com.example.webreader.checkonlylab"
LABEL = PKG

CONTROL = """Package: com.example.webreader.checkonlylab
Name: WebReader CX Check-Only QA
Version: 0.1.0
Architecture: iphoneos-arm
Section: Development
Priority: optional
Maintainer: Personal WebReader QA
Description: iOS12 Chimera mobile read-only check-only service. No app installation.
"""

POSTINST = """#!/bin/sh
set -eu
if [ "$1" = "configure" ]; then
    /bin/launchctl unload /Library/LaunchDaemons/com.example.webreader.checkonlylab.plist 2>/dev/null || true
    /bin/launchctl load -w /Library/LaunchDaemons/com.example.webreader.checkonlylab.plist
fi
exit 0
"""

PRERM = """#!/bin/sh
set -eu
if [ "$1" = "remove" ] || [ "$1" = "upgrade" ]; then
    /bin/launchctl unload /Library/LaunchDaemons/com.example.webreader.checkonlylab.plist 2>/dev/null || true
fi
exit 0
"""


def main():
    if OUT.exists() or OUT.with_name(OUT.name + ".sha256").exists():
        raise RuntimeError("refusing to overwrite existing package or SHA")
    binary = BINARY.read_bytes()
    assert binary.startswith(b"\xcf\xfa\xed\xfe"), "not thin Mach-O ARM64"
    assert b"WRCHK2\n" in binary
    assert b"WRNOTE2\n" in binary
    assert b"WRRATE2\n" in binary
    assert b"WRDENY2\n" in binary
    for forbidden in (b"/usr/bin/appinst", b"WRINST1\n",
                      b"installApplication:", b"/bin/sh"):
        assert forbidden not in binary, forbidden
    settings = plistlib.loads(PLIST.read_bytes())
    assert settings == {
        "Label": LABEL,
        "ProgramArguments": ["/usr/local/libexec/webreader-checkonly", "serve"],
        "UserName": "mobile",
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
    }
    control = pack_tar([
        ("./control", CONTROL.encode("utf-8"), 0o644),
        ("./postinst", POSTINST.encode("utf-8"), 0o755),
        ("./prerm", PRERM.encode("utf-8"), 0o755),
    ])
    data = pack_tar([
        # Chimera dpkg may not have /usr/local/libexec; include parents.
        ("./usr/", None, 0o755),
        ("./usr/local/", None, 0o755),
        ("./usr/local/libexec/", None, 0o755),
        ("./Library/", None, 0o755),
        ("./Library/LaunchDaemons/", None, 0o755),
        (PROGRAM_PATH, binary, 0o755),
        (LAUNCH_PATH, PLIST.read_bytes(), 0o644),
    ])
    archive = (b"!<arch>\n" +
               ar_member("debian-binary", b"2.0\n") +
               ar_member("control.tar.gz", control) +
               ar_member("data.tar.gz", data))
    OUT.write_bytes(archive)
    sha = hashlib.sha256(archive).hexdigest()
    OUT.with_name(OUT.name + ".sha256").write_text(
        sha + "  " + OUT.name + "\n", encoding="ascii"
    )
    print("QA-only DEB created, not installed: " + OUT.name)
    print("No WebReader app, AppInst, IPA or installer service included")


if __name__ == "__main__":
    main()
