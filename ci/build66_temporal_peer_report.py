#!/usr/bin/env python3
"""Strict Phase H temporal peer-token report, NEVER installation authority.

Three application messages share one connected AF_UNIX stream. The sender
sequence is A -> B (passed fd) -> A (while B still holds its fd). Every sample
is obtained by the server after reading the respective message and before its
ACK. The two expected code references are verified independently by codesign.

A text transcript can be forged; neither this parser nor CDHash proves that
WebReader (or a signed publisher) has been authenticated on iOS 12/Chimera.
"""
from dataclasses import dataclass
import re

HEADER = "READY NONROOT THREE_MESSAGES AUTHORIZATION=DENIED"
FOOTER = "FINAL_INSTALL_AUTHORIZATION=DENIED"
MAX_BYTES = 1024
RESULTS = frozenset({
    "MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED", "TOKEN_UNAVAILABLE",
    "CSOPS_MISSING", "CDHASH_UNAVAILABLE", "TOKEN_MUTATION_UNSAFE",
    "CROSS_PID_UNSAFE", "PROTOCOL_REJECTED", "TRANSPORT_FAILED",
})
LINE = re.compile(r"RESULT STEP([1-3])=([A-Z_]+) AUTHORIZATION=DENIED\Z")


class TemporalReportRejected(ValueError):
    pass


@dataclass(frozen=True)
class TemporalPeerReport:
    statuses: tuple
    source_untrusted_text_only: bool = True
    sender_identified_on_ios12: bool = False
    publisher_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


@dataclass(frozen=True)
class TemporalPeerFinding:
    category: str
    observed_origin_sender_sequence: tuple
    current_writer_authenticated: bool = False
    ios12_runtime_verified: bool = False
    publisher_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def parse_temporal_peer_report(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise TemporalReportRejected("bad report bytes")
    try:
        text = raw.decode("ascii")
    except UnicodeError as exc:
        raise TemporalReportRejected("bad report encoding") from exc
    if "\r" in text:
        raise TemporalReportRejected("bad line endings")
    if text.endswith("\n"):
        text = text[:-1]
    lines = text.split("\n")
    if len(lines) != 5 or lines[0] != HEADER or lines[-1] != FOOTER:
        raise TemporalReportRejected("invalid transcript shape")
    observed = []
    for index, line in enumerate(lines[1:4], 1):
        match = LINE.fullmatch(line)
        if not match or int(match.group(1)) != index or match.group(2) not in RESULTS:
            raise TemporalReportRejected("invalid/duplicate/order status")
        observed.append(match.group(2))
    return TemporalPeerReport(tuple(observed))


def classify_temporal_reports(expected_origin, expected_sender):
    if (type(expected_origin) is not TemporalPeerReport or
            type(expected_sender) is not TemporalPeerReport or
            not expected_origin.source_untrusted_text_only or
            not expected_sender.source_untrusted_text_only or
            expected_origin.publisher_authenticated or
            expected_sender.publisher_authenticated or
            expected_origin.installation_authorized or
            expected_sender.installation_authorized):
        raise TemporalReportRejected("untrusted evidence implies authority")
    mapping = []
    for origin, sender in zip(expected_origin.statuses, expected_sender.statuses):
        if origin == "MATCH_ONLY_NO_AUTH" and sender == "MISMATCH_REJECTED":
            mapping.append("A")
        elif origin == "MISMATCH_REJECTED" and sender == "MATCH_ONLY_NO_AUTH":
            mapping.append("B")
        else:
            mapping.append("?")
    sequence = tuple(mapping)
    if sequence == ("A", "B", "A"):
        category = "A_B_A_MESSAGE_SENDER_REBINDING_OBSERVED"
    elif sequence == ("A", "B", "B"):
        category = "TRANSFER_STICKY_AFTER_B_OBSERVED"
    elif sequence == ("A", "A", "A"):
        category = "ORIGIN_STICKY_THROUGH_MESSAGES"
    elif "?" in sequence:
        category = "INCONCLUSIVE_OR_AMBIGUOUS"
    else:
        category = "UNEXPECTED_CONNECTION_IDENTITY_SEQUENCE"
    return TemporalPeerFinding(category, sequence)
