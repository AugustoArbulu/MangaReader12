#!/usr/bin/env python3
"""DI: Build70 -> Build71 QA snapshot preflight negative/host tests.

Fake signed receipts in mock-based cases are NOT Apple code signatures.
All fixture archives are disposable, and success NEVER approves QA delivery.
"""
import hashlib
import io
from pathlib import Path
import plistlib
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from build66_code_signature_gate import INSTALLED_APPLICATION_IDENTIFIER
from build70_di_build71_private_qa_preflight import (
    DIPrivateQARejected, QA_FILENAME, parse_di_checksum,
    preflight_di_build71_private_qa,
)


def arm64_min12_fixture() -> bytes:
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 0, 2, 1, 24, 0, 0)
    lc = struct.pack("<IIIIII", 0x32, 24, 2, 12 << 16, 18 << 16, 0)
    return header + lc


class DISnapshotPreflightHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wr-di-qa-host-only-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ipa = self.root / QA_FILENAME

    def checksum(self, digest: str) -> bytes:
        return (digest + "  " + QA_FILENAME + "\n").encode("ascii")

    def fixture(self, *, build="71", bundle="com.example.MangaReader12",
                min_ios="12.0", binary=None):
        info = {
            "CFBundleVersion": build,
            "CFBundleIdentifier": bundle,
            "CFBundleExecutable": "MangaReader12",
            "CFBundleDisplayName": "WebReader",
            "CFBundleName": "WebReader",
            "MinimumOSVersion": min_ios,
            "CFBundlePackageType": "APPL",
        }
        with zipfile.ZipFile(self.ipa, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("Payload/MangaReader12.app/Info.plist",
                       plistlib.dumps(info))
            z.writestr("Payload/MangaReader12.app/MangaReader12",
                       arm64_min12_fixture() if binary is None else binary)
        self.digest = hashlib.sha256(self.ipa.read_bytes()).hexdigest()
        self.sha_line = self.checksum(self.digest)

    def check(self, *, baseline=70, checksum=None):
        return preflight_di_build71_private_qa(
            self.ipa, checksum_data=self.sha_line if checksum is None else checksum,
            installed_build=baseline,
        )

    def test_strict_sha_line_is_accepted_only_with_exact_case_and_spacing(self):
        payload = self.checksum("f" * 64)
        self.assertEqual(parse_di_checksum(payload), "f" * 64)

    def test_checksum_file_name_is_pinned_to_candidate_71(self):
        for wrong in ("WebReader-Build70-iOS12-adhoc.ipa",
                      "WebReader-Build72-iOS12-adhoc.ipa",
                      "other.ipa"):
            with self.subTest(wrong=wrong), self.assertRaises(DIPrivateQARejected):
                parse_di_checksum(("a" * 64 + "  " + wrong + "\n").encode())

    def test_sha_rejects_uppercase_extra_data_missing_newline_and_ambiguous_spaces(self):
        canonical = self.checksum("a" * 64)
        invalid = (
            canonical[:-1], canonical + b"\n", canonical + b"extra",
            canonical + b"\0", canonical.replace(b"aa", b"AA", 1),
            canonical.replace(b"  ", b" ", 1),
            canonical.replace(b"  ", b"   ", 1),
            canonical.replace(b"\n", b"\r\n", 1),
            b"", b"A" * 513, b"\xff" + canonical,
        )
        for entry in invalid:
            with self.subTest(first=repr(entry[:32])), self.assertRaises(DIPrivateQARejected):
                parse_di_checksum(entry)

    def test_only_exact_installed_build_70_is_accepted(self):
        self.fixture()
        for baseline in (-1, 0, 56, 65, 69, 71, 72, True, False, "70", 70.0, None):
            with self.subTest(baseline=baseline), self.assertRaises(DIPrivateQARejected):
                self.check(baseline=baseline)

    def test_no_checksum_or_wrong_digest_does_not_reach_codesign(self):
        self.fixture()
        with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot") as sign:
            for bad in (self.checksum("0" * 64), b"corrupt", b""):
                with self.subTest(bad=bad), self.assertRaises(DIPrivateQARejected):
                    self.check(checksum=bad)
            sign.assert_not_called()

    def test_forged_build70_downgrade_does_not_reach_codesign(self):
        self.fixture(build="70")
        with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot") as sign:
            with self.assertRaises(DIPrivateQARejected):
                self.check()
            sign.assert_not_called()

    def test_future_build72_is_rejected_before_codesign(self):
        self.fixture(build="72")
        with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot") as sign:
            with self.assertRaises(DIPrivateQARejected):
                self.check()
            sign.assert_not_called()

    def test_wrong_bundle_rejected_before_codesign(self):
        self.fixture(bundle="com.example.other")
        with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot") as sign:
            with self.assertRaises(DIPrivateQARejected):
                self.check()
            sign.assert_not_called()

    def test_ios13_disguised_as_ios12_rejected(self):
        self.fixture(min_ios="13.0")
        with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot") as sign:
            with self.assertRaises(DIPrivateQARejected):
                self.check()
            sign.assert_not_called()

    def test_symlink_ipa_rejected_before_any_hash_or_codesign(self):
        self.fixture()
        target = self.root / "real.ipa"
        self.ipa.rename(target)
        self.ipa.symlink_to(target)
        with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot") as sign:
            with self.assertRaises(DIPrivateQARejected):
                self.check()
            sign.assert_not_called()

    def test_wrong_ipa_filename_rejected(self):
        self.fixture()
        target = self.root / "rogue.ipa"
        self.ipa.rename(target)
        with self.assertRaises(DIPrivateQARejected):
            self.check()

    def test_binary_header_architecture_does_not_pass_even_with_fake_signature(self):
        binary = bytearray(arm64_min12_fixture())
        struct.pack_into("<I", binary, 4, 0x01000007)  # x86_64
        self.fixture(binary=bytes(binary))
        with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot") as sign:
            with self.assertRaises(DIPrivateQARejected):
                self.check()
            sign.assert_not_called()

    def test_signed_receipt_mock_is_not_distribution_or_install_authority(self):
        """Simulated seal only: validate defensive receipt logic, not codesign."""
        self.fixture()
        synthetic_seal = {
            "adHocSignatureIntegrityVerified": True,
            "thinArm64ExecutableVerified": True,
            "installedApplicationIdentifierMatch": True,
            "applicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
            "approvedArtifactStaticCodeDirectoryCDHash": "b" * 40,
        }
        with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot",
                   return_value=synthetic_seal) as mocked:
            report = self.check()
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.args[0], self.ipa.read_bytes())
        self.assertEqual(report["expectedInstalledPhysicalBuild"], 70)
        self.assertEqual(report["candidateBuild"], 71)
        self.assertEqual(report["ipaSHA256"], self.digest)
        self.assertTrue(report["adHocCodeSealIntegrityVerifiedOnHost"])
        self.assertTrue(report["historicalApplicationIdentifierMatches"])
        self.assertEqual(report["iosMinimumFromExecutable"], "12.0")
        self.assertEqual(report["status"],
                         "DI_SIGNED_QA_SNAPSHOT_HOST_ONLY_NOT_DISTRIBUTABLE")
        for key in (
            "checksumSourceIndependentlyAuthenticated",
            "physicalBuild70AppIdentityNewlyAttested",
            "actualDeviceInstallabilityProven",
            "finalInstallerConsumedSameBytesProven",
            "publisherCryptographicallyAuthenticated",
            "productionEditorialTrustConfigured", "liveHelperPeerAuthenticated",
            "libraryBackupValidated",
            "libraryFavoritesProgressPreservedOnDevice",
            "offlineChaptersVerifiedAfterUpgrade",
            "ownerQADistributionApprovalRecorded",
            "readyForPrivateQADistribution", "readyForProductionRelease",
            "githubReleasePublished", "mainModified",
            "automaticUpdaterEnabled", "installationAuthorized",
            "installationPerformed",
        ):
            self.assertFalse(report[key], key)

    def test_signature_receipt_with_wrong_identity_or_cdhash_denied(self):
        self.fixture()
        seal = {
            "adHocSignatureIntegrityVerified": True,
            "thinArm64ExecutableVerified": True,
            "installedApplicationIdentifierMatch": True,
            "applicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
            "approvedArtifactStaticCodeDirectoryCDHash": "a" * 40,
        }
        cases = [
            {"adHocSignatureIntegrityVerified": False},
            {"thinArm64ExecutableVerified": False},
            {"installedApplicationIdentifierMatch": False},
            {"applicationIdentifier": "WRONG"},
            {"approvedArtifactStaticCodeDirectoryCDHash": "BAD"},
        ]
        for patch_data in cases:
            with self.subTest(patch_data=patch_data):
                with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot",
                           return_value={**seal, **patch_data}):
                    with self.assertRaises(DIPrivateQARejected):
                        self.check()

    def test_changed_ipa_after_calculating_checksum_is_rejected(self):
        self.fixture()
        with self.ipa.open("ab") as f:
            f.write(b"UNSIGNED-MUTATION")
        with patch("build70_di_build71_private_qa_preflight.audit_code_signature_snapshot") as sign:
            with self.assertRaises(DIPrivateQARejected):
                self.check()
            sign.assert_not_called()

    def test_preflight_has_no_artifact_creation_install_or_network(self):
        import ast
        source = (Path(__file__).parent / "build70_di_build71_private_qa_preflight.py").read_text()
        tree = ast.parse(source)
        banned = {"posix_spawn", "appinst", "codesign", "system",
                  "upload_artifact", "publish_release", "installApplication",
                  "socket", "connect", "fork", "Popen"}
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called.add(node.func.attr)
        self.assertFalse(called & banned)
        self.assertIn("installed_build != PHYSICAL_BASELINE_BUILD", source)
        self.assertIn('"ownerQADistributionApprovalRecorded": False', source)
        self.assertIn('"installationPerformed": False', source)


if __name__ == "__main__":
    unittest.main()
