#!/usr/bin/env python3
"""Phase F macOS-only signed CodeDirectory ↔ kernel csops CDHash comparison.

Compile a controlled selftest binary, apply an ephemeral ad-hoc code seal,
derive the reference independently from native codesign output, then use
csops_audittoken on a forked child of EXACTLY that same signed executable.
Run good and deliberately mismatched references without ever printing the
kernel CDHash, PID, token, private keys, IPA bytes or personal paths.

The runtime-supplied *test* reference is explicitly NOT suitable for a helper
authentication decision. This code must never ship in the iOS12 CLI binary.
"""
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ci/webreader_chimera_csops_token_probe66.c"
HASH = re.compile(r"\bCDHash=([0-9a-f]{40})\b")
STATUS = re.compile(
    r"PROBE CSOPS_TOKEN_BINDING=([A-Z_]+) AUTHORIZATION=DENIED\Z"
)
END = "FINAL_INSTALL_AUTHORIZATION=DENIED"
MAX_STDOUT = 2048


def invoke(binary, reference):
    env = os.environ.copy()
    env["WR66_HOST_EXPECTED_CDHASH"] = reference
    call = subprocess.run(
        [str(binary), "selftest"], capture_output=True, text=True,
        timeout=15, env=env,
    )
    if call.returncode != 0:
        raise AssertionError(
            f"selftest refused, exit={call.returncode}, diagnostics={call.stderr[:250]}"
        )
    lines = call.stdout.splitlines()
    if len(call.stdout) > MAX_STDOUT or len(lines) != 7 or lines[-1] != END:
        raise AssertionError("malformed or unexpectedly revealing native report")
    if lines[1] != "PROBE UNIX_PEERTOKEN=NONZERO AUTHORIZATION=DENIED":
        raise AssertionError("kernel audit-token not obtained in controlled test")
    match = STATUS.fullmatch(lines[2])
    if not match:
        raise AssertionError("unrecognized token-binding status")
    if not all(row.endswith(" AUTHORIZATION=DENIED") for row in lines[1:6]):
        raise AssertionError("authorization result not fail-closed")
    return match.group(1)


def main():
    if platform.system() != "Darwin":
        raise RuntimeError("native codesign/csops comparison needs a macOS runner")
    source = SOURCE.read_text("utf-8")
    for required in (
        "WEBREADER_HOST_CDHASH_REF", "WR66_HOST_EXPECTED_CDHASH",
        "HOST_CDHASH_MATCH", "HOST_CDHASH_MISMATCH",
        "MUTATION_REJECTED", "CROSS_PID_ACCEPTED_UNSAFE",
    ):
        if required not in source:
            raise AssertionError(f"missing host-only hook: {required}")
    with tempfile.TemporaryDirectory(prefix="wr66-phase-f-cdhash-") as workspace:
        binary = Path(workspace) / "controlled-selftest"
        subprocess.run(
            ["xcrun", "clang", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-DWEBREADER_HOST_CDHASH_REF=1", str(SOURCE), "-o", str(binary)],
            capture_output=True, check=True, timeout=60,
        )
        subprocess.run(
            ["/usr/bin/codesign", "--force", "--sign", "-",
             "--timestamp=none", str(binary)],
            capture_output=True, check=True, timeout=30,
        )
        subprocess.run(
            ["/usr/bin/codesign", "--verify", "--verbose=2", str(binary)],
            capture_output=True, check=True, timeout=20,
        )
        details = subprocess.run(
            ["/usr/bin/codesign", "-d", "--verbose=4", str(binary)],
            capture_output=True, text=True, check=True, timeout=20,
        )
        matching = HASH.search(details.stdout + details.stderr)
        if matching is None:
            raise AssertionError("unable to obtain signed CodeDirectory reference")
        approved_cdhash = matching.group(1)

        for index in range(4):
            actual = invoke(binary, approved_cdhash)
            if actual != "HOST_CDHASH_MATCH":
                raise AssertionError(
                    f"kernel and independent signed code reference disagree: {actual}"
                )
            print(f"RUN#{index + 1} HOST_CDHASH_MATCH AUTHORIZATION=DENIED")

        wrong = ("0" if approved_cdhash[0] != "0" else "1") + approved_cdhash[1:]
        if invoke(binary, wrong) != "HOST_CDHASH_MISMATCH":
            raise AssertionError("forged CodeDirectory reference accepted")
        print("PASS wrong signed CodeDirectory reference rejected")

        for invalid in ("", "not-a-cdhash", "A" * 40):
            result = invoke(binary, invalid)
            if result not in ("HOST_REFERENCE_ABSENT", "HOST_REFERENCE_INVALID",
                              "HOST_CDHASH_MISMATCH"):
                raise AssertionError(f"unrecognized invalid-reference result: {result}")
        print("PASS malformed/missing host-only reference never authorizes")
        print("PASS Phase F: kernel code hash matches verified ad-hoc signed file")
        print("LIMIT: controlled macOS child only, not WebReader/iOS12 peer identity")


if __name__ == "__main__":
    main()
