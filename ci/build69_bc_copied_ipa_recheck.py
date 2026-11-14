#!/usr/bin/env python3
"""Build69 BC: verify a COPIED private-QA IPA against prior host receipt.

Read-only and cross-platform: PC/Android transfer verification, NOT package
signing or editor authentication. A JSON receipt and checksum file can both be
forged, so the owner must obtain/verify the SHA-256 independently of the copy.
No downloads, code execution, repository writes, GitHub release or installation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from build69_bb_private_qa_ipa_preflight import (
    QA_FILE_NAME, PrivateQAPreflightRejected, parse_independent_checksum
)
from build66_ipa_preflight import MAX_IPA_BYTES
from build69_production_release_preflight import _read_external_regular

ROOT = Path(__file__).resolve().parent.parent.resolve()
RECEIPT_MAX_BYTES = 16 * 1024
FALSE_FLAGS = (
    "publisherAuthenticatedByCodeSignature",
    "deviceInstallationCompatibilityProven",
    "qaPhysicalTestCompleted",
    "backupAndOfflineLibraryPreservationProven",
    "editorialProductionKeyProvisioned",
    "ownerDistributionApprovalRecorded",
    "readyForDistribution",
    "githubReleasePublished",
    "mainModified",
    "chimeraInstallationAuthorized",
    "installationAuthorized",
    "installationPerformed",
)
TRUE_FLAGS = (
    "checksumMatchesIndependentlySuppliedFile",
    "adHocSignatureIntegrityVerified",
    "installedApplicationIdentifierMatch",
)


class CopiedQARejected(ValueError):
    pass


def _unique_json_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise CopiedQARejected("duplicate receipt field")
        obj[key] = value
    return obj


def parse_host_receipt(receipt_data):
    if type(receipt_data) is not bytes or not 0 < len(receipt_data) <= RECEIPT_MAX_BYTES:
        raise CopiedQARejected("bounded BB host receipt required")
    try:
        receipt = json.loads(
            receipt_data.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda _: (_ for _ in ()).throw(
                CopiedQARejected("non-finite number is not a valid receipt")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CopiedQARejected("invalid host receipt") from exc
    if type(receipt) is not dict:
        raise CopiedQARejected("host receipt must be a JSON object")
    required_literals = {
        "status": "HOST_ONLY_PRIVATE_QA_PREFLIGHT_NOT_DISTRIBUTION_APPROVAL",
        "build": 69,
        "installedBuildBaseline": 68,
        "bundleID": "com.example.MangaReader12",
        "minimumIOS": "12.0",
        "actualExecutableMinimumIOS": "12.0",
        "binaryArchitecture": "arm64",
        "verifiedApplicationIdentifier":
            "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
    }
    for name, expected in required_literals.items():
        if type(receipt.get(name)) is not type(expected) or receipt[name] != expected:
            raise CopiedQARejected("wrong host receipt identity or QA version")
    for name in FALSE_FLAGS:
        if receipt.get(name) is not False:
            raise CopiedQARejected("host receipt falsely claims installation authority")
    for name in TRUE_FLAGS:
        if receipt.get(name) is not True:
            raise CopiedQARejected("host QA did not verify native code identity")
    if (type(receipt.get("ipaSize")) is not int
            or not 0 < receipt["ipaSize"] <= MAX_IPA_BYTES
            or type(receipt.get("ipaSHA256")) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", receipt["ipaSHA256"])
            or type(receipt.get("codeDirectoryCDHash")) is not str
            or not re.fullmatch(r"[0-9a-f]{40}", receipt["codeDirectoryCDHash"])):
        raise CopiedQARejected("missing bounded IPA or CodeDirectory fingerprint")
    return receipt


def _hash_single_regular_file(path, max_bytes):
    path = Path(path)
    if not hasattr(os, "O_NOFOLLOW") or path.is_symlink():
        raise CopiedQARejected("unsupported or symlinked IPA")
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as f:
            initial = os.fstat(f.fileno())
            if not stat.S_ISREG(initial.st_mode) or not 0 < initial.st_size <= max_bytes:
                raise CopiedQARejected("invalid copied IPA size or type")
            sha = hashlib.sha256()
            length = 0
            while True:
                block = f.read(1024 * 1024)
                if not block:
                    break
                length += len(block)
                if length > max_bytes:
                    raise CopiedQARejected("copied IPA exceeds size limit")
                sha.update(block)
            after = os.fstat(f.fileno())
            if (initial.st_dev, initial.st_ino, initial.st_size,
                initial.st_ctime_ns, initial.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size,
                after.st_ctime_ns, after.st_mtime_ns):
                raise CopiedQARejected("copied IPA changed during transfer recheck")
            if length != initial.st_size:
                raise CopiedQARejected("copied IPA read size changed")
            return length, sha.hexdigest()
    except OSError as exc:
        raise CopiedQARejected("could not securely inspect copied IPA") from exc


def review_copied_qa_ipa(*, ipa_path, host_receipt_data, owner_checksum_data):
    path = Path(ipa_path)
    if path.name != QA_FILE_NAME:
        raise CopiedQARejected("copied asset filename does not match Build69")
    if path.resolve() == ROOT or ROOT in path.resolve().parents:
        raise CopiedQARejected("copied QA IPA must remain outside source tree")
    receipt = parse_host_receipt(host_receipt_data)
    try:
        owner_sha = parse_independent_checksum(owner_checksum_data)
    except PrivateQAPreflightRejected as exc:
        raise CopiedQARejected("invalid separately supplied checksum") from exc
    if receipt["ipaSHA256"] != owner_sha:
        raise CopiedQARejected("owner checksum conflicts with original host receipt")
    length, observed = _hash_single_regular_file(path, MAX_IPA_BYTES)
    if length != receipt["ipaSize"] or observed != owner_sha:
        raise CopiedQARejected("transferred IPA differs from original audited snapshot")
    # This never re-runs codesign on the destination, and a receipt is only
    # trustworthy after authenticating it through an independent owner channel.
    return {
        "status": "COPIED_BYTES_MATCH_HOST_RECEIPT_ONLY",
        "copiedFileName": QA_FILE_NAME,
        "build": 69,
        "fileSize": length,
        "sha256": observed,
        "originalHostReceiptSHA256": hashlib.sha256(host_receipt_data).hexdigest(),
        "hostCodeDirectoryCDHashClaim": receipt["codeDirectoryCDHash"],
        "matchesHostReceipt": True,
        "matchesSeparatelyProvidedChecksum": True,
        "hostReceiptAuthenticityProvenByTool": False,
        "ownerChecksumIndependenceProvenByTool": False,
        "editorialPublisherAuthenticated": False,
        "destinationCodesignRevalidated": False,
        "physicalIOSUpgradeCompatibilityProven": False,
        "ownerDistributionApprovalRecorded": False,
        "authorizedForInstallation": False,
        "installationPerformed": False,
        "githubReleasePublished": False,
        "mainModified": False,
        "networkUsed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copied-ipa", type=Path, required=True)
    parser.add_argument("--host-receipt", type=Path, required=True)
    parser.add_argument("--owner-checksum-file", type=Path, required=True)
    args = parser.parse_args()
    report = review_copied_qa_ipa(
        ipa_path=args.copied_ipa,
        host_receipt_data=_read_external_regular(args.host_receipt, RECEIPT_MAX_BYTES),
        owner_checksum_data=_read_external_regular(args.owner_checksum_file, 512)
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
