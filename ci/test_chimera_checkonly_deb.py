#!/usr/bin/env python3
"""Audit isolated CX iOS12 rootful DEB, without installing or launchctl.

This test uses the known Build61 FIX1 ar/tar parser and empty-root
extraction simulation, protecting against the previous Chimera dpkg
missing-parent-directory issue.
"""
import hashlib
from pathlib import Path
import plistlib
import subprocess

from test_chimera_persistent_ping_deb import ar_entries, tar_items

ROOT = Path(__file__).resolve().parent.parent
DEB = ROOT / "WebReader-Chimera-CheckOnly-CX-iOS12-QA.deb"
SHA = ROOT / (DEB.name + ".sha256")
BIN = ROOT / "WebReader-Chimera-CheckOnly-CX-iOS12"
PLIST = ROOT / "ci/com.example.webreader.checkonlylab.plist"
EXE_PATH = "./usr/local/libexec/webreader-checkonly"
LAUNCH_PATH = "./Library/LaunchDaemons/com.example.webreader.checkonlylab.plist"
DIRECTORIES = (
    "./usr/", "./usr/local/", "./usr/local/libexec/",
    "./Library/", "./Library/LaunchDaemons/",
)
ENTITLEMENTS = {"com.apple.private.security.no-container": True}


def run():
    archive = DEB.read_bytes()
    assert len(archive) < 1024 * 1024
    assert SHA.read_text(encoding="ascii").strip() == (
        hashlib.sha256(archive).hexdigest() + "  " + DEB.name
    )
    members = ar_entries(archive)
    control = tar_items(members["control.tar.gz"])
    data = tar_items(members["data.tar.gz"], DIRECTORIES)
    assert set(control) == {"./control", "./postinst", "./prerm"}
    assert set(data) == {EXE_PATH, LAUNCH_PATH}
    assert data[EXE_PATH] == (BIN.read_bytes(), 0o755, 0, 0)
    assert data[LAUNCH_PATH] == (PLIST.read_bytes(), 0o644, 0, 0)
    assert all(owner == 0 and group == 0
               for _, _, owner, group in list(data.values()) + list(control.values()))
    metadata = control["./control"][0].decode("utf-8")
    for expected in (
        "Package: com.example.webreader.checkonlylab",
        "Version: 0.1.0",
        "Architecture: iphoneos-arm",
    ):
        assert expected in metadata, expected

    launch = plistlib.loads(data[LAUNCH_PATH][0])
    assert launch == {
        "Label": "com.example.webreader.checkonlylab",
        "ProgramArguments": ["/usr/local/libexec/webreader-checkonly", "serve"],
        "UserName": "mobile",
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
    }
    assert "com.example.webreader.pinglab" not in metadata
    assert "com.example.webreader.pinglab" not in str(launch)

    postinst = control["./postinst"][0].decode()
    prerm = control["./prerm"][0].decode()
    assert control["./postinst"][1] == 0o755
    assert control["./prerm"][1] == 0o755
    assert "launchctl load -w" in postinst
    assert "launchctl unload" in prerm
    for script in (postinst, prerm):
        assert "com.example.webreader.checkonlylab.plist" in script
        for forbidden in ("appinst", "chmod", "curl ", "wget ", "su ", "WRINST1",
                          "rm -", "WebReader.app", "webreader-pinglab"):
            assert forbidden not in script, forbidden

    binary = data[EXE_PATH][0]
    assert b"WRCHK2\n" in binary
    for text in (b"WRNOTE2\n", b"WRRATE2\n", b"WRDENY2\n",
                 b"WR_CX_PROBE=NOTE_ONLY_NO_RELEASE_CHECK_NO_INSTALL"):
        assert text in binary, text
    for forbidden in (b"WRINST1\n", b"/usr/bin/appinst", b"/bin/sh",
                      b"installApplication:", b"com.example.webreader.pinglab"):
        assert forbidden not in binary, forbidden
    signature = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(BIN)],
        capture_output=True
    )
    assert signature.returncode == 0, signature.stderr
    assert plistlib.loads(signature.stdout) == ENTITLEMENTS
    result = subprocess.run(
        ["codesign", "--verify", "--verbose", str(BIN)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    undefined = subprocess.run(
        ["xcrun", "nm", "-u", str(BIN)],
        capture_output=True, text=True, check=True
    ).stdout
    for sym in ("_posix_spawn", "_fork", "_execve", "_system", "_popen",
                "_objc_msgSend", "_dlopen", "_chmod", "_chown", "_unlink"):
        assert sym not in undefined, sym
    print("PASS CX: isolated signed mobile check-only service, no install")
    print("PASS CX: archive parent directories, data paths and signing verified")
    print("PASS CX: original Build61 ping daemon not referenced/replaced")
    print("PASS CX: fixed local probe mode, never invokes AppInst")


if __name__ == "__main__":
    run()
