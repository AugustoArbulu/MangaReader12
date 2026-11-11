#!/usr/bin/env python3
"""Build70 DX: immutable original Actions QA ZIP vs optional DQ installed-app TEXT.

This is a STRICT OFFLINE HOST comparison, never device attestation. An owner
can supply the original archived ZIP and separately capture DQ from the
installed Build70 bundle. Text can be forged or obtained from another device.
This does not install, sign, unpack to filesystem, copy data, read offline
images, approve distribution or authorize an update.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import plistlib
import stat
import zipfile

from build69_production_release_preflight import (
    ProductionPreflightRejected, _read_external_regular,
)
from build70_dj_continuity_report_compare import DJRejected, _read_file_once
from build70_dq_installed_bundle_report import (
    DQReportRejected, inspect_dq_text,
    HISTORICAL_ENTITLEMENT, EXPECTED_BUNDLE,
)

ORIGINAL_ARCHIVE_SHA256 = "026c4097af0b24b38ec573cbef9093ff1082496e1e905ce427d42f06f09b3d70"
ORIGINAL_IPA_SHA256 = "526291cc77203c3881e5f3f1c75904e8863dbde3b3bd9df7e1185c3229fb4fc1"
ORIGINAL_IPA_SIZE = 17845463
ORIGINAL_CD_HASH = "e0de7f55a2684da7507c3a862247480bd05c39bd"
ORIGINAL_SOURCE_SHA = "ae931abb725977a417a1fcb20b79c82af825dd55"
ORIGINAL_ACTIONS_RUN = 42705903886
ORIGINAL_IPA_NAME = "WebReader-Build70-iOS12-adhoc.ipa"
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MEMBERS = frozenset((
    ORIGINAL_IPA_NAME,
    ORIGINAL_IPA_NAME + ".sha256",
    "WebReader-Build70-private-qa-audit.json",
    "WebReader-Build70-second-preflight.json",
    "WebReader-Build70-source-provenance.json",
    "WebReader-Build70-packager-summary.json",
))
MAX_REPORT_JSON_BYTES = 8192


class DXRejected(ValueError):
    pass


def _strict_json(content: bytes) -> dict:
    if len(content) > MAX_REPORT_JSON_BYTES:
        raise DXRejected("oversized historical engineering receipt")
    def pairs(values):
        result = {}
        for key, val in values:
            if key in result:
                raise DXRejected("duplicate historical receipt key")
            result[key] = val
        return result
    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=pairs)
    except (ValueError, UnicodeError) as exc:
        raise DXRejected("invalid historical engineering receipt") from exc
    if not isinstance(value, dict):
        raise DXRejected("invalid historical engineering receipt shape")
    return value


def _historical_receipt(result: dict) -> None:
    fixed = {
        "status": "HOST_ONLY_PRIVATE_QA_PREFLIGHT_NOT_DISTRIBUTION_APPROVAL",
        "build": 70,
        "bundleID": EXPECTED_BUNDLE,
        "minimumIOS": "12.0",
        "actualExecutableMinimumIOS": "12.0",
        "binaryArchitecture": "arm64",
        "ipaSHA256": ORIGINAL_IPA_SHA256,
        "ipaSize": ORIGINAL_IPA_SIZE,
        "codeDirectoryCDHash": ORIGINAL_CD_HASH,
        "verifiedApplicationIdentifier": HISTORICAL_ENTITLEMENT,
        "installedApplicationIdentifierMatch": True,
        "adHocSignatureIntegrityVerified": True,
        "publisherAuthenticatedByCodeSignature": False,
        "deviceInstallationCompatibilityProven": False,
        "ownerDistributionApprovalRecorded": False,
        "readyForDistribution": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }
    for key, value in fixed.items():
        if key not in result or type(result[key]) is not type(value) or result[key] != value:
            raise DXRejected("historical preflight mismatch: " + key)


def inspect_dx_archive_and_device_text(
    archive_bytes: bytes, dq_text: bytes,
) -> dict:
    """Return textual comparison, never installation approval/physical proof."""
    if type(archive_bytes) is not bytes or not 0 < len(archive_bytes) <= MAX_ARCHIVE_BYTES:
        raise DXRejected("missing/oversized historical archive")
    if hashlib.sha256(archive_bytes).hexdigest() != ORIGINAL_ARCHIVE_SHA256:
        raise DXRejected("archive SHA256 does not match immutable Actions artifact")
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            entries = archive.infolist()
            if len(entries) != len(MEMBERS) or {x.filename for x in entries} != MEMBERS:
                raise DXRejected("archive has unexpected/missing/duplicate members")
            if any(
                x.flag_bits & 1 or x.is_dir() or
                ((x.external_attr >> 16) & 0o170000) not in (0, stat.S_IFREG)
                for x in entries
            ):
                raise DXRejected("encrypted, linked or nonregular archive member")
            if any(
                x.file_size <= 0 or
                x.file_size > (ORIGINAL_IPA_SIZE if x.filename == ORIGINAL_IPA_NAME
                               else MAX_REPORT_JSON_BYTES)
                for x in entries
            ):
                raise DXRejected("archive member size not bounded")
            ipa_bytes = archive.read(ORIGINAL_IPA_NAME)
            if (
                len(ipa_bytes) != ORIGINAL_IPA_SIZE or
                hashlib.sha256(ipa_bytes).hexdigest() != ORIGINAL_IPA_SHA256
            ):
                raise DXRejected("original IPA bytes do not match pinned hash")
            checksum = archive.read(ORIGINAL_IPA_NAME + ".sha256")
            if checksum != (ORIGINAL_IPA_SHA256 + "  " + ORIGINAL_IPA_NAME + "\n").encode():
                raise DXRejected("original checksum file mismatched")
            first = _strict_json(archive.read("WebReader-Build70-private-qa-audit.json"))
            second = _strict_json(archive.read("WebReader-Build70-second-preflight.json"))
            provenance = _strict_json(archive.read("WebReader-Build70-source-provenance.json"))
            package = _strict_json(archive.read("WebReader-Build70-packager-summary.json"))
    except (OSError, KeyError, EOFError, RuntimeError, zipfile.BadZipFile) as exc:
        if isinstance(exc, DXRejected):
            raise
        raise DXRejected("invalid historical archive ZIP") from exc

    _historical_receipt(first)
    _historical_receipt(second)
    facts = (
        (provenance, "sourceCommit", ORIGINAL_SOURCE_SHA),
        (provenance, "githubActionsRun", ORIGINAL_ACTIONS_RUN),
        (provenance, "sha256", ORIGINAL_IPA_SHA256),
        (provenance, "ipaBytes", ORIGINAL_IPA_SIZE),
        (provenance, "deviceInstallTested", False),
        (provenance, "installationAuthorized", False),
        (provenance, "installationPerformed", False),
        (package, "sourceCommit", ORIGINAL_SOURCE_SHA),
        (package, "sha256", ORIGINAL_IPA_SHA256),
        (package, "ipaBytes", ORIGINAL_IPA_SIZE),
        (package, "publishedAsGitHubRelease", False),
    )
    for receipt, key, expected in facts:
        if key not in receipt or type(receipt[key]) is not type(expected) or receipt[key] != expected:
            raise DXRejected("original archive provenance rejected: " + key)

    try:
        with zipfile.ZipFile(io.BytesIO(ipa_bytes)) as inner:
            infos = inner.infolist()
            name = "Payload/MangaReader12.app/Info.plist"
            matched = [x for x in infos if x.filename == name]
            if len(matched) != 1 or matched[0].file_size > 1024 * 1024:
                raise DXRejected("original IPA Info.plist unavailable/ambiguous")
            plist = plistlib.loads(inner.read(name))
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile,
            plistlib.InvalidFileException) as exc:
        if isinstance(exc, DXRejected):
            raise
        raise DXRejected("original IPA metadata unreadable") from exc
    if (
        not isinstance(plist, dict)
        or plist.get("CFBundleIdentifier") != EXPECTED_BUNDLE
        or plist.get("CFBundleVersion") != "70"
        or plist.get("MinimumOSVersion") != "12.0"
        or plist.get("CFBundleExecutable") != "MangaReader12"
    ):
        raise DXRejected("historical IPA identity contradicts pinned receipt")

    try:
        dq = inspect_dq_text(dq_text)
    except DQReportRejected as exc:
        raise DXRejected("noncanonical installed-app DQ text") from exc

    if dq["status"] == "DQ_REPORTED_BUNDLE_VERSION_OR_ENTITLEMENT_MISMATCH_STOP_QA":
        status = "DX_STOP_REPORTED_INSTALLED_IDENTITY_DIFFERS_FROM_ARCHIVE"
    elif dq["status"] == "DQ_REPORTED_INSTALLED_IDENTITY_FIELDS_UNAVAILABLE":
        status = "DX_WAIT_REPORTED_INSTALLED_IDENTITY_INCOMPLETE"
    elif dq["status"] == "DQ_REPORTED_MATCH_HISTORICAL_METADATA_NOT_ATTESTED":
        status = "DX_ARCHIVED_PACKAGE_MATCHES_DQ_TEXT_ONLY_NOT_DEVICE_ATTESTED"
    else:
        raise DXRejected("unexpected DQ status")

    return {
        "status": status,
        "referenceActionsRun": ORIGINAL_ACTIONS_RUN,
        "referenceBuild": 70,
        "targetIOS": "12.5.8",
        "archivedIPABytes": ORIGINAL_IPA_SIZE,
        "archivedIPASHA256": ORIGINAL_IPA_SHA256,
        "archivedCodeDirectoryCDHashFromHistoricalNativeReceipts": ORIGINAL_CD_HASH,
        "referenceBundleID": EXPECTED_BUNDLE,
        "referenceApplicationIdentifierEntitlement": HISTORICAL_ENTITLEMENT,
        "dqReportedBundleID": dq["reportedBundleID"],
        "dqReportedBuild": dq["reportedInstalledBuild"],
        "dqReportedApplicationIdentifier": dq["reportedApplicationIdentifierEntitlement"],
        "dqTextMatchesReference": dq["allThreeValuesTextuallyMatchHistorical"],
        "archivedArtifactMatchesPinnedOriginalBytes": True,
        "archivedNativeCodeSealReverifiedInThisComparison": False,
        "dqTextOriginCryptographicallyAuthenticated": False,
        "currentlyInstalledBuild70CryptographicallyAttested": False,
        "deviceAndArchiveSameCodeDirectoryProven": False,
        "physicalBundleDataContainerPreservationProven": False,
        "physicalOfflineChapterPagesVerified": False,
        "externalBackupValidated": False,
        "publisherAuthenticated": False,
        "ownerPrivateQADistributionConsentRecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "automaticUpdaterEnabled": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", required=True, type=Path)
    cli.add_argument("--dq", required=True, type=Path)
    args = cli.parse_args()
    try:
        result = inspect_dx_archive_and_device_text(
            _read_external_regular(args.archive, MAX_ARCHIVE_BYTES),
            _read_file_once(args.dq),
        )
    except (DXRejected, ProductionPreflightRejected, DJRejected, OSError) as exc:
        cli.error("BLOCKED: " + str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
