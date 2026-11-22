#!/usr/bin/env python3
"""WebReader Build70 / Phase DH — unsigned Build71 candidate PREVIEW ONLY.

For a future owner-approved manual QA upgrade, do a read-only, SOURCE +
compiled-.app sanity check against the user's physically approved Build70.
No IPA packaging, signing, upload, release, network, installer or iPad action.
An unsigned .app is not ready for distribution nor known safe to install.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import plistlib

from build70_unsigned_candidate_audit import (
    UnsignedCandidateRejected, _bounded_regular_file, _macho_ios_minimum
)

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PHYSICAL = 70
PROPOSED_QA = 71
PROJECT_BASELINE = 56
BUNDLE = "com.example.MangaReader12"
IDENTIFIER_CLAIM = "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
EXECUTABLE = "MangaReader12"
APP = EXECUTABLE + ".app"
MAX_APP_BINARY_BYTES = 256 * 1024 * 1024


class DHPreviewRejected(ValueError):
    pass


def _read(source: Path, relative: str) -> str:
    p = source / relative
    if p.is_symlink() or not p.is_file():
        raise DHPreviewRejected("required read-only source file missing: " + relative)
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DHPreviewRejected("invalid source file: " + relative) from exc


def inspect_dh_source(source_root: Path = ROOT) -> dict:
    """Checks immutable source configuration for a future Build71 PREVIEW.

    Does not request or record the owner's approval to distribute a QA IPA.
    The project remains at base version 56; xcodebuild may override to 71
    in a TEMPORARY build output without editing project or app data.
    """
    source = Path(source_root)
    project = _read(source, "MangaReader12.xcodeproj/project.pbxproj")
    checker = _read(source, "MangaReader12/Core/WebReaderUpdateChecker.swift")
    signer = _read(source, "MangaReader12/Core/WebReaderProductionPublisherTrust.swift")
    installer = _read(source, "MangaReader12/Core/WebReaderAppinstSocket.swift")
    ui = _read(source, "MangaReader12/UI/WebReaderAppUpdatesViewController.swift")
    ent_path = source / "ci/chimera_webreader_qa.entitlements"
    try:
        claims = plistlib.loads(
            _bounded_regular_file(ent_path, max_bytes=4096)
        )
    except (OSError, ValueError, UnsignedCandidateRejected) as exc:
        raise DHPreviewRejected("cannot read saved QA application identifier claim") from exc
    if claims != {"application-identifier": IDENTIFIER_CLAIM}:
        raise DHPreviewRejected("existing QA signing identity claim changed")
    if project.count("CURRENT_PROJECT_VERSION = 56;") != 2:
        raise DHPreviewRejected("do not edit project build identity to prepare QA")
    if 'static let productionPublicKeyX963: Data? = nil' not in checker:
        raise DHPreviewRejected("production publisher key gate changed")
    if 'static let independentlyProvisionedSPKISHA256: String? = nil' not in signer:
        raise DHPreviewRejected("independent signing pin gate changed")
    if 'static let liveInstallationEnabled = false' not in installer:
        raise DHPreviewRejected("automatic installation unexpectedly enabled")
    required_ui = (
        "if source == 3 { return 9 }",
        "private func copyOwnProcessIdentityReport() {",
        "Darwin.getuid()", "Darwin.geteuid()",
        "Darwin.getgid()", "Darwin.getegid()",
        '"APP_SELF_IDENTITY_SCOPE=SELF_ONLY"',
        '"HELPER_PROCESS_IDENTITY=NOT_TESTED"',
        '"IPC_PEER_AUTHENTICATED=NO"',
        '"INSTALLATION_AUTHORIZED=NO"',
        '"INSTALLATION_ATTEMPTED=NO"',
    )
    if any(item not in ui for item in required_ui):
        raise DHPreviewRejected("read-only in-app self identity diagnostic missing")
    if ("WebReaderAppinstSocket.install(" in ui or
            "posix_spawn(" in ui or "appinst(" in ui):
        raise DHPreviewRejected("updates UI contains installation entrypoint")
    return {
        "status": "DH_SOURCE_READY_FOR_UNSIGNED_PREVIEW_ONLY",
        "projectSourceBuild": PROJECT_BASELINE,
        "physicallyApprovedInstalledBuildReference": BASELINE_PHYSICAL,
        "proposedQABuild": PROPOSED_QA,
        "futureBundleIdentifier": BUNDLE,
        "identityClaimMatchesHistoricalQAFile": True,
        "selfOnlyReportWired": True,
        "ownerDistributionApprovalRecorded": False,
        "entitlementsOfCompiledCandidateVerified": False,
        "deviceInstallabilityProven": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def inspect_dh_unsigned_app(app_directory: Path,
                            source_root: Path = ROOT) -> dict:
    """Inspect only an isolated, unsigned Xcode .app — never an IPA."""
    source_status = inspect_dh_source(source_root)
    app = Path(app_directory)
    source = Path(source_root).resolve()
    if (app.name != APP or app.is_symlink() or not app.is_dir()
            or source == app.resolve() or source in app.resolve().parents):
        raise DHPreviewRejected("candidate must be isolated outside source tree")
    if (app / "_CodeSignature").exists() or (app / "embedded.mobileprovision").exists():
        raise DHPreviewRejected("this phase inspects UNSIGNED application only")
    try:
        plist = plistlib.loads(
            _bounded_regular_file(app / "Info.plist", max_bytes=1024 * 1024)
        )
        expected = {
            "CFBundleVersion": str(PROPOSED_QA),
            "CFBundleIdentifier": BUNDLE,
            "CFBundleExecutable": EXECUTABLE,
            "CFBundleDisplayName": "WebReader",
            "CFBundleName": "WebReader",
            "MinimumOSVersion": "12.0",
            "CFBundlePackageType": "APPL",
        }
        if not isinstance(plist, dict) or any(plist.get(k) != v for k, v in expected.items()):
            raise DHPreviewRejected("unsigned Build71 Info.plist mismatch")
        icons = plist.get("CFBundleIcons")
        icon = icons.get("CFBundlePrimaryIcon") if isinstance(icons, dict) else None
        if not isinstance(icon, dict) or icon.get("CFBundleIconName") != "AppIcon":
            raise DHPreviewRejected("existing WebReader icon identity changed")
        _bounded_regular_file(app / "Assets.car", max_bytes=128 * 1024 * 1024)
        binary = _bounded_regular_file(
            app / EXECUTABLE, max_bytes=MAX_APP_BINARY_BYTES
        )
        binary_minimum = _macho_ios_minimum(binary[:1024 * 1024 + 32])
    except (UnsignedCandidateRejected, OSError, ValueError) as exc:
        if isinstance(exc, DHPreviewRejected):
            raise
        raise DHPreviewRejected("malformed or unavailable unsigned candidate") from exc
    result = dict(source_status)
    result.update({
        "status": "DH_UNSIGNED_APP_METADATA_ONLY_NOT_INSTALLABLE",
        "observedCompiledBuild": PROPOSED_QA,
        "actualExecutableMinimumIOS": binary_minimum,
        "compiledBinaryArchitecture": "arm64",
        "unsignedBinarySHA256": hashlib.sha256(binary).hexdigest(),
        "previewOnly": True,
        "installableIPAProduced": False,
        "appCodeSignatureVerified": False,
        "installedApplicationIdentifierMatchedOnDevice": False,
        "libraryDataPreservedOnDevice": False,
        "offlineReadingVerifiedOnDevice": False,
        "qaUserApprovalObtained": False,
        "githubReleasePublished": False,
        "mainModified": False,
    })
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--unsigned-app", type=Path, required=True)
    args = p.parse_args()
    try:
        result = inspect_dh_unsigned_app(args.unsigned_app)
    except DHPreviewRejected as exc:
        p.error("BLOCKED: " + str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
