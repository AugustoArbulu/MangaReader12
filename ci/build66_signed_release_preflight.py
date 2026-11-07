#!/usr/bin/env python3
"""Host-only Build66 signed Release + IPA *preflight* (NO installation).

This connects the pre-existing ECDSA P-256 manifest verifier with the
archive/identity checks. It does NOT authenticate an installed iOS app,
provisioning profile, code-signing entitlements, IPC peer, or appinst caller.

A pass is never permission to install. The real helper would need a separate
trust decision and must independently verify the exact immutable bytes it uses.
"""
from pathlib import Path

from build66_ipa_preflight import AdmissionDenied, inspect_ipa
from webreader_update_manifest import ManifestRejected, validate


class SignedReleaseRejected(ValueError):
    pass


def _ios_tuple(value):
    # Both manifest and IPA validators have already checked format/compatibility.
    parts = tuple(int(component) for component in value.split("."))
    return parts + (0,) * (3 - len(parts))


def verify_signed_release(
    envelope_json, pinned_public_key_pem, ipa_path,
    installed_build=65, installed_ios="12.5.8", *, include_snapshot=False
):
    """Check signed metadata against the locally staged IPA, entirely offline.

    Public key must come from a separately trusted/pinned distribution channel.
    Never accept a public key supplied alongside the untrusted manifest/IPA.
    """
    if type(include_snapshot) is not bool:
        raise SignedReleaseRejected("invalid snapshot policy")
    if type(installed_build) is not int or installed_build < 0:
        raise SignedReleaseRejected("invalid installed build")
    if installed_ios != "12.5.8":
        raise SignedReleaseRejected("host-only iOS 12.5.8 preflight")
    if not isinstance(envelope_json, bytes) or not isinstance(pinned_public_key_pem, bytes):
        raise SignedReleaseRejected("missing trusted signature inputs")
    try:
        signed = validate(envelope_json, pinned_public_key_pem, installed_build, installed_ios)
        # Structural, executable-name and digest checks all inspect ONE
        # hash-verified snapshot from a single O_NOFOLLOW file descriptor.
        # Do not reopen an attacker-controlled path after this point.
        inspected = inspect_ipa(
            Path(ipa_path), signed["sha256"], signed["ipaSize"], installed_build,
            require_exact_identity=True, return_snapshot=include_snapshot
        )
    except (ManifestRejected, AdmissionDenied, OSError, TypeError) as exc:
        raise SignedReleaseRejected("signed manifest or IPA preflight rejected") from exc

    if (signed["build"] != inspected["build"] or
            signed["bundleId"] != inspected["bundle"] or
            _ios_tuple(signed["minimumIOS"]) != _ios_tuple(inspected["minimum_ios"]) or
            signed["ipaSize"] != inspected["ipa_size"] or
            signed["sha256"] != inspected["sha256"]):
        raise SignedReleaseRejected("signed manifest does not match IPA metadata")

    result = {
        "build": signed["build"],
        "bundleId": signed["bundleId"],
        "minimumIOS": signed["minimumIOS"],
        "sha256": signed["sha256"],
        "ipaSize": signed["ipaSize"],
        "releaseURL": signed["ipaUrl"],
        "signed_manifest_verified": True,
        "ipa_metadata_matches_manifest": True,
        "single_snapshot_checked": True,
        "code_signature_verified": False,
        "install_authorized": False,
        "installation_performed": False,
    }
    if include_snapshot:
        result["ipa_snapshot"] = inspected["ipa_snapshot"]
    return result
