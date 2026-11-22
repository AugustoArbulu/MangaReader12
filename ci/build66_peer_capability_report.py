#!/usr/bin/env python3
"""Strict read-only Build63 CLI peer capability report parser (host-only).

Parses only four non-sensitive status lines. Never interprets PID MATCH as
WebReader authentication, never trusts user-supplied output for authorization.
iOS12/Chimera support is not established by macOS probe observations.
"""
from dataclasses import dataclass
import re

HEADER = "WEBREADER_BUILD63_PEER_CAPABILITY: non-root, no install"
FOOTER = "FINAL_INSTALL_AUTHORIZATION=DENIED"
REPORT_LIMIT = 1024
LINE = re.compile(
    r"PROBE (TCP_LOOPBACK|UNIX_LOCAL) "
    r"(?:PEER_PID=(MATCH|MISMATCH|UNAVAILABLE)|TRANSPORT=(FAILED_[0-9]{1,2})) "
    r"AUTHORIZATION=DENIED\Z"
)


@dataclass(frozen=True)
class PeerProbeReport:
    tcp_status: str
    unix_status: str
    observed_metadata_only: bool = True
    ios12_capability_confirmed: bool = False
    peer_authentication_confirmed: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


class PeerProbeReportRejected(ValueError):
    pass


def parse_build63_peer_probe(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= REPORT_LIMIT:
        raise PeerProbeReportRejected("invalid diagnostic report bounds")
    try:
        body = raw.decode("ascii")
    except UnicodeError as exc:
        raise PeerProbeReportRejected("invalid diagnostic report encoding") from exc
    lines = body.splitlines()
    if len(lines) != 4 or lines[0] != HEADER or lines[3] != FOOTER:
        raise PeerProbeReportRejected("unexpected diagnostic report shape")
    results = {}
    for line in lines[1:3]:
        match = LINE.fullmatch(line)
        if match is None:
            raise PeerProbeReportRejected("unknown or untrusted probe result")
        transport = match.group(1)
        if transport in results:
            raise PeerProbeReportRejected("duplicate transport report")
        results[transport] = match.group(2) or match.group(3)
    if set(results) != {"TCP_LOOPBACK", "UNIX_LOCAL"}:
        raise PeerProbeReportRejected("missing diagnostic transport")
    return PeerProbeReport(
        tcp_status=results["TCP_LOOPBACK"],
        unix_status=results["UNIX_LOCAL"],
    )
