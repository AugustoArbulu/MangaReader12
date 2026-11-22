#!/usr/bin/env python3
"""Phase H+ native A -> B -> A three-message audit-token temporal experiment.

Independent signed client A connects to S. A sends the first message, transfers
its connected descriptor via SCM_RIGHTS to independent signed client B.
B sends message two. B deliberately holds the transferred descriptor OPEN
while A sends message three. The server queries LOCAL_PEERTOKEN and csops
after EACH read and BEFORE each acknowledgement, comparing code hash from
kernel against independently codesign-verified A and B binaries.

A successful observation cannot be used to authenticate iOS12 WebReader.
No helper, IPA, appinst, file publication or privileged service exists.
"""
import select
import subprocess
import sys
import tempfile
from pathlib import Path

import test_build66_separate_signed_peer_lab as signed
from build66_temporal_peer_report import (
    classify_temporal_reports, parse_temporal_peer_report,
)
from test_build66_scm_rights_handoff_lab import close_process, ready_line

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ci/build66_scm_rights_handoff_lab.c"
SERVER_READY = "READY NONROOT THREE_MESSAGES AUTHORIZATION=DENIED\n"
RECEIVER_READY = "HANDOFF_RECEIVER_READY NONROOT AUTHORIZATION=DENIED\n"


def triple_case(server_binary, origin_binary, receiver_binary,
                expected_cdhash, root, label):
    app_path = root / f"a-{label}.sock"
    ctl_path = root / f"t-{label}.sock"
    if max(len(str(app_path).encode()),len(str(ctl_path).encode())) > 95:
        raise AssertionError("UNIX diagnostic paths exceed bounds")
    server = subprocess.Popen(
        [str(server_binary), "serve-three", str(app_path), expected_cdhash],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    receiver = None
    try:
        ready_line(server, SERVER_READY, "temporal server")
        receiver = subprocess.Popen(
            [str(receiver_binary), "receiver-hold", str(ctl_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        ready_line(receiver, RECEIVER_READY, "held-descriptor receiver")
        origin = subprocess.run(
            [str(origin_binary), "origin-three", str(app_path), str(ctl_path)],
            capture_output=True, text=True, timeout=9
        )
        if origin.returncode != 0 or origin.stderr:
            raise AssertionError("three-message connector failed")
        if origin.stdout.strip() != "ORIGIN_SENT_FIRST_LAST_NO_INSTALL":
            raise AssertionError("origin did not complete first/last message")
        tail_receiver, errors_receiver = receiver.communicate(timeout=7)
        if receiver.returncode or errors_receiver:
            raise AssertionError("held-descriptor receiver refused")
        if tail_receiver.strip() != "HANDOFF_SENDER_COMPLETED NO_INSTALL":
            raise AssertionError("receiver did not send middle message")
        tail_server, errors_server = server.communicate(timeout=7)
        if server.returncode or errors_server:
            raise AssertionError("three-message server refused")
        report = parse_temporal_peer_report(
            (SERVER_READY + tail_server).encode("ascii")
        )
        if report.installation_authorized or report.publisher_authenticated:
            raise AssertionError("temporal observation cannot authorize")
        if app_path.exists() or ctl_path.exists():
            raise AssertionError("diagnostic socket leaked")
        return report
    finally:
        close_process(server)
        if receiver is not None:
            close_process(receiver)


def main():
    if sys.platform != "darwin":
        raise RuntimeError("requires native macOS kernel audit-token behavior")
    source = SOURCE.read_text("utf8")
    for required in (
        "serve_three(", "origin-three", "receiver-hold", "SCM_RIGHTS",
        "send(ctrl_fd, \"D\"", "WRHELLO1", "CS_OPS_CDHASH",
        "FINAL_INSTALL_AUTHORIZATION=DENIED"
    ):
        if required not in source:
            raise AssertionError("temporal laboratory invariant absent: " + required)
    for forbidden in (
        "appinst(", "posix_spawn(", "execve(", "system(", "setuid(",
        "setgid(", "chown(", "launchctl", "WRINST1"
    ):
        if forbidden in source:
            raise AssertionError("privilege/install API forbidden: " + forbidden)

    original_src = signed.SRC
    signed.SRC = SOURCE
    try:
        with tempfile.TemporaryDirectory(prefix="wr66-temporal-", dir="/tmp") as temp:
            folder = Path(temp)
            server = folder / "server"
            connector = folder / "A-origin"
            receiver = folder / "B-writer"
            serverhash = signed.make_signed_variant(server, 601)
            A = signed.make_signed_variant(connector, 602)
            B = signed.make_signed_variant(receiver, 603)
            if len({serverhash, A, B}) != 3:
                raise AssertionError("signed test executable identities collided")
            seen = []
            for iteration in range(3):
                observed_A = triple_case(
                    server, connector, receiver, A, folder, f"ar{iteration}"
                )
                observed_B = triple_case(
                    server, connector, receiver, B, folder, f"br{iteration}"
                )
                result = classify_temporal_reports(observed_A, observed_B)
                seen.append(result.category)
                print(
                    f"RUN#{iteration+1} A-B-A while B still holds FD: "
                    f"{result.category}; AUTHORIZATION=DENIED"
                )
            if len(set(seen)) != 1:
                raise AssertionError("temporal binding changed across repetitions")

            inverse_A = triple_case(
                server, receiver, connector, B, folder, "reverseA"
            )
            inverse_B = triple_case(
                server, receiver, connector, A, folder, "reverseB"
            )
            inverse = classify_temporal_reports(inverse_A, inverse_B)
            print("PASS reversed writer order: " + inverse.category)
            if inverse.category != seen[0]:
                raise AssertionError("changing executable roles changed binding result")

            if inverse.installation_authorized:
                raise AssertionError("temporal observation is never authority")
            print("PASS Phase H+: temporal peer-code observation across A-B-A messages")
            print("LIMIT: host macOS only; no iOS12/WebReader/publisher authentication")
    finally:
        signed.SRC = original_src


if __name__ == "__main__":
    main()
