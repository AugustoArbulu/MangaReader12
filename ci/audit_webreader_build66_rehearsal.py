#!/usr/bin/env python3
"""Read-only CI audit of Build66 ad-hoc *rehearsal* IPA (not release).

The IPA stays in CI runner temporary storage and MUST NOT be offered as an
automatic update, published to GitHub Releases, or sent to appinst. An ad-hoc
code signature verifies binary integrity and exact on-device entitlement
compatibility; it does NOT authenticate a WebReader publisher.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from build66_ipa_preflight import AdmissionDenied, inspect_ipa
from build66_code_signature_gate import (
    CodeSignatureRejected, audit_code_signature_snapshot
)
from validate_webreader_ipa import IPARejected, validate_ipa

APP_ID = "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
EXPECTED_FILENAME = "WebReader-Build66-iOS12-adhoc.ipa"


class RehearsalRejected(ValueError):
    pass


def audit(ipa_path, sha_file):
    ipa = Path(ipa_path)
    checksum = Path(sha_file)
    if ipa.name != EXPECTED_FILENAME or checksum.name != EXPECTED_FILENAME + ".sha256":
        raise RehearsalRejected("not the exact Build66 QA artifact convention")
    if ipa.is_symlink() or checksum.is_symlink() or not ipa.is_file():
        raise RehearsalRejected("unsafe or missing file")
    try:
        lines = checksum.read_text("ascii").splitlines()
    except OSError as exc:
        raise RehearsalRejected("missing SHA256 manifest") from exc
    if len(lines) != 1:
        raise RehearsalRejected("only one SHA256 record allowed")
    match = re.fullmatch(r"([0-9a-f]{64})  \*?" + re.escape(EXPECTED_FILENAME),
                         lines[0])
    # shasum outputs "<hex>  <filename>" (a single separator blank plus a
    # binary-mode marker would also be accepted).
    if not match:
        raise RehearsalRejected("wrong SHA256 manifest or artifact name")
    sha = match.group(1)
    try:
        size = ipa.stat().st_size
        result = inspect_ipa(
            ipa, sha, size, 65, require_exact_identity=True,
            return_snapshot=True
        )
        if result["build"] != 66 or result["minimum_ios"] != "12.0":
            raise RehearsalRejected("Build66 metadata or iOS12 minimum mismatch")
        snapshot = result.pop("ipa_snapshot")
        codesign = audit_code_signature_snapshot(snapshot, sha, size)
        if (codesign["applicationIdentifier"] != APP_ID or
                not codesign["thinArm64ExecutableVerified"] or
                not codesign["installedApplicationIdentifierMatch"]):
            raise RehearsalRejected("native ad-hoc identity mismatch")
        structure = validate_ipa(
            ipa, sha, installed_build=65, installed_ios="12.5.8"
        )
        if structure["build"] != 66 or structure["minimumIOS"] != "12.0":
            raise RehearsalRejected("read-only IPA validator disagreement")
    except (AdmissionDenied, CodeSignatureRejected, IPARejected, OSError,
            TypeError, KeyError) as exc:
        raise RehearsalRejected("Build66 rehearsal IPA rejected") from exc

    return {
        "status": "PASS",
        "qaArtifact": EXPECTED_FILENAME,
        "build": 66,
        "upgradesFromObservedBuild": 65,
        "minimumIOS": "12.0",
        "ipaSHA256": sha,
        "ipaBytes": size,
        "bundleID": "com.example.MangaReader12",
        "applicationIdentifier": APP_ID,
        "nativeAdHocCodeIntegrityVerified": True,
        "thinArm64Verified": True,
        "sameInstalledEntitlementIdentifier": True,
        "productionPublisherAuthenticated": False,
        "releaseManifestIndependentlySigned": False,
        "ios12DeviceInstallTested": False,
        "userConsentVerified": False,
        "helperPeerAuthenticated": False,
        "installationAuthorized": False,
        "installationPerformed": False,
        "approvedForAutomaticRelease": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--sha256-file", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.ipa, args.sha256_file)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
