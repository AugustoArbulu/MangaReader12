#!/usr/bin/env python3
"""Strict Phase I macOS queued AF_UNIX stream observation. NOT authorization.

A sends a complete 8-byte frame, then B receives the connected socket via
SCM_RIGHTS and sends another complete frame. The server is gated until BOTH
frames are queued, and samples LOCAL_PEERTOKEN only when reading. This is a
timing experiment, not a proof that a token authenticates individual bytes.
The text report itself is entirely untrusted.
"""
from dataclasses import dataclass
import re

MAX_BYTES = 768
FOOTER = "FINAL_INSTALL_AUTHORIZATION=DENIED"
STATES = frozenset({
    "MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED",
    "TOKEN_UNAVAILABLE", "CSOPS_MISSING", "CDHASH_UNAVAILABLE",
    "TOKEN_MUTATION_UNSAFE", "CROSS_PID_UNSAFE",
    "PROTOCOL_REJECTED", "TRANSPORT_FAILED",
})
LINE = re.compile(r"RESULT STEP([12])=([A-Z_]+) AUTHORIZATION=DENIED\Z")


class QueuedReportRejected(ValueError):
    pass


@dataclass(frozen=True)
class QueuedPeerReport:
    mode: str
    statuses: tuple
    untrusted_text_only: bool = True
    peer_authenticated: bool = False
    publisher_authenticated: bool = False
    ios12_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


@dataclass(frozen=True)
class QueuedPeerFinding:
    category: str
    observations: tuple
    stream_frames_authenticated: bool = False
    ios12_verified: bool = False
    publisher_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def parse_queued_report(raw):
    if type(raw) is not bytes or not (0 < len(raw) <= MAX_BYTES):
        raise QueuedReportRejected("invalid byte report")
    try:
        data = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise QueuedReportRejected("non-ASCII report") from exc
    if "\r" in data:
        raise QueuedReportRejected("unsupported line ending")
    if data.endswith("\n"):
        data = data[:-1]
    lines = data.split("\n")
    if len(lines) != 4 or lines[-1] != FOOTER:
        raise QueuedReportRejected("invalid record count or footer")
    if lines[0] == "READY NONROOT QUEUED_SPLIT AUTHORIZATION=DENIED":
        mode = "SPLIT"
    elif lines[0] == "READY NONROOT QUEUED_BATCH AUTHORIZATION=DENIED":
        mode = "BATCH"
    else:
        raise QueuedReportRejected("unexpected report header")
    statuses = []
    for i, item in enumerate(lines[1:3], 1):
        found = LINE.fullmatch(item)
        if not found or int(found.group(1)) != i:
            raise QueuedReportRejected("missing/duplicate/reordered status")
        status = found.group(2)
        if status not in STATES and not (i == 2 and mode == "BATCH" and status == "NO_SECOND_SAMPLE"):
            raise QueuedReportRejected("unknown status")
        if i == 2 and (mode == "BATCH") != (status == "NO_SECOND_SAMPLE"):
            raise QueuedReportRejected("wrong sampling count")
        statuses.append(status)
    return QueuedPeerReport(mode, tuple(statuses))


def classify_queued_reports(reference_a, reference_b):
    if (type(reference_a) is not QueuedPeerReport or
        type(reference_b) is not QueuedPeerReport or
        reference_a.mode != reference_b.mode or
        not reference_a.untrusted_text_only or
        not reference_b.untrusted_text_only or
        reference_a.peer_authenticated or reference_b.peer_authenticated or
        reference_a.publisher_authenticated or reference_b.publisher_authenticated or
        reference_a.ios12_verified or reference_b.ios12_verified or
        reference_a.installation_authorized or reference_b.installation_authorized or
        reference_a.installation_performed or reference_b.installation_performed):
        raise QueuedReportRejected("unsafe evidence or mismatched modes")
    observations = []
    for left, right in zip(reference_a.statuses, reference_b.statuses):
        if left == "MATCH_ONLY_NO_AUTH" and right == "MISMATCH_REJECTED":
            observations.append("A")
        elif left == "MISMATCH_REJECTED" and right == "MATCH_ONLY_NO_AUTH":
            observations.append("B")
        elif left == "NO_SECOND_SAMPLE" and right == "NO_SECOND_SAMPLE":
            observations.append("NO_SECOND_SAMPLE")
        else:
            observations.append("?")
    found = tuple(observations)
    if reference_a.mode == "BATCH":
        category = "BATCH_SINGLE_SAMPLE_CANNOT_ATTRIBUTE_FRAMES"
    elif found == ("B", "B"):
        category = "B_OBSERVED_FOR_BOTH_QUEUED_FRAMES"
    elif found == ("A", "B"):
        category = "A_B_SEQUENCE_OBSERVED_NOT_AUTHENTICATED"
    elif found == ("A", "A"):
        category = "A_OBSERVED_FOR_BOTH_QUEUED_FRAMES"
    elif found == ("B", "A"):
        category = "REVERSED_OBSERVATION_NOT_AUTHENTICATED"
    else:
        category = "INCONCLUSIVE_QUEUED_STREAM_IDENTITY"
    return QueuedPeerFinding(category, found)
