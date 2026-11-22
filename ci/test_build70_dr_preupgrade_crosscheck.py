#!/usr/bin/env python3
"""DR: crosscheck read-only Build70 identity and offline metadata, never authority."""
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from build70_dr_preupgrade_crosscheck import DRRejected, audit_dr_preupgrade
from test_build70_dq_installed_bundle_report import synthetic
from test_build70_do_preupgrade_baseline_audit import continuity, offline

ROOT = Path(__file__).resolve().parent


class DRPreupgradeTests(unittest.TestCase):
    def assert_no_authority(self, receipt):
        for key in (
            "reportOriginsCryptographicallyAuthenticated",
            "sameDeviceAndSameMomentProven",
            "installedBuild70NativeSignatureValidated",
            "installedBuild70EntitlementAttested",
            "build71IPABytesSuppliedOrValidatedHere",
            "build71IOSInstallationCompatibilityProven",
            "publisherAuthenticated",
            "backupOutsideDeviceValidated",
            "libraryAndFavoritesContentsVerified",
            "offlineImageBytesDecodedAndReadWithoutWifi",
            "dataContainerSurvivalAcrossUpgradeProven",
            "ownerPrivateQADistributionConsentRecorded",
            "productionTrustProvisioned",
            "helperPeerAuthenticated",
            "readyToDistributeIPA", "readyToInstallIPA",
            "automaticUpdaterEnabled",
            "installationAuthorized", "installationPerformed",
        ):
            self.assertIs(receipt[key], False, key)

    def assess(self, dq=None, counts=None, batches=None):
        return audit_dr_preupgrade(
            synthetic() if dq is None else dq,
            continuity() if counts is None else counts,
            [offline()] if batches is None else batches,
        )

    def test_matching_reports_never_authorize(self):
        r = self.assess()
        self.assertEqual(r["status"],
                         "DR_PREUPGRADE_TEXT_COHERENT_NOT_ATTESTED_NOT_INSTALLABLE")
        self.assertTrue(r["bothReportFormatsTextuallyCoherent"])
        self.assertEqual(r["reportedInstalledBuild"], "70")
        self.assertEqual(r["reportedCompletedChapterRecords"], 3)
        self.assert_no_authority(r)

    def test_real_shell_single_terminal_lf_acceptance(self):
        r = self.assess(dq=synthetic()+b"\n")
        self.assertTrue(r["bothReportFormatsTextuallyCoherent"])
        self.assert_no_authority(r)

    def test_claimed_installed_identity_mismatch_is_stop(self):
        cases = [
            synthetic(bundle="com.example.other"),
            synthetic(build="71"),
            synthetic(entitlement="DIFFERENT.application-identifier"),
        ]
        for dq in cases:
            with self.subTest(dq=dq[:80]):
                r = self.assess(dq=dq)
                self.assertEqual(r["status"], "DR_REPORTED_IDENTITY_MISMATCH_STOP_QA")
                self.assertFalse(r["bothReportFormatsTextuallyCoherent"])
                self.assert_no_authority(r)

    def test_unavailable_identity_is_not_replaced_with_historical_guess(self):
        for key in ("bundle", "build", "entitlement"):
            r = self.assess(dq=synthetic(**{key: "UNAVAILABLE"}))
            self.assertEqual(r["status"],
                             "DR_REPORTED_INSTALLED_IDENTITY_UNAVAILABLE_NOT_READY")
            self.assert_no_authority(r)

    def test_offline_failure_stop_takes_precedence_over_unavailable_identity(self):
        r = self.assess(
            dq=synthetic(bundle="UNAVAILABLE"),
            batches=[offline(valid=2, sealed=2, pages=4)],
        )
        self.assertEqual(r["status"], "DR_REPORTED_OFFLINE_METADATA_FAILURE_STOP_QA")
        self.assert_no_authority(r)

    def test_identity_mismatch_takes_precedence_over_offline_failure(self):
        r = self.assess(
            dq=synthetic(build="71"),
            batches=[offline(valid=2, sealed=2, pages=4)],
        )
        self.assertEqual(r["status"], "DR_REPORTED_IDENTITY_MISMATCH_STOP_QA")
        self.assert_no_authority(r)

    def test_legacy_offline_records_require_physical_reading(self):
        r = self.assess(batches=[offline(valid=3, sealed=1)])
        self.assertEqual(r["status"],
                         "DR_REPORTED_LEGACY_OFFLINE_NEEDS_REAL_READING")
        self.assertEqual(r["reportedLegacyChapters"], 2)
        self.assert_no_authority(r)

    def test_partial_offline_inventory_never_claims_complete(self):
        r = self.assess(counts=continuity(130), batches=[offline(total=130)])
        self.assertEqual(r["status"], "DR_REPORTED_OFFLINE_BATCHES_INCOMPLETE")
        self.assertEqual(r["reportedRemainingUninspectedChapters"], 66)
        self.assertFalse(r["bothReportFormatsTextuallyCoherent"])
        self.assert_no_authority(r)

    def test_two_sequential_batches_are_textually_coherent_only(self):
        r = self.assess(
            counts=continuity(65),
            batches=[offline(total=65, offset=0), offline(total=65, offset=64)],
        )
        self.assertTrue(r["bothReportFormatsTextuallyCoherent"])
        self.assertEqual(r["reportedInspectedChapterRecords"], 65)
        self.assert_no_authority(r)

    def test_zero_completed_records_is_not_proof_offline_is_empty(self):
        r = self.assess(counts=continuity(0), batches=[offline(total=0)])
        self.assertEqual(
            r["status"], "DR_REPORTED_NO_COMPLETED_OFFLINE_METADATA_NOT_DEVICE_PROOF",
        )
        self.assert_no_authority(r)

    def test_missing_or_out_of_order_offline_batches_rejected(self):
        with self.assertRaises(DRRejected):
            self.assess(counts=continuity(65), batches=[offline(total=65, offset=64)])
        with self.assertRaises(DRRejected):
            self.assess(counts=continuity(65), batches=[offline(total=65)]*2)
        with self.assertRaises(DRRejected):
            self.assess(batches=[])

    def test_tampered_dq_or_different_report_build_rejected(self):
        cases = (
            (synthetic()+b"\n\n", continuity(), [offline()]),
            (synthetic()+b"\nINSTALLATION_AUTHORIZED=YES", continuity(), [offline()]),
            (synthetic(), continuity(build=71), [offline()]),
            (synthetic(), continuity(), [offline(build=71)]),
        )
        for dq, counts, batches in cases:
            with self.subTest(dq=dq[-30:]), self.assertRaises(DRRejected):
                self.assess(dq=dq, counts=counts, batches=batches)

    def test_random_tampering_never_promotes_authority(self):
        rng = random.Random(20261111)
        for _ in range(200):
            data = bytearray(synthetic()+b"\n")
            index = rng.randrange(len(data))
            data[index] ^= rng.randrange(1, 256)
            try:
                receipt = self.assess(dq=bytes(data))
            except DRRejected:
                continue
            self.assert_no_authority(receipt)

    def test_cli_reads_only_user_supplied_regular_text_files(self):
        with tempfile.TemporaryDirectory(prefix="wr-dr-evidence-") as temp:
            folder = Path(temp)
            inputs = {
                "dq.txt": synthetic()+b"\n",
                "counts.txt": continuity(),
                "offline.txt": offline(),
            }
            for name, data in inputs.items():
                (folder/name).write_bytes(data)
            command = [
                sys.executable, str(ROOT/"build70_dr_preupgrade_crosscheck.py"),
                "--dq", str(folder/"dq.txt"),
                "--counts", str(folder/"counts.txt"),
                "--offline", str(folder/"offline.txt"),
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=12,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_no_authority(json.loads(result.stdout))
            for name, data in inputs.items():
                self.assertEqual((folder/name).read_bytes(), data)

    def test_cli_denies_symlinked_dq_report(self):
        with tempfile.TemporaryDirectory(prefix="wr-dr-symlink-") as temp:
            folder = Path(temp)
            (folder/"dq.txt").write_bytes(synthetic())
            (folder/"counts.txt").write_bytes(continuity())
            (folder/"offline.txt").write_bytes(offline())
            (folder/"dq-link.txt").symlink_to(folder/"dq.txt")
            result = subprocess.run(
                [sys.executable, str(ROOT/"build70_dr_preupgrade_crosscheck.py"),
                 "--dq", str(folder/"dq-link.txt"),
                 "--counts", str(folder/"counts.txt"),
                 "--offline", str(folder/"offline.txt")],
                capture_output=True, text=True, timeout=12,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BLOCKED", result.stderr)

    def test_no_install_apis_or_fabricated_attestation_in_source(self):
        source = (ROOT/"build70_dr_preupgrade_crosscheck.py").read_text()
        for prohibited in ("posix_spawn(", "subprocess.run(", "appinst(",
                           "unlink(", "write_bytes(", "write_text("):
            self.assertNotIn(prohibited, source)


if __name__ == "__main__":
    unittest.main()
