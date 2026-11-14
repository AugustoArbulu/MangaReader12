#!/usr/bin/env python3
"""Host-only prototype for a fail-closed WebReader helper request envelope.

This module parses an untrusted client REQUEST. It does not verify the sender,
authenticate a release, obtain file descriptors, allocate an IPC endpoint,
launch appinst, or authorize installation. It has no filesystem/network effects.

A real rootful helper MUST independently authenticate the peer using OS IPC
credentials and MUST independently revalidate manifest/IPA and an already-open
regular file before considering any privileged action. This parser alone is
never an authorization decision.
"""
from dataclasses import dataclass
import json
import re

MAX_REQUEST_BYTES = 2048
MAX_BUILD = 2_147_483_647
BUNDLE_ID = "com.example.MangaReader12"
FIELD_NAMES = frozenset({
    "schemaVersion", "operation", "bundleId", "build",
    "manifestSHA256", "nonce"
})


class HelperRequestRejected(ValueError):
    """Malformed or unsupported untrusted helper request."""


@dataclass(frozen=True)
class ParsedReviewRequest:
    build: int
    manifest_sha256: str
    nonce: str


def _reject_duplicate_json_keys(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise HelperRequestRejected("duplicate JSON object key")
        result[name] = value
    return result


def parse_review_request(data: bytes) -> ParsedReviewRequest:
    if type(data) is not bytes or not 0 < len(data) <= MAX_REQUEST_BYTES:
        raise HelperRequestRejected("oversized, empty, or nonbytes request")
    # Reject U+FEFF BOM and all non-UTF8 input, including invalid surrogates.
    try:
        decoded = data.decode("utf-8", errors="strict")
        obj = json.loads(
            decoded, object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                HelperRequestRejected("nonfinite numeric token")
            )
        )
    except (UnicodeError, ValueError, TypeError, RecursionError) as err:
        if isinstance(err, HelperRequestRejected):
            raise
        raise HelperRequestRejected("invalid JSON request") from err
    if type(obj) is not dict or set(obj) != FIELD_NAMES:
        raise HelperRequestRejected("unknown or missing field")
    if type(obj["schemaVersion"]) is not int or obj["schemaVersion"] != 1:
        raise HelperRequestRejected("unsupported request version")
    if obj["operation"] != "request-install-review":
        raise HelperRequestRejected("unapproved operation")
    if obj["bundleId"] != BUNDLE_ID:
        raise HelperRequestRejected("wrong application")
    if type(obj["build"]) is not int or not 1 <= obj["build"] <= MAX_BUILD:
        raise HelperRequestRejected("invalid build")
    digest = obj["manifestSHA256"]
    nonce = obj["nonce"]
    if type(digest) is not str or re.fullmatch("[0-9a-f]{64}", digest) is None:
        raise HelperRequestRejected("invalid manifest digest")
    if type(nonce) is not str or re.fullmatch("[0-9a-f]{64}", nonce) is None:
        raise HelperRequestRejected("invalid request nonce")
    if digest == nonce:
        # Avoid malformed test requests conflating two independent tokens.
        raise HelperRequestRejected("nonce must be independent of digest")
    return ParsedReviewRequest(
        build=obj["build"], manifest_sha256=digest, nonce=nonce
    )


def redact_request_for_log(request: ParsedReviewRequest) -> dict:
    """Safe logging: no URL/path/file contents/nonce/signature."""
    return {
        "protocol_version": 1,
        "operation": "request-install-review",
        "bundle_id": BUNDLE_ID,
        "requested_build": request.build,
        "authorization_status": "never-authorized-by-request-parser",
    }
