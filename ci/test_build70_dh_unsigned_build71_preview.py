#!/usr/bin/env python3
"""DH: future Build71 unsigned QA preview, including hostile source fixtures.

Never packages a signed IPA or invokes appinst. Fake Mach-O bundles below
are ONLY tests of bounded metadata parsing; not real device executables.
"""
import os
from pathlib import Path
import plistlib
import shutil
import struct
import tempfile
import unittest

from build70_dh_unsigned_build71_preview import (
    DHPreviewRejected, inspect_dh_source, inspect_dh_unsigned_app,
    BUNDLE, IDENTIFIER_CLAIM
)

ROOT = Path(__file__).resolve().parent.parent


class DHBuild71UnsignedPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wr-dh-unsigned-preview-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / "MangaReader12.app"
        self.app.mkdir()
        self._write_plist()
        (self.app / "Assets.car").write_bytes(b"DISPOSABLE-FAKE-CAR-FOR-METADATA-TEST")
        (self.app / "MangaReader12").write_bytes(self._fake_arm64_binary())

    def _write_plist(self, **patch):
        values = {
            "CFBundleVersion": "71",
            "CFBundleIdentifier": BUNDLE,
            "CFBundleExecutable": "MangaReader12",
            "CFBundleDisplayName": "WebReader",
            "CFBundleName": "WebReader",
            "MinimumOSVersion": "12.0",
            "CFBundlePackageType": "APPL",
            "CFBundleIcons": {"CFBundlePrimaryIcon": {"CFBundleIconName": "AppIcon"}},
        }
        values.update(patch)
        (self.app / "Info.plist").write_bytes(plistlib.dumps(values))

    def _fake_arm64_binary(self, *, cputype=0x0100000C,
                           platform=2, minos=12 << 16):
        head = struct.pack("<IiiIIIII", 0xFEEDFACF, cputype, 0,
                           2, 1, 24, 0, 0)
        lc = struct.pack("<IIIIII", 0x32, 24, platform, minos, 18 << 16, 0)
        return head + lc

    def check(self, source=ROOT):
        return inspect_dh_unsigned_app(self.app, source_root=source)

    def assert_no_authority(self, result):
        for key in (
            "ownerDistributionApprovalRecorded",
            "entitlementsOfCompiledCandidateVerified",
            "deviceInstallabilityProven", "installationAuthorized",
            "installationPerformed", "installableIPAProduced",
            "appCodeSignatureVerified",
            "installedApplicationIdentifierMatchedOnDevice",
            "libraryDataPreservedOnDevice", "offlineReadingVerifiedOnDevice",
            "qaUserApprovalObtained", "githubReleasePublished",
            "mainModified"
        ):
            if key in result:
                self.assertFalse(result[key], key)

    def test_current_source_is_ready_only_for_unsigned_preview(self):
        result = inspect_dh_source()
        self.assertEqual(result["projectSourceBuild"], 56)
        self.assertEqual(result["physicallyApprovedInstalledBuildReference"], 70)
        self.assertEqual(result["proposedQABuild"], 71)
        self.assertTrue(result["selfOnlyReportWired"])
        self.assertTrue(result["identityClaimMatchesHistoricalQAFile"])
        self.assert_no_authority(result)

    def test_fake_arm64_ios12_preview_metadata_passes_without_install_authority(self):
        r = self.check()
        self.assertEqual(r["status"], "DH_UNSIGNED_APP_METADATA_ONLY_NOT_INSTALLABLE")
        self.assertEqual(r["observedCompiledBuild"], 71)
        self.assertEqual(r["actualExecutableMinimumIOS"], "12.0")
        self.assertEqual(r["compiledBinaryArchitecture"], "arm64")
        self.assertEqual(len(r["unsignedBinarySHA256"]), 64)
        self.assertTrue(r["previewOnly"])
        self.assert_no_authority(r)

    def test_wrong_versions_rejected_even_if_installation_still_disabled(self):
        for version in ("56", "69", "70", "72", "071", ""):
            with self.subTest(version=version):
                self._write_plist(CFBundleVersion=version)
                with self.assertRaises(DHPreviewRejected):
                    self.check()

    def test_changed_bundle_identity_rejected(self):
        self._write_plist(CFBundleIdentifier="com.example.otherreader")
        with self.assertRaises(DHPreviewRejected):
            self.check()

    def test_changed_minimum_ios_rejected(self):
        for value in ("11.0", "12.5", "13.0", "15.0"):
            with self.subTest(value=value):
                self._write_plist(MinimumOSVersion=value)
                with self.assertRaises(DHPreviewRejected):
                    self.check()

    def test_changed_app_names_rejected(self):
        for key, value in (
            ("CFBundleExecutable", "install"),
            ("CFBundleName", "Other"),
            ("CFBundleDisplayName", "Other"),
            ("CFBundlePackageType", "BNDL"),
        ):
            with self.subTest(key=key):
                self._write_plist(**{key: value})
                with self.assertRaises(DHPreviewRejected):
                    self.check()

    def test_icon_metadata_required(self):
        self._write_plist(CFBundleIcons={})
        with self.assertRaises(DHPreviewRejected):
            self.check()

    def test_assets_car_must_exist_as_regular_file(self):
        (self.app / "Assets.car").unlink()
        with self.assertRaises(DHPreviewRejected):
            self.check()

    def test_symlinked_binary_rejected_even_when_target_is_valid(self):
        actual = self.root / "outside-binary"
        actual.write_bytes(self._fake_arm64_binary())
        (self.app / "MangaReader12").unlink()
        (self.app / "MangaReader12").symlink_to(actual)
        with self.assertRaises(DHPreviewRejected):
            self.check()

    def test_wrong_macho_architecture_rejected(self):
        (self.app / "MangaReader12").write_bytes(
            self._fake_arm64_binary(cputype=0x01000007)
        )
        with self.assertRaises(DHPreviewRejected):
            self.check()

    def test_wrong_macho_minimum_ios_rejected(self):
        (self.app / "MangaReader12").write_bytes(
            self._fake_arm64_binary(minos=13 << 16)
        )
        with self.assertRaises(DHPreviewRejected):
            self.check()

    def test_ios_simulator_binary_rejected(self):
        (self.app / "MangaReader12").write_bytes(
            self._fake_arm64_binary(platform=7)
        )
        with self.assertRaises(DHPreviewRejected):
            self.check()

    def test_signed_candidate_is_not_this_unsigned_preview(self):
        (self.app / "_CodeSignature").mkdir()
        with self.assertRaises(DHPreviewRejected):
            self.check()
        (self.app / "_CodeSignature").rmdir()
        (self.app / "embedded.mobileprovision").write_bytes(b"FAKE")
        with self.assertRaises(DHPreviewRejected):
            self.check()

    def _source_fixture(self):
        root = self.root / "synthetic-reviewed-source"
        fields = (
            "MangaReader12.xcodeproj/project.pbxproj",
            "MangaReader12/Core/WebReaderUpdateChecker.swift",
            "MangaReader12/Core/WebReaderProductionPublisherTrust.swift",
            "MangaReader12/Core/WebReaderAppinstSocket.swift",
            "MangaReader12/UI/WebReaderAppUpdatesViewController.swift",
            "ci/chimera_webreader_qa.entitlements",
        )
        for relative in fields:
            dest = root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, dest)
        return root

    def test_change_installer_permission_rejected(self):
        root = self._source_fixture()
        path = root / "MangaReader12/Core/WebReaderAppinstSocket.swift"
        path.write_text(path.read_text().replace(
            "static let liveInstallationEnabled = false",
            "static let liveInstallationEnabled = true"
        ))
        with self.assertRaises(DHPreviewRejected):
            inspect_dh_source(root)

    def test_change_publisher_key_rejected(self):
        root = self._source_fixture()
        path = root / "MangaReader12/Core/WebReaderUpdateChecker.swift"
        path.write_text(path.read_text().replace(
            "static let productionPublicKeyX963: Data? = nil",
            "static let productionPublicKeyX963: Data? = Data([1, 2, 3])"
        ))
        with self.assertRaises(DHPreviewRejected):
            inspect_dh_source(root)

    def test_change_independent_spki_pin_rejected(self):
        root = self._source_fixture()
        path = root / "MangaReader12/Core/WebReaderProductionPublisherTrust.swift"
        path.write_text(path.read_text().replace(
            "static let independentlyProvisionedSPKISHA256: String? = nil",
            'static let independentlyProvisionedSPKISHA256: String? = "forged"'
        ))
        with self.assertRaises(DHPreviewRejected):
            inspect_dh_source(root)

    def test_modified_entitlements_claim_rejected(self):
        root = self._source_fixture()
        p = root / "ci/chimera_webreader_qa.entitlements"
        p.write_bytes(plistlib.dumps({
            "application-identifier": "FORGED." + IDENTIFIER_CLAIM,
        }))
        with self.assertRaises(DHPreviewRejected):
            inspect_dh_source(root)

    def test_missing_inapp_diagnostic_is_rejected(self):
        root = self._source_fixture()
        p = root / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift"
        p.write_text(p.read_text().replace(
            "Darwin.geteuid()", "UNSAFE_VALUE_FROM_IPC()"
        ))
        with self.assertRaises(DHPreviewRejected):
            inspect_dh_source(root)

    def test_changed_project_version_is_rejected(self):
        root = self._source_fixture()
        p = root / "MangaReader12.xcodeproj/project.pbxproj"
        p.write_text(p.read_text().replace(
            "CURRENT_PROJECT_VERSION = 56;", "CURRENT_PROJECT_VERSION = 71;"
        ))
        with self.assertRaises(DHPreviewRejected):
            inspect_dh_source(root)

    def test_bundle_inside_source_root_is_denied(self):
        # Use disposable copies only, never write into the real checkout.
        source = self._source_fixture()
        child = source / "MangaReader12.app"
        shutil.copytree(self.app, child)
        with self.assertRaises(DHPreviewRejected):
            inspect_dh_unsigned_app(child, source_root=source)

    def test_symlinked_app_directory_is_denied(self):
        link = self.root / "alias" / "MangaReader12.app"
        link.parent.mkdir()
        link.symlink_to(self.app, target_is_directory=True)
        with self.assertRaises(DHPreviewRejected):
            inspect_dh_unsigned_app(link)

    def test_no_automatic_install_qa_packaging_or_release_entrypoint(self):
        text = (ROOT / "ci/build70_dh_unsigned_build71_preview.py").read_text()
        for needle in ("posix_spawn(", "subprocess.run(", "socket(", "appinst(",
                       "codesign(", "zipfile.ZipFile(", "shutil.make_archive(",
                       "upload_artifact(", "publish_release(", "installApplication:"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
