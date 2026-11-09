#!/usr/bin/env python3
"""Build69 BC: hostile copied IPA/receipt tests, with temporary dummy bytes.

These are host byte-transfer tests, NOT a real iOS code-signing result.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from build69_bc_copied_ipa_recheck import (
    CopiedQARejected, FALSE_FLAGS, TRUE_FLAGS,
    QA_FILE_NAME, parse_host_receipt, review_copied_qa_ipa
)


class CopiedPrivateQATests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="wr69-bc-copy-fixture-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.asset = self.root / QA_FILE_NAME
        self.asset.write_bytes(b"synthetic transfer test ONLY: NOT a real IPA")
        self.receipt = self.good_receipt()
        self.checksum = self.owner_checksum()

    def good_receipt(self):
        fields = {
            "status": "HOST_ONLY_PRIVATE_QA_PREFLIGHT_NOT_DISTRIBUTION_APPROVAL",
            "build": 69,
            "installedBuildBaseline": 68,
            "bundleID": "com.example.MangaReader12",
            "minimumIOS": "12.0",
            "actualExecutableMinimumIOS": "12.0",
            "binaryArchitecture": "arm64",
            "verifiedApplicationIdentifier":
                "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
            "ipaSHA256": hashlib.sha256(self.asset.read_bytes()).hexdigest(),
            "ipaSize": self.asset.stat().st_size,
            "codeDirectoryCDHash": "f" * 40,
        }
        fields.update({k: False for k in FALSE_FLAGS})
        fields.update({k: True for k in TRUE_FLAGS})
        return fields

    def owner_checksum(self):
        return (self.receipt["ipaSHA256"] + "  " + QA_FILE_NAME + "\n").encode("ascii")

    def review(self, *, receipt=None, checksum=None, asset=None):
        body = json.dumps(
            self.receipt if receipt is None else receipt, sort_keys=True
        ).encode("utf-8")
        return review_copied_qa_ipa(
            ipa_path=self.asset if asset is None else asset,
            host_receipt_data=body,
            owner_checksum_data=self.checksum if checksum is None else checksum,
        )

    def test_copy_matches_only_bytes_and_never_authorizes_install(self):
        result = self.review()
        self.assertEqual(result["status"], "COPIED_BYTES_MATCH_HOST_RECEIPT_ONLY")
        self.assertTrue(result["matchesHostReceipt"])
        self.assertTrue(result["matchesSeparatelyProvidedChecksum"])
        self.assertEqual(result["fileSize"], self.asset.stat().st_size)
        self.assertEqual(result["sha256"], self.receipt["ipaSHA256"])
        self.assertEqual(result["hostCodeDirectoryCDHashClaim"], "f" * 40)
        for name, value in result.items():
            if name in ("hostReceiptAuthenticityProvenByTool",
                        "ownerChecksumIndependenceProvenByTool",
                        "editorialPublisherAuthenticated",
                        "destinationCodesignRevalidated",
                        "physicalIOSUpgradeCompatibilityProven",
                        "ownerDistributionApprovalRecorded",
                        "authorizedForInstallation", "installationPerformed",
                        "githubReleasePublished", "mainModified", "networkUsed"):
                self.assertIs(value, False, name)

    def test_destination_bytes_changed_without_changing_size(self):
        self.asset.write_bytes(self.asset.read_bytes()[:-1] + b"!")
        with self.assertRaises(CopiedQARejected):
            self.review()

    def test_destination_bytes_truncated(self):
        self.asset.write_bytes(self.asset.read_bytes()[:10])
        with self.assertRaises(CopiedQARejected):
            self.review()

    def test_reject_different_source_receipt_and_owner_checksum(self):
        for alteration in (
            {"ipaSHA256": "0" * 64},
            {"ipaSize": self.receipt["ipaSize"] + 1},
            {"codeDirectoryCDHash": "NOPE"},
            {"build": 68},
            {"installedBuildBaseline": 67},
            {"verifiedApplicationIdentifier": "WRONG.com.example.MangaReader12"},
            {"status": "DISTRIBUTION_APPROVED"},
            {"checksumMatchesIndependentlySuppliedFile": False},
            {"adHocSignatureIntegrityVerified": False},
            {"readyForDistribution": True},
            {"installationAuthorized": True},
            {"ownerDistributionApprovalRecorded": True},
            {"qaPhysicalTestCompleted": True},
            {"publisherAuthenticatedByCodeSignature": True},
        ):
            with self.subTest(alteration=alteration):
                with self.assertRaises(CopiedQARejected):
                    self.review(receipt={**self.receipt, **alteration})
        with self.assertRaises(CopiedQARejected):
            self.review(checksum=("0"*64 + "  " + QA_FILE_NAME).encode("ascii"))

    def test_symlink_and_wrong_filename_rejected(self):
        other_folder = self.root / "received"
        other_folder.mkdir()
        symlink = other_folder / QA_FILE_NAME
        symlink.symlink_to(self.asset)
        with self.assertRaises(CopiedQARejected):
            self.review(asset=symlink)
        wrong_filename = self.root / "wrong.ipa"
        self.asset.rename(wrong_filename)
        with self.assertRaises(CopiedQARejected):
            self.review(asset=wrong_filename)

    def test_duplicate_json_fields_and_nonfinite_rejected(self):
        data = json.dumps(self.receipt)
        duplicated = data[:-1] + ', "build": 69}'
        for invalid in (
            duplicated.encode(), b'{"build": 69, "build": 69}',
            b'{"build": NaN}', b'[]', b'{}', b'',
            b'{"status":"abc", "evil": Infinity}',
            b'x' * (16 * 1024 + 1),
        ):
            with self.subTest(size=len(invalid)):
                with self.assertRaises(CopiedQARejected):
                    parse_host_receipt(invalid)


if __name__ == "__main__":
    unittest.main()
