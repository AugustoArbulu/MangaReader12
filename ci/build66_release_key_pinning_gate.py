#!/usr/bin/env python3
"""Build66 phase-B independent, HOST-ONLY pinned release key audit.

The expected SHA-256 of the EC P-256 SubjectPublicKeyInfo DER must be known
BEFORE consulting the release, and come from trusted application provisioning.
Never derive that pin from the downloaded manifest, release page, or IPA.

No production pin or private key is stored here. The iOS production key is
still nil. This module never downloads, installs or authorizes an update.
"""
import hashlib
import re
import subprocess

from build66_signed_release_preflight import (
    SignedReleaseRejected, verify_signed_release
)
from webreader_update_manifest import ManifestRejected, validate

HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
MAX_PUBLIC_PEM_BYTES = 4096


class ReleaseKeyUntrusted(ValueError):
    pass


def _openssl(args, input_bytes):
    try:
        result = subprocess.run(
            ["openssl", *args],
            input=input_bytes, capture_output=True, check=False, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReleaseKeyUntrusted("host OpenSSL not available") from exc
    if result.returncode != 0:
        raise ReleaseKeyUntrusted("invalid EC public release key")
    return result.stdout


def public_key_spki_sha256(public_pem):
    """Return fingerprint for an independently provisioned P-256 public key."""
    if (type(public_pem) is not bytes
            or not 100 <= len(public_pem) <= MAX_PUBLIC_PEM_BYTES):
        raise ReleaseKeyUntrusted("public key missing or unbounded")
    key_info = _openssl(
        ["ec", "-pubin", "-text", "-noout"], public_pem
    )
    if b"ASN1 OID: prime256v1" not in key_info:
        raise ReleaseKeyUntrusted("release public key must use P-256")
    spki = _openssl(["pkey", "-pubin", "-outform", "DER"], public_pem)
    if not 80 <= len(spki) <= 160:
        raise ReleaseKeyUntrusted("invalid DER subjectPublicKeyInfo")
    return hashlib.sha256(spki).hexdigest()


def verify_independently_pinned_v2(
    envelope_json, public_pem, expected_spki_sha256, ipa_path,
    installed_build=65
):
    """Read-only v2 receipt, never an installation capability.

    The trusted key fingerprint must be supplied by policy outside this code.
    """
    if (type(expected_spki_sha256) is not str or
            HEX_DIGEST.fullmatch(expected_spki_sha256) is None):
        raise ReleaseKeyUntrusted("no valid independently pinned key fingerprint")
    if public_key_spki_sha256(public_pem) != expected_spki_sha256:
        raise ReleaseKeyUntrusted("release public key does not match pinned fingerprint")
    try:
        signed = validate(
            envelope_json, public_pem, installed_build=installed_build,
            installed_ios="12.5.8"
        )
        if signed["schemaVersion"] != 2:
            raise ReleaseKeyUntrusted("only v2 ad-hoc signed assets are considered")
        structural = verify_signed_release(
            envelope_json, public_pem, ipa_path,
            installed_build=installed_build, installed_ios="12.5.8"
        )
    except (ManifestRejected, SignedReleaseRejected) as exc:
        raise ReleaseKeyUntrusted("signed v2 release or IPA rejected") from exc
    return {
        "build": structural["build"],
        "ipa_sha256": structural["sha256"],
        "signed_manifest_and_ipa_match": True,
        "pinned_spki_fingerprint_match": True,
        "native_codesign_verified": False,
        "publisher_trust_root_configured_by_app": False,
        "peer_authenticated": False,
        "user_consent_verified": False,
        "installation_authorized": False,
        "installation_performed": False,
    }
