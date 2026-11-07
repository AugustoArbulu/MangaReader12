#!/usr/bin/env python3
"""Strict independent signed-peer test transcript parser, NON-authoritative.

All text is forgeable. Even MATCH_ONLY_NO_AUTH is not publisher verification
or user approval. Mac-only harness uses this to reject unexpected disclosure,
install wording, ambiguous/missing states and status injection.
"""
from dataclasses import dataclass
import re

HEAD = "READY NONROOT SINGLE_CONNECTION AUTHORIZATION=DENIED"
TAIL = "FINAL_INSTALL_AUTHORIZATION=DENIED"
STATUS = frozenset({
    "MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED", "TOKEN_UNAVAILABLE",
    "CSOPS_MISSING", "CDHASH_UNAVAILABLE", "TOKEN_MUTATION_UNSAFE",
    "CROSS_PID_UNSAFE", "PROTOCOL_REJECTED", "TRANSPORT_FAILED",
})
LINE = re.compile(r"RESULT ([A-Z_]+) AUTHORIZATION=DENIED\Z")
MAX_BYTES = 512


class IndependentPeerTranscriptRejected(ValueError):
    pass


@dataclass(frozen=True)
class PeerTranscript:
    result: str
    exact_codehash_match_observed: bool
    from_untrusted_text_only: bool = True
    kernel_binding_cryptographically_trusted_on_ios12: bool = False
    authenticated_webreader_peer: bool = False
    publisher_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def parse_independent_peer_transcript(blob):
    if type(blob) is not bytes or not 0 < len(blob) <= MAX_BYTES:
        raise IndependentPeerTranscriptRejected("invalid transcript size/type")
    try:
        value = blob.decode("ascii")
    except UnicodeError as exc:
        raise IndependentPeerTranscriptRejected("non-ascii transcript") from exc
    if "\r" in value:
        raise IndependentPeerTranscriptRejected("noncanonical line ending")
    if value.endswith("\n"):
        value = value[:-1]
    lines = value.split("\n")
    if len(lines) != 3 or lines[0] != HEAD or lines[2] != TAIL:
        raise IndependentPeerTranscriptRejected("invalid peer transcript")
    match = LINE.fullmatch(lines[1])
    if not match or match.group(1) not in STATUS:
        raise IndependentPeerTranscriptRejected("invalid diagnostic status")
    return PeerTranscript(
        result=match.group(1),
        exact_codehash_match_observed=match.group(1) == "MATCH_ONLY_NO_AUTH",
    )
