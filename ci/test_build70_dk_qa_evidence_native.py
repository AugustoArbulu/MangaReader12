#!/usr/bin/env python3
"""DK macOS-only REAL native signed disposable IPA + canonical count reports.

Unlike the Linux mock tests, the temporary executable is compiled for iOS12
and the .app is ad-hoc signed with macOS codesign. The IPA exists only in
TemporaryDirectory for testing, never published/uploaded or used on an iPad.
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
from build70_di_build71_private_qa_preflight import QA_FILENAME
from build70_dj_continuity_report_compare import (
    HEADER, NOTE, DB_HEALTH, FOOTER, COUNT_LABELS, IOS_VERSION,
)
from build70_dk_qa_evidence_bridge import audit_dk_qa_evidence


def synthetic_report(build: int, downloads: int = 5) -> bytes:
    numbers = (4, 104, 20, 11, 3, downloads, 6, 2, 5)
    values = (
        [HEADER, f"Build observada: {build} • iOS: {IOS_VERSION}", NOTE, DB_HEALTH]
        + [f"{label}: {n}" for label, n in zip(COUNT_LABELS, numbers)]
        + list(FOOTER)
    )
    return "\n".join(values).encode("utf-8")


@unittest.skipUnless(sys.platform == "darwin", "needs Apple native codesign")
class DKNativeSignedFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="wr-dk-synthetic-qa-")
        cls.folder = Path(cls.temporary.name)
        cls.ipa = cls.folder / QA_FILENAME
        app = cls.folder / "payload" / "Payload" / "MangaReader12.app"
        app.mkdir(parents=True, exist_ok=True)
        (app / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleIdentifier": "com.example.MangaReader12",
            "CFBundleExecutable": "MangaReader12",
            "CFBundleDisplayName": "WebReader",
            "CFBundleName": "WebReader",
            "CFBundleVersion": "71",
            "CFBundlePackageType": "APPL",
            "MinimumOSVersion": "12.0",
        }))
        src = cls.folder / "synthetic.c"
        src.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        subprocess.run(
            ["xcrun", "--sdk", "iphoneos", "clang",
             "-arch", "arm64", "-miphoneos-version-min=12.0",
             str(src), "-o", str(app / "MangaReader12")],
            check=True, capture_output=True, timeout=45,
        )
        entitlements = cls.folder / "synthetic.entitlements"
        entitlements.write_bytes(plistlib.dumps({
            "application-identifier": INSTALLED_APPLICATION_IDENTIFIER,
        }))
        subprocess.run(
            ["/usr/bin/codesign", "--force", "--sign", "-",
             "--timestamp=none", "--entitlements", str(entitlements),
             str(app)],
            check=True, capture_output=True, timeout=45,
        )
        with zipfile.ZipFile(cls.ipa, "w", zipfile.ZIP_DEFLATED) as package:
            for path in sorted((cls.folder / "payload" / "Payload").rglob("*")):
                if path.is_file():
                    package.write(path, path.relative_to(cls.folder / "payload").as_posix())
        data = cls.ipa.read_bytes()
        cls.sha = hashlib.sha256(data).hexdigest()
        cls.checksum = (cls.sha + "  " + QA_FILENAME + "\n").encode("ascii")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_real_codesign_and_readonly_build70_baseline_have_no_authority(self):
        outcome = audit_dk_qa_evidence(
            ipa_path=self.ipa,
            checksum_data=self.checksum,
            before_report=synthetic_report(70),
        )
        self.assertEqual(
            outcome["status"],
            "DK_HOST_PACKAGE_CHECKED_BASELINE_TEXT_ONLY_NO_DISTRIBUTION",
        )
        self.assertEqual(outcome["hostIPALocalHash"], self.sha)
        self.assertEqual(len(outcome["hostStaticCodeDirectoryCDHash"]), 40)
        self.assertTrue(outcome["hostAdHocSealVerified"])
        self.assertFalse(outcome["deviceBuild70IdentityAttestedNow"])
        self.assertFalse(outcome["offlinePageFilesVerified"])
        self.assertFalse(outcome["ownerDistributionApprovalRecorded"])
        self.assertFalse(outcome["installationAuthorized"])
        self.assertFalse(outcome["installationPerformed"])

    def test_real_codesign_plus_equal_fake_reports_never_proves_offline(self):
        outcome = audit_dk_qa_evidence(
            ipa_path=self.ipa, checksum_data=self.checksum,
            before_report=synthetic_report(70),
            after_report=synthetic_report(71),
        )
        self.assertEqual(outcome["status"],
                         "DK_EQUAL_COUNT_TEXT_NOT_OFFLINE_OR_INSTALL_PROOF")
        self.assertTrue(outcome["nineCountsTextuallyEqual"])
        self.assertFalse(outcome["actualBuild71InstallationProven"])
        self.assertFalse(outcome["offlinePageFilesVerified"])
        self.assertFalse(outcome["readyToInstall"])

    def test_real_codesign_plus_changed_download_count_requires_owner_review(self):
        outcome = audit_dk_qa_evidence(
            ipa_path=self.ipa, checksum_data=self.checksum,
            before_report=synthetic_report(70),
            after_report=synthetic_report(71, downloads=4),
        )
        self.assertEqual(outcome["status"],
                         "DK_STOP_COUNT_DIFFERENCE_OWNER_REVIEW_REQUIRED")
        self.assertEqual(outcome["changedCountLabels"],
                         ["Downloads marcados completos no banco"])
        self.assertFalse(outcome["readyToDistributePrivateIPA"])
        self.assertFalse(outcome["installationAuthorized"])


if __name__ == "__main__":
    unittest.main()
