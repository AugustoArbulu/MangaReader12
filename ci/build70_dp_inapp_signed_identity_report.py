#!/usr/bin/env python3
"""WebReader Build70 / DP — parse untrusted FUTURE Build71 iOS12 self report.

The currently installed Build70 does NOT contain DP. The iPhoneOS12 SDK
DOES NOT expose SecTask signing APIs to this Swift app. A future Build71
readout of Bundle ID / UID can only describe its OWN running task, never re-attest
the previous installed Build70, a helper peer, publisher or a safe upgrade.

The report is copied to the clipboard, not signed. DO NOT use this as
authorization to prepare, distribute, or install any IPA.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import json

from build70_dj_continuity_report_compare import _read_file_once, DJRejected

MAX_TEXT_BYTES = 2048
EXPECTED_BUILD = 71
EXPECTED_IOS = "12.5.8"
EXPECTED_BUNDLE_ID = "com.example.MangaReader12"
SIGNING_UNAVAILABLE = "UNAVAILABLE_IOS12_PUBLIC_SDK"
HEADER = "WebReader • Diagnóstico de identidade do próprio app (DG/DP)"
IDENTITY_RE = re.compile(r"[A-Za-z0-9._-]{1,256}\Z", re.ASCII)
DECIMAL_RE = re.compile(r"(?:0|[1-9][0-9]{0,9})\Z", re.ASCII)
STATIC_LINES = (
    "APP_SELF_IDENTITY_SCOPE=SELF_ONLY",
    "APP_SELF_SIGNING_CLAIM_SCOPE=OBSERVATION_ONLY_NOT_VERIFIED",
    "INSTALLED_PREVIOUS_BUILD_IDENTITY_ATTESTED=NO",
    "HELPER_PROCESS_IDENTITY=NOT_TESTED",
    "IPC_PEER_AUTHENTICATED=NO",
    "IOS12_SANDBOX_SEPARATION_PROVEN=NO",
    "APP_WRITE_DENIAL_TO_HELPER_VAULT_PROVEN=NO",
    "PUBLISHER_TRUST_CONFIGURED=NO",
    "INSTALLATION_AUTHORIZED=NO",
    "INSTALLATION_ATTEMPTED=NO",
)


class DPRejected(ValueError):
    pass


def _identity(line: str, label: str) -> str:
    prefix = label + "="
    if not line.startswith(prefix):
        raise DPRejected("missing or reordered own signing data")
    value = line[len(prefix):]
    if IDENTITY_RE.fullmatch(value) is None:
        raise DPRejected("unsafe or noncanonical self-identity string")
    return value


def parse_dp_report(blob: bytes) -> dict:
    if type(blob) is not bytes or not 0 < len(blob) <= MAX_TEXT_BYTES:
        raise DPRejected("missing or oversized DP text")
    if b"\x00" in blob or b"\r" in blob:
        raise DPRejected("invalid control characters")
    try:
        text = blob.decode("utf-8")
    except UnicodeError as exc:
        raise DPRejected("invalid report encoding") from exc
    lines = text.split("\n")
    if len(lines) != 10 + len(STATIC_LINES) or lines[0] != HEADER:
        raise DPRejected("unknown or reordered DP report shape")
    if lines[1] != f"Build: {EXPECTED_BUILD}" or lines[2] != f"iOS: {EXPECTED_IOS}":
        raise DPRejected("must be future Build71 on actual iOS12.5.8")
    values = []
    for idx, label in enumerate(
        ("APP_SELF_UID", "APP_SELF_EUID", "APP_SELF_GID", "APP_SELF_EGID"),
        start=3,
    ):
        prefix = label + "="
        raw = lines[idx]
        if not raw.startswith(prefix):
            raise DPRejected("self-UID/GID field missing or reordered")
        number = raw[len(prefix):]
        if DECIMAL_RE.fullmatch(number) is None or int(number) > 2**32-1:
            raise DPRejected("invalid Unix self-identity number")
        values.append(int(number))
    bundle = _identity(lines[7], "APP_SELF_BUNDLE_ID")
    signing = _identity(lines[8], "APP_SELF_SIGNING_ID")
    entitlement = _identity(lines[9], "APP_SELF_APPLICATION_IDENTIFIER_ENTITLEMENT")
    if tuple(lines[10:]) != STATIC_LINES:
        raise DPRejected("DP report missing negative authority gates")
    # The source report must NEVER claim a signed entitlement was read.
    # Importing Apple's SecTask symbols failed with the actual iPhoneOS SDK.
    # Accept only an explicit unavailable status; forged "present" values
    # are rejected rather than promoted to a notion of authorization.
    if signing != SIGNING_UNAVAILABLE or entitlement != SIGNING_UNAVAILABLE:
        raise DPRejected("unsigned self report cannot claim signing entitlements")
    status = (
        "DP_REPORTED_BUNDLE_MISMATCH_NO_SIGNING_ATTESTATION"
        if bundle != EXPECTED_BUNDLE_ID
        else "DP_IOS12_SIGNING_ENTITLEMENT_UNAVAILABLE_NO_INSTALL"
    )

    return {
        "status": status,
        "futureBuildObservedInText": 71,
        "iosObservedInText": EXPECTED_IOS,
        "currentProcessUIDText": values[0],
        "currentProcessEUIDText": values[1],
        "currentProcessGIDText": values[2],
        "currentProcessEGIDText": values[3],
        "bundleIdentifierText": bundle,
        "signingIdentifierText": signing,
        "applicationIdentifierEntitlementText": entitlement,
        "historicalEntitlementTextComparisonMatches": False,
        "sourceIsUserSuppliedClipboardText": True,
        "sourceCryptographicallyAuthenticated": False,
        "secTaskSuccessfulOnActualiPadProvenByParser": False,
        "currentProcessCodeSignatureIntegrityVerified": False,
        "installedBuild70ApplicationIdentifierReattested": False,
        "build70To71InPlaceInstallationProven": False,
        "appContainerAndLibraryPreservationVerified": False,
        "offlineReadingVerified": False,
        "helperPeerAuthenticated": False,
        "productionPublisherAuthenticated": False,
        "ownerQADistributionApprovalRecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--report", type=Path, required=True)
    args = cli.parse_args()
    try:
        raw = _read_file_once(args.report)
        response = parse_dp_report(raw)
    except (DPRejected, DJRejected, OSError, ValueError) as exc:
        cli.error("BLOCKED: " + str(exc))
    print(json.dumps(response, sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
