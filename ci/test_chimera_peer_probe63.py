#!/usr/bin/env python3
"""Build63 native macOS capability test, with no installer or persistent job."""
import hashlib
from pathlib import Path
import platform
import subprocess
import tempfile
from build66_peer_capability_report import parse_build63_peer_probe

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ci/webreader_chimera_peer_probe63.c"


def main():
    source = SOURCE.read_text()
    assert "WR_TCP_PEER_PID_PRIVATE 0x204" in source
    assert "LOCAL_PEERPID" in source
    assert "AF_INET" in source and "AF_UNIX" in source
    assert "htonl(INADDR_LOOPBACK)" in source
    assert "geteuid() == 0" in source
    assert "FINAL_INSTALL_AUTHORIZATION=DENIED" in source
    assert "AUTHORIZATION=DENIED" in source
    assert "fork()" in source
    assert "mkdtemp(" in source
    assert 'strcmp(argv[1], "selftest")' in source
    for forbidden in (
        "/usr/bin/appinst", "appinst(", "posix_spawn", "execve(",
        "system(", "dlopen(", "curl ", "wget ", "install-v2",
        "I-CONFIRM-INSTALL", "WRINST1", "launchctl",
    ):
        assert forbidden not in source, forbidden
    if platform.system() != "Darwin":
        raise RuntimeError("Build63 native peer test requires macOS")
    with tempfile.TemporaryDirectory(prefix="wrpeer63-host-") as directory:
        exe = Path(directory) / "peerprobe"
        build = subprocess.run([
            "xcrun", "clang", "-std=c11", "-O2", "-Wall", "-Wextra",
            "-Werror", str(SOURCE), "-o", str(exe)
        ], text=True, capture_output=True, timeout=60)
        assert build.returncode == 0, build.stdout + build.stderr
        no_args = subprocess.run([str(exe)], capture_output=True, text=True,
                                 timeout=7)
        assert no_args.returncode == 2
        assert "Usage:" in no_args.stderr
        for iteration in range(4):
            outcome = subprocess.run(
                [str(exe), "selftest"], capture_output=True, text=True,
                timeout=18
            )
            assert outcome.returncode == 0, (
                f"probe#{iteration} exit {outcome.returncode}\n"
                + outcome.stdout + outcome.stderr
            )
            parsed = parse_build63_peer_probe(outcome.stdout.encode("ascii"))
            assert parsed.observed_metadata_only
            assert not parsed.ios12_capability_confirmed
            assert not parsed.peer_authentication_confirmed
            assert not parsed.installation_authorized
            lines = outcome.stdout.splitlines()
            assert len(lines) == 4, lines
            assert lines[0] == "WEBREADER_BUILD63_PEER_CAPABILITY: non-root, no install"
            assert lines[1].startswith("PROBE TCP_LOOPBACK PEER_PID=")
            assert lines[2].startswith("PROBE UNIX_LOCAL PEER_PID=")
            assert lines[-1] == "FINAL_INSTALL_AUTHORIZATION=DENIED"
            for line in lines[1:3]:
                assert "AUTHORIZATION=DENIED" in line
                assert "TRANSPORT=FAILED" not in line
                assert any(v in line for v in (
                    "PEER_PID=MATCH ", "PEER_PID=UNAVAILABLE ",
                    "PEER_PID=MISMATCH "
                ))
            print(f"RUN#{iteration+1}: {lines[1]} | {lines[2]}")
    print("PASS Build63: macOS local TCP/UNIX selftests 4x")
    print("PASS Build63: no installer, code execution or persistent service")
    print("PASS Build63: PID availability never authorizes installation")


if __name__ == "__main__":
    main()
