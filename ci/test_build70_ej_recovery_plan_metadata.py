#!/usr/bin/env python3
"""EJ tests: synthetic private-looking recovery metadata; no network/device."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest

import test_build70_ei_all_downloads_inventory as ei_fixtures
from build70_ej_recovery_plan_metadata import (
    audit_recovery_plans, plausible_plan, EJRejected,
    MAX_PLAN_BYTES, MAX_PAGES,
)


def fake_plan(source="asura", manga="fictitious2", chapter="ch2", pages=2):
    return {
        "schemaVersion": 1,
        "sourceID": source,
        "manga": {"id": manga},
        "chapter": {"id": chapter},
        "manifest": {"id": source},
        "queueOrder": 4,
        "pages": [
            {"index": i, "imageUrl": "https://secret.example.test/page-" + str(i),
             "headers": {"Authorization": "private-test-token"}}
            for i in range(pages)
        ],
    }


class EJRecoveryPlanTests(unittest.TestCase):
    def setUp(self):
        fixture = ei_fixtures.EIAllDownloadsInventoryTests(
            "test_completed_snapshot_has_only_accounted_files"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fx = fixture
        self.root = fixture.root
        self.plan = None

    def active(self, state="paused"):
        folder = self.fx.add_noncompleted(state=state)
        self.plan = folder / "_download-plan.json"
        return self.plan

    def write_plan(self, plan=None):
        plan = fake_plan() if plan is None else plan
        self.plan.write_bytes(json.dumps(plan, sort_keys=True).encode("utf-8"))

    def audit(self):
        return audit_recovery_plans(self.root)

    def denied(self, report):
        for key in (
            "fullSwiftCodableDecodePerformed", "resumabilityProvenOnIOS12",
            "headersOrURLsPrinted", "originalIPadAttested",
            "ownerReleaseApprovalRecorded", "readyToDistributeIPA",
            "readyToInstallIPA", "installationAuthorized",
            "restorationAuthorized", "automaticUpdaterEnabled",
        ):
            self.assertIs(report[key], False, key)
        self.assertTrue(report["noChangesMadeToCopies"])

    def test_no_pending_legacy_completed_does_not_claim_ready(self):
        r = self.audit()
        self.assertEqual(r["status"], "EJ_NO_PENDING_RECOVERY_ROWS_NOT_DEVICE_PROOF")
        self.assertEqual(r["downloadRowsExamined"], 1)
        self.denied(r)

    def test_valid_paused_plan_still_requires_owner_review(self):
        self.active()
        self.write_plan()
        r = self.audit()
        self.assertEqual(r["status"], "EJ_STOP_RECOVERY_ROWS_REQUIRE_DEVICE_REVIEW")
        self.assertEqual(r["plansWithPlausibleMetadata"], 1)
        self.assertEqual(r["sumOfDeclaredPlanPages"], 2)
        self.assertEqual(r["activeRecoveryRows"], 1)
        self.assertEqual(r["missingRequiredPlans"], 0)
        self.denied(r)
        self.assertNotIn("secret.example.test", str(r))
        self.assertNotIn("private-test-token", str(r))


    def test_optional_replay_flag_true_requires_device_review(self):
        self.active()
        obj = fake_plan()
        obj["requiresFullReplay"] = True
        self.write_plan(obj)
        r = self.audit()
        self.assertEqual(r["status"], "EJ_STOP_RECOVERY_ROWS_REQUIRE_DEVICE_REVIEW")
        self.assertEqual(r["plansWithPlausibleMetadata"], 1)
        self.assertEqual(r["sumOfDeclaredPlanPages"], 2)
        self.denied(r)

    def test_optional_replay_flag_false_and_missing_are_legacy_compatible(self):
        self.active()
        obj = fake_plan()
        obj["requiresFullReplay"] = False
        self.write_plan(obj)
        self.assertEqual(self.audit()["plansWithPlausibleMetadata"], 1)
        obj.pop("requiresFullReplay")
        self.write_plan(obj)
        self.assertEqual(self.audit()["plansWithPlausibleMetadata"], 1)

    def test_wrong_type_replay_flag_refused_without_repair(self):
        self.active()
        for value in (1, 0, "true", None, [], {}):
            with self.subTest(value=value):
                obj = fake_plan()
                obj["requiresFullReplay"] = value
                self.write_plan(obj)
                report = self.audit()
                self.assertEqual(report["malformedOrUnsafePlans"], 1)
                self.assertEqual(report["status"],
                                 "EJ_STOP_MISSING_MALFORMED_OR_STALE_RECOVERY_PLANS")
                self.denied(report)

    def test_missing_paused_plan_is_not_recovered_by_guess(self):
        self.active()
        r = self.audit()
        self.assertEqual(r["status"], "EJ_STOP_MISSING_MALFORMED_OR_STALE_RECOVERY_PLANS")
        self.assertEqual(r["missingRequiredPlans"], 1)
        self.assertEqual(r["plansWithPlausibleMetadata"], 0)
        self.denied(r)

    def test_queued_missing_plan_is_blocked(self):
        self.active(state="queued")
        r = self.audit()
        self.assertEqual(r["missingRequiredPlans"], 1)
        self.assertTrue(r["status"].startswith("EJ_STOP_"))

    def test_downloading_missing_plan_is_blocked(self):
        self.active(state="downloading")
        r = self.audit()
        self.assertEqual(r["missingRequiredPlans"], 1)
        self.assertTrue(r["status"].startswith("EJ_STOP_"))

    def test_failed_download_does_not_require_plan_for_auto_resume(self):
        self.active(state="failed")
        r = self.audit()
        self.assertEqual(r["status"], "EJ_STOP_RECOVERY_ROWS_REQUIRE_DEVICE_REVIEW")
        self.assertEqual(r["missingRequiredPlans"], 0)
        self.assertEqual(r["otherNoncompletedRows"], 1)
        self.denied(r)

    def test_failed_download_plan_if_present_still_checked(self):
        self.active(state="failed")
        self.write_plan()
        r = self.audit()
        self.assertEqual(r["plansWithPlausibleMetadata"], 1)
        self.assertEqual(r["otherNoncompletedRows"], 1)
        self.denied(r)

    def test_plan_manga_identity_mismatch(self):
        self.active()
        data = fake_plan()
        data["manga"]["id"] = "different"
        self.write_plan(data)
        r = self.audit()
        self.assertEqual(r["identityMismatchedPlans"], 1)
        self.assertEqual(r["status"], "EJ_STOP_MISSING_MALFORMED_OR_STALE_RECOVERY_PLANS")

    def test_plan_source_manifest_identity_mismatch(self):
        self.active()
        data = fake_plan()
        data["manifest"]["id"] = "fake-source"
        self.write_plan(data)
        r = self.audit()
        self.assertEqual(r["identityMismatchedPlans"], 1)

    def test_plan_chapter_identity_mismatch(self):
        self.active()
        data = fake_plan()
        data["chapter"]["id"] = "other-chapter"
        self.write_plan(data)
        r = self.audit()
        self.assertEqual(r["identityMismatchedPlans"], 1)

    def test_wrong_schema_version_is_rejected(self):
        self.active()
        data = fake_plan()
        data["schemaVersion"] = 2
        self.write_plan(data)
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_bool_schema_value_does_not_equal_integer(self):
        self.active()
        data = fake_plan()
        data["schemaVersion"] = True
        self.write_plan(data)
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_negative_queue_order_is_rejected(self):
        self.active()
        data = fake_plan()
        data["queueOrder"] = -1
        self.write_plan(data)
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_missing_page_array_is_rejected(self):
        self.active()
        data = fake_plan()
        del data["pages"]
        self.write_plan(data)
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_excessive_page_count_is_rejected(self):
        self.active()
        data = fake_plan(pages=5001)
        self.write_plan(data)
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_nonsequential_page_index_is_rejected(self):
        self.active()
        data = fake_plan()
        data["pages"][1]["index"] = 15
        self.write_plan(data)
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_non_string_page_headers_are_rejected(self):
        self.active()
        data = fake_plan()
        data["pages"][0]["headers"]["Authorization"] = 12
        self.write_plan(data)
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_empty_page_url_is_rejected(self):
        self.active()
        data = fake_plan()
        data["pages"][0]["imageUrl"] = ""
        self.write_plan(data)
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_malformed_json_is_rejected(self):
        self.active()
        self.plan.write_bytes(b"{")
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_duplicate_json_keys_are_rejected(self):
        self.active()
        self.plan.write_bytes(b'{"schemaVersion":1,"schemaVersion":1}')
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_nonfinite_json_number_is_rejected(self):
        self.active()
        raw = json.dumps(fake_plan()).replace('"queueOrder": 4', '"queueOrder": NaN')
        self.plan.write_bytes(raw.encode("utf-8"))
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)

    def test_empty_plan_file_is_rejected_without_modifying_it(self):
        self.active()
        self.plan.write_bytes(b"")
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)
        self.assertEqual(self.plan.read_bytes(), b"")

    def test_oversized_plan_is_rejected_without_reading_all_contents(self):
        self.active()
        with self.plan.open("wb") as stream:
            stream.truncate(MAX_PLAN_BYTES + 1)
        self.assertEqual(self.audit()["malformedOrUnsafePlans"], 1)
        self.assertEqual(self.plan.stat().st_size, MAX_PLAN_BYTES + 1)

    def test_symlinked_plan_is_blocked_by_base_inventory(self):
        self.active()
        target = self.plan.with_name("plan-private.json")
        target.write_bytes(b'{"credentials":"secret"}')
        self.plan.symlink_to(target.name)
        with self.assertRaises(EJRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EJ_STOP_EXTERNAL_COPY_INVALID")
        self.assertTrue(self.plan.is_symlink())

    def test_completed_job_stale_plan_requires_review(self):
        folder = self.fx.base / "asura" / "fiction1" / "chap1"
        stale = folder / "_download-plan.json"
        stale.write_bytes(json.dumps(fake_plan(
            source="asura", manga="fiction1", chapter="chap1")).encode("utf-8"))
        r = self.audit()
        self.assertEqual(r["stalePlansOnCompletedRows"], 1)
        self.assertTrue(r["status"].startswith("EJ_STOP_"))
        self.denied(r)

    def test_orphan_plan_is_rejected_by_inventory(self):
        folder = self.fx.base / "unknown" / "manga" / "chapter"
        folder.mkdir(parents=True)
        (folder / "_download-plan.json").write_bytes(b"{}")
        with self.assertRaises(EJRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EJ_STOP_UNACCOUNTED_DOWNLOAD_TREE")

    def test_plan_cli_fail_closed_and_private_data_redacted(self):
        self.active()
        self.write_plan()
        script = Path(__file__).resolve().parent / "build70_ej_recovery_plan_metadata.py"
        p = subprocess.run([sys.executable, str(script), "--snapshot", str(self.root)],
                           text=True, capture_output=True, timeout=15)
        self.assertEqual(p.returncode, 2, p.stderr)
        r = json.loads(p.stdout)
        self.assertEqual(r["status"], "EJ_STOP_RECOVERY_ROWS_REQUIRE_DEVICE_REVIEW")
        self.assertNotIn("secret.example.test", p.stdout + p.stderr)
        self.assertNotIn("private-test-token", p.stdout + p.stderr)
        self.assertNotIn(str(self.root), p.stdout + p.stderr)
        self.assertFalse(r["installationAuthorized"])

    def test_no_pending_cli_is_informational_only(self):
        script = Path(__file__).resolve().parent / "build70_ej_recovery_plan_metadata.py"
        p = subprocess.run([sys.executable, str(script), "--snapshot", str(self.root)],
                           text=True, capture_output=True, timeout=15)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["status"],
                         "EJ_NO_PENDING_RECOVERY_ROWS_NOT_DEVICE_PROOF")

    def test_constants_match_native_reader_and_resume_guard(self):
        base = Path(__file__).resolve().parent.parent / "MangaReader12/Downloads"
        reader = (base / "WebReaderOfflineRecoveryPlanReader.swift").read_text()
        resume = (base / "WebReaderOfflineResumePrefix.swift").read_text()
        self.assertEqual(MAX_PLAN_BYTES, 16 * 1024 * 1024)
        self.assertIn("static let maxBytes = 16 * 1024 * 1024", reader)
        self.assertEqual(MAX_PAGES, 5000)
        self.assertIn("static let maximumPlannedPages = 5_000", resume)

    def test_no_write_restoration_or_install_in_ej_source(self):
        source = (Path(__file__).resolve().parent /
                  "build70_ej_recovery_plan_metadata.py").read_text()
        for forbidden in ("appinst", ".unlink(", ".write_bytes(", ".write_text(",
                          "shutil.rmtree", "restoreBackup(", "subprocess.run(",
                          "requests.get(", "DELETE FROM", "UPDATE downloads"):
            self.assertNotIn(forbidden, source)
        self.assertIn('"installationAuthorized": False', source)
        self.assertIn('"restorationAuthorized": False', source)
        self.assertIn('return 2 if result["status"].startswith("EJ_STOP_") else 0',
                      source)


if __name__ == "__main__":
    unittest.main()
