#!/usr/bin/env python3
"""Build66 host-only two-key rotation *candidate* audit, not a key installer.

A rotation requires signatures by both the currently pinned P-256 key and the
proposed successor. The current pin MUST come from an independently trusted
channel, never from the rotation JSON itself. A passing candidate never
changes a production trust anchor or proves operator approval.

All signing keys in tests are ephemeral, no production pins are bundled.
"""
import base64
import binascii
import json
from pathlib import Path
import re
import subprocess
import tempfile

from build66_release_key_pinning_gate import (
    ReleaseKeyUntrusted, public_key_spki_sha256
)

FIELDS = frozenset({
    "schemaVersion", "purpose", "generation", "activateAtBuild",
    "fromSPKI", "toSPKI"
})
ENVELOPE_FIELDS = frozenset({
    "schemaVersion", "algorithm", "payload", "oldSignature", "newSignature"
})
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
MAX_ENVELOPE_BYTES = 8192
MAX_PAYLOAD_BYTES = 4096


class RotationCandidateRejected(ValueError):
    pass


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise RotationCandidateRejected("duplicate JSON key")
        value[key] = item
    return value


def _decode_json(data, size):
    if type(data) is not bytes or not 0 < len(data) <= size:
        raise RotationCandidateRejected("invalid size or JSON input")
    try:
        value = json.loads(
            data.decode("utf8"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite"))
        )
    except (UnicodeError, ValueError, TypeError, OverflowError) as exc:
        if isinstance(exc, RotationCandidateRejected):
            raise
        raise RotationCandidateRejected("invalid JSON") from exc
    if not isinstance(value, dict):
        raise RotationCandidateRejected("not a JSON object")
    return value


def _decode_signature(value):
    if not isinstance(value, str) or not 85 <= len(value) <= 120:
        raise RotationCandidateRejected("signature length invalid")
    try:
        signature = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeError, ValueError, binascii.Error) as exc:
        raise RotationCandidateRejected("invalid signature base64") from exc
    if not 64 <= len(signature) <= 80:
        raise RotationCandidateRejected("ECDSA DER signature out of bounds")
    return signature


def _verify(public_pem, signed_data, der_signature):
    try:
        with tempfile.TemporaryDirectory(prefix="wr66-rotation-verify-") as root:
            folder = Path(root)
            (folder / "payload").write_bytes(signed_data)
            (folder / "key").write_bytes(public_pem)
            (folder / "sig").write_bytes(der_signature)
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", str(folder / "key"),
                 "-signature", str(folder / "sig"), str(folder / "payload")],
                capture_output=True, timeout=10, check=False
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RotationCandidateRejected("rotation cryptographic verifier unavailable") from exc
    if result.returncode != 0:
        raise RotationCandidateRejected("rotation key signature rejected")


def inspect_rotation_candidate(
    signed_envelope, old_public_pem, proposed_public_pem,
    independently_pinned_old_spki, *, current_generation, installed_build
):
    """Validate two cryptographic signatures; NEVER activate a release key."""
    if (type(current_generation) is not int or current_generation < 0 or
            type(installed_build) is not int or installed_build < 0):
        raise RotationCandidateRejected("invalid local generation/build")
    if (not isinstance(independently_pinned_old_spki, str)
            or DIGEST.fullmatch(independently_pinned_old_spki) is None):
        raise RotationCandidateRejected("current key is not independently pinned")
    try:
        old_fingerprint = public_key_spki_sha256(old_public_pem)
        new_fingerprint = public_key_spki_sha256(proposed_public_pem)
    except ReleaseKeyUntrusted as exc:
        raise RotationCandidateRejected("unsupported rotation public key") from exc
    if old_fingerprint != independently_pinned_old_spki:
        raise RotationCandidateRejected("old key does not match trusted pin")
    if old_fingerprint == new_fingerprint:
        raise RotationCandidateRejected("rotation must change the key")
    envelope = _decode_json(signed_envelope, MAX_ENVELOPE_BYTES)
    if set(envelope) != ENVELOPE_FIELDS:
        raise RotationCandidateRejected("invalid envelope fields")
    if (type(envelope["schemaVersion"]) is not int or
            envelope["schemaVersion"] != 1 or
            envelope["algorithm"] != "ecdsa-p256-sha256"):
        raise RotationCandidateRejected("unsupported rotation envelope")
    encoded_payload = envelope["payload"]
    if not isinstance(encoded_payload, str) or len(encoded_payload) > 5500:
        raise RotationCandidateRejected("invalid payload base64")
    try:
        payload_bytes = base64.b64decode(encoded_payload.encode("ascii"), validate=True)
    except (UnicodeError, ValueError, binascii.Error) as exc:
        raise RotationCandidateRejected("invalid payload base64") from exc
    payload = _decode_json(payload_bytes, MAX_PAYLOAD_BYTES)
    if set(payload) != FIELDS:
        raise RotationCandidateRejected("unexpected rotation claim fields")
    if (type(payload["schemaVersion"]) is not int or
            payload["schemaVersion"] != 1 or
            payload["purpose"] != "WEBREADER-RELEASE-KEY-ROTATION-QA" or
            type(payload["generation"]) is not int or
            payload["generation"] != current_generation + 1 or
            type(payload["activateAtBuild"]) is not int or
            not installed_build < payload["activateAtBuild"] <= 2_147_483_647 or
            payload["fromSPKI"] != old_fingerprint or
            payload["toSPKI"] != new_fingerprint):
        raise RotationCandidateRejected("rotation claim does not match policy")
    old_der = _decode_signature(envelope["oldSignature"])
    new_der = _decode_signature(envelope["newSignature"])
    _verify(old_public_pem, payload_bytes, old_der)
    _verify(proposed_public_pem, payload_bytes, new_der)
    return {
        "candidate_generation": payload["generation"],
        "candidate_activates_at_build": payload["activateAtBuild"],
        "next_spki_fingerprint": new_fingerprint,
        "dual_signature_chain_verified": True,
        "independent_operator_review_required": True,
        "revocation_checked": False,
        "production_key_rotated": False,
        "installation_authorized": False,
        "installation_performed": False,
    }
