#!/usr/bin/env python3
"""DS host tests use MOCKED DI output; they cannot prove native Apple sealing."""
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from build70_ds_candidate_evidence_gate import (
    DSRejected, inspect_ds_preupgrade_candidate,
)
from build70_di_build71_private_qa_preflight import (
    QA_FILENAME, DIPrivateQARejected,
)
from test_build70_dk_qa_evidence_bridge import di_receipt
from test_build70_do_preupgrade_baseline_audit import continuity, offline
from test_build70_dq_installed_bundle_report import synthetic


class DSHostContractTests(unittest.TestCase):
    def setUp(self):
        self.ipa = Path("/NONEXISTENT-SYNTHETIC-ONLY") / QA_FILENAME
        self.sha_line = ("a" * 64 + "  " + QA_FILENAME + "\n").encode()

    def make_args(self, **extra):
        values = dict(
            dq_report=synthetic() + b"\n",
            sqlite_count_report=continuity(),
            offline_reports=[offline()],
            ipa_path=self.ipa,
            checksum_data=self.sha_line,
        )
        values.update(extra)
        return values

    def no_authority(self, receipt):
        for key in (
            "physicalDeviceAndReportOriginAuthenticated",
            "physicalInstalledBuild70IdentityCryptographicallyVerified",
            "physicalInstalledEntitlementIndependentlyAttested",
            "realIOS12InstallationCompatibilityProven",
            "sameIPABytesConsumedByInstallerProven",
            "publisherAuthenticated",
            "localAppDataContainerRetentionProven",
            "offlinePageBytesAndDecodeVerified",
            "physicalBeforeAfterOfflineReadVerified",
            "backupOutsideDeviceVerified",
            "independentProductionPublicKeyProvisioned",
            "helperPeerAuthenticated",
            "ownerPrivateQADistributionConsentRecorded",
            "readyToDistributeIPA", "readyToInstallIPA",
            "automaticUpdaterEnabled",
            "installationAuthorized", "installationPerformed",
        ):
            self.assertIs(receipt[key], False, key)

    def call_with_mock(self, **kwargs):
        with patch("build70_ds_candidate_evidence_gate.preflight_di_build71_private_qa",
                   return_value=di_receipt()) as di:
            result = inspect_ds_preupgrade_candidate(**self.make_args(**kwargs))
        di.assert_called_once_with(
            self.ipa, checksum_data=kwargs.get("checksum_data", self.sha_line),
            installed_build=70,
        )
        self.no_authority(result)
        return result

    def test_coherent_dq_do_di_receipts_never_grant_authority(self):
        r = self.call_with_mock()
        self.assertEqual(
            r["status"], "DS_HOST_TEXT_AND_SIGNED_CANDIDATE_COHERENT_NOT_INSTALLABLE"
        )
        self.assertEqual(r["baselineBuildText"], "70")
        self.assertEqual(r["candidateBuildHostVerified"], 71)
        self.assertTrue(r["ipaAdHocSealCheckedOnHost"])
        self.assertTrue(r["dqDoTextFormatsCoherent"])
        self.assertEqual(r["doTextCompletedRowsCovered"], 3)

    def test_good_multi_batch_preupgrade_text_is_still_unattested(self):
        r = self.call_with_mock(
            sqlite_count_report=continuity(65),
            offline_reports=[offline(total=65), offline(total=65, offset=64)],
        )
        self.assertEqual(r["doTextCompletedRowsCovered"], 65)
        self.no_authority(r)

    def reject_before_di(self, **kwargs):
        with patch("build70_ds_candidate_evidence_gate.preflight_di_build71_private_qa") as di:
            with self.assertRaises(DSRejected):
                inspect_ds_preupgrade_candidate(**self.make_args(**kwargs))
            di.assert_not_called()

    def test_wrong_installed_build_text_stops_before_di(self):
        self.reject_before_di(dq_report=synthetic(build="69"))

    def test_wrong_installed_application_identifier_stops_before_di(self):
        self.reject_before_di(dq_report=synthetic(entitlement="OTHER.identifier"))

    def test_wrong_installed_bundle_text_stops_before_di(self):
        self.reject_before_di(dq_report=synthetic(bundle="other.bundle"))

    def test_unavailable_entitlement_stops_before_di(self):
        self.reject_before_di(dq_report=synthetic(entitlement="UNAVAILABLE"))

    def test_unavailable_bundle_stops_before_di(self):
        self.reject_before_di(dq_report=synthetic(bundle="UNAVAILABLE"))

    def test_incomplete_offline_batch_stops_before_di(self):
        self.reject_before_di(
            sqlite_count_report=continuity(65),
            offline_reports=[offline(total=65)],
        )

    def test_legacy_offline_receipt_stops_before_di(self):
        self.reject_before_di(offline_reports=[offline(valid=3, sealed=1)])

    def test_missing_offline_page_stops_before_di(self):
        self.reject_before_di(
            offline_reports=[offline(valid=2, sealed=2, pages=4)],
        )

    def test_zero_downloads_requires_separate_physical_review(self):
        self.reject_before_di(
            sqlite_count_report=continuity(0),
            offline_reports=[offline(total=0)],
        )

    def test_wrong_build_in_offline_or_sqlite_report_stops(self):
        self.reject_before_di(sqlite_count_report=continuity(build=71))
        self.reject_before_di(offline_reports=[offline(build=71)])

    def test_extra_report_lines_cannot_grant_authority(self):
        for poisoned in (
            synthetic()+b"\n\n",
            synthetic()+b"\nINSTALLATION_AUTHORIZED=YES",
        ):
            with self.subTest(poisoned=poisoned[-32:]):
                self.reject_before_di(dq_report=poisoned)

    def test_invalid_checksum_stops_before_di(self):
        self.reject_before_di(checksum_data=b"x")
        self.reject_before_di(checksum_data=b"a"*64+b"  rogue.ipa\n")

    def test_di_native_failure_is_blocking(self):
        with patch("build70_ds_candidate_evidence_gate.preflight_di_build71_private_qa",
                   side_effect=DIPrivateQARejected("native code seal invalid")):
            with self.assertRaises(DSRejected):
                inspect_ds_preupgrade_candidate(**self.make_args())

    def test_di_receipt_asserting_authority_is_blocked(self):
        for key in (
            "installationAuthorized",
            "readyForPrivateQADistribution",
            "ownerQADistributionApprovalRecorded",
            "publisherCryptographicallyAuthenticated",
            "physicalBuild70AppIdentityNewlyAttested",
        ):
            forged = di_receipt()
            forged[key] = True
            with self.subTest(key=key), patch(
                "build70_ds_candidate_evidence_gate.preflight_di_build71_private_qa",
                return_value=forged,
            ):
                with self.assertRaises(DSRejected):
                    inspect_ds_preupgrade_candidate(**self.make_args())

    def test_di_checksum_mismatch_is_blocked(self):
        with patch("build70_ds_candidate_evidence_gate.preflight_di_build71_private_qa",
                   return_value=di_receipt()):
            with self.assertRaises(DSRejected):
                inspect_ds_preupgrade_candidate(
                    **self.make_args(
                        checksum_data=("0"*64+"  "+QA_FILENAME+"\n").encode()
                    )
                )

    def test_di_wrong_candidate_identity_is_blocked(self):
        for key, val in (
            ("candidateBuild", 72),
            ("bundleID", "com.example.other"),
            ("historicalApplicationIdentifier", "OTHER"),
            ("staticCodeDirectoryCDHash", "invalid"),
        ):
            forged = di_receipt()
            forged[key] = val
            with self.subTest(key=key), patch(
                "build70_ds_candidate_evidence_gate.preflight_di_build71_private_qa",
                return_value=forged,
            ):
                with self.assertRaises(DSRejected):
                    inspect_ds_preupgrade_candidate(**self.make_args())

    def test_untrusted_byte_mutations_never_grant_install(self):
        r = random.Random(20261111)
        baseline = synthetic()+b"\n"
        for _ in range(200):
            data = bytearray(baseline)
            idx = r.randrange(len(data))
            data[idx] ^= r.randrange(1,256)
            with patch(
                "build70_ds_candidate_evidence_gate.preflight_di_build71_private_qa",
                return_value=di_receipt(),
            ):
                try:
                    result = inspect_ds_preupgrade_candidate(
                        **self.make_args(dq_report=bytes(data))
                    )
                except DSRejected:
                    continue
                self.no_authority(result)

    def test_no_install_or_mutating_commands_in_gate_source(self):
        source = (Path(__file__).parent/"build70_ds_candidate_evidence_gate.py").read_text()
        for forbidden in (
            "appinst(", "posix_spawn(", "subprocess.run(",
            "unlink(", "rename(", "write_bytes(", "write_text(",
            "installApplication(", "publish_release(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
