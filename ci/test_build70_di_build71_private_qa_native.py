#!/usr/bin/env python3
"""DI native macOS tests: disposable Build71 iOS12 ad-hoc-signed QA fixture.

Never touches WebReader's installed iPad, publishes a release, or uploads
test IPAs. A valid local ad-hoc code seal does NOT authenticate the publisher,
prove compatibility with the physical Build70 app, or authorize distribution.
"""
import hashlib
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

from build66_code_signature_gate import INSTALLED_APPLICATION_IDENTIFIER
from build70_di_build71_private_qa_preflight import (
    DIPrivateQARejected, QA_FILENAME, preflight_di_build71_private_qa,
)


@unittest.skipUnless(sys.platform == "darwin", "requires native Apple codesign")
class DINativeBuild71QATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wr-di-71-disposable-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ipa = self.root / QA_FILENAME

    def build_disposable_ipa(
        self, *, build="71", executable_min="12.0",
        ios_plist_min="12.0", entitlement=INSTALLED_APPLICATION_IDENTIFIER,
        sign=True, alter_signed_exe=False,
    ):
        stage = self.root / "staging"
        app = stage / "Payload" / "MangaReader12.app"
        app.mkdir(parents=True, exist_ok=True)
        info = {
            "CFBundleIdentifier": "com.example.MangaReader12",
            "CFBundleExecutable": "MangaReader12",
            "CFBundleDisplayName": "WebReader",
            "CFBundleName": "WebReader",
            "CFBundleVersion": build,
            "CFBundlePackageType": "APPL",
            "MinimumOSVersion": ios_plist_min,
        }
        (app / "Info.plist").write_bytes(plistlib.dumps(info))
        sample_source = self.root / "self-only-qa-fixture.c"
        sample_source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        subprocess.run([
            "xcrun", "--sdk", "iphoneos", "clang",
            "-arch", "arm64", "-miphoneos-version-min=" + executable_min,
            str(sample_source), "-o", str(app / "MangaReader12"),
        ], check=True, capture_output=True, timeout=45)
        entitlement_path = self.root / "fixture.entitlements"
        entitlement_path.write_bytes(plistlib.dumps({
            "application-identifier": entitlement,
        }))
        if sign:
            subprocess.run([
                "/usr/bin/codesign", "--force", "--sign", "-",
                "--timestamp=none", "--entitlements", str(entitlement_path),
                str(app)
            ], check=True, capture_output=True, timeout=45)
        if alter_signed_exe:
            exe = app / "MangaReader12"
            exe.write_bytes(exe.read_bytes() + b"MODIFIED-AFTER-CODESIGN")
        with zipfile.ZipFile(self.ipa, "w", zipfile.ZIP_DEFLATED) as archive:
            for member in sorted((stage / "Payload").rglob("*")):
                if member.is_file():
                    archive.write(member, member.relative_to(stage).as_posix())
        self.digest = hashlib.sha256(self.ipa.read_bytes()).hexdigest()
        self.checksum = (self.digest + "  " + QA_FILENAME + "\n").encode("ascii")

    def audit(self, *, baseline=70, checksum=None):
        return preflight_di_build71_private_qa(
            self.ipa, installed_build=baseline,
            checksum_data=self.checksum if checksum is None else checksum,
        )

    def test_real_apple_ad_hoc_signed_build71_is_host_only_not_distributable(self):
        self.build_disposable_ipa()
        receipt = self.audit()
        self.assertEqual(receipt["candidateBuild"], 71)
        self.assertEqual(receipt["expectedInstalledPhysicalBuild"], 70)
        self.assertEqual(receipt["iosMinimumDeclared"], "12.0")
        self.assertEqual(receipt["iosMinimumFromExecutable"], "12.0")
        self.assertEqual(receipt["ipaSHA256"], self.digest)
        self.assertEqual(receipt["historicalApplicationIdentifier"],
                         INSTALLED_APPLICATION_IDENTIFIER)
        self.assertTrue(receipt["adHocCodeSealIntegrityVerifiedOnHost"])
        self.assertTrue(receipt["historicalApplicationIdentifierMatches"])
        self.assertEqual(len(receipt["staticCodeDirectoryCDHash"]), 40)
        for field in (
            "checksumSourceIndependentlyAuthenticated",
            "physicalBuild70AppIdentityNewlyAttested",
            "actualDeviceInstallabilityProven",
            "finalInstallerConsumedSameBytesProven",
            "publisherCryptographicallyAuthenticated",
            "productionEditorialTrustConfigured",
            "liveHelperPeerAuthenticated",
            "libraryBackupValidated",
            "libraryFavoritesProgressPreservedOnDevice",
            "offlineChaptersVerifiedAfterUpgrade",
            "ownerQADistributionApprovalRecorded",
            "readyForPrivateQADistribution",
            "readyForProductionRelease", "githubReleasePublished",
            "mainModified", "automaticUpdaterEnabled",
            "installationAuthorized", "installationPerformed",
        ):
            self.assertFalse(receipt[field], field)

    def test_native_wrong_historical_entitlement_is_rejected(self):
        self.build_disposable_ipa(entitlement="FORGED.com.example.MangaReader12")
        with self.assertRaises(DIPrivateQARejected):
            self.audit()

    def test_native_unsigned_fixture_is_rejected(self):
        self.build_disposable_ipa(sign=False)
        with self.assertRaises(DIPrivateQARejected):
            self.audit()

    def test_native_signed_then_modified_executable_is_rejected(self):
        self.build_disposable_ipa(alter_signed_exe=True)
        with self.assertRaises(DIPrivateQARejected):
            self.audit()

    def test_native_ios13_executable_camouflaged_as_ios12_plist_is_rejected(self):
        self.build_disposable_ipa(executable_min="13.0")
        with self.assertRaises(DIPrivateQARejected):
            self.audit()

    def test_native_wrong_build70_downgrade_is_rejected(self):
        self.build_disposable_ipa(build="70")
        with self.assertRaises(DIPrivateQARejected):
            self.audit()

    def test_native_wrong_build72_upversion_is_rejected(self):
        self.build_disposable_ipa(build="72")
        with self.assertRaises(DIPrivateQARejected):
            self.audit()

    def test_native_checksum_mutation_after_local_signing_is_rejected(self):
        self.build_disposable_ipa()
        self.ipa.write_bytes(self.ipa.read_bytes() + b"POST-CHECKSUM-MUTATION")
        with self.assertRaises(DIPrivateQARejected):
            self.audit()

    def test_native_wrong_physical_baseline_is_rejected(self):
        self.build_disposable_ipa()
        for baseline in (69, 71):
            with self.subTest(baseline=baseline), self.assertRaises(DIPrivateQARejected):
                self.audit(baseline=baseline)


if __name__ == "__main__":
    unittest.main()
