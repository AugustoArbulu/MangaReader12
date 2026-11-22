#!/usr/bin/env python3
"""Package an opt-in, non-root Build63 one-shot peer capability CLI.
No daemon, launchd job, appinst, IPA, install command or post-install script.
The .deb merely deploys a diagnostic executable for an explicit local run.
"""
import hashlib
from pathlib import Path
from package_chimera_persistent_ping_deb import pack_tar, ar_member

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / "WebReader-Build63-PeerProbe-iOS12"
OUTPUT = ROOT / "WebReader-Chimera-PeerProbe63-iOS12.deb"
EXECUTABLE = "./usr/local/bin/webreader-peerprobe63"

CONTROL = """Package: com.example.webreader.peerprobe63
Name: WebReader Build63 Peer Identity Probe
Version: 0.1.0
Architecture: iphoneos-arm
Section: Development
Priority: optional
Maintainer: Personal WebReader QA
Description: Opt-in iOS12 non-root TCP and UNIX peer PID capability test. No installer.
"""


def main():
    assert not OUTPUT.exists(), "refusing overwrite"
    binary = BINARY.read_bytes()
    assert binary[:4] == b"\xcf\xfa\xed\xfe", "expected arm64 Mach-O"
    assert b"WEBREADER_BUILD63_PEER_CAPABILITY" in binary
    assert b"FINAL_INSTALL_AUTHORIZATION=DENIED" in binary
    assert b"/usr/bin/appinst" not in binary
    ctl = pack_tar([("./control", CONTROL.encode(), 0o644)])
    data = pack_tar([
        ("./usr/", None, 0o755),
        ("./usr/local/", None, 0o755),
        ("./usr/local/bin/", None, 0o755),
        (EXECUTABLE, binary, 0o755),
    ])
    archive = (b"!<arch>\n" +
               ar_member("debian-binary", b"2.0\n") +
               ar_member("control.tar.gz", ctl) +
               ar_member("data.tar.gz", data))
    OUTPUT.write_bytes(archive)
    sha = hashlib.sha256(archive).hexdigest()
    (ROOT / (OUTPUT.name + ".sha256")).write_text(
        sha + "  " + OUTPUT.name + "\n"
    )
    print("Build63 peer probe .deb created: non-root and one-shot")
    print("No postinst, launchd, persistent listener or installer capability")
    print("SHA256: " + sha)


if __name__ == "__main__":
    main()
