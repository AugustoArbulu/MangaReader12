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
from validate_webreader_ipa import IPARejected, validate_ipa
from webreader_update_manifest import ManifestRejected, validate


class SignedReleaseRejected(ValueError):
    pass


def _ios_tuple(value):
    # Both manifest and IPA validators have already checked format/compatibility.
    parts = tuple(int(component) for component in value.split("."))
    return parts + (0,) * (3 - len(parts))


def verify_signed_release(
    envelope_json, pinned_public_key_pem, ipa_path,
    installed_build=65, installed_ios="12.5.8"
):
    """Check signed metadata against the locally staged IPA, entirely offline.

    Public key must come from a separately trusted/pinned distribution channel.
    Never accept a public key supplied alongside the untrusted manifest/IPA.
    """
    if type(installed_build) is not int or installed_build < 0:
        raise SignedReleaseRejected("invalid installed build")
    if installed_ios != "12.5.8":
        raise SignedReleaseRejected("host-only iOS 12.5.8 preflight")
    if not isinstance(envelope_json, bytes) or not isinstance(pinned_public_key_pem, bytes):
        raise SignedReleaseRejected("missing trusted signature inputs")
    try:
        signed = validate(envelope_json, pinned_public_key_pem, installed_build, installed_ios)
        # The descriptor-based preflight rejects a final-component symlink and
        # hashes a single consistent snapshot; never pass its path to appinst.
        inspected = inspect_ipa(
            Path(ipa_path), signed["sha256"], signed["ipaSize"], installed_build
        )
        # Existing stricter IPA validator additionally enforces exact app name,
        # executable, display name and safe Payload paths.
        structural = validate_ipa(
            Path(ipa_path), signed["sha256"], installed_build, installed_ios
        )
    except (ManifestRejected, AdmissionDenied, IPARejected, OSError, TypeError) as exc:
        raise SignedReleaseRejected("signed manifest or IPA preflight rejected") from exc

    if (signed["build"] != inspected["build"] or
            signed["build"] != structural["build"] or
            signed["bundleId"] != structural["bundleId"] or
            _ios_tuple(signed["minimumIOS"]) != _ios_tuple(inspected["minimum_ios"]) or
            _ios_tuple(signed["minimumIOS"]) != _ios_tuple(structural["minimumIOS"]) or
            signed["ipaSize"] != structural["bytes"] or
            signed["sha256"] != inspected["sha256"] or
            signed["sha256"] != structural["sha256"]):
        raise SignedReleaseRejected("signed manifest does not match IPA metadata")

    return {
        "build": signed["build"],
        "bundleId": signed["bundleId"],
        "minimumIOS": signed["minimumIOS"],
        "sha256": signed["sha256"],
        "ipaSize": signed["ipaSize"],
        "releaseURL": signed["ipaUrl"],
        "signed_manifest_verified": True,
        "ipa_metadata_matches_manifest": True,
        "code_signature_verified": False,
        "install_authorized": False,
        "installation_performed": False,
    }
