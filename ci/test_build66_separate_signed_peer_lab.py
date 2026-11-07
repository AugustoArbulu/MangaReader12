#!/usr/bin/env python3
"""Phase G macOS native: independent signed CLIENT vs signed SERVER.

This corrects the fork-only interpretation of earlier tests. Both client and
server are separately compiled, separately ad-hoc signed, separately launched
executables. The server accepts just one local connection, obtains the token
from that connection, and compares the kernel CDHash to a reference from the
verified CLIENT file. Tests use a deliberately different signed client.

It is not an iOS12/runtime test, publisher authentication or appinst helper.
All keys are ad-hoc and host-only. There is NO installed iOS binary here.
"""
import os
from pathlib import Path
import re
import shutil
import select
import subprocess
import sys
import tempfile

from build66_independent_peer_report import parse_independent_peer_transcript

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "ci/build66_separate_signed_peer_lab.c"
CDHASH = re.compile(r"\bCDHash=([0-9a-f]{40})\b")
READY = "READY NONROOT SINGLE_CONNECTION AUTHORIZATION=DENIED\n"


def run(*args, timeout=35):
    p = subprocess.run(
        [str(x) for x in args], capture_output=True, check=False,
        timeout=timeout, text=True
    )
    if p.returncode:
        raise AssertionError(
            f"host compiler/signature tool failed ({p.returncode}): {p.stderr[:800]}"
        )
    return p


def make_signed_variant(destination, number):
    run(
        "xcrun", "clang", "-std=c11", "-O2", "-Wall", "-Wextra",
        "-Werror", f"-DWR66_VARIANT={number}",
        SRC, "-o", destination
    )
    run("/usr/bin/codesign", "--force", "--sign", "-",
        "--timestamp=none", destination)
    run("/usr/bin/codesign", "--verify", "--verbose=2", destination)
    details = run("/usr/bin/codesign", "-d", "--verbose=4", destination)
    found = CDHASH.findall(details.stdout + details.stderr)
    if len(found) != 1:
        raise AssertionError("ambiguous or missing CodeDirectory reference")
    return found[0]


def one_connection(server_bin, client_bin, expected_hash, root, case):
    path = root / f"c{case}.sock"
    if len(str(path).encode()) >= 96:
        raise AssertionError("AF_UNIX path not short enough")
    server = subprocess.Popen(
        [str(server_bin), "serve-once", str(path), expected_hash],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        read_ready, _, _ = select.select([server.stdout], [], [], 5)
        if not read_ready:
            raise AssertionError("separate signed server never became ready")
        ready = server.stdout.readline()
        if ready != READY:
            raise AssertionError("unexpected server readiness status")
        child = subprocess.run(
            [str(client_bin), "client-once", str(path)],
            capture_output=True, text=True, timeout=6
        )
        if child.returncode != 0:
            raise AssertionError(
                f"separate client unable to complete: {child.returncode}"
            )
        if child.stdout or child.stderr:
            raise AssertionError("client disclosed unexpected output")
        tail, stderr = server.communicate(timeout=7)
        if server.returncode != 0 or stderr:
            raise AssertionError("server refused controlled connection")
        report = parse_independent_peer_transcript(
            (ready + tail).encode("ascii")
        )
        if report.installation_authorized or report.publisher_authenticated:
            raise AssertionError("test transcript improperly authorizes install")
        # The same socket is removed after one controlled request.
        if path.exists():
            raise AssertionError("server left a persistent listener")
        return report
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate(timeout=3)


def main():
    if sys.platform != "darwin":
        raise RuntimeError("macOS-only independent signed peer test")
    source = SRC.read_text("utf8")
    for required in (
        "LOCAL_PEERTOKEN", "csops_audittoken", "WR_CS_OPS_CDHASH",
        "TOKEN_MUTATION_UNSAFE", "CROSS_PID_UNSAFE",
        "MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED",
        "geteuid() == 0", "single", "FINAL_INSTALL_AUTHORIZATION=DENIED",
    ):
        if required.lower() not in source.lower():
            raise AssertionError("lab invariant missing: " + required)
    for forbidden in (
        "appinst(", "posix_spawn(", "execve(", "system(", "setuid(",
        "setgid(", "chown(", "launchctl", "WRINST1", "I-CONFIRM-INSTALL"
    ):
        if forbidden in source:
            raise AssertionError("privileged API forbidden: " + forbidden)

    with tempfile.TemporaryDirectory(prefix="wr66-phase-g-", dir="/tmp") as tmp:
        root = Path(tmp)
        server = root / "server"
        allowed = root / "client-allowed"
        foreign = root / "client-different"

        server_hash = make_signed_variant(server, 100)
        allowed_hash = make_signed_variant(allowed, 200)
        foreign_hash = make_signed_variant(foreign, 300)
        if len({server_hash, allowed_hash, foreign_hash}) != 3:
            raise AssertionError("separate signed CodeDirectories not distinct")

        # Different independently launched processes from distinct signed files.
        for idx in range(4):
            match = one_connection(
                server, allowed, allowed_hash, root, f"match{idx}"
            )
            if not match.exact_codehash_match_observed:
                raise AssertionError("correct independently signed client rejected")
            print(f"RUN#{idx + 1}: INDEPENDENT_SIGNED_CLIENT_MATCH; NO INSTALL")

        wrong_client = one_connection(
            server, foreign, allowed_hash, root, "foreign"
        )
        if wrong_client.result != "MISMATCH_REJECTED":
            raise AssertionError("different signed executable was not rejected")
        print("PASS: different signed client executable rejected")

        wrong_reference = (
            ("0" if allowed_hash[0] != "0" else "1") + allowed_hash[1:]
        )
        changed = one_connection(
            server, allowed, wrong_reference, root, "fakehash"
        )
        if changed.result != "MISMATCH_REJECTED":
            raise AssertionError("forged static hash was not rejected")
        print("PASS: forged independent CodeDirectory hash rejected")

        # A copied ad-hoc executable is expected to have the SAME
        # CodeDirectory. This must NOT be mistaken for publisher or bundle
        # identity; it is a deliberate negative security finding.
        copied = root / "client-copied-binary"
        shutil.copy2(allowed, copied)
        run("/usr/bin/codesign", "--verify", "--verbose=2", copied)
        copied_match = one_connection(
            server, copied, allowed_hash, root, "copy"
        )
        if not copied_match.exact_codehash_match_observed:
            raise AssertionError("copied signed client changed code identity")
        if copied_match.publisher_authenticated:
            raise AssertionError("ad-hoc copied code cannot prove publisher")
        print("KNOWN LIMIT: byte-for-byte copied ad-hoc client has same CDHash")

        foreign_ok = one_connection(
            server, foreign, foreign_hash, root, "foreign-own-pin"
        )
        if not foreign_ok.exact_codehash_match_observed:
            raise AssertionError("host cannot verify second independently signed client")
        print("PASS: distinct client matches only its own signed CDHash")

        wrong_server = one_connection(
            server, allowed, server_hash, root, "serverhash"
        )
        if wrong_server.result != "MISMATCH_REJECTED":
            raise AssertionError("server code hash improperly matched client")
        print("PASS: peer does not inherit server code identity")

        # Malformed expected hashes never create a listening socket.
        invalid = subprocess.run(
            [str(server), "serve-once", str(root / "invalid.sock"), "NOTHEX"],
            capture_output=True, text=True, timeout=5
        )
        if (invalid.returncode != 5
                or "REFERENCE_INVALID AUTHORIZATION=DENIED" not in invalid.stdout
                or "FINAL_INSTALL_AUTHORIZATION=DENIED" not in invalid.stdout):
            raise AssertionError("invalid-reference server did not fail closed")

        for bad_args in ([], ["install"], ["serve-once", str(root / "bad.sock")]):
            refused = subprocess.run(
                [str(server), *bad_args],
                capture_output=True, text=True, timeout=5
            )
            if refused.returncode != 2:
                raise AssertionError("unrecognized command not rejected")

        print("PASS Phase G: independently executed signed client and server")
        print("LIMIT: macOS-only, no iOS12 peer/publisher/device identity")


if __name__ == "__main__":
    main()
