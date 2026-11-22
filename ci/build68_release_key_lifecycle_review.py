#!/usr/bin/env python3
"""Build68 Phase X: host-only offline review of key rotation and revocation.

Purpose: make dangerous trust transitions visible and fail closed. This module
NEVER activates keys or installs apps. A caller-provided "owner approved" value
is NOT a security proof. Genuine editorial trust must originate outside the
manifest, GitHub Release, IPA, CLI arguments, and this module.

This is an ephemeral *review*, not a durable production trust store.
"""
from dataclasses import dataclass
import hmac
import re

from build66_release_key_pinning_gate import (
    ReleaseKeyUntrusted, public_key_spki_sha256
)
from build66_release_key_rotation_lab import (
    RotationCandidateRejected, inspect_rotation_candidate
)
from build68_release_public_key_handoff import (
    PublicKeyHandoffRejected, prepare_public_key_handoff
)

HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_GENERATION = 2_147_483_647
MAX_REVOCATIONS = 64


class LifecycleReviewDenied(ValueError):
    pass


@dataclass(frozen=True)
class KeyLifecycleReview:
    old_spki_sha256: str
    successor_spki_sha256: str
    proposed_generation: int
    activates_at_build: int
    dual_signature_candidate_verified: bool = True
    current_key_not_revoked: bool = True
    successor_not_revoked: bool = True
    production_key_configured: bool = False
    owner_independent_consent_verified: bool = False
    revocation_list_anchored_to_device: bool = False
    release_authenticated_on_ios12: bool = False
    helper_peer_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def _validated_revocations(items):
    """Accept immutable, bounded, syntactically exact pins only.

    This is NOT proof that the provided revocations came from the owner.
    """
    if type(items) not in (frozenset, tuple):
        raise LifecycleReviewDenied("revocation list must be immutable")
    if len(items) > MAX_REVOCATIONS:
        raise LifecycleReviewDenied("revocation list too large")
    # Validate types before constructing a set: untrusted tuple entries may
    # be unhashable (dict/list); a bad list should deny, not crash the tool.
    if any(type(v) is not str or HEX.fullmatch(v) is None for v in items):
        raise LifecycleReviewDenied("invalid revoked SPKI fingerprint")
    if len(set(items)) != len(items):
        raise LifecycleReviewDenied("duplicate revoked SPKI fingerprint")
    return frozenset(items)


def inspect_unapplied_rotation(
    *, dual_signed_envelope, old_public_pem, proposed_public_pem,
    independently_pinned_old_spki, current_generation, installed_build,
    revoked_spki_pins=()
):
    """Inspect a signed candidate but NEVER return a production trust root."""
    if type(current_generation) is not int or not 0 <= current_generation < MAX_GENERATION:
        raise LifecycleReviewDenied("invalid current key generation")
    if type(installed_build) is not int or not 0 <= installed_build < MAX_GENERATION:
        raise LifecycleReviewDenied("invalid current installed build")
    if (type(independently_pinned_old_spki) is not str
            or HEX.fullmatch(independently_pinned_old_spki) is None):
        raise LifecycleReviewDenied("independent owner trust anchor absent")
    revoked = _validated_revocations(revoked_spki_pins)
    try:
        previous = prepare_public_key_handoff(
            old_public_pem, independently_pinned_old_spki
        )
        successor_pin = public_key_spki_sha256(proposed_public_pem)
    except (PublicKeyHandoffRejected, ReleaseKeyUntrusted) as exc:
        raise LifecycleReviewDenied("public key or old pin untrusted") from exc
    if (previous.canonical_spki_sha256 in revoked or
            successor_pin in revoked):
        raise LifecycleReviewDenied("a revoked old or successor key cannot rotate")
    if hmac.compare_digest(previous.canonical_spki_sha256, successor_pin):
        raise LifecycleReviewDenied("successor must differ from trusted previous key")

    try:
        result = inspect_rotation_candidate(
            dual_signed_envelope, old_public_pem, proposed_public_pem,
            independently_pinned_old_spki,
            current_generation=current_generation,
            installed_build=installed_build
        )
    except RotationCandidateRejected as exc:
        raise LifecycleReviewDenied("dual-signed rotation rejected") from exc
    if (result["candidate_generation"] != current_generation + 1 or
            result["next_spki_fingerprint"] != successor_pin or
            not result["dual_signature_chain_verified"] or
            result["production_key_rotated"] or
            result["installation_authorized"]):
        raise LifecycleReviewDenied("unexpected rotation-laboratory receipt")

    return KeyLifecycleReview(
        old_spki_sha256=previous.canonical_spki_sha256,
        successor_spki_sha256=successor_pin,
        proposed_generation=result["candidate_generation"],
        activates_at_build=result["candidate_activates_at_build"]
    )
