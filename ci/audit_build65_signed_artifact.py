#!/usr/bin/env python3
"""Read-only audit of the approved Build65 QA artifact from GitHub Actions.

This is NOT an updater, an iOS installation test, or a release certificate.
Requires macOS native codesign and an exact pinned known-good IPA digest.
Never modifies, signs or installs the candidate IPA.
"""
import argparse
import hashlib
import json
from pathlib import Path

from build66_ipa_preflight import inspect_ipa, AdmissionDenied
from build66_code_signature_gate import (
    audit_code_signature_snapshot, CodeSignatureRejected,
    INSTALLED_APPLICATION_IDENTIFIER,
)

# Known-good manual QA Build65 artifact (run 42263333598, artifact 13526372276).
# Pin from the approved manual QA handoff, never from the downloaded artifact.
APPROVED_BUILD65_SHA256 = (
    "798d2bc9472e626eea9dd9c794fb7d6053b4eac01d288e86d0f04a3c092af10a"
)


def audit_build65(ipa: Path, checksum_file: Path):
    ipa = Path(ipa)
    checksum_file = Path(checksum_file)
    fields = checksum_file.read_text("utf-8").strip().split()
    if len(fields) != 2 or fields[0] != APPROVED_BUILD65_SHA256 or fields[1] != ipa.name:
        raise ValueError("artifact checksum sidecar does not match pinned Build65")
    inspected = inspect_ipa(
        ipa, APPROVED_BUILD65_SHA256, ipa.stat().st_size, 64,
        require_exact_identity=True, return_snapshot=True
    )
    if inspected["build"] != 65 or inspected["minimum_ios"] != "12.0":
        raise ValueError("not the approved Build65 metadata")
    snapshot = inspected.pop("ipa_snapshot")
    if hashlib.sha256(snapshot).hexdigest() != APPROVED_BUILD65_SHA256:
        raise ValueError("approved Build65 byte hash mismatch")
    identity = audit_code_signature_snapshot(
        snapshot, APPROVED_BUILD65_SHA256, inspected["ipa_size"]
    )
    if identity["applicationIdentifier"] != INSTALLED_APPLICATION_IDENTIFIER:
        raise ValueError("installed app entitlement mismatch")
    return {
        "build": 65,
        "bundleId": inspected["bundle"],
        "sha256MatchesPinnedApprovedBuild65": True,
        "nativeCodeSignatureIntegrityVerified": identity["adHocSignatureIntegrityVerified"],
        "thinArm64ExecutableVerified": identity["thinArm64ExecutableVerified"],
        "installedApplicationIdentifierMatch": identity["installedApplicationIdentifierMatch"],
        "publisherAuthenticatedByAdHocSignature": False,
        "deviceInstallTested": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--checksum-file", type=Path, required=True)
    options = parser.parse_args()
    try:
        print(json.dumps(
            audit_build65(options.ipa, options.checksum_file), sort_keys=True, indent=2
        ))
    except (OSError, ValueError, AdmissionDenied, CodeSignatureRejected) as error:
        parser.error("Build65 artifact audit rejected: " + str(error))
