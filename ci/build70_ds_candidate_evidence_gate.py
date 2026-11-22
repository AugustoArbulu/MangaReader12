#!/usr/bin/env python3
"""Build70/DS: read-only HOST consistency of pre-upgrade TEXT + signed IPA.

DQ and DO observations can be fabricated and might come from different iPads
or moments. A successful ad-hoc native code seal on an IPA does NOT prove
publisher identity, physical iOS installation, or preservation of app data.
Never distributes, signs, publishes, installs or authorizes an update.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build69_production_release_preflight import _read_external_regular
from build70_di_build71_private_qa_preflight import (
    DIPrivateQARejected, preflight_di_build71_private_qa,
    parse_di_checksum,
)
from build70_dk_qa_evidence_bridge import (
    DKEvidenceRejected, _check_di_receipt,
)
from build70_dr_preupgrade_crosscheck import (
    DRRejected, audit_dr_preupgrade,
)
from build70_dj_continuity_report_compare import DJRejected, _read_file_once


class DSRejected(ValueError):
    pass


ALLOWED_DR_OBSERVATION = (
    "DR_PREUPGRADE_TEXT_COHERENT_NOT_ATTESTED_NOT_INSTALLABLE"
)
MUST_STAY_FALSE_DR = (
    "reportOriginsCryptographicallyAuthenticated",
    "sameDeviceAndSameMomentProven",
    "installedBuild70NativeSignatureValidated",
    "installedBuild70EntitlementAttested",
    "readyToDistributeIPA",
    "readyToInstallIPA",
    "installationAuthorized",
    "installationPerformed",
)


def inspect_ds_preupgrade_candidate(
    *, dq_report: bytes, sqlite_count_report: bytes,
    offline_reports: list[bytes], ipa_path: Path,
    checksum_data: bytes,
) -> dict:
    """Audit untrusted reports FIRST, then a real signed IPA snapshot on macOS.

    The only positive outcome is a HOST-ONLY consistency receipt with explicit
    negative installation and publisher fields. It is never a distribution gate.
    """
    try:
        dr = audit_dr_preupgrade(dq_report, sqlite_count_report, offline_reports)
    except DRRejected as exc:
        raise DSRejected("malformed DQ/DO evidence, stop QA") from exc
    if dr.get("status") != ALLOWED_DR_OBSERVATION:
        raise DSRejected("DQ/DO identity or offline baseline not fully text-coherent")
    if dr.get("bothReportFormatsTextuallyCoherent") is not True:
        raise DSRejected("missing textual coherence")
    for key in MUST_STAY_FALSE_DR:
        if dr.get(key) is not False:
            raise DSRejected("untrusted report asserts authority: " + key)
    if dr.get("reportedInstalledBuild") != "70":
        raise DSRejected("incorrect textual pre-upgrade build")

    try:
        sha256 = parse_di_checksum(checksum_data)
        di = preflight_di_build71_private_qa(
            ipa_path, checksum_data=checksum_data, installed_build=70,
        )
        _check_di_receipt(di, sha256)
    except (DIPrivateQARejected, DKEvidenceRejected, OSError) as exc:
        raise DSRejected("signed Build71 host snapshot failed DI/DK preflight") from exc

    if dr["reportedInstalledBundle"] != di["bundleID"]:
        raise DSRejected("candidate and reported installed bundle ID differ")
    if dr["reportedApplicationIdentifier"] != di["historicalApplicationIdentifier"]:
        raise DSRejected("candidate and reported installed entitlement text differ")

    return {
        "status": "DS_HOST_TEXT_AND_SIGNED_CANDIDATE_COHERENT_NOT_INSTALLABLE",
        "baselineBuildText": "70",
        "candidateBuildHostVerified": 71,
        "targetIOS": "12.5.8",
        "candidateBundleID": di["bundleID"],
        "candidateIPAStaticSHA256": di["ipaSHA256"],
        "candidateIPABytes": di["ipaBytes"],
        "candidateStaticCDHash": di["staticCodeDirectoryCDHash"],
        "ipaAdHocSealCheckedOnHost": True,
        "dqDoTextFormatsCoherent": True,
        "doTextCompletedRowsCovered": dr["reportedInspectedChapterRecords"],
        "doTextMissingUnsafeRows": dr["reportedMissingUnsafeChapters"],
        "physicalDeviceAndReportOriginAuthenticated": False,
        "physicalInstalledBuild70IdentityCryptographicallyVerified": False,
        "physicalInstalledEntitlementIndependentlyAttested": False,
        "realIOS12InstallationCompatibilityProven": False,
        "sameIPABytesConsumedByInstallerProven": False,
        "publisherAuthenticated": False,
        "localAppDataContainerRetentionProven": False,
        "offlinePageBytesAndDecodeVerified": False,
        "physicalBeforeAfterOfflineReadVerified": False,
        "backupOutsideDeviceVerified": False,
        "independentProductionPublicKeyProvisioned": False,
        "helperPeerAuthenticated": False,
        "ownerPrivateQADistributionConsentRecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "automaticUpdaterEnabled": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--dq", type=Path, required=True)
    cli.add_argument("--counts", type=Path, required=True)
    cli.add_argument("--offline", type=Path, action="append", required=True)
    cli.add_argument("--ipa", type=Path, required=True)
    cli.add_argument("--checksum-file", type=Path, required=True)
    args = cli.parse_args()
    try:
        if len(args.offline) > 256:
            raise DSRejected("too many offline batches")
        receipt = inspect_ds_preupgrade_candidate(
            dq_report=_read_file_once(args.dq),
            sqlite_count_report=_read_file_once(args.counts),
            offline_reports=[_read_file_once(path) for path in args.offline],
            ipa_path=args.ipa,
            checksum_data=_read_external_regular(args.checksum_file, 512),
        )
    except (DSRejected, DJRejected, OSError, ValueError) as exc:
        cli.error("BLOCKED: " + str(exc))
    print(json.dumps(receipt, sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
