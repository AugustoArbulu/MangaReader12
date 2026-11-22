#!/usr/bin/env python3
"""Phase CL: strict parser for *untrusted* optional iOS12 peer lab reports.

The CLI output is forgeable, and client binaries are test-only ad-hoc signed.
Even the expected controlled pattern does not prove WebReader request identity,
publisher, an OS-backed credential of the app, or install authorization.
"""
from dataclasses import dataclass
import re

MAX_REPORT_BYTES = 1024
HEADER = "WEBREADER_CL_IOS12_SIGNED_PEER: NONROOT READ_ONLY"
FOOTER = "FINAL_INSTALL_AUTHORIZATION=DENIED"
STATES = frozenset({
    "MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED",
    "INCONCLUSIVE", "SOCKET_UNAVAILABLE", "CLIENT_FAILED"
})
OBSERVATION = re.compile(
    r"OBSERVATION_([abc])=([A-Z_]+) AUTHORIZATION=DENIED\Z"
)


class CLPeerReportRejected(ValueError):
    pass


@dataclass(frozen=True)
class CLPeerFinding:
    observations: tuple
    controlled_codehash_comparison_observed: bool
    interpretation: str
    report_source_untrusted: bool = True
    webreader_process_authenticated: bool = False
    ios12_kernel_authority_established: bool = False
    publisher_authenticated: bool = False
    install_authorized: bool = False
    installation_performed: bool = False


def inspect_untrusted_cl_report(raw) -> CLPeerFinding:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REPORT_BYTES:
        raise CLPeerReportRejected("missing, nonbytes or oversized diagnostic")
    try:
        report = raw.decode("ascii")
    except UnicodeError as exc:
        raise CLPeerReportRejected("not ASCII diagnostic") from exc
    if "\r" in report or "\x00" in report:
        raise CLPeerReportRejected("noncanonical control in diagnostic")
    if report.endswith("\n"):
        report = report[:-1]
    lines = report.split("\n")
    if len(lines) != 10 or lines != [
        HEADER,
        "REFERENCE=ADHOC_HOST_BUILT_NOT_EDITORIAL",
        "APP_PEER_AUTHENTICATED=NO",
        "TRANSPORT_TEST=UNIX_LOCAL_TWO_SIGNED_EXECUTABLES",
        *lines[4:7],
        "IOS12_RUNTIME_CODE_IDENTITY_SUPPORT=UNPROVEN_BY_THIS_REPORT",
        "BUNDLE_AND_PUBLISHER_IDENTITY=NOT_TESTED",
        FOOTER,
    ]:
        raise CLPeerReportRejected("unexpected lab report shape")
    values = []
    for i, row in enumerate(lines[4:7]):
        match = OBSERVATION.fullmatch(row)
        if not match or match.group(1) != "abc"[i] or match.group(2) not in STATES:
            raise CLPeerReportRejected("unknown or out-of-order peer result")
        values.append(match.group(2))
    statuses = tuple(values)
    matches = statuses == (
        "MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED", "MATCH_ONLY_NO_AUTH"
    )
    return CLPeerFinding(
        observations=statuses,
        controlled_codehash_comparison_observed=matches,
        interpretation=(
            "EXPECTED_CONTROLLED_CDHASH_PATTERN_UNTRUSTED_TEXT_ONLY"
            if matches else "INCONCLUSIVE_OR_UNEXPECTED_RUNTIME_OBSERVATION"
        ),
    )
