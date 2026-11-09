#!/usr/bin/env python3
"""CG — OFFLINE public-only proposal for the initial owner trust root.

Accept a public P-256 PEM and an independently verified SPKI SHA-256.
Produce ONLY an external, owner-reviewable unified diff. Do not apply it.
Never read a private key, enroll trust, modify Git, generate a Release,
contact a server, publish, install, or turn on appinst.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
from pathlib import Path
import re
import stat

from build69_publisher_bootstrap_review import (
    OwnerBootstrapRejected, review_owner_public_bootstrap
)
from build69_production_release_preflight import (
    ProductionPreflightRejected, _read_external_regular
)

ROOT = Path(__file__).resolve().parent.parent.resolve()
KEY_SOURCE = Path("MangaReader12/Core/WebReaderUpdateChecker.swift")
TRUST_SOURCE = Path("MangaReader12/Core/WebReaderProductionPublisherTrust.swift")
INSTALL_SOURCE = Path("MangaReader12/Core/WebReaderAppinstSocket.swift")
PROJECT_SOURCE = Path("MangaReader12.xcodeproj/project.pbxproj")
OLD_KEY = "static let productionPublicKeyX963: Data? = nil"
OLD_PIN = "static let independentlyProvisionedSPKISHA256: String? = nil"
OLD_GENERATION = "static let productionTrustGeneration = 0"
OLD_INSTALL = "static let liveInstallationEnabled = false"


class OwnerPublicProposalRejected(ValueError):
    pass


def _exact_replace(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise OwnerPublicProposalRejected("reviewed compiled-root source changed")
    return source.replace(old, new, 1)


def _source(path: Path) -> str:
    full = ROOT / path
    if full.is_symlink() or not full.is_file():
        raise OwnerPublicProposalRejected("compiled-root source missing")
    return full.read_text(encoding="utf-8")


def _proposal(handoff: dict, installed_build: int) -> tuple[str, dict]:
    if type(installed_build) is not int or installed_build < 70:
        raise OwnerPublicProposalRejected("Build70 owner baseline required")
    project = _source(PROJECT_SOURCE)
    if project.count("CURRENT_PROJECT_VERSION = 56;") != 2:
        raise OwnerPublicProposalRejected("versioned iOS12 project source changed")
    installer = _source(INSTALL_SOURCE)
    if installer.count(OLD_INSTALL) != 1:
        raise OwnerPublicProposalRejected("installer no longer fail-closed")
    key_file = _source(KEY_SOURCE)
    trust_file = _source(TRUST_SOURCE)
    if trust_file.count("static let revokedPublisherPins: Set<String> = []") != 1:
        raise OwnerPublicProposalRejected("unexpected trust revocations")
    x963 = bytes.fromhex(handoff["publicX963Hex"])
    if len(x963) != 65 or x963[0] != 4:
        raise OwnerPublicProposalRejected("invalid owner public P-256 point")
    if (not re.fullmatch(r"[0-9a-f]{64}", handoff["canonicalSPKISHA256"])
            or handoff["proposedTrustGeneration"] != 1
            or handoff["productionKeyProvisionedInApp"] is not False):
        raise OwnerPublicProposalRejected("untrusted public owner proposal")
    key_bytes = ", ".join("0x" + format(b, "02x") for b in x963)
    # Single public-only constant. No private signing key is ever generated.
    public_constant = (
        "static let productionPublicKeyX963: Data? = Data(["
        + key_bytes + "])"
    )
    updated_key = _exact_replace(key_file, OLD_KEY, public_constant)
    updated_trust = _exact_replace(
        trust_file, OLD_PIN,
        'static let independentlyProvisionedSPKISHA256: String? = "'
        + handoff["canonicalSPKISHA256"] + '"'
    )
    updated_trust = _exact_replace(
        updated_trust, OLD_GENERATION,
        "static let productionTrustGeneration = 1"
    )
    patches = []
    for filename, previous, revised in (
        (KEY_SOURCE, key_file, updated_key),
        (TRUST_SOURCE, trust_file, updated_trust),
    ):
        patch = "".join(difflib.unified_diff(
            previous.splitlines(keepends=True),
            revised.splitlines(keepends=True),
            fromfile="a/" + filename.as_posix(),
            tofile="b/" + filename.as_posix(),
            n=3
        ))
        if not patch:
            raise OwnerPublicProposalRejected("missing public root diff")
        patches.append(patch)
    return "".join(patches), {
        "schema": "WebReader-CG-Initial-Owner-Public-Root-Proposal-v1",
        "installedBuildReference": installed_build,
        "publicKeyAlgorithm": "ecdsa-p256-sha256",
        "canonicalSPKISHA256": handoff["canonicalSPKISHA256"],
        "proposedTrustGeneration": 1,
        "compiledPublicRootFilesToReview": [
            KEY_SOURCE.as_posix(), TRUST_SOURCE.as_posix()
        ],
        "privateKeyReadOrCreated": False,
        "ownerIdentityIndependentlyEstablishedByTool": False,
        "ownerExplicitApprovalRecorded": False,
        "sourceTreeChanged": False,
        "proposedSourcePatchApplied": False,
        "productionTrustActivated": False,
        "publisherChannelPublished": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def propose_public_root(*, public_pem: bytes, independently_verified_pin: str,
                        installed_build: int = 70) -> tuple[str, dict]:
    try:
        reviewed = review_owner_public_bootstrap(
            public_pem=public_pem,
            independently_verified_pin=independently_verified_pin,
            trust_generation=1,
            revoked_pins=(),
            installed_build=installed_build
        )
    except OwnerBootstrapRejected as exc:
        raise OwnerPublicProposalRejected("public key/pin review failed") from exc
    return _proposal(reviewed, installed_build)


def write_external_proposal(patch: str, destination: Path) -> None:
    if type(patch) is not str or not 0 < len(patch) < 32 * 1024:
        raise OwnerPublicProposalRejected("public patch outside size limit")
    dest = Path(destination)
    resolved = dest.resolve()
    if dest.is_symlink() or resolved == ROOT or ROOT in resolved.parents:
        raise OwnerPublicProposalRejected("output must be outside repository")
    parent = dest.parent
    if not parent.is_dir() or parent.is_symlink() or dest.exists():
        raise OwnerPublicProposalRejected("output parent is unsafe or already exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        handle = os.open(str(dest), flags, 0o600)
        with os.fdopen(handle, "wb") as out:
            before = os.fstat(out.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise OwnerPublicProposalRejected("public patch output not a file")
            out.write(patch.encode("utf-8"))
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        # Avoid silently publishing partial material after a failed write.
        dest.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--independent-spki-sha256", required=True)
    parser.add_argument("--output-patch", type=Path, required=True)
    parser.add_argument("--installed-build", type=int, default=70)
    args = parser.parse_args()
    try:
        public = _read_external_regular(args.public_key, 4096)
        diff, receipt = propose_public_root(
            public_pem=public,
            independently_verified_pin=args.independent_spki_sha256,
            installed_build=args.installed_build
        )
        write_external_proposal(diff, args.output_patch)
    except ProductionPreflightRejected as exc:
        raise SystemExit("BLOCKED: external public PEM is inaccessible") from exc
    print(json.dumps(
        {**receipt, "reviewPatchBytes": len(diff.encode("utf-8")),
         "externalPatch": str(args.output_patch)}, sort_keys=True, indent=2
    ))


if __name__ == "__main__":
    main()
