#!/usr/bin/env python3
"""Strict Phase E csops_audittoken observational report parser.

Never interprets successful CDHASH retrieval or mutated-token rejection as
authenticating WebReader. Text is untrusted and forgeable. No codehash is exposed.
"""
from dataclasses import dataclass
import re

HEAD = "WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY: non-root, read-only"
TAIL = "FINAL_INSTALL_AUTHORIZATION=DENIED"
MAX_SIZE = 2048
SOCKET = re.compile(
    r"PROBE UNIX_PEERTOKEN=(NONZERO|ZERO|UNAVAILABLE|TRANSPORT_FAILED) "
    r"AUTHORIZATION=DENIED\Z"
)
BINDING = re.compile(
    r"PROBE CSOPS_TOKEN_BINDING=(NOT_TESTED|SYMBOL_MISSING|"
    r"TOKEN_FIELDS_UNAVAILABLE|CALL_DENIED|MUTATION_REJECTED|"
    r"MUTATION_ACCEPTED_UNSAFE|CROSS_PID_ACCEPTED_UNSAFE) AUTHORIZATION=DENIED\Z"
)
SYMBOL = re.compile(
    r"PROBE SECURITY_(SecCodeCreateWithAuditToken|SecCodeCopyGuestWithAttributes|"
    r"SecCodeCreateWithPID)=(PRESENT|MISSING|FRAMEWORK_UNAVAILABLE) "
    r"AUTHORIZATION=DENIED\Z"
)
NAMES = {
    "SecCodeCreateWithAuditToken",
    "SecCodeCopyGuestWithAttributes",
    "SecCodeCreateWithPID",
}


class CSOpsReportRejected(ValueError):
    pass


@dataclass(frozen=True)
class CSOpsReport:
    socket_observation: str
    csops_observation: str
    security_symbol_observations: tuple
    diagnostic_only: bool = True
    ios12_runtime_verified: bool = False
    publisher_authenticated: bool = False
    webreader_peer_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def parse_csops_report(blob):
    if type(blob) is not bytes or not 0 < len(blob) <= MAX_SIZE:
        raise CSOpsReportRejected("report type/size rejected")
    try:
        data = blob.decode("ascii")
    except UnicodeError as exc:
        raise CSOpsReportRejected("report encoding rejected") from exc
    if data.endswith("\n"):
        data = data[:-1]
    if "\r" in data:
        raise CSOpsReportRejected("noncanonical newline")
    rows = data.split("\n")
    if len(rows) != 7 or rows[0] != HEAD or rows[6] != TAIL:
        raise CSOpsReportRejected("unexpected report shape")
    sock = SOCKET.fullmatch(rows[1])
    csops = BINDING.fullmatch(rows[2])
    if not sock or not csops:
        raise CSOpsReportRejected("unknown socket or csops result")
    found = {}
    for row in rows[3:6]:
        m = SYMBOL.fullmatch(row)
        if not m or m.group(1) in found:
            raise CSOpsReportRejected("unknown or duplicate Security status")
        found[m.group(1)] = m.group(2)
    if set(found) != NAMES:
        raise CSOpsReportRejected("incomplete Security status")
    if sock.group(1) != "NONZERO" and csops.group(1) != "NOT_TESTED":
        raise CSOpsReportRejected("cannot test csops without nonzero audit token")
    if sock.group(1) == "NONZERO" and csops.group(1) == "NOT_TESTED":
        raise CSOpsReportRejected("missing expected csops observation")
    return CSOpsReport(
        socket_observation=sock.group(1),
        csops_observation=csops.group(1),
        security_symbol_observations=tuple(sorted(found.items())),
    )
