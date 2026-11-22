#!/usr/bin/env python3
"""Build69 AZ: read-only QA IPA readiness diagnostics, NEVER a release permit.

Checks local reviewed source configuration, not device state, Apple signing,
owner approval, or physical QA. Outputs no binary, manifest or mutable marker.
An apparent success can NEVER authorize package/upload/install.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_QA_BUILD = 69
BASELINE_APPROVED_BUILD = 68


class CandidateConfigurationRejected(ValueError):
    pass


def inspect_xcode_settings(project_text: str) -> dict:
    if type(project_text) is not str:
        raise CandidateConfigurationRejected("project settings unavailable")
    versions = [int(v) for v in re.findall(
        r"\bCURRENT_PROJECT_VERSION\s*=\s*([0-9]+)\s*;", project_text
    )]
    identifiers = re.findall(
        r"\bPRODUCT_BUNDLE_IDENTIFIER\s*=\s*([^;\s]+)\s*;", project_text
    )
    targets = re.findall(
        r"\bIPHONEOS_DEPLOYMENT_TARGET\s*=\s*([^;\s]+)\s*;", project_text
    )
    if len(versions) != 2 or len(set(versions)) != 1 or versions[0] < 1:
        raise CandidateConfigurationRejected("Debug/Release versions differ")
    if identifiers != ["com.example.MangaReader12"] * 2:
        raise CandidateConfigurationRejected("installed bundle identity changed")
    if not targets or any(v != "12.0" for v in targets):
        raise CandidateConfigurationRejected("iOS12 minimum deployment target changed")
    return {
        "sourceBuildVersion": versions[0],
        "expectedQABuildVersion": EXPECTED_QA_BUILD,
        "targetVersionMatched": versions[0] == EXPECTED_QA_BUILD,
        "sameBundleIdentifierInBothConfigurations": True,
        "iOS12DeploymentPreserved": True,
    }


def inspect_future_candidate_source(source_root: Path = ROOT) -> dict:
    project = (source_root / "MangaReader12.xcodeproj/project.pbxproj").read_text("utf-8")
    info = (source_root / "MangaReader12/Info.plist").read_text("utf-8")
    trust = (source_root / "MangaReader12/Core/WebReaderProductionPublisherTrust.swift").read_text("utf-8")
    channel = (source_root / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text("utf-8")
    installer = (source_root / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text("utf-8")
    db = (source_root / "MangaReader12/Database/SQLiteDatabase.swift").read_text("utf-8")
    backup = (source_root / "MangaReader12/Core/BackupManager.swift").read_text("utf-8")
    if '<string>$(CURRENT_PROJECT_VERSION)</string>' not in info:
        raise CandidateConfigurationRejected("Info.plist version no longer follows project")
    if '<string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>' not in info:
        raise CandidateConfigurationRejected("Info.plist no longer follows bundle identity")
    if 'static let currentSchemaVersion = 1' not in db:
        raise CandidateConfigurationRejected("database schema change requires separate migration review")
    if 'static let formatVersion = 1' not in backup:
        raise CandidateConfigurationRejected("backup format change requires separate restore review")
    if ('static let independentlyProvisionedSPKISHA256: String? = nil' not in trust
            or 'static let productionTrustGeneration = 0' not in trust
            or 'static let productionPublicKeyX963: Data? = nil' not in channel
            or 'static let liveInstallationEnabled = false' not in installer):
        raise CandidateConfigurationRejected("production trust/Chimera unexpectedly enabled")
    if (source_root / "ci/build69_candidate_trigger.txt").exists():
        raise CandidateConfigurationRejected("unapproved Build69 packaging trigger exists")

    configuration = inspect_xcode_settings(project)
    # Version ==69 means just version consistency. Packaging still needs
    # explicit approval, ad-hoc IPA signature, exact bytes and physical QA.
    return {
        "status": "SOURCE_REVIEW_ONLY_NOT_QA_IPA_READY",
        "baselineInstalledBuild": BASELINE_APPROVED_BUILD,
        **configuration,
        "backupFormatUnchanged": True,
        "databaseSchemaUnchanged": True,
        "signedProductionTrustProvisioned": False,
        "chimeraLiveInstallationEnabled": False,
        "qaIPACreated": False,
        "qaIPASigningVerified": False,
        "qaIPAPublisherAuthenticated": False,
        "onDeviceDataPreservationVerified": False,
        "physicalQAPassed": False,
        "ownerDistributionApprovalRecorded": False,
        "releasePublished": False,
        "mainChanged": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main():
    print(json.dumps(inspect_future_candidate_source(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
