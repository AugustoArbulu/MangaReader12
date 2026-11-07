#!/usr/bin/env python3
"""Compile and exercise the actual Build66 Phase E Darwin CLI on macOS.

This intentionally checks ONLY audit-token socket-option availability and
optional Security.framework symbol lookup. No code signature is inspected,
no device behavior is inferred, no helper or IPA is ever installed.
"""
from pathlib import Path
import platform
import re
import subprocess
import tempfile
from build66_audit_token_capability_report import parse_audit_token_report

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ci/webreader_chimera_csops_token_probe66.c"
HEAD = "WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY: non-root, read-only"
TAIL = "FINAL_INSTALL_AUTHORIZATION=DENIED"
TOKEN = re.compile(
    r"PROBE UNIX_PEERTOKEN=(?:NONZERO|ZERO|UNAVAILABLE) AUTHORIZATION=DENIED\Z"
)
BINDING = re.compile(
    r"PROBE CSOPS_TOKEN_BINDING=(?:NOT_TESTED|SYMBOL_MISSING|"
    r"TOKEN_FIELDS_UNAVAILABLE|CALL_DENIED|MUTATION_REJECTED|"
    r"MUTATION_ACCEPTED_UNSAFE) AUTHORIZATION=DENIED\Z"
)
SYMBOL = re.compile(
    r"PROBE SECURITY_(SecCodeCreateWithAuditToken|SecCodeCopyGuestWithAttributes|"
    r"SecCodeCreateWithPID)=(PRESENT|MISSING|FRAMEWORK_UNAVAILABLE) "
    r"AUTHORIZATION=DENIED\Z"
)


def check_output(lines):
    assert len(lines) == 7, lines
    assert lines[0] == HEAD and lines[6] == TAIL, lines
    assert TOKEN.fullmatch(lines[1]), lines
    assert BINDING.fullmatch(lines[2]), lines
    observed = set()
    for line in lines[3:6]:
        match = SYMBOL.fullmatch(line)
        assert match, line
        assert match.group(1) not in observed, observed
        observed.add(match.group(1))
    assert len(observed) == 3, observed
    parsed = parse_audit_token_report(("\n".join(lines) + "\n").encode("ascii"))
    assert parsed.diagnostic_only
    assert not parsed.ios12_capability_verified
    assert not parsed.webreader_peer_authenticated
    assert not parsed.installation_authorized
    return lines[1:6]


def main():
    source = SOURCE.read_text()
    for required in (
        "WR_LOCAL_PEERTOKEN", "audit_token_t", "getsockopt(",
        "WR_CS_OPS_CDHASH", "csops_audittoken", "MUTATION_REJECTED",
        "Security.framework/Security", "dlsym(", "fork()", "mkdtemp(",
        "geteuid() == 0", "FINAL_INSTALL_AUTHORIZATION=DENIED"
    ):
        assert required in source, required
    for forbidden in (
        "appinst(", "/usr/bin/appinst", "posix_spawn(", "execve(",
        "system(", "curl ", "wget ", "launchctl", "WRINST1",
        "I-CONFIRM-INSTALL", "setuid(", "setgid(", "chown("
    ):
        assert forbidden not in source, forbidden

    if platform.system() != "Darwin":
        raise RuntimeError("requires a native macOS test runner")

    with tempfile.TemporaryDirectory(prefix="wr66-audittoken-host-") as work:
        binpath = Path(work) / "audit-probe"
        cmd = [
            "xcrun", "clang", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            str(SOURCE), "-o", str(binpath)
        ]
        compiled = subprocess.run(
            cmd, capture_output=True, text=True, timeout=90
        )
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr

        for args in ([], ["nonsense"], ["selftest", "install"]):
            denied = subprocess.run(
                [str(binpath), *args], capture_output=True, text=True,
                timeout=10
            )
            assert denied.returncode == 2, (denied.stdout, denied.stderr)
            assert "Usage:" in denied.stderr, denied.stderr

        for iteration in range(4):
            observed = subprocess.run(
                [str(binpath), "selftest"],
                capture_output=True, text=True, timeout=20
            )
            assert observed.returncode == 0, (
                observed.returncode, observed.stdout, observed.stderr
            )
            lines = observed.stdout.splitlines()
            statuses = check_output(lines)
            print(f"RUN#{iteration+1}: " + " | ".join(statuses))
        print("PASS Build66 Phase E macOS: 4 nonroot csops token-binding capability selftests")
        print("PASS: no PID/token bytes output, no authorization or installation")
        print("PASS: Security.framework symbols tested for presence ONLY")


if __name__ == "__main__":
    main()
