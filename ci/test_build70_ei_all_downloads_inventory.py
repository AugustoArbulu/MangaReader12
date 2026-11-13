#!/usr/bin/env python3
"""EI tests using synthetic SQLite v1 and fake offline files, no real iPad."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest import mock
import build70_ei_all_downloads_inventory as ei

import test_build70_ed_portable_vs_external_library as fixtures
from build70_ei_all_downloads_inventory import (
    EIRejected, audit_noncompleted_and_orphans, _collect_download_tree,
)


class EIAllDownloadsInventoryTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.EDPortableLibraryTests(
            "test_exact_library_rows_equal_but_not_attested")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fx = fixture
        self.root = fixture.root
        self.base = fixture.app / "Downloads"

    def mutate(self, query):
        with sqlite3.connect(self.fx.db) as db:
            db.execute(query)

    def add_noncompleted(self, state="paused", source="asura",
                         title="fictitious2", chapter="ch2", ident=2):
        with sqlite3.connect(self.fx.db) as db:
            db.execute("""
                INSERT INTO manga(internal_id,source_id,source_manga_id,
                    title,status,date_added) VALUES (?,?,?,'Example','unknown',1)
            """, (ident, source, title))
            db.execute("""
                INSERT INTO chapters(internal_id,manga_id,source_chapter_id,name)
                VALUES (?,?,?,'Chapter')""", (ident, ident, chapter))
            db.execute("""
                INSERT INTO downloads(chapter_id,state,progress,updated_at)
                VALUES (?,?,0.2,5)
            """, (ident, state))
        source = "".join(c if c.isalnum() or c in "._-" else "_" for c in source)
        folder = self.base / source / title / chapter
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def audit(self):
        return audit_noncompleted_and_orphans(self.root)

    def denied(self, value):
        for field in ("contentBytesVerifiedHere",
                      "noncompletedFilesConfirmedToSurviveUpgrade",
                      "allUserFilesOffDeviceProven",
                      "sourceDeviceAttested", "originalIPadRead",
                      "readyToDistributeIPA", "readyToInstallIPA",
                      "installationAuthorized", "restorationAuthorized",
                      "automaticUpdaterEnabled"):
            self.assertIs(value[field], False, field)

    def test_completed_snapshot_has_only_accounted_files(self):
        r = self.audit()
        self.assertEqual(r["status"], "EI_ALL_SCANNED_FILES_ACCOUNTED_NOT_DEVICE_PROOF")
        self.assertEqual(r["downloadRows"], 1)
        self.assertEqual(r["noncompletedDownloadRows"], 0)
        self.assertEqual(r["totalRegularFilesWithinDownloads"], 3)
        self.assertEqual(r["orphanChapterFiles"], 0)
        self.denied(r)

    def test_paused_download_pages_and_recovery_plan_preserved_as_material(self):
        folder = self.add_noncompleted(state="paused")
        (folder / "page-00000.bin").write_bytes(b"part1")
        (folder / "_download-plan.json").write_bytes(b'{"private":"fiction"}')
        r = self.audit()
        self.assertEqual(r["status"], "EI_STOP_NONCOMPLETED_OR_UNICODE_REQUIRE_OWNER_REVIEW")
        self.assertEqual(r["downloadRows"], 2)
        self.assertEqual(r["noncompletedDownloadRows"], 1)
        self.assertEqual(r["partialJobFiles"], 2)
        self.assertEqual(r["partialJobBytes"], 26)
        self.assertEqual(r["orphanChapterFiles"], 0)
        self.denied(r)
        self.assertNotIn("fictitious2", str(r))

    def test_paused_download_requires_nonzero_cli_owner_review(self):
        folder = self.add_noncompleted(state="paused")
        (folder / "page-00000.bin").write_bytes(b"partial private test bytes")
        script = Path(__file__).resolve().parent / "build70_ei_all_downloads_inventory.py"
        p = subprocess.run([sys.executable, str(script), "--snapshot", str(self.root)],
                           text=True, capture_output=True, timeout=15)
        self.assertEqual(p.returncode, 2)
        report = json.loads(p.stdout)
        self.assertEqual(report["status"],
                         "EI_STOP_NONCOMPLETED_OR_UNICODE_REQUIRE_OWNER_REVIEW")
        self.assertEqual(report["partialJobFiles"], 1)
        self.assertNotIn("partial private test bytes", p.stdout + p.stderr)
        self.assertFalse(report["installationAuthorized"])

    def test_failed_job_pages_also_counted(self):
        folder = self.add_noncompleted(state="failed")
        (folder / "page-00000.bin").write_bytes(b"x")
        r = self.audit()
        self.assertEqual(r["partialJobFiles"], 1)
        self.assertEqual(r["noncompletedDownloadRows"], 1)

    def test_queued_job_empty_directory_is_not_pretended_offline(self):
        self.add_noncompleted(state="queued")
        r = self.audit()
        self.assertEqual(r["partialJobFiles"], 0)
        self.assertEqual(r["noncompletedDownloadRows"], 1)
        self.assertIn("REVIEW", r["status"])
        self.denied(r)

    def test_orphan_chapter_file_is_never_ignored(self):
        folder = self.base / "lost-source" / "manga" / "chapter"
        folder.mkdir(parents=True)
        (folder / "page-00000.bin").write_bytes(b"unreferenced")
        r = self.audit()
        self.assertEqual(r["status"], "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES")
        self.assertEqual(r["orphanChapterDirectoriesWithFiles"], 1)
        self.assertEqual(r["orphanChapterFiles"], 1)
        self.assertEqual(r["orphanChapterBytes"], len(b"unreferenced"))
        self.denied(r)

    def test_empty_orphan_chapter_folder_is_preserved_and_blocks(self):
        folder = self.base / "orphan-source" / "orphan-manga" / "orphan-chapter"
        folder.mkdir(parents=True)
        r = self.audit()
        self.assertEqual(r["status"], "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES")
        self.assertEqual(r["orphanEmptyChapterDirectories"], 1)
        self.assertEqual(r["orphanChapterDirectoriesWithFiles"], 0)
        self.assertEqual(r["orphanChapterFiles"], 0)
        self.assertTrue(folder.exists())
        self.denied(r)

    def test_empty_orphan_source_prefix_blocks(self):
        orphan = self.base / "abandoned-source"
        orphan.mkdir()
        r = self.audit()
        self.assertEqual(r["status"], "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES")
        self.assertEqual(r["unreferencedPrefixDirectories"], 1)
        self.assertEqual(r["orphanEmptyChapterDirectories"], 0)
        self.denied(r)

    def test_orphan_empty_manga_prefix_blocks(self):
        orphan = self.base / "asura" / "abandoned-manga"
        orphan.mkdir()
        r = self.audit()
        self.assertEqual(r["status"], "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES")
        self.assertEqual(r["unreferencedPrefixDirectories"], 1)
        self.denied(r)

    def test_unexpected_empty_nested_directory_blocks(self):
        folder = self.base / "asura" / "fiction1" / "chap1" / "extra-empty"
        folder.mkdir()
        r = self.audit()
        self.assertEqual(r["status"], "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES")
        self.assertEqual(r["nestedUnexpectedDirectoryCount"], 1)
        self.assertEqual(r["unclassifiedFileCount"], 0)
        self.denied(r)

    def test_known_empty_queued_folder_is_not_mislabeled_orphan(self):
        self.add_noncompleted(state="queued")
        r = self.audit()
        self.assertEqual(r["status"], "EI_STOP_NONCOMPLETED_OR_UNICODE_REQUIRE_OWNER_REVIEW")
        self.assertEqual(r["orphanEmptyChapterDirectories"], 0)
        self.assertEqual(r["unreferencedPrefixDirectories"], 0)
        self.assertEqual(r["recordedChapterDirectoriesMissingFromCopy"], 0)

    def test_missing_noncompleted_directory_is_visible_to_owner(self):
        folder = self.add_noncompleted(state="failed")
        folder.rmdir()
        r = self.audit()
        self.assertEqual(r["status"], "EI_STOP_NONCOMPLETED_OR_UNICODE_REQUIRE_OWNER_REVIEW")
        self.assertEqual(r["recordedChapterDirectoriesMissingFromCopy"], 1)
        self.assertEqual(r["orphanEmptyChapterDirectories"], 0)
        self.denied(r)

    def test_unclassified_root_file_blocks_even_if_completed_valid(self):
        (self.base / "unclassified-private.bin").write_bytes(b"secret")
        r = self.audit()
        self.assertEqual(r["status"], "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES")
        self.assertEqual(r["unclassifiedFileCount"], 1)
        self.assertEqual(r["unclassifiedFileBytes"], 6)

    def test_extra_nested_files_not_misclassified_as_legitimate_pages(self):
        extra = self.base / "asura" / "fiction1" / "chap1" / "unusual"
        extra.mkdir()
        (extra / "page-00099.bin").write_bytes(b"x")
        r = self.audit()
        self.assertEqual(r["unclassifiedFileCount"], 1)
        self.assertEqual(r["nestedUnexpectedDirectoryCount"], 1)
        self.assertTrue(r["status"].startswith("EI_STOP_"))

    def test_mutated_complete_page_during_inventory_is_not_accepted(self):
        chapter = self.base / "asura" / "fiction1" / "chap1"
        target = chapter / "page-00000.bin"
        before = target.read_bytes()
        original_scan = ei._collect_download_tree

        def mutate_after_tree_walk(root):
            result = original_scan(root)
            target.write_bytes(b"X" + before[1:])
            return result

        with mock.patch.object(ei, "_collect_download_tree",
                               side_effect=mutate_after_tree_walk):
            with self.assertRaises(EIRejected) as caught:
                self.audit()
        self.assertEqual(
            caught.exception.code, "EI_STOP_SNAPSHOT_CHANGED_DURING_INVENTORY"
        )
        self.assertNotEqual(target.read_bytes(), before)
        # Fixture is synthetic; auditor did not repair or roll back the bytes.

    def test_mutated_sqlite_during_inventory_is_not_accepted(self):
        original_scan = ei._collect_download_tree

        def mutate_after_tree_walk(root):
            result = original_scan(root)
            with sqlite3.connect(self.fx.db) as db:
                db.execute(
                    "UPDATE manga SET title = title || '-mutated' WHERE internal_id=1"
                )
            return result

        with mock.patch.object(ei, "_collect_download_tree",
                               side_effect=mutate_after_tree_walk):
            with self.assertRaises(EIRejected) as caught:
                self.audit()
        self.assertEqual(
            caught.exception.code, "EI_STOP_SNAPSHOT_CHANGED_DURING_INVENTORY"
        )

    def test_unrecognized_regular_file_in_completed_chapter_blocks(self):
        chapter = self.base / "asura" / "fiction1" / "chap1"
        payload = chapter / "hidden-recoverable-data"
        payload.write_bytes(b"synthetic-extra-bytes")
        result = self.audit()
        self.assertEqual(result["status"],
                         "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES")
        self.assertEqual(result["unrecognizedChapterLeafFiles"], 1)
        self.assertEqual(result["unrecognizedLeafFilesInRecordedChapters"], 1)
        self.assertEqual(result["orphanChapterFiles"], 0)
        self.assertTrue(payload.exists())
        self.denied(result)
        self.assertNotIn(payload.name, str(result))

    def test_unrecognized_regular_file_in_paused_chapter_blocks(self):
        chapter = self.add_noncompleted(state="paused")
        extra = chapter / ".wr69-plan-aborted.tmp"
        extra.write_bytes(b"synthetic-incomplete-plan")
        result = self.audit()
        self.assertEqual(result["status"],
                         "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES")
        self.assertEqual(result["unrecognizedChapterLeafFiles"], 1)
        self.assertEqual(result["unrecognizedLeafFilesInRecordedChapters"], 1)
        self.assertEqual(result["partialJobFiles"], 1)
        self.assertTrue(extra.exists())
        self.denied(result)

    def test_expected_plan_and_receipt_are_not_unknown_leaves(self):
        chapter = self.add_noncompleted(state="paused")
        (chapter / "_download-plan.json").write_bytes(b"{ }")
        result = self.audit()
        self.assertEqual(result["unrecognizedChapterLeafFiles"], 0)
        self.assertEqual(result["unrecognizedLeafFilesInRecordedChapters"], 0)
        self.assertEqual(result["status"],
                         "EI_STOP_NONCOMPLETED_OR_UNICODE_REQUIRE_OWNER_REVIEW")

    def test_stray_page_like_filename_in_partial_chapter_is_not_silently_accounted(self):
        # EA already rejects an invalid "page-" prefix inside a COMPLETED
        # chapter. Use an incomplete row to exercise the EI-specific gap.
        chapter = self.add_noncompleted(state="paused")
        unexpected = chapter / "page-extra.bin"
        unexpected.write_bytes(b"synthetic")
        result = self.audit()
        self.assertEqual(result["status"],
                         "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES")
        self.assertEqual(result["unrecognizedChapterLeafFiles"], 1)
        self.assertEqual(result["unrecognizedLeafFilesInRecordedChapters"], 1)
        self.assertTrue(unexpected.exists())

    def test_unrecognized_leaf_cli_exits_nonzero_without_name_leak(self):
        chapter = self.base / "asura" / "fiction1" / "chap1"
        secret_name = "private-unknown-name-a1"
        (chapter / secret_name).write_bytes(b"private-fixture")
        script = Path(__file__).resolve().parent / "build70_ei_all_downloads_inventory.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--snapshot", str(self.root)],
            capture_output=True, text=True, timeout=15
        )
        self.assertEqual(proc.returncode, 2)
        report = json.loads(proc.stdout)
        self.assertEqual(report["unrecognizedLeafFilesInRecordedChapters"], 1)
        self.assertNotIn(secret_name, proc.stdout + proc.stderr)
        self.assertNotIn(str(self.root), proc.stdout + proc.stderr)

    def test_symlinked_orphan_folder_is_refused(self):
        link = self.base / "link"
        link.symlink_to(self.base / "asura", target_is_directory=True)
        with self.assertRaises(EIRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EI_STOP_SYMLINK")

    def test_symlinked_orphan_file_is_refused(self):
        folder = self.base / "lost-source" / "manga" / "chapter"
        folder.mkdir(parents=True)
        (folder / "page-00000.bin").symlink_to(
            self.base / "asura" / "fiction1" / "chap1" / "page-00000.bin"
        )
        with self.assertRaises(EIRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EI_STOP_SYMLINK")

    def test_special_fifo_rejected_without_reading_contents(self):
        path = self.base / "asura" / "fiction1" / "chap1" / "special.fifo"
        os.mkfifo(path)
        with self.assertRaises(EIRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EI_STOP_SPECIAL_FILE")

    def test_unreferenced_and_queued_are_both_counted(self):
        self.add_noncompleted(state="queued")
        orphan = self.base / "other" / "manga" / "chapter"
        orphan.mkdir(parents=True)
        (orphan / "page-00000.bin").write_bytes(b"orphan")
        r = self.audit()
        self.assertEqual(r["noncompletedDownloadRows"], 1)
        self.assertEqual(r["orphanChapterFiles"], 1)
        self.assertTrue(r["status"].startswith("EI_STOP_"))

    def test_mixed_completed_and_paused_sanitized_collision_is_refused(self):
        completed = self.add_noncompleted(
            state="paused", source="a?b", title="fiction2", chapter="ch2", ident=2
        )
        (completed / "page-00000.bin").write_bytes(b"fictitious-page")
        (completed / ".webreader-completion-v1").write_bytes(
            b"WR-OFFLINE-COMPLETE-V1:1\\n".replace(b"\\n", b"\n")
        )
        self.mutate("UPDATE downloads SET state='completed',progress=1 WHERE chapter_id=2")
        self.mutate("UPDATE chapters SET downloaded=1 WHERE internal_id=2")
        self.add_noncompleted(
            state="paused", source="a/b", title="fiction2", chapter="ch2", ident=3
        )
        with self.assertRaises(EIRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EI_STOP_SANITIZED_PATH_COLLISION")

    def test_collision_between_two_noncompleted_paths_is_refused(self):
        self.add_noncompleted(source="a?b", title="fictitious2",
                              chapter="ch2", ident=2)
        self.add_noncompleted(source="a/b", title="fictitious2",
                              chapter="ch2", ident=3)
        with self.assertRaises(EIRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EI_STOP_SANITIZED_PATH_COLLISION")

    def test_untrusted_directory_listing_is_bounded_before_sort(self):
        folder = self.base / "asura" / "fiction1" / "chap1"
        for i in range(6):
            (folder / ("extra-" + str(i))).write_bytes(b"x")
        # Four directories (root / source / manga / chapter); cap file
        # names to two + four => seven or more names must abort early.
        with mock.patch.object(ei, "MAX_FILES", 2), mock.patch.object(ei, "MAX_DIRS", 4):
            with self.assertRaises(EIRejected) as caught:
                _collect_download_tree(self.base)
        self.assertEqual(caught.exception.code, "EI_STOP_ENTRY_LIMIT")

    def test_orphan_cli_must_exit_nonzero_without_private_paths(self):
        folder = self.base / "lost-source" / "manga" / "chapter"
        folder.mkdir(parents=True)
        (folder / "page-00000.bin").write_bytes(b"secret")
        script = Path(__file__).resolve().parent / "build70_ei_all_downloads_inventory.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--snapshot", str(self.root)],
            capture_output=True, text=True, timeout=15
        )
        self.assertEqual(proc.returncode, 2)
        report = json.loads(proc.stdout)
        self.assertEqual(report["orphanChapterFiles"], 1)
        self.assertNotIn(str(self.root), proc.stdout + proc.stderr)
        self.assertNotIn("lost-source", proc.stdout + proc.stderr)
        self.assertFalse(report["installationAuthorized"])

    def test_cli_success_requires_only_accounted_local_files(self):
        script = Path(__file__).resolve().parent / "build70_ei_all_downloads_inventory.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--snapshot", str(self.root)],
            capture_output=True, text=True, timeout=15
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["status"], "EI_ALL_SCANNED_FILES_ACCOUNTED_NOT_DEVICE_PROOF")
        self.denied(report)

    def test_readonly_source_never_repairs_or_installs(self):
        source = (Path(__file__).resolve().parent /
                  "build70_ei_all_downloads_inventory.py").read_text()
        for forbidden in ("appinst", "restoreBackup(", ".unlink(", ".write_bytes(",
                          ".write_text(", "shutil.rmtree(", "subprocess.run(",
                          "DELETE FROM ", "UPDATE downloads"):
            self.assertNotIn(forbidden, source)
        self.assertIn('os.scandir(folder_fd)', source)
        self.assertIn('dir_fd=folder_fd', source)
        self.assertIn('"installationAuthorized": False', source)
        self.assertIn('return 2 if result["status"].startswith("EI_STOP_") else 0', source)


if __name__ == "__main__":
    unittest.main()
