#!/usr/bin/env python3
"""Phase CM parse untrusted post-Chimera field diagnostic without escalation."""
from dataclasses import dataclass
import re

HEAD = "WEBREADER_CM_IOS12_PEER_REASON: NONROOT READ_ONLY"
TAIL = "FINAL_INSTALL_AUTHORIZATION=DENIED"
MAX_BYTES = 1536
EXPECTED = (
    "MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED", "MATCH_ONLY_NO_AUTH"
)
STATUS = frozenset({
    "MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED",
    "TOKEN_UNAVAILABLE", "CSOPS_MISSING", "CDHASH_UNAVAILABLE",
    "TOKEN_MUTATION_UNSAFE", "CROSS_PID_UNSAFE",
    "PROTOCOL_REJECTED", "TRANSPORT_FAILED",
    "SOCKET_UNAVAILABLE", "CLIENT_FAILED", "INCONCLUSIVE",
})
LINE = re.compile(
    r"OBSERVATION_([abc])=([A-Z_]+) AUTHORIZATION=DENIED\Z"
)


class CMPeerReasonRejected(ValueError):
    pass


@dataclass(frozen=True)
class CMReadOnlyFinding:
    observations: tuple
    evidence_category: str
    all_expected_controlled_comparisons: bool = False
    untrusted_report_only: bool = True
    ios12_runtime_verified_by_this_parser: bool = False
    webreader_process_authenticated: bool = False
    publisher_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def inspect_untrusted_cm_report(raw: bytes) -> CMReadOnlyFinding:
    if type(raw) is not bytes or not (0 < len(raw) <= MAX_BYTES):
        raise CMPeerReasonRejected("invalid untrusted byte report")
    try:
        source = raw.decode("ascii")
    except UnicodeError as exc:
        raise CMPeerReasonRejected("invalid report encoding") from exc
    if "\r" in source or "\x00" in source:
        raise CMPeerReasonRejected("invalid controls")
    if source.endswith("\n"):
        source = source[:-1]
    lines = source.split("\n")
    if (len(lines) != 10 or lines[0] != HEAD
            or lines[1:4] != [
                "REFERENCE=ADHOC_HOST_BUILT_NOT_EDITORIAL",
                "APP_PEER_AUTHENTICATED=NO",
                "TRANSPORT_TEST=UNIX_LOCAL_TWO_SIGNED_EXECUTABLES"
            ] or lines[7:] != [
                "IOS12_RUNTIME_CODE_IDENTITY_SUPPORT=UNPROVEN_BY_THIS_REPORT",
                "BUNDLE_AND_PUBLISHER_IDENTITY=NOT_TESTED",
                TAIL
            ]):
        raise CMPeerReasonRejected("invalid report structure or denial footer")
    found = []
    for index, row in enumerate(lines[4:7]):
        match = LINE.fullmatch(row)
        if not match or match.group(1) != "abc"[index] or match.group(2) not in STATUS:
            raise CMPeerReasonRejected("unknown, injected or reordered case result")
        found.append(match.group(2))
    statuses = tuple(found)
    matched = statuses == EXPECTED
    if matched:
        category = "EXPECTED_CDHASH_LAB_PATTERN_UNTRUSTED"
    elif len(set(statuses)) == 1 and statuses[0] in (
        "TOKEN_UNAVAILABLE", "CSOPS_MISSING", "CDHASH_UNAVAILABLE"
    ):
        category = "SAME_KERNEL_CAPABILITY_FAILURE_ALL_THREE"
    elif any(x in ("TOKEN_MUTATION_UNSAFE", "CROSS_PID_UNSAFE") for x in statuses):
        category = "KERNEL_TOKEN_VALIDATION_FAILED_UNSAFE"
    elif any(x in ("SOCKET_UNAVAILABLE", "CLIENT_FAILED", "TRANSPORT_FAILED") for x in statuses):
        category = "LOCAL_TRANSPORT_FAILURE"
    else:
        category = "INCONCLUSIVE_OR_MIXED_OBSERVATIONS"
    return CMReadOnlyFinding(
        observations=statuses,
        evidence_category=category,
        all_expected_controlled_comparisons=matched
    )
