#!/usr/bin/env python3
"""Offline, host-only handoff for an OUT-OF-BAND trusted P-256 release key.

The Swift/iOS12 verifier consumes an ANSI X9.63 uncompressed 65-byte point,
while the existing host gate pins the SHA-256 of the canonical DER SPKI.
This module reconciles both representations without generating a signing key,
configuring production, authorizing installation or contacting GitHub.

Never treat a key/pin supplied together by an untrusted release as independent.
Private keys must remain outside the repository and application.
"""
from dataclasses import dataclass
import hashlib
import hmac
import re

from build66_release_key_pinning_gate import (
    ReleaseKeyUntrusted, _openssl, public_key_spki_sha256
)

# OpenSSL canonical SubjectPublicKeyInfo for id-ecPublicKey / prime256v1.
# Includes the ASN.1 BIT STRING with 0 unused bits; 65 point bytes follow.
P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d030107034200"
)
FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
SINGLE_PUBLIC_PEM = re.compile(
    rb"-----BEGIN PUBLIC KEY-----\r?\n"
    rb"(?:[A-Za-z0-9+/=]{1,76}\r?\n)+"
    rb"-----END PUBLIC KEY-----\r?\n?\Z"
)


class PublicKeyHandoffRejected(ValueError):
    pass


@dataclass(frozen=True)
class PublicKeyHandoff:
    # These are *public* bytes, safe to display during owner review.
    canonical_spki_sha256: str
    x963_public_key_hex: str
    algorithm: str = "ecdsa-p256-sha256"
    independent_pin_matched: bool = True
    production_key_configured: bool = False
    publisher_authenticated_on_device: bool = False
    signed_release_verified: bool = False
    peer_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def prepare_public_key_handoff(public_pem, independent_spki_sha256):
    """Convert a public P-256 key only when a separate trusted pin matches.

    The independent fingerprint MUST be provisioned out of band. This is
    verification-only, not an application trust-root enrollment function.
    """
    if (type(independent_spki_sha256) is not str or
            FINGERPRINT.fullmatch(independent_spki_sha256) is None):
        raise PublicKeyHandoffRejected("independent trusted SPKI fingerprint missing")
    if (type(public_pem) is not bytes or not 100 <= len(public_pem) <= 4096
            or SINGLE_PUBLIC_PEM.fullmatch(public_pem) is None):
        raise PublicKeyHandoffRejected("expected a single public-only PEM block")
    try:
        pinned = public_key_spki_sha256(public_pem)
        spki = _openssl(["pkey", "-pubin", "-outform", "DER"], public_pem)
    except ReleaseKeyUntrusted as exc:
        raise PublicKeyHandoffRejected("unsupported public key") from exc
    canonical = hashlib.sha256(spki).hexdigest()
    if (not hmac.compare_digest(canonical, pinned) or
            not hmac.compare_digest(canonical, independent_spki_sha256)):
        raise PublicKeyHandoffRejected("public key does not match out-of-band pin")
    if (len(spki) != len(P256_SPKI_PREFIX) + 65 or
            not spki.startswith(P256_SPKI_PREFIX) or
            spki[len(P256_SPKI_PREFIX)] != 4):
        raise PublicKeyHandoffRejected("noncanonical P-256 SPKI/X9.63 point")
    x963 = spki[len(P256_SPKI_PREFIX):]
    return PublicKeyHandoff(
        canonical_spki_sha256=canonical,
        x963_public_key_hex=x963.hex()
    )
