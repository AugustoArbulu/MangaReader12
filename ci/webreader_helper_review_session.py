#!/usr/bin/env python3
"""Host-only, memory-only prototype for helper review-session replay safety.

No IPC listener, authentication, file access, update download, root process,
or installer is present here. A REVIEW MATCH IS NEVER INSTALL AUTHORIZATION.

An eventual privileged service must derive peer identity from OS-provided
authenticated IPC credentials. An arbitrary peer_context object is only a
test stand-in, and expected_digest must come from *independent* verification
by the helper, never copied from an untrusted client request.
"""
from dataclasses import dataclass
import hmac
import math
import re
import secrets

from webreader_helper_request_contract import ParsedReviewRequest

HEX256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class ReviewSessionRejected(ValueError):
    """Fail-closed review transaction, not a device installation outcome."""


@dataclass(frozen=True)
class ReviewChallenge:
    token: str
    expires_at_seconds: float


@dataclass(frozen=True)
class ReviewAssessment:
    requested_build: int
    manifest_sha256_matches_independent_check: bool
    install_authorized: bool = False


@dataclass(frozen=True)
class _Pending:
    peer_context: object
    request: ParsedReviewRequest
    expires_at: float


class ReviewSessionLedger:
    """One-shot review challenges bound to a per-connection peer object.

    Never use these checks as a substitute for authenticated IPC, signature
    verification, safe file handling, or consent. This prototype cannot
    authorize installation, even on success.
    """

    def __init__(self, *, ttl_seconds=30.0, max_pending=8,
                 challenge_factory=None):
        if (type(ttl_seconds) not in (float, int) or
                not math.isfinite(ttl_seconds) or not 0 < ttl_seconds <= 120):
            raise ValueError("invalid TTL")
        if type(max_pending) is not int or not 1 <= max_pending <= 64:
            raise ValueError("invalid pending capacity")
        self.ttl_seconds = float(ttl_seconds)
        self.max_pending = max_pending
        self._new_token = challenge_factory or (lambda: secrets.token_hex(32))
        self._pending = {}
        # Keep client correlation nonces until expiry, including after a
        # challenge is consumed or cancelled, to reject request replay.
        self._correlations = []

    @staticmethod
    def _validate_now(now):
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ReviewSessionRejected("invalid monotonic timestamp")
        return float(now)

    @staticmethod
    def _validate_peer(peer_context):
        # Real peer credentials MUST be checked by a separate, native IPC
        # transport. Strings and integers cannot represent that identity.
        if peer_context is None or isinstance(
            peer_context, (str, bytes, int, float, bool)
        ):
            raise ReviewSessionRejected("untrusted peer identity placeholder")

    def _expire(self, now):
        self._pending = {
            token: ticket for token, ticket in self._pending.items()
            if now < ticket.expires_at
        }
        self._correlations = [
            (peer, nonce, deadline)
            for peer, nonce, deadline in self._correlations
            if now < deadline
        ]

    def begin_review(self, request, peer_context, *, now):
        now = self._validate_now(now)
        self._validate_peer(peer_context)
        if type(request) is not ParsedReviewRequest:
            raise ReviewSessionRejected("unparsed client request")
        self._expire(now)
        if len(self._pending) >= self.max_pending:
            raise ReviewSessionRejected("too many pending review challenges")
        if any(peer is peer_context and nonce == request.nonce
               for peer, nonce, _ in self._correlations):
            raise ReviewSessionRejected("replayed client correlation nonce")
        token = None
        for _ in range(3):
            candidate = self._new_token()
            if (type(candidate) is str and HEX256.fullmatch(candidate) and
                    candidate not in self._pending):
                token = candidate
                break
        if token is None:
            raise ReviewSessionRejected("cannot issue unique challenge")
        deadline = now + self.ttl_seconds
        self._pending[token] = _Pending(peer_context, request, deadline)
        self._correlations.append((peer_context, request.nonce, deadline))
        return ReviewChallenge(token=token, expires_at_seconds=deadline)

    def confirm_review(self, challenge_token, peer_context, *,
                       independently_verified_digest, checked_build, now):
        """Consume a challenge once, and return a review-only observation.

        Passing the digest argument directly from the untrusted request is
        forbidden by the future helper design (not enforceable in Python).
        """
        now = self._validate_now(now)
        self._validate_peer(peer_context)
        if type(challenge_token) is not str or not HEX256.fullmatch(
            challenge_token
        ):
            raise ReviewSessionRejected("malformed review challenge")
        pending = self._pending.get(challenge_token)
        if pending is None:
            raise ReviewSessionRejected("unknown or used review challenge")
        if pending.peer_context is not peer_context:
            # Avoid letting an unrelated peer consume someone else's token.
            raise ReviewSessionRejected("challenge belongs to another peer")
        del self._pending[challenge_token]  # Single use even on later failure.
        if now >= pending.expires_at:
            raise ReviewSessionRejected("expired review challenge")
        if (type(independently_verified_digest) is not str or
                not HEX256.fullmatch(independently_verified_digest)):
            raise ReviewSessionRejected("invalid independently checked digest")
        if type(checked_build) is not int or checked_build != pending.request.build:
            raise ReviewSessionRejected("independent build check differs")
        matches = hmac.compare_digest(
            pending.request.manifest_sha256, independently_verified_digest
        )
        if not matches:
            raise ReviewSessionRejected("independent manifest hash differs")
        return ReviewAssessment(
            requested_build=pending.request.build,
            manifest_sha256_matches_independent_check=True,
            install_authorized=False,
        )

    def cancel_review(self, challenge_token, peer_context):
        self._validate_peer(peer_context)
        pending = self._pending.get(challenge_token)
        if pending is None or pending.peer_context is not peer_context:
            return False
        del self._pending[challenge_token]
        return True

    def revoke_peer(self, peer_context):
        """Invalidate all pending reviews when an IPC connection terminates."""
        self._validate_peer(peer_context)
        for token, pending in list(self._pending.items()):
            if pending.peer_context is peer_context:
                del self._pending[token]
