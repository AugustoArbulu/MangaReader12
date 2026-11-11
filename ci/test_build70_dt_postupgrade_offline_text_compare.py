#!/usr/bin/env python3
"""Build70/DT: before 70 vs after 71 read-only TEXT QA (no iPad or installer)."""
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from build70_dt_postupgrade_offline_text_compare import (
    DTRejected, compare_dt_upgrade_reports, _canonical_after_as_before,
    FALSE_FIELDS,
)
from test_build70_do_preupgrade_baseline_audit import continuity, offline

ROOT = Path(__file__).resolve().parent
OLD = "Build observada: 70 • iOS: 12.5.8".encode()
NEW = "Build observada: 71 • iOS: 12.5.8".encode()


def after(source: bytes) -> bytes:
    if source.count(OLD) != 1:
        raise AssertionError("invalid synthetic input")
    return source.replace(OLD, NEW)


class DTPostupgradeTextTests(unittest.TestCase):
    def compare(self, **kwargs):
        values = dict(
            before_counts=continuity(),
            after_counts=after(continuity()),
            before_offline=[offline()],
            after_offline=[after(offline())],
        )
        values.update(kwargs)
        result = compare_dt_upgrade_reports(**values)
        self.assert_no_authority(result)
        return result

    def assert_no_authority(self, result):
        for field in FALSE_FIELDS:
            self.assertIs(result[field], False, field)

    def test_equal_sqlite_and_offline_counts_not_proof(self):
        r = self.compare()
        self.assertEqual(r["status"],
                         "DT_BEFORE_AFTER_TEXT_AGGREGATES_EQUAL_NOT_DATA_PROOF")
        self.assertTrue(r["allNineSQLiteCountsTextuallyEqual"])
        self.assertTrue(r["offlineAggregateValuesTextuallyEqual"])
        self.assertEqual(r["changedSQLiteCountLabels"], [])
        self.assertEqual(r["changedOfflineAggregateFields"], [])

    def test_real_canonical_after_71_is_mapped_only_to_70_for_do(self):
        data = after(offline())
        self.assertEqual(_canonical_after_as_before(data), offline())
        self.assertFalse(data == offline())

    def test_sqlite_library_count_loss_is_stop(self):
        wrong = after(continuity()).replace(
            b"Obras na biblioteca: 12", b"Obras na biblioteca: 11"
        )
        r = self.compare(after_counts=wrong)
        self.assertEqual(r["status"], "DT_STOP_SQLITE_COUNTS_CHANGED_REVIEW_REQUIRED")
        self.assertEqual(r["changedSQLiteCountLabels"], ["Obras na biblioteca"])

    def test_progress_count_loss_is_stop(self):
        wrong = after(continuity()).replace(
            "Capítulos lidos: 15".encode(), "Capítulos lidos: 14".encode()
        )
        r = self.compare(after_counts=wrong)
        self.assertEqual(r["status"], "DT_STOP_SQLITE_COUNTS_CHANGED_REVIEW_REQUIRED")
        self.assertEqual(r["changedSQLiteCountLabels"], ["Capítulos lidos"])

    def test_equal_sqlite_with_missing_offline_files_is_stop(self):
        r = self.compare(after_offline=[after(offline(valid=2, sealed=2, pages=4))])
        self.assertEqual(
            r["status"], "DT_STOP_OFFLINE_FILE_METADATA_UNSAFE_REVIEW_REQUIRED"
        )
        self.assertIn("missingOrUnsafeChaptersAsText", r["changedOfflineAggregateFields"])

    def test_different_page_totals_are_stop_even_if_all_chapters_valid(self):
        r = self.compare(after_offline=[after(offline(pages=7))])
        self.assertEqual(
            r["status"], "DT_STOP_OFFLINE_AGGREGATES_CHANGED_REVIEW_REQUIRED"
        )
        self.assertIn("offlinePageEntriesAsText", r["changedOfflineAggregateFields"])

    def test_legacy_unsealed_chapters_are_unsafe_to_equate(self):
        r = self.compare(after_offline=[after(offline(sealed=1))])
        self.assertEqual(
            r["status"], "DT_REPORTED_LEGACY_CHAPTERS_REQUIRE_REAL_OFFLINE_READING"
        )

    def test_preexisting_legacy_chapters_also_flagged(self):
        r = self.compare(before_offline=[offline(sealed=1)])
        self.assertEqual(
            r["status"], "DT_REPORTED_LEGACY_CHAPTERS_REQUIRE_REAL_OFFLINE_READING"
        )

    def test_both_partial_65_coverage_remains_pending(self):
        r = self.compare(
            before_counts=continuity(65),
            after_counts=after(continuity(65)),
            before_offline=[offline(total=65)],
            after_offline=[after(offline(total=65))],
        )
        self.assertEqual(
            r["status"], "DT_REPORTED_OFFLINE_BATCHES_INCOMPLETE_REVIEW_REQUIRED"
        )
        self.assertFalse(r["beforeCompletedRowsCoveredByTexts"])
        self.assertFalse(r["afterCompletedRowsCoveredByTexts"])

    def test_before_complete_after_incomplete_is_pending(self):
        r = self.compare(
            before_counts=continuity(65),
            after_counts=after(continuity(65)),
            before_offline=[offline(total=65), offline(total=65, offset=64)],
            after_offline=[after(offline(total=65))],
        )
        self.assertEqual(
            r["status"], "DT_REPORTED_OFFLINE_BATCHES_INCOMPLETE_REVIEW_REQUIRED"
        )
        self.assertTrue(r["beforeCompletedRowsCoveredByTexts"])
        self.assertFalse(r["afterCompletedRowsCoveredByTexts"])

    def test_both_complete_65_batches_still_not_image_proof(self):
        r = self.compare(
            before_counts=continuity(65),
            after_counts=after(continuity(65)),
            before_offline=[offline(total=65), offline(total=65, offset=64)],
            after_offline=[
                after(offline(total=65)),
                after(offline(total=65, offset=64))
            ],
        )
        self.assertEqual(r["status"],
                         "DT_BEFORE_AFTER_TEXT_AGGREGATES_EQUAL_NOT_DATA_PROOF")
        self.assertTrue(r["afterCompletedRowsCoveredByTexts"])

    def test_zero_download_record_is_not_offline_device_proof(self):
        r = self.compare(
            before_counts=continuity(0),
            after_counts=after(continuity(0)),
            before_offline=[offline(total=0)],
            after_offline=[after(offline(total=0))],
        )
        self.assertEqual(
            r["status"], "DT_REPORTED_ZERO_OFFLINE_RECORDS_NOT_PHYSICAL_PROOF"
        )

    def test_bad_offline_metadata_outranks_legacy_in_other_side(self):
        r = self.compare(
            before_offline=[offline(sealed=1)],
            after_offline=[after(offline(valid=2, sealed=2, pages=4))],
        )
        self.assertEqual(r["status"], "DT_STOP_OFFLINE_FILE_METADATA_UNSAFE_REVIEW_REQUIRED")

    def test_count_difference_outranks_bad_offline_sample(self):
        modified = after(continuity()).replace(
            b"Obras na biblioteca: 12", b"Obras na biblioteca: 0"
        )
        r = self.compare(
            after_counts=modified,
            after_offline=[after(offline(valid=2, sealed=2, pages=4))],
        )
        self.assertEqual(r["status"], "DT_STOP_SQLITE_COUNTS_CHANGED_REVIEW_REQUIRED")

    def test_forged_after_build70_not_accepted(self):
        with self.assertRaises(DTRejected):
            self.compare(after_offline=[offline()])

    def test_wrong_ios_minor_or_build72_refused(self):
        for version in ("12.5.7", "12.5.9", "13.0"):
            b = after(offline()).replace(b"12.5.8", version.encode())
            with self.subTest(version=version), self.assertRaises(DTRejected):
                self.compare(after_offline=[b])
        with self.assertRaises(DTRejected):
            self.compare(after_counts=after(continuity()).replace(NEW, "Build observada: 72 • iOS: 12.5.8".encode("utf-8")))

    def test_duplicate_or_extra_after_rows_are_rejected(self):
        samples = (
            after(offline())+b"\n",
            after(offline())+b"\nINSTALLATION_AUTHORIZED=YES",
            after(offline()).replace(b"\n", b"\r\n"),
            after(offline())+b"\x00",
        )
        for data in samples:
            with self.subTest(data=data[-32:]), self.assertRaises(DTRejected):
                self.compare(after_offline=[data])

    def test_old_and_new_reports_must_not_skip_or_duplicate_batches(self):
        with self.assertRaises(DTRejected):
            self.compare(
                before_counts=continuity(65),
                after_counts=after(continuity(65)),
                before_offline=[offline(total=65, offset=64)],
                after_offline=[after(offline(total=65)), after(offline(total=65, offset=64))],
            )
        with self.assertRaises(DTRejected):
            self.compare(
                before_counts=continuity(65),
                after_counts=after(continuity(65)),
                before_offline=[offline(total=65)]*2,
                after_offline=[after(offline(total=65)), after(offline(total=65, offset=64))],
            )

    def test_missing_or_excess_offline_batches_are_rejected(self):
        with self.assertRaises(DTRejected):
            self.compare(before_offline=[])
        with self.assertRaises(DTRejected):
            self.compare(after_offline=[])
        with self.assertRaises(DTRejected):
            self.compare(before_offline=[offline()]*257)
        with self.assertRaises(DTRejected):
            self.compare(after_offline=[after(offline())]*257)

    def test_wrong_input_types_fail_closed(self):
        for source in (None, b"", "not bytes", bytearray(after(offline()))):
            with self.subTest(source=repr(source)[:50]), self.assertRaises(DTRejected):
                self.compare(after_offline=[source])

    def test_after_report_random_mutations_never_grant_authority(self):
        rng = random.Random(20261111)
        fixture = after(offline())
        for _ in range(200):
            modified = bytearray(fixture)
            pos = rng.randrange(len(modified))
            modified[pos] ^= rng.randrange(1, 256)
            try:
                result = self.compare(after_offline=[bytes(modified)])
            except DTRejected:
                continue
            self.assert_no_authority(result)

    def test_cli_reads_untrusted_text_without_mutating_files(self):
        with tempfile.TemporaryDirectory(prefix="wr-dt-text-") as directory:
            d = Path(directory)
            inputs = dict(
                before_counts=continuity(),
                after_counts=after(continuity()),
                before_offline=offline(),
                after_offline=after(offline()),
            )
            for name, data in inputs.items():
                (d / (name+".txt")).write_bytes(data)
            proc = subprocess.run(
                [sys.executable, str(ROOT/"build70_dt_postupgrade_offline_text_compare.py"),
                 "--before-counts", str(d/"before_counts.txt"),
                 "--after-counts", str(d/"after_counts.txt"),
                 "--before-offline", str(d/"before_offline.txt"),
                 "--after-offline", str(d/"after_offline.txt")],
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(proc.stdout)
            self.assert_no_authority(receipt)
            self.assertEqual(receipt["status"],
                             "DT_BEFORE_AFTER_TEXT_AGGREGATES_EQUAL_NOT_DATA_PROOF")
            for name, data in inputs.items():
                self.assertEqual((d / (name+".txt")).read_bytes(), data)

    def test_cli_refuses_symlink_to_report(self):
        with tempfile.TemporaryDirectory(prefix="wr-dt-symlink-") as directory:
            d = Path(directory)
            (d/"old.txt").write_bytes(continuity())
            (d/"new.txt").write_bytes(after(continuity()))
            (d/"offline-old.txt").write_bytes(offline())
            (d/"offline-new.txt").write_bytes(after(offline()))
            (d/"alias.txt").symlink_to(d/"new.txt")
            proc = subprocess.run(
                [sys.executable, str(ROOT/"build70_dt_postupgrade_offline_text_compare.py"),
                 "--before-counts", str(d/"old.txt"),
                 "--after-counts", str(d/"alias.txt"),
                 "--before-offline", str(d/"offline-old.txt"),
                 "--after-offline", str(d/"offline-new.txt")],
                capture_output=True, text=True, timeout=15,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("BLOCKED:", proc.stderr)

    def test_no_install_or_data_mutation_commands_in_dt(self):
        source = (ROOT/"build70_dt_postupgrade_offline_text_compare.py").read_text()
        for token in ("posix_spawn(", "appinst(", "subprocess.run(",
                      "installApplication(", "unlink(", "write_bytes(",
                      "write_text(", "restoreBackup(", "publish_release("):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
