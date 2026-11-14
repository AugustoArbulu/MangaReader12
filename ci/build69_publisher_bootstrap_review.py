#!/usr/bin/env python3
"""Build69 AT — read-only owner public trust bootstrap rehearsal.

No key generation, no private-key read, no network, no repository edits, no IPA,
no installation and no publication. This verifies technical consistency only;
independent owner identity/authority cannot be proven by a CLI supplied pin.
"""
import argparse
import json
from pathlib import Path

from build68_release_public_key_handoff import (
    PublicKeyHandoffRejected, prepare_public_key_handoff
)
from build69_production_release_preflight import _read_external_regular

class OwnerBootstrapRejected(ValueError):
    pass


def review_owner_public_bootstrap(*, public_pem: bytes, independently_verified_pin: str,
                                  trust_generation: int, revoked_pins=(),
                                  installed_build: int = 68) -> dict:
    # This is a proposed *future* root of trust. It is not written to Swift.
    if type(trust_generation) is not int or trust_generation != 1:
        raise OwnerBootstrapRejected("initial owner trust generation must be 1")
    if type(installed_build) is not int or installed_build < 68:
        raise OwnerBootstrapRejected("baseline requires physically accepted Build68 or newer")
    if type(revoked_pins) is not tuple or len(revoked_pins) > 64:
        raise OwnerBootstrapRejected("immutable bounded revocation policy required")
    if (any(type(pin) is not str or len(pin) != 64 or
            any(ch not in "0123456789abcdef" for ch in pin)
            for pin in revoked_pins) or
        len(set(revoked_pins)) != len(revoked_pins)):
        raise OwnerBootstrapRejected("invalid or duplicated revoked SPKI fingerprint")
    try:
        material = prepare_public_key_handoff(public_pem, independently_verified_pin)
    except PublicKeyHandoffRejected as exc:
        raise OwnerBootstrapRejected("public P256 point or independent fingerprint rejected") from exc
    if independently_verified_pin in revoked_pins:
        raise OwnerBootstrapRejected("cannot bootstrap revoked release key")
    return {
        "status": "candidate_review_only",
        "schema": "WebReader-Owner-Publisher-Bootstrap-Review-v1",
        "proposedTrustGeneration": trust_generation,
        "installedBuildBaseline": installed_build,
        "publicKeyAlgorithm": material.algorithm,
        "canonicalSPKISHA256": material.canonical_spki_sha256,
        "publicX963Hex": material.x963_public_key_hex,
        "publicX963LengthBytes": len(bytes.fromhex(material.x963_public_key_hex)),
        "revokedPublicPinCount": len(revoked_pins),
        "ownerIndependenceVerifiedByScript": False,
        "ownerExplicitApprovalRecorded": False,
        "sourceTreeChanged": False,
        "productionKeyProvisionedInApp": False,
        "publicationAuthorized": False,
        "githubReleasePublished": False,
        "ipADistributed": False,
        "chimeraInstallationAuthorized": False,
        "installationPerformed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key", type=Path, required=True,
                        help="public-only PEM outside source repository")
    parser.add_argument("--independent-spki-sha256", required=True,
                        help="verified via separate trusted owner-controlled channel")
    parser.add_argument("--trust-generation", type=int, default=1)
    parser.add_argument("--installed-build", type=int, default=68)
    args = parser.parse_args()
    result = review_owner_public_bootstrap(
        public_pem=_read_external_regular(args.public_key, 4096),
        independently_verified_pin=args.independent_spki_sha256,
        trust_generation=args.trust_generation,
        installed_build=args.installed_build
    )
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
