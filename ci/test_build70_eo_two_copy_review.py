#!/usr/bin/env python3
"""EO synthetic host-only tests. NEVER open real iPad paths or install IPAs."""
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import build70_eo_two_copy_review as eo
import test_build70_ed_portable_vs_external_library as fake_library


class EOTwoCopyReviewTests(unittest.TestCase):
    def setUp(self):
        fixture = fake_library.EDPortableLibraryTests(
            "test_exact_library_rows_equal_but_not_attested"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fx = fixture
        self.first = fixture.root
        self.second = self.first.parent / "independent-copy"
        shutil.copytree(self.first, self.second)
        self.addCleanup(lambda: shutil.rmtree(self.second, ignore_errors=True))

    def check_denied(self, report):
        for key in (
            "originalDeviceIdentityAttested", "independentPhysicalCustodyProven",
            "offlineReadingOfSameChapterProven", "readyToDistributeIPA",
            "readyToInstallIPA", "installationAuthorized",
            "restorationAuthorized", "automaticUpdaterEnabled"
        ):
            self.assertIs(report[key], False, key)

    def review(self):
        return eo.review_pair(self.first, self.second)

    def test_two_matching_full_copies_are_not_device_evidence(self):
        result = self.review()
        # The synthetic pages are arbitrary bytes, not known image signatures.
        # Matching hashes alone must not be labelled locally coherent.
        self.assertEqual(result["status"], "EO_STOP_REQUIRES_HUMAN_REVIEW_OF_COPY")
        self.assertTrue(result["copiesByteIdenticalAtTwoChecks"])
        self.assertEqual(result["observedAggregateCounts"]["completedChapterRows"], 1)
        self.assertEqual(result["observedAggregateCounts"]["completedPageFilesHashed"], 2)
        self.assertEqual(result["observedAggregateCounts"]["incompleteDownloadRows"], 0)
        self.assertEqual(result["observedAggregateCounts"]["orphanChapterFiles"], 0)
        for stage in ("EC", "EA", "EH", "EI", "EJ", "EK", "EF"):
            self.assertIn(stage, result["auditStatuses"])
        self.check_denied(result)
        self.assertNotIn("sha256", json.dumps(result, sort_keys=True).lower())

    def test_completed_copy_with_unrecognized_images_never_claims_decode(self):
        result = self.review()
        self.assertEqual(result["auditStatuses"]["EF"],
                         "EF_UNKNOWN_FORMATS_REQUIRE_REAL_IOS12_READ")
        self.assertEqual(result["observedAggregateCounts"]["unknownPageFormats"], 2)
        self.assertEqual(result["status"], "EO_STOP_REQUIRES_HUMAN_REVIEW_OF_COPY")
        self.assertIs(result["allImagesDecodeOnIOS12Proven"], False)
        self.check_denied(result)

    def test_plausible_png_signatures_only_allow_host_coherence_never_install(self):
        # Minimal plausible signature, NOT a decodable PNG, on both copies.
        # EF classifies these as plausible; no full decoder ever runs.
        header = b"\x89PNG\r\n\x1a\n"
        trailer = b"\x00\x00\x00\x00IEND\xaeB\x60\x82"
        payload = header + b"synthetic-only" * 4 + trailer
        for root in (self.first, self.second):
            chapter = (root / "Library" / "Application Support" /
                       "MangaReader12" / "Downloads" / "asura" /
                       "fiction1" / "chap1")
            for name in ("page-00000.bin", "page-00001.bin"):
                (chapter / name).write_bytes(payload)
        report = self.review()
        self.assertEqual(report["status"],
                         "EO_TWO_COPIES_COHERENT_NOT_DEVICE_ATTESTED")
        self.assertEqual(report["auditStatuses"]["EF"],
                         "EF_KNOWN_IMAGE_SIGNATURES_PLAUSIBLE_NOT_DECODED")
        self.assertEqual(report["observedAggregateCounts"]["unknownPageFormats"], 0)
        self.assertIs(report["allImagesDecodeOnIOS12Proven"], False)
        self.check_denied(report)

    def test_legacy_completed_receipts_require_manual_review(self):
        for root in (self.first, self.second):
            receipt = (root / "Library" / "Application Support" /
                       "MangaReader12" / "Downloads" / "asura" /
                       "fiction1" / "chap1" / ".webreader-completion-v1")
            receipt.unlink()
        report = self.review()
        self.assertEqual(report["status"], "EO_STOP_REQUIRES_HUMAN_REVIEW_OF_COPY")
        self.assertEqual(report["observedAggregateCounts"]["legacyCompletedChapterRows"], 1)
        self.check_denied(report)

    def test_hardlinked_page_never_qualifies_as_second_copy(self):
        # cp -al or a hand-linked file may share physical inode storage.
        # The pre-existing EC st_nlink == 1 guard must reject it.
        original = (self.first / "Library" / "Application Support" /
                    "MangaReader12" / "Downloads" / "asura" /
                    "fiction1" / "chap1" / "page-00000.bin")
        linked = (self.second / "Library" / "Application Support" /
                  "MangaReader12" / "Downloads" / "asura" /
                  "fiction1" / "chap1" / "page-00000.bin")
        linked.unlink()
        import os
        os.link(original, linked)
        with self.assertRaises(eo.EORejected) as error:
            self.review()
        self.assertEqual(error.exception.code, "EO_STOP_EC_FAILED")
        self.assertTrue(original.is_file())
        self.assertEqual(original.read_bytes(), linked.read_bytes())

    def test_one_copy_changed_preference_is_rejected(self):
        prefs = self.second / "Library" / "Preferences"
        prefs.mkdir(parents=True)
        (prefs / "private-foo.plist").write_bytes(b"secret preference")
        with self.assertRaises(eo.EORejected) as err:
            self.review()
        self.assertEqual(err.exception.code, "EO_STOP_TWO_COPIES_NOT_IDENTICAL")

    def test_missing_offline_page_is_rejected(self):
        missing = (self.second / "Library" / "Application Support" /
                   "MangaReader12" / "Downloads" / "asura" / "fiction1" /
                   "chap1" / "page-00001.bin")
        missing.unlink()
        with self.assertRaises(eo.EORejected) as err:
            self.review()
        self.assertEqual(err.exception.code, "EO_STOP_EC_FAILED")

    def test_same_root_never_counts_as_two_backups(self):
        with self.assertRaises(eo.EORejected) as err:
            eo.review_pair(self.first, self.first)
        self.assertEqual(err.exception.code, "EO_STOP_EC_FAILED")

    def test_symlinked_files_are_rejected_without_following(self):
        (self.second / "Documents").mkdir()
        outside = self.second / "Library" / "Preferences"
        outside.mkdir()
        (outside / "private.plist").write_bytes(b"SECRET")
        (self.second / "Documents" / "link").symlink_to(outside / "private.plist")
        with self.assertRaises(eo.EORejected) as err:
            self.review()
        self.assertEqual(err.exception.code, "EO_STOP_EC_FAILED")
        self.assertEqual((outside / "private.plist").read_bytes(), b"SECRET")

    def test_orphan_data_is_reported_for_review_not_removed(self):
        for copy in (self.first, self.second):
            folder = (copy / "Library" / "Application Support" /
                      "MangaReader12" / "Downloads" / "untracked" / "m" / "c")
            folder.mkdir(parents=True)
            (folder / "page-00000.bin").write_bytes(b"PRIVATE_ORPHAN")
        result = self.review()
        self.assertEqual(result["status"], "EO_STOP_REQUIRES_HUMAN_REVIEW_OF_COPY")
        self.assertIn("EI_STOP_", result["auditStatuses"]["EI"])
        self.assertEqual(result["observedAggregateCounts"]["orphanChapterFiles"], 1)
        self.check_denied(result)
        self.assertNotIn("PRIVATE_ORPHAN", json.dumps(result))
        for copy in (self.first, self.second):
            self.assertTrue((copy / "Library" / "Application Support" /
                "MangaReader12" / "Downloads" / "untracked" / "m" / "c" /
                "page-00000.bin").exists())

    def test_interrupted_download_requires_manual_review_not_install(self):
        for copy in (self.first, self.second):
            db = copy / "Library" / "Application Support" / "MangaReader12" / "library.sqlite"
            with sqlite3.connect(db) as con:
                con.execute("""INSERT INTO manga(
                    internal_id, source_id, source_manga_id, title, status, date_added)
                    VALUES (2, 'asura', 'partial-m', 'Partial', 'unknown', 1)""")
                con.execute("""INSERT INTO chapters(
                    internal_id, manga_id, source_chapter_id, name)
                    VALUES (2, 2, 'part-c', 'Chapter')""")
                con.execute("""INSERT INTO downloads(
                    chapter_id, state, progress, updated_at)
                    VALUES (2, 'failed', 0.5, 5)""")
            partial = (copy / "Library" / "Application Support" /
                       "MangaReader12" / "Downloads" / "asura" / "partial-m" /
                       "part-c")
            partial.mkdir(parents=True)
            (partial / "page-00000.bin").write_bytes(b"PARTIAL_KEEP")
        value = self.review()
        self.assertEqual(value["status"], "EO_STOP_REQUIRES_HUMAN_REVIEW_OF_COPY")
        self.assertIn("EI_STOP_", value["auditStatuses"]["EI"])
        self.assertEqual(value["observedAggregateCounts"]["incompleteDownloadRows"], 1)
        self.check_denied(value)

    def test_copies_changed_during_checks_are_rejected(self):
        actual = eo.audit_metadata_relations
        def changed(root):
            report = actual(root)
            (self.first / "Documents").mkdir(exist_ok=True)
            (self.first / "Documents" / "changed-private").write_bytes(b"secret")
            return report
        with mock.patch.object(eo, "audit_metadata_relations", side_effect=changed):
            with self.assertRaises(eo.EORejected) as err:
                self.review()
        self.assertEqual(err.exception.code, "EO_STOP_TWO_COPIES_CHANGED_DURING_REVIEW")

    def test_exception_with_private_path_never_leaks_to_report(self):
        with mock.patch.object(
            eo, "audit_snapshot",
            side_effect=RuntimeError("secret private iPad chapter path")
        ):
            report = self.review()
        self.assertEqual(report["status"], "EO_STOP_REQUIRES_HUMAN_REVIEW_OF_COPY")
        self.assertEqual(report["auditStatuses"]["EA"], "EA_STOP_EO_AUDIT_FAILED")
        self.assertNotIn("secret", json.dumps(report))
        self.check_denied(report)

    def test_cli_always_stops_instead_of_authorizing_install(self):
        script = Path(__file__).parent / "build70_eo_two_copy_review.py"
        p = subprocess.run([sys.executable, str(script), "--first",
                            str(self.first), "--second", str(self.second)],
                           text=True, capture_output=True, timeout=25)
        self.assertEqual(p.returncode, 2, p.stderr)
        report = json.loads(p.stdout)
        self.assertEqual(report["status"], "EO_STOP_REQUIRES_HUMAN_REVIEW_OF_COPY")
        self.check_denied(report)
        self.assertNotIn(str(self.first), p.stdout + p.stderr)
        self.assertNotIn("fic", p.stdout + p.stderr)
        self.assertNotIn("asura", p.stdout + p.stderr)

    def test_bad_inputs_exit_nonzero_without_private_path_disclosure(self):
        script = Path(__file__).parent / "build70_eo_two_copy_review.py"
        missing = self.second / "sensitive-identifier-do-not-print"
        p = subprocess.run([sys.executable, str(script), "--first",
                            str(self.first), "--second", str(missing)],
                           text=True, capture_output=True, timeout=25)
        self.assertEqual(p.returncode, 2)
        report = json.loads(p.stdout)
        self.assertTrue(report["status"].startswith("EO_STOP_"))
        self.assertNotIn("sensitive-identifier-do-not-print", p.stdout + p.stderr)
        self.check_denied(report)

    def test_script_has_no_device_io_writes_or_install_authority(self):
        source = (Path(__file__).parent / "build70_eo_two_copy_review.py").read_text()
        for forbidden in ("os.system(", "subprocess.", "shutil.", ".unlink(",
                          ".write_bytes(", ".write_text(", "sqlite3.connect(",
                          "appinst(", "install(", "restoreBackup(", "URLSession(",
                          "requests.get(", "os.remove(", "os.rename("):
            self.assertNotIn(forbidden, source)
        self.assertIn('return 2', source)
        self.assertIn('"installationAuthorized": False', source)
        self.assertIn('"originalDeviceIdentityAttested": False', source)


if __name__ == "__main__":
    unittest.main()
