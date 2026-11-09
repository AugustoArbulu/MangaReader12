#!/usr/bin/env python3
"""Build70 BB: PRIVATE QA IPA preflight, no publisher authentication or install.

To be used ONLY after the owner explicitly approves preparing a new test IPA.
Requires checksum obtained separately from the IPA, single-FD hash-verified
snapshot, iOS12 ARM64 executable, native ad-hoc codesign, and the EXACT
application-identifier observed on the already-installed iPad.
This tool NEVER signs, packages, uploads, publishes or installs an IPA.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import plistlib
import re
import zipfile

from build66_ipa_preflight import AdmissionDenied, inspect_ipa
from build66_code_signature_gate import (
    CodeSignatureRejected, audit_code_signature_snapshot,
    INSTALLED_APPLICATION_IDENTIFIER
)
from build70_unsigned_candidate_audit import (
    UnsignedCandidateRejected, _macho_ios_minimum
)
from build69_production_release_preflight import _read_external_regular

QA_BUILD = 70
INSTALLED_BUILD = 69
QA_FILE_NAME = "WebReader-Build70-iOS12-adhoc.ipa"


class PrivateQAPreflightRejected(ValueError):
    pass


def parse_independent_checksum(checksum: bytes, expected_filename: str = QA_FILE_NAME) -> str:
    if type(checksum) is not bytes or not 0 < len(checksum) <= 512:
        raise PrivateQAPreflightRejected("missing bounded independent SHA256 file")
    try:
        line = checksum.decode("ascii").strip("\r\n")
    except UnicodeError as exc:
        raise PrivateQAPreflightRejected("checksum file must be ASCII") from exc
    if "\n" in line or "\r" in line or "\x00" in line:
        raise PrivateQAPreflightRejected("ambiguous checksum lines")
    fields = line.split()
    if len(fields) != 2 or not re.fullmatch("[0-9a-f]{64}", fields[0]):
        raise PrivateQAPreflightRejected("invalid independent SHA256")
    if fields[1] != expected_filename:
        raise PrivateQAPreflightRejected("checksum is not for the exact QA asset")
    return fields[0]


def preflight_private_qa_ipa(ipa_path: Path, *, checksum_data: bytes,
                             baseline: int = INSTALLED_BUILD) -> dict:
    if type(baseline) is not int or baseline != 69:
        raise PrivateQAPreflightRejected("baseline must be physically approved Build69")
    path = Path(ipa_path)
    if path.name != QA_FILE_NAME or path.is_symlink():
        raise PrivateQAPreflightRejected("wrong Build70 QA filename or symlink")
    expected_sha = parse_independent_checksum(checksum_data)
    try:
        size = path.stat().st_size
        package = inspect_ipa(
            path, expected_sha, size, baseline,
            require_exact_identity=True, return_snapshot=True
        )
        snapshot = package.pop("ipa_snapshot")
        if (package["build"] != QA_BUILD or package["minimum_ios"] != "12.0"
                or package["bundle"] != "com.example.MangaReader12"):
            raise PrivateQAPreflightRejected("wrong application build or minimum iOS")
        # Check the actual executable's platform, not merely a configurable
        # Info.plist minimum; ad-hoc signing does not establish this.
        with zipfile.ZipFile(io.BytesIO(snapshot)) as z:
            executable = z.read("Payload/MangaReader12.app/MangaReader12")
            binary_minimum = _macho_ios_minimum(executable[:1024 * 1024 + 32])
            plist = plistlib.loads(z.read("Payload/MangaReader12.app/Info.plist"))
            if plist.get("CFBundleVersion") != "70":
                raise PrivateQAPreflightRejected("invalid embedded QA version")
        seal = audit_code_signature_snapshot(
            snapshot, package["sha256"], package["ipa_size"]
        )
    except (AdmissionDenied, CodeSignatureRejected, UnsignedCandidateRejected,
            OSError, ValueError, KeyError, zipfile.BadZipFile,
            plistlib.InvalidFileException) as exc:
        if isinstance(exc, PrivateQAPreflightRejected):
            raise
        raise PrivateQAPreflightRejected(
            "Build70 private QA IPA failed exact-byte preflight"
        ) from exc
    if (not seal["adHocSignatureIntegrityVerified"]
            or not seal["installedApplicationIdentifierMatch"]
            or not seal["thinArm64ExecutableVerified"]
            or seal["applicationIdentifier"] != INSTALLED_APPLICATION_IDENTIFIER):
        raise PrivateQAPreflightRejected("existing iPad upgrade identity mismatch")
    return {
        "status": "HOST_ONLY_PRIVATE_QA_PREFLIGHT_NOT_DISTRIBUTION_APPROVAL",
        "build": QA_BUILD,
        "installedBuildBaseline": INSTALLED_BUILD,
        "bundleID": package["bundle"],
        "minimumIOS": package["minimum_ios"],
        "actualExecutableMinimumIOS": binary_minimum,
        "binaryArchitecture": "arm64",
        "ipaSHA256": package["sha256"],
        "ipaSize": package["ipa_size"],
        "checksumMatchesIndependentlySuppliedFile": True,
        "adHocSignatureIntegrityVerified": True,
        "installedApplicationIdentifierMatch": True,
        "verifiedApplicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
        "codeDirectoryCDHash": seal["approvedArtifactStaticCodeDirectoryCDHash"],
        "publisherAuthenticatedByCodeSignature": False,
        "deviceInstallationCompatibilityProven": False,
        "qaPhysicalTestCompleted": False,
        "backupAndOfflineLibraryPreservationProven": False,
        "editorialProductionKeyProvisioned": False,
        "ownerDistributionApprovalRecorded": False,
        "readyForDistribution": False,
        "githubReleasePublished": False,
        "mainModified": False,
        "chimeraInstallationAuthorized": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--sha256-file", type=Path, required=True)
    parser.add_argument("--installed-build", type=int, default=69)
    args = parser.parse_args()
    receipt = preflight_private_qa_ipa(
        args.ipa,
        checksum_data=_read_external_regular(args.sha256_file, 512),
        baseline=args.installed_build
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
