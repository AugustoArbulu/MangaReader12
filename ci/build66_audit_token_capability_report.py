#!/usr/bin/env python3
"""Strictly parse non-sensitive Build66 Phase-D audit-token capability report.

Every successful parse is observational ONLY: no PID/user identity, audit token
bytes, executable publisher, authenticated WebReader or installer permission.
Text can be forged; no caller may treat this parser as an authenticator.
"""
from dataclasses import dataclass
import re

HEADER = "WEBREADER_BUILD66_AUDITTOKEN_CAPABILITY: non-root, read-only"
FOOTER = "FINAL_INSTALL_AUTHORIZATION=DENIED"
MAX_BYTES = 1536
TOKEN = re.compile(
    r"PROBE UNIX_PEERTOKEN=(NONZERO|ZERO|UNAVAILABLE|TRANSPORT_FAILED) "
    r"AUTHORIZATION=DENIED\Z"
)
SYMBOL = re.compile(
    r"PROBE SECURITY_(SecCodeCreateWithAuditToken|"
    r"SecCodeCopyGuestWithAttributes|SecCodeCreateWithPID)="
    r"(PRESENT|MISSING|FRAMEWORK_UNAVAILABLE) AUTHORIZATION=DENIED\Z"
)
NAMES = frozenset({
    "SecCodeCreateWithAuditToken",
    "SecCodeCopyGuestWithAttributes",
    "SecCodeCreateWithPID"
})


class AuditTokenReportRejected(ValueError):
    pass


@dataclass(frozen=True)
class AuditTokenCapabilityReport:
    token_socket_observation: str
    security_symbol_observations: tuple
    diagnostic_only: bool = True
    ios12_capability_verified: bool = False
    token_bound_to_verified_code: bool = False
    webreader_peer_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def parse_audit_token_report(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise AuditTokenReportRejected("invalid report type/length")
    try:
        text = raw.decode("ascii")
    except UnicodeError as exc:
        raise AuditTokenReportRejected("invalid report encoding") from exc
    # Permit exactly one optional trailing LF; do not permit blank trailing
    # lines or arbitrary whitespace that could hide other status claims.
    if text.endswith("\n"):
        text = text[:-1]
    if "\r" in text:
        raise AuditTokenReportRejected("noncanonical line ending")
    lines = text.split("\n")
    if len(lines) != 6 or lines[0] != HEADER or lines[5] != FOOTER:
        raise AuditTokenReportRejected("invalid report structure")
    token = TOKEN.fullmatch(lines[1])
    if not token:
        raise AuditTokenReportRejected("invalid token availability status")
    seen = {}
    for line in lines[2:5]:
        match = SYMBOL.fullmatch(line)
        if not match or match.group(1) in seen:
            raise AuditTokenReportRejected("invalid/duplicated symbol observation")
        seen[match.group(1)] = match.group(2)
    if set(seen) != NAMES:
        raise AuditTokenReportRejected("missing diagnostic symbol")
    return AuditTokenCapabilityReport(
        token_socket_observation=token.group(1),
        security_symbol_observations=tuple(sorted(seen.items()))
    )
