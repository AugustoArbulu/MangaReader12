#!/usr/bin/env python3
"""Private Build68 manual-QA delivery gate: no installation authority.

The upstream macOS runner builds and audits an ad-hoc IPA in a separate
sandbox. This gate binds its audit JSON, the exact IPA bytes and the SHA256
sidecar before a PRIVATE GitHub Actions QA artifact can be uploaded.

Passing permits ONLY provision of a diagnostic/test artifact to the repository
owner. It is not publisher-signature authentication, in-place device
compatibility proof, permission for appinst, or permission to delete the old app.
"""
from dataclasses import dataclass, asdict
import hashlib
import json
import os
from pathlib import Path
import re
import stat

IPA_NAME = "WebReader-Build68-iOS12-adhoc.ipa"
EXPECTED_ID = "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
EXPECTED_BUNDLE = "com.example.MangaReader12"
MAX_IPA_SIZE = 512 * 1024 * 1024
MAX_RECEIPT_BYTES = 8192
CHECKSUM_LINE = re.compile(r"([0-9a-f]{64})  WebReader-Build68-iOS12-adhoc\.ipa\Z")


class ManualQADeliveryRejected(ValueError):
    pass


@dataclass(frozen=True)
class ManualQADelivery:
    artifact: str
    build: int
    installedBuildReference: int
    sha256: str
    ipaBytes: int
    minimumIOS: str = "12.0"
    bundleID: str = EXPECTED_BUNDLE
    applicationIdentifier: str = EXPECTED_ID
    privateManualQAArtifactEligible: bool = True
    checksumReverificationRequiredAfterTransfer: bool = True
    userBackupAndRollbackRequiredBeforeInstall: bool = True
    releasePublisherAuthenticated: bool = False
    automaticUpdateEnabled: bool = False
    deviceInstallValidated: bool = False
    userApprovedInstallation: bool = False
    privilegedHelperAuthenticated: bool = False
    installationAuthorized: bool = False
    installationPerformed: bool = False


def _unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ManualQADeliveryRejected("duplicate JSON field")
        result[key] = value
    return result


def _read_file_bounded(path, limit):
    # O_NOFOLLOW protects against final-component symlink substitution and
    # fstat checks reject nonregular files and writes while reading.
    if not hasattr(os, "O_NOFOLLOW"):
        raise ManualQADeliveryRejected("symlink protection unavailable")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 <= before.st_size <= limit:
                raise ManualQADeliveryRejected("nonregular or oversized sidecar")
            content = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            if len(content) > limit or before.st_size != len(content):
                raise ManualQADeliveryRejected("sidecar changed size")
            if (before.st_dev, before.st_ino, before.st_mtime_ns,
                    before.st_ctime_ns) != (
                    after.st_dev, after.st_ino, after.st_mtime_ns,
                    after.st_ctime_ns):
                raise ManualQADeliveryRejected("sidecar changed during inspection")
            return content
    except OSError as exc:
        raise ManualQADeliveryRejected("cannot safely read sidecar") from exc


def _hash_ipa(path, claimed_size):
    if not hasattr(os, "O_NOFOLLOW"):
        raise ManualQADeliveryRejected("symlink protection unavailable")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or
                    before.st_size != claimed_size or
                    not 0 < claimed_size <= MAX_IPA_SIZE):
                raise ManualQADeliveryRejected("nonregular or unexpected IPA size")
            h = hashlib.sha256()
            total = 0
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                h.update(block)
                total += len(block)
                if total > MAX_IPA_SIZE:
                    raise ManualQADeliveryRejected("oversized IPA")
            after = os.fstat(stream.fileno())
            if total != claimed_size or (
                before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size,
                after.st_mtime_ns, after.st_ctime_ns
            ):
                raise ManualQADeliveryRejected("candidate modified during hash")
            return h.hexdigest()
    except OSError as exc:
        raise ManualQADeliveryRejected("cannot safely read candidate") from exc


def verify_private_manual_qa(ipa_path, sha256_file, audit_json_file):
    ipa = Path(ipa_path)
    checksum = Path(sha256_file)
    audit_file = Path(audit_json_file)
    if (ipa.name != IPA_NAME or checksum.name != IPA_NAME + ".sha256" or
            audit_file.name != "WebReader-Build68-private-rehearsal-audit.json"):
        raise ManualQADeliveryRejected("unexpected artifact naming")
    raw = _read_file_bounded(audit_file, MAX_RECEIPT_BYTES)
    try:
        receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ManualQADeliveryRejected("invalid JSON audit receipt") from exc
    if not isinstance(receipt, dict):
        raise ManualQADeliveryRejected("invalid audit JSON type")
    expected_true = (
        "nativeAdHocCodeIntegrityVerified",
        "thinArm64Verified",
        "sameInstalledEntitlementIdentifier",
    )
    expected_false = (
        "productionPublisherAuthenticated", "releaseManifestIndependentlySigned",
        "ios12DeviceInstallTested", "userConsentVerified",
        "helperPeerAuthenticated", "installationAuthorized",
        "installationPerformed", "approvedForAutomaticRelease",
    )
    if (receipt.get("status") != "PASS" or
            receipt.get("qaArtifact") != IPA_NAME or
            type(receipt.get("build")) is not int or receipt["build"] != 67 or
            type(receipt.get("upgradesFromObservedBuild")) is not int or
            receipt["upgradesFromObservedBuild"] != 66 or
            receipt.get("minimumIOS") != "12.0" or
            receipt.get("bundleID") != EXPECTED_BUNDLE or
            receipt.get("applicationIdentifier") != EXPECTED_ID or
            type(receipt.get("ipaBytes")) is not int or
            not 0 < receipt["ipaBytes"] <= MAX_IPA_SIZE or
            type(receipt.get("ipaSHA256")) is not str or
            re.fullmatch("[0-9a-f]{64}", receipt["ipaSHA256"]) is None or
            any(receipt.get(k) is not True for k in expected_true) or
            any(receipt.get(k) is not False for k in expected_false)):
        raise ManualQADeliveryRejected("audit did not satisfy manual-only policy")
    raw_checksum = _read_file_bounded(checksum, 256)
    try:
        checksum_line = raw_checksum.decode("ascii")
    except UnicodeError as exc:
        raise ManualQADeliveryRejected("checksum was not ASCII") from exc
    if not checksum_line.endswith("\n") or checksum_line.count("\n") != 1:
        raise ManualQADeliveryRejected("checksum must contain exactly one line")
    match = CHECKSUM_LINE.fullmatch(checksum_line[:-1])
    if not match or match.group(1) != receipt["ipaSHA256"]:
        raise ManualQADeliveryRejected("sidecar differs from audited bytes")
    current_hash = _hash_ipa(ipa, receipt["ipaBytes"])
    if current_hash != match.group(1):
        raise ManualQADeliveryRejected("candidate IPA changed since audit")
    return ManualQADelivery(
        artifact=IPA_NAME,
        build=67,
        installedBuildReference=66,
        sha256=current_hash,
        ipaBytes=receipt["ipaBytes"],
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--sha256-file", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--delivery-report", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify_private_manual_qa(args.ipa, args.sha256_file, args.audit_json)
    target = args.delivery_report
    if target.name != "WebReader-Build68-private-manual-qa-delivery.json" or target.exists():
        raise ManualQADeliveryRejected("unsafe delivery report destination")
    target.write_text(json.dumps(asdict(receipt), sort_keys=True, indent=2) + "\n")
    print(json.dumps(asdict(receipt), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
