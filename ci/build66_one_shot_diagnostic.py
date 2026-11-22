#!/usr/bin/env python3
"""Build66 offline one-shot *preflight* state-machine research.

This is NOT a local-socket service or installation authorization. A successful
CHECK_ONLY proves only that a diagnostic request matches pre-provisioned
reference fields and has not been reused inside this one process. It proves
NOTHING about the client peer, signing key custody, on-device consent or IPA
immutability at the future installer. No installation can result from this API.

A future installer must perform independent publisher, requester, signed
manifest, code-signature, exact-file and user-consent checks. The read-only PING
bridge must NEVER share a privilege boundary with this research prototype.
"""
import json
import math
import re
import secrets
import threading
import time
from dataclasses import dataclass

APP_BUNDLE_ID = "com.example.MangaReader12"
INSTALLED_APPLICATION_IDENTIFIER = (
    "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
)
EXPECTED_FIELDS = frozenset({
    "protocolVersion", "operation", "challenge", "manifestSHA256",
    "ipaSHA256", "targetBuild", "bundleId", "applicationIdentifier"
})
MAX_MESSAGE_BYTES = 2048
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
NONCE = re.compile(r"[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class DiagnosticResult:
    request_consistent: bool
    reason: str
    # Immutable false by contract: an authenticated installer is not present.
    installation_authorized: bool = False
    installation_performed: bool = False
    peer_identity_authenticated: bool = False
    user_install_consent_verified: bool = False


def _unique_keys(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate JSON key")
        data[key] = value
    return data


def _no_nonfinite(value):
    raise ValueError("nonfinite JSON is forbidden")


def _valid_sha(value):
    return isinstance(value, str) and DIGEST.fullmatch(value) is not None


class OneShotDiagnostic:
    """An isolated, nonprivileged request-consistency/replay laboratory.

    Reference hashes and build numbers MUST be supplied by a caller which has
    independently verified the release; this class does not verify signatures.
    Injected clock/entropy functions are ONLY for deterministic host tests.
    """

    def __init__(
        self, *, target_build, installed_build, manifest_sha256, ipa_sha256,
        ttl_seconds=30, clock=None, entropy=None
    ):
        if (type(target_build) is not int or type(installed_build) is not int
            or not 0 <= installed_build < target_build <= 2_147_483_647):
            raise ValueError("invalid diagnostic build reference")
        if not _valid_sha(manifest_sha256) or not _valid_sha(ipa_sha256):
            raise ValueError("invalid diagnostic SHA-256 reference")
        if (type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 60):
            raise ValueError("invalid diagnostic lifetime")
        self._clock = clock or time.monotonic
        entropy = entropy or secrets.token_bytes
        seed = entropy(16)
        if not isinstance(seed, bytes) or len(seed) != 16:
            raise ValueError("diagnostic entropy failed")
        self._nonce = seed.hex()
        self._begin = self._read_clock()
        self._deadline = self._begin + ttl_seconds
        self._target_build = target_build
        self._manifest_sha256 = manifest_sha256
        self._ipa_sha256 = ipa_sha256
        self._spent = False
        self._lock = threading.Lock()

    def _read_clock(self):
        now = self._clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise ValueError("diagnostic clock invalid")
        return now

    def challenge(self):
        """Public diagnostic nonce, NOT a secret or installation capability."""
        return self._nonce

    def check_once(self, request_bytes):
        with self._lock:
            if self._spent:
                return DiagnosticResult(False, "REPLAY_REJECTED")
            # Consume even malformed requests so guessing cannot be retried.
            self._spent = True
            try:
                if self._read_clock() >= self._deadline:
                    return DiagnosticResult(False, "EXPIRED_REJECTED")
                if (not isinstance(request_bytes, bytes) or
                    not 0 < len(request_bytes) <= MAX_MESSAGE_BYTES):
                    return DiagnosticResult(False, "SIZE_OR_TYPE_REJECTED")
                parsed = json.loads(
                    request_bytes.decode("utf-8"),
                    object_pairs_hook=_unique_keys,
                    parse_constant=_no_nonfinite
                )
                if not isinstance(parsed, dict) or set(parsed) != EXPECTED_FIELDS:
                    return DiagnosticResult(False, "FIELD_SET_REJECTED")
                if (type(parsed["protocolVersion"]) is not int or
                    parsed["protocolVersion"] != 1 or
                    parsed["operation"] != "CHECK_ONLY"):
                    return DiagnosticResult(False, "OPERATION_REJECTED")
                if (not isinstance(parsed["challenge"], str) or
                    NONCE.fullmatch(parsed["challenge"]) is None or
                    not secrets.compare_digest(parsed["challenge"], self._nonce)):
                    return DiagnosticResult(False, "CHALLENGE_REJECTED")
                if (type(parsed["targetBuild"]) is not int or
                    parsed["targetBuild"] != self._target_build or
                    parsed["bundleId"] != APP_BUNDLE_ID or
                    parsed["applicationIdentifier"] != INSTALLED_APPLICATION_IDENTIFIER or
                    not _valid_sha(parsed["manifestSHA256"]) or
                    not _valid_sha(parsed["ipaSHA256"]) or
                    not secrets.compare_digest(
                        parsed["manifestSHA256"], self._manifest_sha256
                    ) or
                    not secrets.compare_digest(
                        parsed["ipaSHA256"], self._ipa_sha256
                    )):
                    return DiagnosticResult(False, "REFERENCE_REJECTED")
                return DiagnosticResult(True, "DIAGNOSTIC_MATCH_NOT_AUTHORIZED")
            except (UnicodeError, ValueError, TypeError, KeyError, OverflowError):
                return DiagnosticResult(False, "MALFORMED_REJECTED")
