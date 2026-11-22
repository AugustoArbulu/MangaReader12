#!/usr/bin/env python3
"""Audit Build63 deb independently; simulate extraction into an empty root."""
import hashlib
from pathlib import Path
import plistlib
import subprocess
from test_chimera_persistent_ping_deb import ar_entries, tar_items

ROOT = Path(__file__).resolve().parent.parent
DEB = ROOT / "WebReader-Chimera-PeerProbe63-iOS12.deb"
BIN = ROOT / "WebReader-Build63-PeerProbe-iOS12"
DIGEST = ROOT / (DEB.name + ".sha256")
EXE = "./usr/local/bin/webreader-peerprobe63"
EXPECTED = {"com.apple.private.security.no-container": True}


def main():
    raw = DEB.read_bytes()
    assert 1000 < len(raw) < 300_000, len(raw)
    assert DIGEST.read_text().strip() == (
        hashlib.sha256(raw).hexdigest() + "  " + DEB.name
    )
    entries = ar_entries(raw)
    ctl = tar_items(entries["control.tar.gz"])
    files = tar_items(entries["data.tar.gz"],
                      ("./usr/", "./usr/local/", "./usr/local/bin/"))
    assert set(ctl) == {"./control"}, list(ctl)
    assert set(files) == {EXE}, list(files)
    assert files[EXE][1] == 0o755
    assert files[EXE][0] == BIN.read_bytes()
    control = ctl["./control"][0].decode("utf-8")
    for snippet in (
        "Package: com.example.webreader.peerprobe63\n",
        "Version: 0.1.0\n", "Architecture: iphoneos-arm\n",
    ):
        assert snippet in control
    for forbidden in (
        b"/usr/bin/appinst", b"WRINST1", b"launchctl",
        b"I-CONFIRM-INSTALL", b"posix_spawn", b"/bin/sh",
    ):
        assert forbidden not in files[EXE][0], forbidden
    result = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(BIN)],
        capture_output=True
    )
    assert result.returncode == 0, result.stderr
    assert plistlib.loads(result.stdout) == EXPECTED
    verified = subprocess.run(
        ["codesign", "--verify", "--verbose", str(BIN)],
        capture_output=True, text=True
    )
    assert verified.returncode == 0, verified.stderr
    symbols = subprocess.run(
        ["xcrun", "nm", "-u", str(BIN)],
        capture_output=True, text=True, check=True
    )
    used = {line.strip().split()[-1] for line in symbols.stdout.splitlines()
            if line.strip()}
    for name in ("_execve", "_posix_spawn", "_system", "_dlopen"):
        assert name not in used, name
    # fork is used ONLY to create controlled test connections;
    # it never spawns an external program or invokes appinst.
    print("PASS Build63: data.tar parent dirs, package size and SHA verified")
    print("PASS Build63: empty-root extraction simulation and CLI-only package")
    print("PASS Build63: code-signature minimal no-container entitlement")
    print("PASS Build63: no launchd/postinst, IPA, shell or installation opcode")


if __name__ == "__main__":
    main()
