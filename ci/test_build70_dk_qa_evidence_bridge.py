#!/usr/bin/env python3
"""DK host-only evidence-bridge tests. Mock DI seals NEVER equal real signing.

The actual native Apple signed-IPA test is a separate macOS-only suite.
These tests do not read or write a WebReader user library or install anything.
"""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from build70_di_build71_private_qa_preflight import QA_FILENAME
from build70_dj_continuity_report_compare import (
    COUNT_LABELS, HEADER, NOTE, DB_HEALTH, FOOTER, IOS_VERSION,
)
from build70_dk_qa_evidence_bridge import (
    DKEvidenceRejected, _check_di_receipt, audit_dk_qa_evidence,
)

ROOT = Path(__file__).resolve().parent


def report(build: int, counts=(7, 120, 15, 2, 4, 3, 9, 1, 6)) -> bytes:
    lines = [
        HEADER, f"Build observada: {build} • iOS: {IOS_VERSION}",
        NOTE, DB_HEALTH,
        *(label + ": " + str(n) for label, n in zip(COUNT_LABELS, counts)),
        *FOOTER,
    ]
    return "\n".join(lines).encode("utf-8")


def di_receipt() -> dict:
    r = {
        "status": "DI_SIGNED_QA_SNAPSHOT_HOST_ONLY_NOT_DISTRIBUTABLE",
        "expectedInstalledPhysicalBuild": 70,
        "candidateBuild": 71,
        "bundleID": "com.example.MangaReader12",
        "iosMinimumDeclared": "12.0",
        "iosMinimumFromExecutable": "12.0",
        "architecture": "arm64",
        "ipaSHA256": "a" * 64,
        "ipaBytes": 123456,
        "checksumMatchesProvidedFile": True,
        "adHocCodeSealIntegrityVerifiedOnHost": True,
        "historicalApplicationIdentifierMatches": True,
        "historicalApplicationIdentifier":
            "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
        "staticCodeDirectoryCDHash": "b" * 40,
    }
    for key in (
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
        "readyForProductionRelease",
        "githubReleasePublished", "mainModified",
        "automaticUpdaterEnabled", "installationAuthorized",
        "installationPerformed",
    ):
        r[key] = False
    return r


class DKNoInstallEvidenceHostTests(unittest.TestCase):
    def setUp(self):
        self.before = report(70)
        self.after = report(71)
        self.checksum = ("a" * 64 + "  " + QA_FILENAME + "\n").encode("ascii")
        self.fake_ipa = Path("/DISPOSABLE-CI-MOCK-NOT-REAL-IPA") / QA_FILENAME

    def audit(self, **kwargs):
        args = {
            "ipa_path": self.fake_ipa,
            "checksum_data": self.checksum,
            "before_report": self.before,
        }
        args.update(kwargs)
        with patch("build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa",
                   return_value=di_receipt()) as mock_di:
            result = audit_dk_qa_evidence(**args)
        mock_di.assert_called_once_with(
            self.fake_ipa, checksum_data=args["checksum_data"], installed_build=70
        )
        self.assert_untrusted(result)
        return result

    def assert_untrusted(self, value: dict):
        for name in (
            "reportsIndependentlyAuthenticated",
            "deviceBuild70IdentityAttestedNow",
            "actualBuild71InstallationProven",
            "libraryContentsVerified",
            "offlinePageFilesVerified",
            "physicalOfflineChapterOpened",
            "beforeAfterReportsGenuinelyCapturedOnDevice",
            "backupPreservedOutsideDevice",
            "sameIPABytesConsumedByAppleInstaller",
            "publisherIdentityTrusted", "helperIPCAuthenticated",
            "productionEditorialTrustConfigured",
            "ownerDistributionApprovalRecorded",
            "readyToDistributePrivateIPA", "readyToInstall",
            "installationAuthorized", "installationPerformed"
        ):
            self.assertIs(value[name], False, name)

    def test_source_and_signed_qa_mock_with_baseline_remain_not_distributable(self):
        result = self.audit()
        self.assertEqual(result["status"],
                         "DK_HOST_PACKAGE_CHECKED_BASELINE_TEXT_ONLY_NO_DISTRIBUTION")
        self.assertTrue(result["baselineCountReportFormatAccepted"])
        self.assertFalse(result["afterCountReportFormatAccepted"])
        self.assertFalse(result["nineCountsTextuallyEqual"])
        self.assertEqual(result["hostIPALocalHash"], "a" * 64)

    def test_equal_before_after_counts_are_not_physical_or_install_proof(self):
        result = self.audit(after_report=self.after)
        self.assertEqual(result["status"], "DK_EQUAL_COUNT_TEXT_NOT_OFFLINE_OR_INSTALL_PROOF")
        self.assertTrue(result["nineCountsTextuallyEqual"])
        self.assertTrue(result["afterCountReportFormatAccepted"])
        self.assertEqual(result["changedCountLabels"], [])

    def test_decrease_in_offline_download_records_requires_owner_review(self):
        changed = report(71, (7, 120, 15, 2, 4, 2, 9, 1, 6))
        result = self.audit(after_report=changed)
        self.assertEqual(result["status"],
                         "DK_STOP_COUNT_DIFFERENCE_OWNER_REVIEW_REQUIRED")
        self.assertEqual(result["changedCountLabels"],
                         ["Downloads marcados completos no banco"])

    def test_increase_in_chapter_records_also_requires_review(self):
        changed = report(71, (7, 121, 15, 2, 4, 3, 9, 1, 6))
        result = self.audit(after_report=changed)
        self.assertEqual(result["status"],
                         "DK_STOP_COUNT_DIFFERENCE_OWNER_REVIEW_REQUIRED")
        self.assertEqual(result["changedCountLabels"], ["Capítulos registrados"])

    def test_all_nine_changes_report_only_labels_not_private_values(self):
        changed = report(71, (9, 150, 20, 4, 7, 5, 11, 3, 10))
        result = self.audit(after_report=changed)
        self.assertEqual(result["changedCountLabels"], list(COUNT_LABELS))
        self.assertNotIn("counts", result)
        self.assertNotIn("Obras na biblioteca: 7", str(result))

    def test_after_report_from_build70_rejected_before_any_di(self):
        with patch("build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa") as di:
            with self.assertRaises(DKEvidenceRejected):
                audit_dk_qa_evidence(
                    ipa_path=self.fake_ipa, checksum_data=self.checksum,
                    before_report=self.before, after_report=report(70),
                )
            di.assert_not_called()

    def test_missing_before_report_rejected_before_any_di(self):
        with patch("build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa") as di:
            with self.assertRaises(DKEvidenceRejected):
                audit_dk_qa_evidence(
                    ipa_path=self.fake_ipa, checksum_data=self.checksum,
                    before_report=b"",
                )
            di.assert_not_called()

    def test_wrong_ios_or_database_unavailable_prevents_di_call(self):
        for bad in (
            self.before.replace(b"12.5.8", b"13.0"),
            self.before.replace(DB_HEALTH.encode(), b"Banco: INDISPONIVEL"),
        ):
            with self.subTest(bad=bad[:55]):
                with patch("build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa") as di:
                    with self.assertRaises(DKEvidenceRejected):
                        audit_dk_qa_evidence(
                            ipa_path=self.fake_ipa, checksum_data=self.checksum,
                            before_report=bad,
                        )
                    di.assert_not_called()

    def test_wrong_checksum_or_candidate_filename_prevents_di_call(self):
        for bad in (
            ("0" * 64 + "  " + QA_FILENAME + "\n").encode(),
            ("a" * 64 + "  WebReader-Build70-iOS12-adhoc.ipa\n").encode(),
            b"",
        ):
            with patch("build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa") as di:
                # Wrong SHA digest is syntactically valid, so it must
                # reach the real DI verifier (mocked here), but mismatched
                # receipts are rejected independently in DK.
                if bad.startswith(b"0" * 64):
                    with patch("build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa",
                               return_value=di_receipt()) as fake:
                        with self.assertRaises(DKEvidenceRejected):
                            audit_dk_qa_evidence(
                                ipa_path=self.fake_ipa, checksum_data=bad,
                                before_report=self.before,
                            )
                        fake.assert_called_once()
                else:
                    with self.assertRaises(DKEvidenceRejected):
                        audit_dk_qa_evidence(
                            ipa_path=self.fake_ipa, checksum_data=bad,
                            before_report=self.before,
                        )
                    di.assert_not_called()

    def test_di_failure_never_promoted_to_receipt(self):
        with patch("build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa",
                   side_effect=OSError("codesign unavailable")):
            with self.assertRaises(DKEvidenceRejected):
                audit_dk_qa_evidence(
                    ipa_path=self.fake_ipa, checksum_data=self.checksum,
                    before_report=self.before,
                )

    def test_forged_positive_di_authority_flag_rejected(self):
        for key in (
            "installationAuthorized", "readyForPrivateQADistribution",
            "ownerQADistributionApprovalRecorded",
            "mainModified", "liveHelperPeerAuthenticated",
            "checksumSourceIndependentlyAuthenticated",
        ):
            poisoned = di_receipt()
            poisoned[key] = True
            with self.subTest(key=key), patch(
                "build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa",
                return_value=poisoned,
            ):
                with self.assertRaises(DKEvidenceRejected):
                    audit_dk_qa_evidence(
                        ipa_path=self.fake_ipa, checksum_data=self.checksum,
                        before_report=self.before,
                    )

    def test_forged_identity_and_signing_metadata_rejected(self):
        cases = (
            ("expectedInstalledPhysicalBuild", 69),
            ("candidateBuild", 70),
            ("candidateBuild", True),
            ("bundleID", "com.example.spoofed"),
            ("iosMinimumFromExecutable", "13.0"),
            ("architecture", "x86_64"),
            ("adHocCodeSealIntegrityVerifiedOnHost", False),
            ("ipaSHA256", "c" * 64),
            ("staticCodeDirectoryCDHash", "not-hex"),
            ("historicalApplicationIdentifier", "FAKE.application.identifier"),
        )
        for key, value in cases:
            poisoned = di_receipt()
            poisoned[key] = value
            with self.subTest(key=key), patch(
                "build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa",
                return_value=poisoned,
            ):
                with self.assertRaises(DKEvidenceRejected):
                    audit_dk_qa_evidence(
                        ipa_path=self.fake_ipa, checksum_data=self.checksum,
                        before_report=self.before,
                    )

    def test_missing_di_key_fails_closed(self):
        poisoned = di_receipt()
        poisoned.pop("installationPerformed")
        with patch("build70_dk_qa_evidence_bridge.preflight_di_build71_private_qa",
                   return_value=poisoned):
            with self.assertRaises(DKEvidenceRejected):
                audit_dk_qa_evidence(
                    ipa_path=self.fake_ipa, checksum_data=self.checksum,
                    before_report=self.before,
                )

    def test_di_receipt_rejects_bad_file_size_and_cdhash(self):
        for key, value in (
            ("ipaBytes", 0),
            ("ipaBytes", True),
            ("ipaBytes", 512 * 1024 * 1024 + 1),
            ("staticCodeDirectoryCDHash", "x" * 40),
        ):
            poisoned = di_receipt()
            poisoned[key] = value
            with self.subTest(key=key), self.assertRaises(DKEvidenceRejected):
                _check_di_receipt(poisoned, "a" * 64)

    def test_signing_hash_and_report_counts_are_never_cryptographic_provenance(self):
        result = self.audit(after_report=self.after)
        self.assertTrue(result["hostAdHocSealVerified"])
        self.assertFalse(result["publisherIdentityTrusted"])
        self.assertFalse(result["reportsIndependentlyAuthenticated"])
        self.assertFalse(result["sameIPABytesConsumedByAppleInstaller"])
        self.assertFalse(result["readyToDistributePrivateIPA"])

    def test_dk_only_calls_readonly_preflight_and_report_helpers(self):
        tree = ast.parse((ROOT / "build70_dk_qa_evidence_bridge.py").read_text())
        calls = {
            n.func.id if isinstance(n.func, ast.Name) else n.func.attr
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, (ast.Name, ast.Attribute))
        }
        prohibited = {
            "appinst", "posix_spawn", "installApplication", "Popen",
            "system", "unlink", "rename", "write_bytes", "write_text",
            "chmod", "chown", "upload_artifact", "publish_release",
            "make_archive", "ZipFile", "codesign",
        }
        self.assertFalse(calls & prohibited)
        for necessary in (
            "preflight_di_build71_private_qa", "parse_di_checksum",
            "check_before_report", "compare_reports", "inspect_dh_source",
        ):
            self.assertIn(necessary, calls)


if __name__ == "__main__":
    unittest.main()
