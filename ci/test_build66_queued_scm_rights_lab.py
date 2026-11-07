#!/usr/bin/env python3
"""Phase I macOS runtime experiment: two independently signed writers queue data.

A writes frame 1, hands the same connected AF_UNIX descriptor to B over
SCM_RIGHTS, then B writes frame 2. A separate server gate prevents reading
ANY application bytes until B confirms both frames have been sent. Compare
split recv(8)+recv(8) to one batched recv(16).

The only findings are NON-AUTHORITATIVE observations. No IPA/appinst/helper.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

import test_build66_separate_signed_peer_lab as signed
from build66_queued_peer_report import (
    parse_queued_report, classify_queued_reports
)
from test_build66_scm_rights_handoff_lab import ready_line, close_process

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ci/build66_scm_rights_handoff_lab.c"
RECEIVER_READY = "QUEUED_RECEIVER_READY NONROOT AUTHORIZATION=DENIED\n"


def queued_case(server_bin, a_bin, b_bin, expected_hash, root, label, mode):
    app_path = root / f"a{label}.sock"
    ctrl_path = root / f"c{label}.sock"
    gate_path = root / f"g{label}.sock"
    if max(len(str(p).encode("utf8")) for p in
           (app_path, ctrl_path, gate_path)) > 95:
        raise AssertionError("AF_UNIX path is too long")
    header = f"READY NONROOT QUEUED_{mode.upper()} AUTHORIZATION=DENIED\n"
    server = subprocess.Popen(
        [str(server_bin), f"serve-queued-{mode}", str(app_path),
         str(gate_path), expected_hash],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    receiver = None
    try:
        ready_line(server, header, "queued gated server")
        receiver = subprocess.Popen(
            [str(b_bin), "receiver-queued", str(ctrl_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        ready_line(receiver, RECEIVER_READY, "queued receiver")
        origin = subprocess.run(
            [str(a_bin), "origin-queued", str(app_path),
             str(ctrl_path), str(gate_path)],
            capture_output=True, text=True, timeout=12
        )
        if origin.returncode or origin.stderr or origin.stdout.strip() != "ORIGIN_QUEUED_TWO_FRAMES NO_INSTALL":
            raise AssertionError(f"queued origin control handshake failed: {origin.returncode}")
        receiver_out, receiver_err = receiver.communicate(timeout=10)
        if receiver.returncode or receiver_err or receiver_out.strip() != "QUEUED_RECEIVER_COMPLETED NO_INSTALL":
            raise AssertionError("separate queued writer did not complete")
        server_out, server_err = server.communicate(timeout=10)
        if server.returncode or server_err:
            raise AssertionError("gated server failed to read queued stream")
        result = parse_queued_report((header + server_out).encode("ascii"))
        if (result.mode != mode.upper() or result.installation_authorized or
            result.peer_authenticated or result.publisher_authenticated or
            result.ios12_verified):
            raise AssertionError("queued results imply unavailable authority")
        if any(path.exists() for path in (app_path, ctrl_path, gate_path)):
            raise AssertionError("temporary UNIX socket left behind")
        return result
    finally:
        close_process(server)
        if receiver is not None:
            close_process(receiver)


def main():
    if sys.platform != "darwin":
        raise RuntimeError("requires native macOS and signed separate processes")
    code = SOURCE.read_text("utf8")
    for token in (
        "SCM_RIGHTS", "LOCAL_PEERTOKEN", "csops_audittoken",
        "static int serve_queued(", "static int origin_queued(",
        "static int receiver_queued(", "MSG_WAITALL", "NO_SECOND_SAMPLE",
        "FINAL_INSTALL_AUTHORIZATION=DENIED", "geteuid() == 0"
    ):
        if token not in code:
            raise AssertionError("missing queued laboratory safety property")
    for forbidden in (
        "appinst(", "/usr/bin/appinst", "posix_spawn(", "execve(",
        "system(", "setuid(", "setgid(", "chown(", "launchctl", "WRINST1"
    ):
        if forbidden in code:
            raise AssertionError("forbidden privileged surface in lab")

    original = signed.SRC
    signed.SRC = SOURCE
    try:
        with tempfile.TemporaryDirectory(prefix="wr66q-", dir="/tmp") as temp:
            root = Path(temp)
            server = root / "server"
            client_a = root / "A"
            client_b = root / "B"
            hashes = [
                signed.make_signed_variant(server, 710),
                signed.make_signed_variant(client_a, 711),
                signed.make_signed_variant(client_b, 712),
            ]
            if len(set(hashes)) != 3:
                raise AssertionError("separate executable signatures collide")
            for mode in ("split", "batch"):
                outcomes = []
                for repeat in range(3):
                    result_a = queued_case(
                        server, client_a, client_b, hashes[1], root,
                        f"{mode[0]}a{repeat}", mode
                    )
                    result_b = queued_case(
                        server, client_a, client_b, hashes[2], root,
                        f"{mode[0]}b{repeat}", mode
                    )
                    finding = classify_queued_reports(result_a, result_b)
                    if finding.installation_authorized or finding.stream_frames_authenticated:
                        raise AssertionError("stream samples never confer authority")
                    outcomes.append(finding.category)
                    print(
                        f"RUN#{repeat+1} QUEUED_{mode.upper()} "
                        f"{finding.category} observations={','.join(finding.observations)} "
                        "AUTHORIZATION=DENIED"
                    )
                print(
                    f"SUMMARY QUEUED_{mode.upper()} "
                    f"stable={len(set(outcomes)) == 1} "
                    "NO_AUTHENTICATION_NO_INSTALL"
                )
                reverse_a = queued_case(
                    server, client_b, client_a, hashes[2], root,
                    f"{mode[0]}ra", mode
                )
                reverse_b = queued_case(
                    server, client_b, client_a, hashes[1], root,
                    f"{mode[0]}rb", mode
                )
                reverse = classify_queued_reports(reverse_a, reverse_b)
                print(
                    f"REVERSED QUEUED_{mode.upper()} {reverse.category} "
                    "NO_AUTHENTICATION_NO_INSTALL"
                )
            print("PASS Phase I: two frames queued BEFORE gated server recv")
            print("LIMIT: macOS only, stream observations never prove authorship")
    finally:
        signed.SRC = original


if __name__ == "__main__":
    main()
