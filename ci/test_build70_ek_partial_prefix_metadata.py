#!/usr/bin/env python3
"""EK tests: synthetic paused download page-prefix metadata only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import test_build70_ej_recovery_plan_metadata as fixtures
from build70_ek_partial_prefix_metadata import (
    audit_partial_prefixes, EKRejected, MAX_PAGE_BYTES, MAX_PAGES,
)


class EKPartialPagePrefixTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.EJRecoveryPlanTests(
            "test_no_pending_legacy_completed_does_not_claim_ready"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fx = fixture
        self.root = fixture.root
        self.folder = None
        self.plan = None

    def start(self, state="paused", count=3):
        self.plan = self.fx.active(state=state)
        self.folder = self.plan.parent
        data = fixtures.fake_plan(pages=count)
        self.fx.write_plan(data)
        return self.folder

    def page(self, index, data=b"synthetic page"):
        dest = self.folder / f"page-{index:05d}.bin"
        dest.write_bytes(data)
        return dest

    def audit(self):
        return audit_partial_prefixes(self.root)

    def deny(self, result):
        for key in (
            "byteContentsOfPagesVerifiedHere", "validImageDecodingProven",
            "resumeOnIOS12Proven", "sourceDeviceAttested",
            "allUserDataRetainedProven", "readyToDistributeIPA",
            "readyToInstallIPA", "installationAuthorized",
            "restorationAuthorized", "automaticUpdaterEnabled",
        ):
            self.assertIs(result[key], False, key)

    def test_no_incomplete_rows_is_only_informational(self):
        result = self.audit()
        self.assertEqual(result["status"], "EK_NO_INCOMPLETE_DOWNLOAD_ROWS_NOT_DEVICE_PROOF")
        self.assertEqual(result["noncompletedChapterRows"], 0)
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 0)
        self.deny(result)

    def test_two_real_filename_prefix_files_are_not_image_proof(self):
        self.start(count=3)
        self.page(0)
        self.page(1)
        result = self.audit()
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PREFIX_NEEDS_IOS12_READING")
        self.assertEqual(result["noncompletedChapterRows"], 1)
        self.assertEqual(result["rowsWithPlausiblePlanPageCount"], 1)
        self.assertEqual(result["noncompletedPageFilesObserved"], 2)
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 2)
        self.assertEqual(result["nonPrefixPageFiles"], 0)
        self.deny(result)

    def test_full_page_count_but_paused_row_still_requires_physical_review(self):
        self.start(count=2)
        self.page(0)
        self.page(1)
        result = self.audit()
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 2)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PREFIX_NEEDS_IOS12_READING")
        self.deny(result)

    def test_gap_page_0_then_2_is_anomaly(self):
        self.start(count=3)
        self.page(0)
        self.page(2)
        result = self.audit()
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 1)
        self.assertEqual(result["nonPrefixPageFiles"], 1)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PAGES_OR_PLANS_REQUIRE_REVIEW")
        self.deny(result)

    def test_only_page_2_never_proves_reusable_prefix(self):
        self.start(count=3)
        self.page(2)
        result = self.audit()
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 0)
        self.assertEqual(result["nonPrefixPageFiles"], 1)
        self.deny(result)

    def test_oversized_partial_page_requires_review_without_deletion(self):
        self.start(count=2)
        path = self.folder / "page-00000.bin"
        with path.open("wb") as f:
            f.truncate(MAX_PAGE_BYTES + 1)
        result = self.audit()
        self.assertEqual(result["zeroOrOversizePageFiles"], 1)
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 0)
        self.assertTrue(path.exists())
        self.assertEqual(path.stat().st_size, MAX_PAGE_BYTES + 1)
        self.deny(result)

    def test_zero_byte_partial_page_requires_review(self):
        self.start(count=2)
        self.page(0, b"")
        result = self.audit()
        self.assertEqual(result["zeroOrOversizePageFiles"], 1)
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 0)
        self.deny(result)

    def test_page_beyond_declared_plan_is_not_reusable(self):
        self.start(count=2)
        self.page(0)
        self.page(2)
        result = self.audit()
        self.assertEqual(result["pageFilesBeyondPlan"], 1)
        self.assertEqual(result["nonPrefixPageFiles"], 0)
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 1)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PAGES_OR_PLANS_REQUIRE_REVIEW")

    def test_malformed_page_filename_is_not_silently_ignored(self):
        self.start(count=2)
        (self.folder / "page-invalid.bin").write_bytes(b"private bytes")
        result = self.audit()
        self.assertEqual(result["unexpectedChapterLeafFiles"], 1)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PAGES_OR_PLANS_REQUIRE_REVIEW")
        self.assertNotIn("page-invalid.bin", str(result))

    def test_stale_completed_receipt_in_paused_folder_is_flagged(self):
        self.start(count=2)
        (self.folder / ".webreader-completion-v1").write_bytes(
            b"WR-OFFLINE-COMPLETE-V1:2\n"
        )
        result = self.audit()
        self.assertEqual(result["unexpectedChapterLeafFiles"], 1)

    def test_missing_active_plan_is_anomaly_not_auto_resume(self):
        self.start(count=2)
        self.plan.unlink()
        self.page(0)
        result = self.audit()
        self.assertEqual(result["missingPlans"], 1)
        self.assertEqual(result["rowsWithoutValidatedPlanPageCount"], 1)
        self.assertEqual(result["unverifiedPageFilesWithoutPlan"], 1)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PAGES_OR_PLANS_REQUIRE_REVIEW")

    def test_failed_job_missing_optional_plan_is_not_called_invalid(self):
        self.plan = self.fx.active(state="failed")
        self.folder = self.plan.parent
        self.page(0)
        result = self.audit()
        self.assertEqual(result["missingPlans"], 0)
        self.assertEqual(result["invalidPlans"], 0)
        self.assertEqual(result["unverifiedPageFilesWithoutPlan"], 1)
        self.assertEqual(result["nonPrefixPageFiles"], 0)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PREFIX_NEEDS_IOS12_READING")
        self.deny(result)

    def test_failed_job_with_valid_plan_can_be_classified_not_resumed(self):
        self.start(state="failed", count=2)
        self.page(0)
        result = self.audit()
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 1)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PREFIX_NEEDS_IOS12_READING")

    def test_queued_empty_folder_without_plan_stops(self):
        self.plan = self.fx.active(state="queued")
        self.folder = self.plan.parent
        result = self.audit()
        self.assertEqual(result["missingPlans"], 1)
        self.assertEqual(result["noncompletedPageFilesObserved"], 0)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PAGES_OR_PLANS_REQUIRE_REVIEW")

    def test_invalid_recovery_plan_blocks_metadata_reuse(self):
        self.start(count=2)
        self.plan.write_bytes(b'{"pages":"wrong"}')
        self.page(0)
        result = self.audit()
        self.assertEqual(result["invalidPlans"], 1)
        self.assertEqual(result["metadataOnlyContiguousPrefixFiles"], 0)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PAGES_OR_PLANS_REQUIRE_REVIEW")

    def test_missing_chapter_directory_not_silent(self):
        plan = self.fx.active(state="paused")
        plan.parent.rmdir()
        result = self.audit()
        self.assertEqual(result["missingNoncompletedFolders"], 1)
        self.assertEqual(result["status"], "EK_STOP_PARTIAL_PAGES_OR_PLANS_REQUIRE_REVIEW")

    def test_symlink_page_in_paused_chapter_blocks_at_ei(self):
        self.start(count=2)
        destination = self.page(0)
        (self.folder / "page-00001.bin").symlink_to(destination)
        with self.assertRaises(EKRejected) as exc:
            self.audit()
        self.assertEqual(exc.exception.code, "EK_STOP_EXTERNAL_COPY_INVALID")

    def test_orphan_page_in_unknown_chapter_blocks_at_ei(self):
        self.start(count=2)
        orphan = self.fx.fx.base / "alien-source" / "manga" / "chapter"
        orphan.mkdir(parents=True)
        (orphan / "page-00000.bin").write_bytes(b"x")
        with self.assertRaises(EKRejected) as exc:
            self.audit()
        self.assertEqual(exc.exception.code, "EK_STOP_UNACCOUNTED_DOWNLOADS")

    def test_overflow_plan_page_count_invalid(self):
        self.start(count=2)
        self.fx.write_plan(fixtures.fake_plan(pages=MAX_PAGES + 1))
        self.page(0)
        result = self.audit()
        self.assertEqual(result["invalidPlans"], 1)

    def test_cli_exits_two_and_never_prints_private_identifiers(self):
        self.start(count=2)
        self.page(1, b"PRIVATE-IMAGE-BYTES")
        script = Path(__file__).resolve().parent / "build70_ek_partial_prefix_metadata.py"
        proc = subprocess.run([sys.executable, str(script), "--snapshot", str(self.root)],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["nonPrefixPageFiles"], 1)
        for secret in (str(self.root), "fictitious2", "PRIVATE-IMAGE-BYTES"):
            self.assertNotIn(secret, proc.stdout + proc.stderr)
        self.assertFalse(report["installationAuthorized"])

    def test_cli_no_pending_returns_informational_zero(self):
        script = Path(__file__).resolve().parent / "build70_ek_partial_prefix_metadata.py"
        proc = subprocess.run([sys.executable, str(script), "--snapshot", str(self.root)],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"],
                         "EK_NO_INCOMPLETE_DOWNLOAD_ROWS_NOT_DEVICE_PROOF")

    def test_constants_match_native_ios_12_download_prefix(self):
        swift = (Path(__file__).resolve().parent.parent / "MangaReader12" /
                 "Downloads" / "WebReaderOfflineResumePrefix.swift").read_text()
        self.assertIn("maximumPlannedPages = 5_000", swift)
        self.assertIn("maximumPageBytes: Int64 = 20 * 1024 * 1024", swift)
        self.assertEqual(MAX_PAGES, 5000)
        self.assertEqual(MAX_PAGE_BYTES, 20 * 1024 * 1024)

    def test_no_destructive_or_network_operations_in_auditor(self):
        src = (Path(__file__).resolve().parent /
               "build70_ek_partial_prefix_metadata.py").read_text()
        for forbidden in (".unlink(", ".write_bytes(", ".write_text(",
                          "shutil.rmtree", "appinst", "subprocess.run(",
                          "restoreBackup(", "DELETE FROM", "UPDATE downloads",
                          "requests.get("):
            self.assertNotIn(forbidden, src)
        self.assertIn('return 2 if result["status"].startswith("EK_STOP_") else 0', src)
        self.assertIn('"installationAuthorized": False', src)


if __name__ == "__main__":
    unittest.main()
