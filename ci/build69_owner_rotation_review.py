#!/usr/bin/env python3
"""Build69 AU: offline dual-key rotation review with independent successor pin.

Never activates, revokes, generates, writes or uploads signing keys. An old
compromised/revoked key cannot use this path to self-authorize a successor:
recovery requires separately approved, physically installed app trust root.
"""
from build68_release_key_lifecycle_review import (
    LifecycleReviewDenied, inspect_unapplied_rotation
)
from build68_release_public_key_handoff import (
    PublicKeyHandoffRejected, prepare_public_key_handoff
)

class OwnerRotationRejected(ValueError):
    pass


def review_owner_rotation(*, old_public_pem: bytes, successor_public_pem: bytes,
                          independent_old_spki: str, independent_successor_spki: str,
                          dual_signed_envelope: bytes, current_generation: int,
                          installed_build: int, revoked_pins=()):
    if type(current_generation) is not int or current_generation < 1:
        raise OwnerRotationRejected("already-provisioned owner key required")
    if type(installed_build) is not int or installed_build < 68:
        raise OwnerRotationRejected("physically approved Build68+ required")
    try:
        proposed = prepare_public_key_handoff(
            successor_public_pem, independent_successor_spki
        )
        result = inspect_unapplied_rotation(
            dual_signed_envelope=dual_signed_envelope,
            old_public_pem=old_public_pem,
            proposed_public_pem=successor_public_pem,
            independently_pinned_old_spki=independent_old_spki,
            current_generation=current_generation,
            installed_build=installed_build,
            revoked_spki_pins=revoked_pins
        )
    except (PublicKeyHandoffRejected, LifecycleReviewDenied) as exc:
        raise OwnerRotationRejected(
            "two independently pinned public keys or dual-signature rotation rejected"
        ) from exc
    if result.successor_spki_sha256 != proposed.canonical_spki_sha256:
        raise OwnerRotationRejected("independent successor pin conflicts with signed claim")
    return {
        "status": "dual_signature_review_only",
        "oldSPKISHA256": result.old_spki_sha256,
        "successorSPKISHA256": proposed.canonical_spki_sha256,
        "successorPublicX963Hex": proposed.x963_public_key_hex,
        "proposedGeneration": result.proposed_generation,
        "proposedActivationBuild": result.activates_at_build,
        "dualSignatureChainVerified": result.dual_signature_candidate_verified,
        "successorMatchesProvidedIndependentPin": True,
        "ownerIndependentApprovalVerifiedByScript": False,
        "ownerPublicationApprovalRecorded": False,
        "revocationsUpdatedOnDevice": False,
        "successorTrustRootInstalledInApp": False,
        "automaticRecoveryFromRevokedKeyAllowed": False,
        "manualRebootstrapRequiredIfOldKeyCompromised": True,
        "githubReleasePublished": False,
        "mainModified": False,
        "chimeraInstallationAuthorized": False,
        "installationPerformed": False,
    }
