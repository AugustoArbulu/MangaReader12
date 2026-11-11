#!/usr/bin/env python3
"""DJ tests use synthetic exact WebReaderUpgradeContinuitySnapshot clipboard.

No real library, private user report, images, device or data are accessed.
The fixture may be forged, so even an equal result never proves continuity.
"""
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from build70_dj_continuity_report_compare import (
    AFTER_BUILD, BEFORE_BUILD, COUNT_LABELS, DB_HEALTH, FOOTER, HEADER,
    IOS_VERSION, NOTE, DJRejected, check_before_report, compare_reports,
    parse_continuity_report, _read_file_once,
)

ROOT = Path(__file__).resolve().parent


def canonical(build, counts=None):
    if counts is None:
        counts = (14, 180, 34, 9, 11, 5, 19, 2, 16)
    lines = [
        HEADER,
        f"Build observada: {build} • iOS: {IOS_VERSION}",
        NOTE,
        DB_HEALTH,
    ] + [f"{label}: {number}" for label, number in zip(COUNT_LABELS, counts)] + list(FOOTER)
    return "\n".join(lines).encode("utf-8")


class DJHostContinuityAuditTests(unittest.TestCase):
    def setUp(self):
        self.before = canonical(BEFORE_BUILD)
        self.after = canonical(AFTER_BUILD)

    def assert_permanently_unverified(self, receipt):
        for key in (
            "originalReportsAuthenticated", "physicalBeforeAndAfterExecutionAttested",
            "sqliteContentsVerified", "libraryTitlesOrProgressIntegrityVerified",
            "offlinePageImageBytesVerified", "offlineReadingWithoutWifiVerified",
            "externalPortableBackupVerified", "onDeviceBuild71Installed",
            "publisherAuthenticated", "ownerQADistributionApprovalRecorded",
            "readyToDistributeIPA", "readyToInstallIPA",
            "installationAuthorized", "installationPerformed",
        ):
            self.assertIs(receipt[key], False, key)
        self.assertEqual(receipt["expectedInstalledBuild"], 70)
        self.assertEqual(receipt["candidateQABuild"], 71)

    def test_baseline_readonly_report_only_accepts_text_and_never_consents(self):
        report = check_before_report(self.before)
        self.assertEqual(report["status"], "DJ_BASELINE_COUNT_TEXT_ACCEPTED_UNATTESTED")
        self.assertFalse(report["allNineCountsTextuallyEqual"])
        self.assertEqual(report["differentCountLabels"], [])
        self.assert_permanently_unverified(report)

    def test_identical_nine_counters_are_not_offline_or_install_proof(self):
        report = compare_reports(self.before, self.after)
        self.assertEqual(report["status"], "DJ_NINE_COUNTS_TEXTUALLY_EQUAL_NOT_OFFLINE_PROOF")
        self.assertTrue(report["allNineCountsTextuallyEqual"])
        self.assertEqual(report["countLabelTotal"], 9)
        self.assertEqual(report["differentCountLabels"], [])
        self.assert_permanently_unverified(report)

    def test_increase_in_counts_requires_manual_review_not_silent_success(self):
        after = canonical(AFTER_BUILD, (14, 181, 34, 9, 11, 5, 19, 2, 16))
        report = compare_reports(self.before, after)
        self.assertEqual(report["status"], "DJ_COUNT_DIFFERENCE_REQUIRES_MANUAL_REVIEW")
        self.assertEqual(report["differentCountLabels"], ["Capítulos registrados"])
        self.assertFalse(report["allNineCountsTextuallyEqual"])
        self.assert_permanently_unverified(report)

    def test_decrease_in_downloaded_records_requires_manual_review(self):
        after = canonical(AFTER_BUILD, (14, 180, 34, 9, 11, 4, 19, 2, 16))
        report = compare_reports(self.before, after)
        self.assertEqual(report["differentCountLabels"],
                         ["Downloads marcados completos no banco"])
        self.assertFalse(report["offlinePageImageBytesVerified"])
        self.assert_permanently_unverified(report)

    def test_every_count_is_checked_not_just_library_total(self):
        for idx, label in enumerate(COUNT_LABELS):
            counts = [14, 180, 34, 9, 11, 5, 19, 2, 16]
            counts[idx] += 1
            with self.subTest(label=label):
                report = compare_reports(
                    self.before, canonical(AFTER_BUILD, counts))
                self.assertEqual(report["differentCountLabels"], [label])
                self.assert_permanently_unverified(report)

    def test_all_count_changes_are_reported_without_disclosing_values(self):
        different = (21, 190, 3, 10, 17, 6, 21, 8, 20)
        report = compare_reports(self.before, canonical(AFTER_BUILD, different))
        self.assertEqual(report["differentCountLabels"], list(COUNT_LABELS))
        self.assertNotIn("counts", report)
        self.assert_permanently_unverified(report)

    def test_wrong_app_build_or_wrong_order_not_accepted(self):
        for a,b in (
            (canonical(71),canonical(70)),
            (canonical(69),canonical(71)),
            (canonical(70),canonical(72)),
            (canonical(70),canonical(70)),
            (canonical(71),canonical(71)),
        ):
            with self.subTest(builds=(a[50:90],b[50:90])), self.assertRaises(DJRejected):
                compare_reports(a,b)

    def test_invalid_baseline_parameter_is_rejected(self):
        for build in (True, False, 0, 1, 56, 69, 72, 70.0, "70", None):
            with self.subTest(build=build), self.assertRaises(DJRejected):
                parse_continuity_report(self.before, expected_build=build)

    def test_database_unavailable_report_never_masquerades_as_empty(self):
        bad = self.before.replace(
            DB_HEALTH.encode(), b"Banco: INDISPON\xcdVEL (ausente)")
        with self.assertRaises(DJRejected):
            check_before_report(bad)

    def test_expected_sqlite_schema_version_is_required(self):
        for change in (
            "Banco SQLite: legível • schema v2",
            "Banco SQLite: legível • schema v0",
            "Banco SQLite: INDISPONÍVEL",
            "Banco: INDISPONÍVEL (não significa biblioteca vazia)"
        ):
            with self.subTest(change=change), self.assertRaises(DJRejected):
                check_before_report(self.before.replace(DB_HEALTH.encode(), change.encode()))

    def test_only_ios_12_5_8_is_accepted(self):
        for version in ("12.5.7", "12.0", "13.0", "16.0", "999.0"):
            with self.subTest(ios=version), self.assertRaises(DJRejected):
                check_before_report(self.before.replace(IOS_VERSION.encode(), version.encode()))

    def test_missing_or_reordered_counter_is_rejected(self):
        lines = self.before.decode().split("\n")
        for modified in (
            "\n".join(lines[:4] + lines[5:]),
            "\n".join(lines[:4] + [lines[5],lines[4]] + lines[6:]),
            "\n".join(lines[:4] + [lines[4]] + lines[4:]),
            "\n".join(lines[:-1]),
        ):
            with self.assertRaises(DJRejected):
                check_before_report(modified.encode())

    def test_renamed_fields_and_missing_offline_warnings_rejected(self):
        for changed in (
            self.before.replace(b"Obras na biblioteca", b"Obras total"),
            self.before.replace("Wi-Fi DESLIGADO".encode(), b"ONLINE"),
            self.before.replace("NÃO páginas verificadas".encode(), b"páginas OK"),
            self.before.replace("restaurar apaga Downloads".encode(), b"restore safe"),
        ):
            with self.assertRaises(DJRejected):
                check_before_report(changed)

    def test_malicious_fake_counts_rejected(self):
        for raw in (
            "-1","01","+1","1.0"," 1","1 ","1e4","nan","999999999999999999999",
            "9223372036854775808", "1\\nINSTALLATION=YES", "", "1 1",
        ):
            changed = self.before.replace(b"Obras na biblioteca: 14",
                                          f"Obras na biblioteca: {raw}".encode())
            with self.subTest(value=raw), self.assertRaises(DJRejected):
                check_before_report(changed)

    def test_zero_and_int64_max_are_accepted_without_authority(self):
        zero = canonical(BEFORE_BUILD, (0,)*9)
        maxvalue = canonical(AFTER_BUILD, (9223372036854775807,)*9)
        self.assertEqual(parse_continuity_report(zero, expected_build=70).counts,
                         (0,)*9)
        changed = compare_reports(zero, maxvalue)
        self.assertEqual(len(changed["differentCountLabels"]), 9)
        self.assert_permanently_unverified(changed)

    def test_truncated_unicode_oversized_cr_null_and_extra_fields_fail(self):
        cases = (
            self.before[:-1], self.before + b"\n", self.before + b"EXTRA",
            self.before.replace(b"\n", b"\r\n"),
            self.before + b"\x00", self.before + b"\xff",
            self.before + b"X"*4096, b"", "🔒".encode(),
        )
        for item in cases:
            with self.subTest(length=len(item)), self.assertRaises(DJRejected):
                check_before_report(item)

    def test_immutable_observation_cannot_have_authority_mutated(self):
        report = parse_continuity_report(self.before, expected_build=70)
        self.assertFalse(report.installation_authorized)
        with self.assertRaises(FrozenInstanceError):
            report.installation_authorized = True

    def test_read_only_regular_file_input_and_cli_baseline(self):
        with tempfile.TemporaryDirectory(prefix="wr-dj-host-") as tmp:
            root = Path(tmp)
            first = root / "before.txt"
            second = root / "after.txt"
            first.write_bytes(self.before)
            second.write_bytes(self.after)
            before_bytes = first.read_bytes()
            assert _read_file_once(first) == before_bytes
            proc = subprocess.run(
                [sys.executable,
                 str(ROOT / "build70_dj_continuity_report_compare.py"),
                 "--before", str(first)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["status"], "DJ_BASELINE_COUNT_TEXT_ACCEPTED_UNATTESTED")
            compare = subprocess.run(
                [sys.executable,
                 str(ROOT / "build70_dj_continuity_report_compare.py"),
                 "--before", str(first), "--after", str(second)],
                capture_output=True, text=True, timeout=10
            )
            self.assertEqual(compare.returncode, 0, compare.stderr)
            self.assertTrue(json.loads(compare.stdout)["allNineCountsTextuallyEqual"])
            self.assertEqual(first.read_bytes(), before_bytes)

    def test_symlink_and_fifo_input_rejected(self):
        if os.name != "posix":
            self.skipTest("requires POSIX O_NOFOLLOW")
        with tempfile.TemporaryDirectory(prefix="wr-dj-fifo-") as tmp:
            root = Path(tmp)
            regular = root / "good.txt"
            regular.write_bytes(self.before)
            link = root / "bad-link.txt"
            link.symlink_to(regular)
            with self.assertRaises(DJRejected):
                _read_file_once(link)
            fifo = root / "bad-fifo"
            os.mkfifo(fifo)
            with self.assertRaises(DJRejected):
                _read_file_once(fifo)

    def test_250_seeded_mutations_never_grant_authority(self):
        rng = random.Random(20261110)
        for _ in range(250):
            data = bytearray(self.before)
            i = rng.randrange(len(data))
            data[i] = rng.randrange(256)
            try:
                report = check_before_report(bytes(data))
            except DJRejected:
                continue
            self.assert_permanently_unverified(report)

    def test_source_has_no_appinst_release_ipc_or_write_calls(self):
        import ast
        source = (ROOT / "build70_dj_continuity_report_compare.py").read_text()
        calls = {
            n.func.id if isinstance(n.func, ast.Name) else n.func.attr
            for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.Call)
            and isinstance(n.func, (ast.Name, ast.Attribute))
        }
        forbidden = {
            "appinst", "installApplication", "posix_spawn", "Popen", "run",
            "chmod", "chown", "unlink", "rename", "write_text", "write_bytes",
            "upload_artifact", "publish_release", "download", "connect"
        }
        self.assertFalse(calls & forbidden)
        self.assertIn("offlinePageImageBytesVerified", source)
        self.assertIn('"installationAuthorized": False', source)


if __name__ == "__main__":
    unittest.main()
