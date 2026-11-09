#!/usr/bin/env python3
"""Offline, read-only *production* Release preflight; never publish or install.

Run on macOS with a genuine already-signed IPA, a separately supplied trusted
SPKI fingerprint and an existing ECDSA v2 production manifest. This tool never
generates/imports private keys, provisions trust in iOS, uploads, or invokes appinst.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

from build68_release_public_key_handoff import (
    PublicKeyHandoffRejected, prepare_public_key_handoff
)
from build66_signed_release_preflight import (
    SignedReleaseRejected, verify_signed_release
)
from build66_code_signature_gate import (
    CodeSignatureRejected, audit_code_signature_snapshot
)

REPO = Path(__file__).resolve().parent.parent.resolve()


class ProductionPreflightRejected(ValueError):
    pass


def _read_external_regular(path, max_bytes):
    """Do not accept repo-managed, symlinked, changed or oversized inputs."""
    path = Path(path)
    if path.is_symlink() or path.resolve() == REPO or REPO in path.resolve().parents:
        raise ProductionPreflightRejected("production inputs must stay outside source tree")
    if not hasattr(os, "O_NOFOLLOW"):
        raise ProductionPreflightRejected("platform lacks no-follow file opening")
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= max_bytes:
                raise ProductionPreflightRejected("invalid bounded input file")
            content = handle.read(max_bytes + 1)
            after = os.fstat(handle.fileno())
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                    before.st_ctime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
                    after.st_ctime_ns) or len(content) != before.st_size:
                raise ProductionPreflightRejected("input changed during read")
            return content
    except OSError as exc:
        raise ProductionPreflightRejected("cannot read input securely") from exc


def review_production_release(*, public_key_pem, independent_spki_sha256,
                              manifest_v2, ipa_path, installed_build=68):
    if type(installed_build) is not int or installed_build < 68:
        raise ProductionPreflightRejected("explicit installed Build68+ baseline required")
    try:
        owner_key = prepare_public_key_handoff(
            public_key_pem, independent_spki_sha256
        )
        result = verify_signed_release(
            manifest_v2, public_key_pem, ipa_path, installed_build=installed_build,
            installed_ios="12.5.8", include_snapshot=True,
            expected_channel="production"
        )
        expected_name = "WebReader-Build" + str(result["build"]) + "-iOS12-adhoc.ipa"
        if Path(ipa_path).name != expected_name:
            raise ProductionPreflightRejected("staged IPA filename does not match release asset")
        snapshot = result.pop("ipa_snapshot")
        code_seal = audit_code_signature_snapshot(
            snapshot, result["sha256"], result["ipaSize"]
        )
    except (PublicKeyHandoffRejected, SignedReleaseRejected,
            CodeSignatureRejected) as exc:
        raise ProductionPreflightRejected("production signature, pin or IPA rejected") from exc
    if not (code_seal["adHocSignatureIntegrityVerified"] and
            code_seal["installedApplicationIdentifierMatch"] and
            code_seal["thinArm64ExecutableVerified"]):
        raise ProductionPreflightRejected("native signed application identity denied")
    return {
        "status": "offline_review_only",
        "channel": "production",
        "schemaVersion": 2,
        "build": result["build"],
        "installedBuildReviewed": installed_build,
        "publicSPKISHA256": owner_key.canonical_spki_sha256,
        "publicX963Hex": owner_key.x963_public_key_hex,
        "manifestSHA256": hashlib.sha256(manifest_v2).hexdigest(),
        "ipaSHA256": result["sha256"],
        "ipaSize": result["ipaSize"],
        "releaseURL": result["releaseURL"],
        "releaseManifestDestination": "updates/channel-production-v2.json",
        "nativeCodeSealVerified": True,
        "independentPublicPinMatched": True,
        "publicKeyProvisionedOnDevice": False,
        "ownerPublicationApprovalRecorded": False,
        "githubReleasePublished": False,
        "mainModified": False,
        "chimeraPeerAuthenticated": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--independent-spki-sha256", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--installed-build", type=int, required=True)
    args = parser.parse_args()
    report = review_production_release(
        public_key_pem=_read_external_regular(args.public_key, 4096),
        independent_spki_sha256=args.independent_spki_sha256,
        manifest_v2=_read_external_regular(args.manifest, 64 * 1024),
        ipa_path=args.ipa, installed_build=args.installed_build
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
