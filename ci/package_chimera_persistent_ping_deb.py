#!/usr/bin/env python3
"""Package Build61 read-only ping service as a reproducible rootful .deb.

No appinst, installation requests or remote network hosts are present.
The user must explicitly install the .deb once with their jailbreak manager.
"""
import hashlib
import io
import plistlib
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "WebReader-Chimera-Persistent-Ping-iOS12"
PLIST = ROOT / "ci/com.example.webreader.pinglab.plist"
OUT = ROOT / "WebReader-Chimera-Persistent-PingLab-iOS12.deb"
APP_PATH = "./usr/local/libexec/webreader-pinglab"
DAEMON_PATH = "./Library/LaunchDaemons/com.example.webreader.pinglab.plist"
PKG = "com.example.webreader.pinglab"
LABEL = "com.example.webreader.pinglab"

CONTROL = """Package: com.example.webreader.pinglab
Name: WebReader Persistent Ping QA
Version: 0.1.0
Architecture: iphoneos-arm
Section: Development
Priority: optional
Maintainer: Personal WebReader QA
Description: iOS12 non-root persistent PING-only diagnostic service. No appinst.
"""

POSTINST = """#!/bin/sh
set -eu
if [ "$1" = "configure" ]; then
    /bin/launchctl unload /Library/LaunchDaemons/com.example.webreader.pinglab.plist 2>/dev/null || true
    /bin/launchctl load -w /Library/LaunchDaemons/com.example.webreader.pinglab.plist
fi
exit 0
"""
PRERM = """#!/bin/sh
set -eu
if [ "$1" = "remove" ] || [ "$1" = "upgrade" ]; then
    /bin/launchctl unload /Library/LaunchDaemons/com.example.webreader.pinglab.plist 2>/dev/null || true
fi
exit 0
"""


def pack_tar(items):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz", format=tarfile.GNU_FORMAT,
                      compresslevel=9) as tar:
        for name, content, mode in items:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = mode
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            info.uname = "root"
            info.gname = "wheel"
            tar.addfile(info, io.BytesIO(content))
    return data.getvalue()


def ar_member(name, payload):
    assert len(name) <= 15
    encoded = (name + "/").ljust(16) + str(0).ljust(12) + \
        str(0).ljust(6) + str(0).ljust(6) + str(0o100644).ljust(8) + \
        str(len(payload)).ljust(10) + "\x60\n"
    return encoded.encode("ascii") + payload + (b"\n" if len(payload) & 1 else b"")


def main():
    assert not OUT.exists(), "refusing to overwrite an existing package"
    binary = BIN.read_bytes()
    assert binary[:4] == b"\xcf\xfa\xed\xfe", "not thin ARM64 Mach-O"
    assert b"/usr/bin/appinst" not in binary
    assert b"WRPING1\n" in binary and b"WRPONG1\n" in binary
    launch = plistlib.loads(PLIST.read_bytes())
    assert launch["Label"] == LABEL
    assert launch["ProgramArguments"] == [
        "/usr/local/libexec/webreader-pinglab", "serve"
    ]
    assert launch["UserName"] == "mobile"
    assert launch["RunAtLoad"] and launch["KeepAlive"]
    assert "RootDirectory" not in launch
    assert "Sockets" not in launch
    control = pack_tar([
        ("./control", CONTROL.encode(), 0o644),
        ("./postinst", POSTINST.encode(), 0o755),
        ("./prerm", PRERM.encode(), 0o755)
    ])
    data = pack_tar([
        (APP_PATH, binary, 0o755),
        (DAEMON_PATH, PLIST.read_bytes(), 0o644)
    ])
    archive = b"!<arch>\n" + ar_member("debian-binary", b"2.0\n") + \
        ar_member("control.tar.gz", control) + ar_member("data.tar.gz", data)
    OUT.write_bytes(archive)
    sha = hashlib.sha256(archive).hexdigest()
    (ROOT / (OUT.name + ".sha256")).write_text(
        sha + "  " + OUT.name + "\n"
    )
    print(f"Built opt-in read-only Chimera PING lab: {OUT.name}")
    print("No WebReader .app, appinst, installer or root daemon executable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
