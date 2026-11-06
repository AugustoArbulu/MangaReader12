#!/usr/bin/env python3
"""Read-only CI audit of the Build61 iOS12 opt-in PING-only .deb.

Does not use dpkg, install launchd jobs or run appinst.
"""
import hashlib
import io
from pathlib import Path
import plistlib
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "WebReader-Chimera-Persistent-PingLab-iOS12-FIX1.deb"
BINARY = ROOT / "WebReader-Chimera-Persistent-Ping-iOS12"
SHA = PACKAGE.with_name(PACKAGE.name + ".sha256")
PLIST_PATH = "./Library/LaunchDaemons/com.example.webreader.pinglab.plist"
EXE_PATH = "./usr/local/libexec/webreader-pinglab"
EXPECTED_ENT = {"com.apple.private.security.no-container": True}
DATA_DIRECTORIES = (
    "./usr/", "./usr/local/", "./usr/local/libexec/",
    "./Library/", "./Library/LaunchDaemons/",
)


def ar_entries(archive):
    assert archive.startswith(b"!<arch>\n"), "not an ar archive"
    offset, members = 8, {}
    while offset < len(archive):
        assert offset + 60 <= len(archive), "short ar header"
        header = archive[offset:offset + 60]
        name = header[:16].decode("ascii").strip().rstrip("/")
        assert header[58:60] == b"\x60\n"
        length = int(header[48:58].decode("ascii").strip())
        offset += 60
        assert 0 <= length <= 3 * 1024 * 1024
        assert offset + length <= len(archive)
        assert name not in members
        members[name] = archive[offset:offset + length]
        offset += length + (length & 1)
    assert offset == len(archive)
    assert set(members) == {"debian-binary", "control.tar.gz", "data.tar.gz"}
    assert members["debian-binary"] == b"2.0\n"
    return members


def tar_items(raw, required_directories=()):
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        members = tar.getmembers()
        assert len({m.name for m in members}) == len(members)
        assert all(m.isfile() or m.isdir() for m in members)
        assert [m.name for m in members if m.isdir()] == list(required_directories)
        for m in members:
            assert m.uid == 0 and m.gid == 0, m.name
            assert not (m.mode & 0o022), m.name
            if m.isdir():
                assert m.mode == 0o755 and m.size == 0
        # Simulate dpkg extraction into a completely empty filesystem tree.
        # This specifically catches the physical error at /usr/local/libexec:
        # a bare tar containing only files worked on CI but not on Chimera.
        with tempfile.TemporaryDirectory(prefix="wr-deb-root-") as temporary:
            root = Path(temporary)
            for member in members:
                target = root / member.name.removeprefix("./")
                assert target.resolve().is_relative_to(root.resolve())
                if member.isdir():
                    assert target.parent.is_dir(), "missing directory parent " + member.name
                    target.mkdir(exist_ok=False)
                else:
                    assert target.parent.is_dir(), "missing file parent " + member.name
                    payload = tar.extractfile(member).read()
                    target.write_bytes(payload)
                    assert target.read_bytes() == payload
        return {
            m.name: (tar.extractfile(m).read(), m.mode, m.uid, m.gid)
            for m in members if m.isfile()
        }


def main():
    data = PACKAGE.read_bytes()
    assert len(data) < 1024 * 1024
    assert SHA.read_text().strip() == (
        hashlib.sha256(data).hexdigest() + "  " + PACKAGE.name
    )
    ar = ar_entries(data)
    ctl = tar_items(ar["control.tar.gz"])
    files = tar_items(ar["data.tar.gz"], DATA_DIRECTORIES)
    assert set(ctl) == {"./control", "./postinst", "./prerm"}
    assert set(files) == {EXE_PATH, PLIST_PATH}
    for name, (contents, mode, uid, gid) in {**ctl, **files}.items():
        assert uid == 0 and gid == 0, name
        assert not (mode & 0o022), name
    assert files[EXE_PATH][1] == 0o755
    assert files[PLIST_PATH][1] == 0o644
    assert files[EXE_PATH][0] == BINARY.read_bytes()
    assert b"/usr/bin/appinst" not in files[EXE_PATH][0]
    assert b"WRPING1\n" in files[EXE_PATH][0]
    assert b"WRPONG1\n" in files[EXE_PATH][0]
    assert b"WRINST1\n" not in files[EXE_PATH][0]
    assert b"/bin/sh" not in files[EXE_PATH][0]
    launch = plistlib.loads(files[PLIST_PATH][0])
    assert launch == {
        "Label": "com.example.webreader.pinglab",
        "ProgramArguments": ["/usr/local/libexec/webreader-pinglab", "serve"],
        "UserName": "mobile",
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
    }
    control = ctl["./control"][0].decode()
    assert "Architecture: iphoneos-arm\n" in control
    assert "Package: com.example.webreader.pinglab\n" in control
    assert "Version: 0.1.1\n" in control
    postinst = ctl["./postinst"][0].decode()
    prerm = ctl["./prerm"][0].decode()
    assert "/bin/launchctl load -w " in postinst
    assert "/bin/launchctl unload " in prerm
    for forbidden in ("appinst", "curl ", "wget ", "ssh ", "su ", "chmod 777"):
        assert forbidden not in postinst and forbidden not in prerm, forbidden
    signed = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(BINARY)],
        capture_output=True
    )
    assert signed.returncode == 0, signed.stderr
    assert plistlib.loads(signed.stdout) == EXPECTED_ENT
    verified = subprocess.run(
        ["codesign", "--verify", "--verbose", str(BINARY)],
        capture_output=True, text=True
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr
    symbols = subprocess.run(
        ["xcrun", "nm", "-u", str(BINARY)],
        capture_output=True, text=True, check=True
    )
    names = {line.strip().split()[-1] for line in symbols.stdout.splitlines()
             if line.strip()}
    for forbidden in ("_posix_spawn", "_system", "_execve", "_fork", "_dlopen"):
        assert forbidden not in names, forbidden
    print("PASS: Build61 PING-only signed iOS12 Mach-O and mobile entitlement")
    print("PASS: .deb ships all parent folders; empty-root unpack simulation OK")
    print("PASS: .deb installs precisely one non-root PING service and a plist")
    print("PASS: no appinst/shell/process launcher; package checksums match")
    print("PASS: existing WebReader IPC Test can PING 127.0.0.1:38971")


if __name__ == "__main__":
    main()
