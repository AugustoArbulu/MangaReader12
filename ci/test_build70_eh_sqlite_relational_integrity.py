#!/usr/bin/env python3
"""EH fixture tests: SQLite v1 from production Swift, synthetic downloads."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest import mock

import test_build70_ed_portable_vs_external_library as base
from build70_eh_sqlite_relational_integrity import (
    EHRejected, audit_metadata_relations,
)


class EHRelationalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = base.EDPortableLibraryTests(
            "test_exact_library_rows_equal_but_not_attested")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.db = self.fixture.db

    def mutate(self, sql):
        with sqlite3.connect(self.db) as conn:
            conn.execute(sql)

    def audit(self):
        return audit_metadata_relations(self.root)

    def test_valid_production_schema_copy_never_attests_device(self):
        r = self.audit()
        self.assertEqual(r["status"],
                         "EH_COPIED_SQLITE_METADATA_CONSISTENT_NOT_DEVICE_ATTESTED")
        self.assertTrue(r["foreignKeysChecked"])
        self.assertTrue(r["fullSQLiteIntegrityChecked"])
        for k in ("repairAttempted", "rowsChanged", "snapshotOriginAttested",
                  "consistencyOfSourceIPadProven", "readyToDistributeIPA",
                  "readyToInstallIPA", "installationAuthorized",
                  "restorationAuthorized", "automaticUpdaterEnabled",
                  "iOS12OfflineReadingVerified"):
            self.assertIs(r[k], False, k)

    def test_orphan_library_fk_detected_despite_sqlite_quick_check_ok(self):
        self.mutate("UPDATE library SET manga_id=999")
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("PRAGMA quick_check").fetchone(), ("ok",))
            self.assertNotEqual(db.execute("PRAGMA foreign_key_check").fetchone(), None)
        with self.assertRaises(EHRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EH_STOP_FOREIGN_KEY_VIOLATIONS")

    def test_orphan_history_fk_detected(self):
        self.mutate("UPDATE history SET chapter_id=888")
        with self.assertRaises(EHRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EH_STOP_FOREIGN_KEY_VIOLATIONS")

    def test_orphan_category_relation_detected(self):
        self.mutate("UPDATE manga_categories SET category_id=999")
        with self.assertRaises(EHRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EH_STOP_FOREIGN_KEY_VIOLATIONS")

    def test_orphan_source_settings_detected(self):
        self.mutate("UPDATE source_settings SET source_id='missing-source'")
        with self.assertRaises(EHRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EH_STOP_FOREIGN_KEY_VIOLATIONS")

    def test_downloaded_flag_zero_but_completed_download_stops(self):
        self.mutate("UPDATE chapters SET downloaded=0")
        result = self.audit()
        self.assertEqual(result["status"], "EH_STOP_DOWNLOAD_FLAG_STATE_MISMATCH")
        self.assertEqual(result["chaptersWithDownloadFlagMismatch"], 1)

    def test_downloaded_flag_1_but_noncompleted_download_stops(self):
        self.mutate("UPDATE downloads SET state='failed'")
        result = self.audit()
        self.assertEqual(result["status"], "EH_STOP_DOWNLOAD_FLAG_STATE_MISMATCH")
        self.assertEqual(result["chaptersWithDownloadFlagMismatch"], 1)

    def test_downloaded_flag_abnormal_value_stops(self):
        self.mutate("UPDATE chapters SET downloaded=2")
        result = self.audit()
        self.assertEqual(result["status"], "EH_STOP_DOWNLOAD_FLAG_STATE_MISMATCH")

    def test_completed_download_progress_less_than_one_stops(self):
        self.mutate("UPDATE downloads SET progress=0.5")
        result = self.audit()
        self.assertEqual(result["status"], "EH_STOP_COMPLETED_DOWNLOAD_PROGRESS_MISMATCH")
        self.assertEqual(result["completedDownloadsWithInvalidProgress"], 1)

    def test_read_marker_negative_page_stops(self):
        self.mutate("UPDATE chapters SET last_page_read=-1")
        result = self.audit()
        self.assertEqual(result["status"], "EH_STOP_CHAPTER_MARKER_OUT_OF_RANGE")

    def test_invalid_bookmark_flag_stops(self):
        self.mutate("UPDATE chapters SET bookmarked=5")
        result = self.audit()
        self.assertEqual(result["status"], "EH_STOP_CHAPTER_MARKER_OUT_OF_RANGE")

    def test_invalid_read_flag_stops(self):
        self.mutate("UPDATE chapters SET is_read=3")
        result = self.audit()
        self.assertEqual(result["status"], "EH_STOP_CHAPTER_MARKER_OUT_OF_RANGE")

    def test_missing_completed_page_blocked_by_ea_before_relations(self):
        page = (self.fixture.app / "Downloads" / "asura" / "fiction1" /
                "chap1" / "page-00001.bin")
        page.unlink()
        with self.assertRaises(EHRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EH_STOP_EXTERNAL_COPY_INVALID")

    def test_nonempty_wal_blocked_without_modification(self):
        wal = self.fixture.app / "library.sqlite-wal"
        wal.write_bytes(b"pending transaction")
        with self.assertRaises(EHRejected) as caught:
            self.audit()
        self.assertEqual(caught.exception.code, "EH_STOP_EXTERNAL_COPY_INVALID")
        self.assertEqual(wal.read_bytes(), b"pending transaction")

    def test_cli_status_success_and_stop_exit_code(self):
        script = Path(__file__).resolve().parent / "build70_eh_sqlite_relational_integrity.py"
        def run():
            result = subprocess.run([sys.executable, str(script), "--snapshot",
                                     str(self.root)], capture_output=True,
                                    text=True, timeout=15)
            return result, json.loads(result.stdout)
        before, good = run()
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(good["status"],
                         "EH_COPIED_SQLITE_METADATA_CONSISTENT_NOT_DEVICE_ATTESTED")
        self.mutate("UPDATE chapters SET bookmarked=3")
        after, bad = run()
        self.assertEqual(after.returncode, 2, after.stderr)
        self.assertEqual(bad["status"], "EH_STOP_CHAPTER_MARKER_OUT_OF_RANGE")
        self.assertNotIn(str(self.root), after.stdout + after.stderr)
        self.assertNotIn("fiction1", after.stdout + after.stderr)

    def test_source_guard_and_no_write_or_install(self):
        src = (Path(__file__).resolve().parent /
               "build70_eh_sqlite_relational_integrity.py").read_text()
        self.assertIn("PRAGMA foreign_key_check", src)
        self.assertIn("PRAGMA integrity_check", src)
        self.assertIn('"installationAuthorized": False', src)
        self.assertIn('return 2 if report["status"].startswith("EH_STOP_") else 0', src)
        for forbidden in (".unlink(", ".write_bytes(", "UPDATE downloads",
                          "DELETE FROM", "appinst", "subprocess.run(", "restoreBackup("):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
