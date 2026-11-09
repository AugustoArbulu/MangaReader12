#!/usr/bin/env python3
"""Build69 BB: macOS test with disposable iOS12 ARM64 executable and ad-hoc seal.

Never uses a real WebReader IPA, device, release private key, or live installer.
The synthetic archive exists only under TemporaryDirectory and is destroyed.
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
from build69_bb_private_qa_ipa_preflight import (
    QA_FILE_NAME, PrivateQAPreflightRejected, preflight_private_qa_ipa,
    parse_independent_checksum
)


@unittest.skipUnless(sys.platform == "darwin", "requires macOS native codesign")
class NativePrivateQAReceipt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wr69-bb-qa-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ipa = self.root / QA_FILE_NAME

    def fixture(self, *, build="69", compile_min="12.0",
                entitlement=INSTALLED_APPLICATION_IDENTIFIER,
                sign=True, tamper=False):
        app = self.root / "staging" / "Payload" / "MangaReader12.app"
        app.mkdir(parents=True, exist_ok=True)
        info = {
            "CFBundleIdentifier": "com.example.MangaReader12",
            "CFBundleExecutable": "MangaReader12",
            "CFBundleDisplayName": "WebReader",
            "CFBundleName": "WebReader",
            "CFBundleVersion": build,
            "CFBundlePackageType": "APPL",
            "MinimumOSVersion": "12.0",
        }
        (app / "Info.plist").write_bytes(plistlib.dumps(info))
        src = self.root / "hello.c"
        src.write_text("int main(void) { return 0; }\n", encoding="utf8")
        subprocess.run([
            "xcrun", "--sdk", "iphoneos", "clang",
            "-arch", "arm64", "-miphoneos-version-min=" + compile_min,
            str(src), "-o", str(app / "MangaReader12")
        ], check=True, capture_output=True, timeout=45)
        ent_path = self.root / "ad-hoc-only.entitlements"
        ent_path.write_bytes(plistlib.dumps({"application-identifier": entitlement}))
        if sign:
            subprocess.run([
                "/usr/bin/codesign", "--force", "--sign", "-",
                "--timestamp=none", "--entitlements", str(ent_path), str(app)
            ], check=True, capture_output=True, timeout=45)
        if tamper:
            exe = app / "MangaReader12"
            exe.write_bytes(exe.read_bytes() + b"AFTER-SIGNING")
        with zipfile.ZipFile(self.ipa, "w", zipfile.ZIP_DEFLATED) as bundle:
            for file in sorted((self.root / "staging" / "Payload").rglob("*")):
                if file.is_file():
                    bundle.write(file, file.relative_to(self.root / "staging").as_posix())
        payload = self.ipa.read_bytes()
        self.sha = hashlib.sha256(payload).hexdigest()
        self.checksum = (self.sha + "  " + QA_FILE_NAME + "\n").encode("ascii")

    def audit(self, *, checksum=None, baseline=68):
        return preflight_private_qa_ipa(
            self.ipa, checksum_data=self.checksum if checksum is None else checksum,
            baseline=baseline
        )

    def test_real_ios12_arm64_ad_hoc_fixture_has_no_publish_or_install_authority(self):
        self.fixture()
        receipt = self.audit()
        self.assertEqual(receipt["build"], 69)
        self.assertEqual(receipt["actualExecutableMinimumIOS"], "12.0")
        self.assertEqual(receipt["binaryArchitecture"], "arm64")
        self.assertEqual(receipt["ipaSHA256"], self.sha)
        self.assertTrue(receipt["adHocSignatureIntegrityVerified"])
        self.assertTrue(receipt["installedApplicationIdentifierMatch"])
        self.assertEqual(receipt["verifiedApplicationIdentifier"],
                         INSTALLED_APPLICATION_IDENTIFIER)
        for key in (
            "publisherAuthenticatedByCodeSignature",
            "deviceInstallationCompatibilityProven",
            "qaPhysicalTestCompleted",
            "backupAndOfflineLibraryPreservationProven",
            "editorialProductionKeyProvisioned", "ownerDistributionApprovalRecorded",
            "readyForDistribution", "githubReleasePublished", "mainModified",
            "chimeraInstallationAuthorized", "installationAuthorized",
            "installationPerformed"
        ):
            self.assertFalse(receipt[key], key)

    def test_bad_independent_checksum_and_old_baseline(self):
        self.fixture()
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit(checksum=("0" * 64 + "  " + QA_FILE_NAME).encode())
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit(baseline=67)
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit(baseline=True)
        for invalid in (
            b"", b"corrupt", b"0"*64 + b"  other.ipa\n",
            b"f"*64 + b"  " + QA_FILE_NAME.encode() + b"\nother",
        ):
            with self.subTest(invalid=invalid[:20]):
                with self.assertRaises(PrivateQAPreflightRejected):
                    parse_independent_checksum(invalid)

    def test_unrelated_or_symlinked_ipa_rejected(self):
        self.fixture()
        new_name = self.root / "other.ipa"
        self.ipa.rename(new_name)
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit()
        self.ipa.symlink_to(new_name)
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit()

    def test_wrong_ad_hoc_entitlement_rejected(self):
        self.fixture(entitlement="WRONG.com.example.MangaReader12")
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit()

    def test_unsigned_ipa_rejected(self):
        self.fixture(sign=False)
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit()

    def test_tampered_executable_rejected(self):
        self.fixture(tamper=True)
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit()

    def test_ios13_binary_disguised_by_ios12_plist_rejected(self):
        self.fixture(compile_min="13.0")
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit()

    def test_wrong_build_version_rejected(self):
        self.fixture(build="70")
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit()

    def test_mutated_package_rejected_with_same_checksum(self):
        self.fixture()
        with self.ipa.open("ab") as out:
            out.write(b"POST-HASH-MUTATION")
        with self.assertRaises(PrivateQAPreflightRejected):
            self.audit()


if __name__ == "__main__":
    unittest.main()
