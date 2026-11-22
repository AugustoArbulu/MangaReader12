#!/usr/bin/env python3
"""Untrusted SCM_RIGHTS observation pair classification (never an auth gate).

Both probes are made with the SAME origin/writer binaries but with two
independently prepared expectations: origin binary CodeDirectory and sender
binary CodeDirectory. Either transcript can be fabricated and therefore cannot
provide trusted policy input. This module is purely reporting.
"""
from dataclasses import dataclass
from build66_independent_peer_report import PeerTranscript

MATCH = "MATCH_ONLY_NO_AUTH"
MISMATCH = "MISMATCH_REJECTED"


class HandoffFindingsRejected(ValueError):
    pass


@dataclass(frozen=True)
class HandoffFinding:
    category: str
    origin_connector_is_current_message_writer: bool = False
    current_writer_authenticated: bool = False
    origin_code_authenticates_publisher: bool = False
    iOS12_runtime_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def classify_handoff_pair(origin_report, sender_report):
    if (type(origin_report) is not PeerTranscript
            or type(sender_report) is not PeerTranscript
            or not origin_report.from_untrusted_text_only
            or not sender_report.from_untrusted_text_only):
        raise HandoffFindingsRejected("expected two strictly parsed lab transcripts")
    if (origin_report.installation_authorized or sender_report.installation_authorized
            or origin_report.authenticated_webreader_peer
            or sender_report.authenticated_webreader_peer
            or origin_report.publisher_authenticated
            or sender_report.publisher_authenticated):
        raise HandoffFindingsRejected("a diagnostic must never carry authority")
    origin, sender = origin_report.result, sender_report.result
    if origin == MATCH and sender == MISMATCH:
        # A was the original connector; B sent the application payload.
        # This would demonstrate the peer token reports connection origin,
        # NOT that A necessarily wrote any particular subsequent message.
        return HandoffFinding("ORIGIN_STICKY_AFTER_FD_TRANSFER")
    if origin == MISMATCH and sender == MATCH:
        return HandoffFinding("SENDER_CODE_OBSERVED_AFTER_FD_TRANSFER")
    if origin == MATCH and sender == MATCH:
        return HandoffFinding("AMBIGUOUS_BOTH_REFERENCES_MATCH")
    if origin == MISMATCH and sender == MISMATCH:
        return HandoffFinding("NEITHER_REFERENCE_MATCHES")
    return HandoffFinding("INCONCLUSIVE_KERNEL_CAPABILITY")
