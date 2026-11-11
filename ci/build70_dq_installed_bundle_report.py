#!/usr/bin/env python3
"""DQ: analyze untrusted TEXT from optional iOS12 installed-bundle shell probe.

Even matching local ldid -e metadata does not validate CodeDirectory, signed
IPA provenance, actual device identity, installed container or publisher.
Never read user files except the explicitly supplied bounded report text.
"""
import argparse
import json
from pathlib import Path
import re

from build70_dj_continuity_report_compare import _read_file_once, DJRejected

HEADER="WebReader Build70 DQ • Observação local somente leitura"
FIXED=(
    "SOURCE=USER_SELECTED_INSTALLED_APP_BUNDLE_NOT_ATTESTED",
    "CODE_SIGNATURE_CRYPTOGRAPHIC_VALIDITY_PROVEN=NO",
    "PUBLISHER_IDENTITY_AUTHENTICATED=NO",
    "CURRENT_DEVICE_PROVEN_BY_SHELL_TEXT=NO",
    "DATA_CONTAINER_RETENTION_PROVEN=NO",
    "LIBRARY_AND_OFFLINE_PRESERVATION_PROVEN=NO",
    "HELPER_IPC_AUTHENTICATED=NO",
    "READY_TO_DISTRIBUTE_IPA=NO",
    "INSTALLATION_AUTHORIZED=NO",
    "INSTALLATION_ATTEMPTED=NO",
)
EXPECTED_BUNDLE="com.example.MangaReader12"
EXPECTED_VERSION="70"
HISTORICAL_ENTITLEMENT="AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
SAFE=re.compile(r"[A-Za-z0-9._-]{1,256}\Z",re.ASCII)


class DQReportRejected(ValueError):
    pass


def _field(line,prefix):
    if not line.startswith(prefix+"="):
        raise DQReportRejected("field missing or reordered")
    value=line[len(prefix)+1:]
    if SAFE.fullmatch(value) is None:
        raise DQReportRejected("noncanonical metadata or unauthorized characters")
    return value


def inspect_dq_text(data):
    if type(data) is not bytes or not 0<len(data)<=2048:
        raise DQReportRejected("unavailable/oversized report")
    if b"\x00" in data or b"\r" in data:
        raise DQReportRejected("control characters in report")
    try:
        rows=data.decode("utf-8").split("\n")
    except UnicodeError as exc:
        raise DQReportRejected("invalid encoding") from exc
    if len(rows)!=4+len(FIXED) or rows[0]!=HEADER or tuple(rows[4:])!=FIXED:
        raise DQReportRejected("unknown report format or missing negative authority")
    bundle=_field(rows[1],"BUNDLE_IDENTIFIER_TEXT")
    build=_field(rows[2],"BUNDLE_VERSION_TEXT")
    entitlement=_field(rows[3],"APPLICATION_IDENTIFIER_ENTITLEMENT_TEXT")
    if any(x not in (expected,"UNAVAILABLE") for x,expected in (
        (bundle,EXPECTED_BUNDLE),(build,EXPECTED_VERSION),
        (entitlement,HISTORICAL_ENTITLEMENT)
    )):
        status="DQ_REPORTED_BUNDLE_VERSION_OR_ENTITLEMENT_MISMATCH_STOP_QA"
    elif "UNAVAILABLE" in (bundle,build,entitlement):
        status="DQ_REPORTED_INSTALLED_IDENTITY_FIELDS_UNAVAILABLE"
    else:
        status="DQ_REPORTED_MATCH_HISTORICAL_METADATA_NOT_ATTESTED"
    return {
        "status":status,
        "reportedBundleID":bundle,
        "reportedInstalledBuild":build,
        "reportedApplicationIdentifierEntitlement":entitlement,
        "allThreeValuesTextuallyMatchHistorical":status.endswith("NOT_ATTESTED"),
        "inputShellReportCryptographicallyAuthenticated":False,
        "inputProvenToComeFromCurrentPhysicalIPad":False,
        "nativeCodeSignatureCryptographicallyValidated":False,
        "installedBundleActuallyExistsProvenByParser":False,
        "publisherIdentityAuthenticated":False,
        "installedBuild70IndependentEntitlementAttested":False,
        "futureBuild71OSUpgradeCompatibilityProven":False,
        "userLibraryAndOfflinePreservationVerified":False,
        "helperPeerAuthenticated":False,
        "ownerDistributionApprovalRecorded":False,
        "readyToDistributeIPA":False,
        "readyToInstallIPA":False,
        "installationAuthorized":False,
        "installationPerformed":False
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    try:
        receipt=inspect_dq_text(_read_file_once(args.report))
    except (DQReportRejected,DJRejected,OSError) as exc:
        p.error("BLOCKED: "+str(exc))
    print(json.dumps(receipt,sort_keys=True,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
