#!/usr/bin/env python3
"""Phase H: controlled macOS transfer of a CONNECTED socket via SCM_RIGHTS.

A and B are independently built and ad-hoc signed EXECUTABLES. A creates the
application connection. B runs as another executable, receives the already
connected socket descriptor through SCM_RIGHTS, then alone sends WRHELLO1.
The server interrogates LOCAL_PEERTOKEN and csops_audittoken on the application
connection. This measures whether the code identity refers to connector A or
writer B. It MUST NOT become a helper admission or appinst implementation.

No user app, iOS12 device, privileged service or real IPA is involved.
"""
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile

from build66_independent_peer_report import parse_independent_peer_transcript
from build66_fd_handoff_findings import classify_handoff_pair
from test_build66_separate_signed_peer_lab import make_signed_variant, one_connection

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ci/build66_scm_rights_handoff_lab.c"
SERVER_READY = "READY NONROOT SINGLE_CONNECTION AUTHORIZATION=DENIED\n"
RECEIVER_READY = "HANDOFF_RECEIVER_READY NONROOT AUTHORIZATION=DENIED\n"


def ready_line(process, expected, label):
    found, _, _ = select.select([process.stdout], [], [], 6)
    if not found:
        raise AssertionError(f"{label} did not become ready")
    line = process.stdout.readline()
    if line != expected:
        raise AssertionError(f"{label} returned unexpected readiness")


def close_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=2)


def handoff_case(server_binary, origin_binary, receiver_binary,
                 expected_cdhash, root, label):
    """Read-only two-process transfer. A never sends the app payload."""
    application_path = root / f"a-{label}.sock"
    transfer_path = root / f"t-{label}.sock"
    if max(len(str(application_path).encode()),
           len(str(transfer_path).encode())) > 95:
        raise AssertionError("UNIX path too long")
    server = subprocess.Popen(
        [str(server_binary), "serve-once",
         str(application_path), expected_cdhash],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    receiver = None
    try:
        ready_line(server, SERVER_READY, "server")
        receiver = subprocess.Popen(
            [str(receiver_binary), "receiver-once", str(transfer_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        ready_line(receiver, RECEIVER_READY, "receiver")
        origin = subprocess.run(
            [str(origin_binary), "origin-pass",
             str(application_path), str(transfer_path)],
            capture_output=True, text=True, timeout=9
        )
        if origin.returncode != 0:
            raise AssertionError(
                f"connector failed to transfer: exit {origin.returncode}"
            )
        if origin.stdout.strip() != "ORIGIN_TRANSFERRED_WITHOUT_MESSAGE NO_INSTALL":
            raise AssertionError("connector made unrecognized output")
        if origin.stderr:
            raise AssertionError("unexpected connector diagnostics")

        sender_end, sender_errors = receiver.communicate(timeout=8)
        if receiver.returncode != 0 or sender_errors:
            raise AssertionError("separately signed receiver failed")
        if sender_end.strip() != "HANDOFF_SENDER_COMPLETED NO_INSTALL":
            raise AssertionError("could not verify receiver wrote app message")

        server_end, server_errors = server.communicate(timeout=8)
        if server.returncode != 0 or server_errors:
            raise AssertionError("application server failed on handoff")
        report = parse_independent_peer_transcript(
            (SERVER_READY + server_end).encode("ascii")
        )
        if (report.installation_authorized or report.publisher_authenticated
                or report.authenticated_webreader_peer):
            raise AssertionError("a transferred fd must not authorize anything")
        if application_path.exists() or transfer_path.exists():
            raise AssertionError("lingering socket after one-shot observation")
        return report
    finally:
        close_process(server)
        if receiver is not None:
            close_process(receiver)


def main():
    if sys.platform != "darwin":
        raise RuntimeError("requires native macOS for SCM_RIGHTS and audit-token")
    code = SOURCE.read_text("utf8")
    for item in (
        "SCM_RIGHTS", "CMSG_SPACE", "CMSG_FIRSTHDR", "CMSG_DATA",
        "sendmsg(", "recvmsg(", "LOCAL_PEERTOKEN", "csops_audittoken",
        "WRHELLO1", "WR66-TEST-EXECUTABLE-VARIANT-", "geteuid() == 0",
        "ORIGIN_TRANSFERRED_WITHOUT_MESSAGE", "HANDOFF_SENDER_COMPLETED",
        "FINAL_INSTALL_AUTHORIZATION=DENIED"
    ):
        if item not in code:
            raise AssertionError("handoff implementation incomplete: " + item)
    for forbidden in (
        "appinst(", "posix_spawn(", "execve(", "system(", "setuid(",
        "setgid(", "chown(", "launchctl", "WRINST1", "I-CONFIRM-INSTALL"
    ):
        if forbidden in code:
            raise AssertionError("privileged install surface introduced: " + forbidden)

    # The helper below invokes only LOCAL macOS codesign/clang with a
    # disposable ad-hoc signature and cannot publish or install code.
    import test_build66_separate_signed_peer_lab as g
    original_source = g.SRC
    g.SRC = SOURCE
    try:
        with tempfile.TemporaryDirectory(prefix="wr66-phase-h-", dir="/tmp") as temp:
            root = Path(temp)
            server_binary = root / "server"
            connector = root / "client-A-origin"
            writer = root / "client-B-writer"
            server_hash = make_signed_variant(server_binary, 401)
            connector_hash = make_signed_variant(connector, 402)
            writer_hash = make_signed_variant(writer, 403)
            if len({server_hash, connector_hash, writer_hash}) != 3:
                raise AssertionError("individual signed executable identities collided")

            direct_origin = one_connection(
                server_binary, connector, connector_hash, root, "origin-direct"
            )
            direct_writer = one_connection(
                server_binary, writer, connector_hash, root, "writer-direct"
            )
            if (direct_origin.result != "MATCH_ONLY_NO_AUTH" or
                direct_writer.result != "MISMATCH_REJECTED"):
                raise AssertionError("independent process baseline failed")
            print("PASS direct A matches pin A; direct B does not")

            results = []
            for iteration in range(3):
                a_view = handoff_case(
                    server_binary, connector, writer, connector_hash,
                    root, f"origin-{iteration}"
                )
                b_view = handoff_case(
                    server_binary, connector, writer, writer_hash,
                    root, f"sender-{iteration}"
                )
                finding = classify_handoff_pair(a_view, b_view)
                results.append(finding.category)
                print(
                    f"RUN#{iteration + 1} A-connects/B-sends: "
                    f"{finding.category}, INSTALL_AUTHORIZED=NO"
                )
            if len(set(results)) != 1:
                raise AssertionError("kernel token behavior changed between repetitions")

            # Reverse who connected and who emitted bytes; this prevents a
            # false positive due to code variant numbering or test fixture.
            reverse_origin = handoff_case(
                server_binary, writer, connector, writer_hash, root, "reverseorigin"
            )
            reverse_sender = handoff_case(
                server_binary, writer, connector, connector_hash, root, "reversesender"
            )
            reversed_finding = classify_handoff_pair(
                reverse_origin, reverse_sender
            )
            print(
                "PASS reverse B-connects/A-sends observation: "
                + reversed_finding.category
            )
            if reversed_finding.category != results[0]:
                raise AssertionError("direction-dependent kernel identity result")

            # Byte-for-byte signed copy intentionally shares the original
            # CDHash. This remains NOT publisher authentication.
            clone = root / "clone-A"
            shutil.copy2(connector, clone)
            codesign = subprocess.run(
                ["/usr/bin/codesign", "--verify", "--verbose=2", str(clone)],
                capture_output=True, timeout=15
            )
            if codesign.returncode != 0:
                raise AssertionError("copied ad-hoc seal did not verify")
            clone_finding = handoff_case(
                server_binary, clone, writer, connector_hash, root, "clone"
            )
            if clone_finding.result not in ("MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED"):
                raise AssertionError("copied-code token behavior is inconclusive")
            print("KNOWN LIMIT: identical signed clone shares origin CDHash")

            bad = subprocess.run(
                [str(server_binary), "serve-once",
                 str(root / "invalid.sock"), "INVALID"],
                capture_output=True, text=True, timeout=6
            )
            if (bad.returncode != 5 or
                "FINAL_INSTALL_AUTHORIZATION=DENIED" not in bad.stdout):
                raise AssertionError("invalid hash was not fail-closed")
            for mode in ("install", "WRINST1"):
                denied = subprocess.run(
                    [str(connector), mode], capture_output=True,
                    text=True, timeout=6
                )
                if denied.returncode != 2:
                    raise AssertionError("unauthorized operation was accepted")

            print("PASS Phase H: isolated cross-process SCM_RIGHTS observation")
            print("NO iOS12 runtime claim, peer authentication, root or installation")
    finally:
        g.SRC = original_source


if __name__ == "__main__":
    main()
