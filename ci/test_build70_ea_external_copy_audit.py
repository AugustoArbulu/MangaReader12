#!/usr/bin/env python3
"""Host-only adversarial tests for EA extracted data-container audit."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from build70_ea_external_copy_audit import AuditRejected, audit_snapshot

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "build70_ea_external_copy_audit.py"
SCHEMA = """
PRAGMA user_version=1;
CREATE TABLE manga(internal_id INTEGER PRIMARY KEY, source_id TEXT,
                   source_manga_id TEXT);
CREATE TABLE chapters(internal_id INTEGER PRIMARY KEY, manga_id INTEGER,
                      source_chapter_id TEXT);
CREATE TABLE downloads(internal_id INTEGER PRIMARY KEY, chapter_id INTEGER,
                       state TEXT);
"""


class ExternalBackupCopyAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "copied-container"
        self.app = self.root / "Library" / "Application Support" / "MangaReader12"
        self.app.mkdir(parents=True)
        self.db = self.app / "library.sqlite"
        with sqlite3.connect(self.db) as conn:
            conn.executescript(SCHEMA)
        self.downloads = self.app / "Downloads"

    def add_completed(self, source="asura", manga="title-1", chapter="chapter-1",
                      count=2, receipt=True, identifier=1):
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT INTO manga VALUES(?,?,?)", (identifier, source, manga))
            conn.execute("INSERT INTO chapters VALUES(?,?,?)", (identifier, identifier, chapter))
            conn.execute("INSERT INTO downloads VALUES(?,?,'completed')",
                         (identifier, identifier))
        # These test identifiers are ASCII unless this test explicitly checks Unicode.
        scrub = lambda s: "".join(c if c.isalnum() or c in "._-" else "_" for c in s)
        folder = self.downloads / scrub(source) / scrub(manga) / scrub(chapter)
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            (folder / f"page-{i:05d}.bin").write_bytes(b"\xff\xd8" + bytes([i]) + b"\xff\xd9")
        if receipt:
            (folder / ".webreader-completion-v1").write_text(
                f"WR-OFFLINE-COMPLETE-V1:{count}\n", encoding="ascii"
            )
        return folder

    def run_audit(self):
        return audit_snapshot(self.root)

    def fail_code(self, code):
        with self.assertRaises(AuditRejected) as raised:
            self.run_audit()
        self.assertEqual(raised.exception.code, code)

    def assert_denied(self, output):
        for field in ("installationAuthorized", "restorationAuthorized",
                      "automaticUpdaterEnabled", "completeUserDataBackupProven",
                      "physicalOfflineReadingVerified",
                      "copyRetainedOffDeviceIndependentlyProven"):
            self.assertIs(output[field], False)

    def test_real_bytes_and_receipts_are_hashed_reproducibly(self):
        self.add_completed()
        first = self.run_audit()
        self.assertEqual(first["status"], "EA_COPIED_SQLITE_AND_OFFLINE_BYTES_COHERENT_NOT_DEVICE_PROOF")
        self.assertEqual((first["completedChapters"], first["receiptVerifiedChapters"],
                          first["pageFilesReadAndHashed"]), (1, 1, 2))
        self.assertEqual(first["offlineContentSHA256"], self.run_audit()["offlineContentSHA256"])
        self.assert_denied(first)
        self.assertFalse((self.app / "library.sqlite-shm").exists())
        self.assertFalse((self.app / "library.sqlite-wal").exists())

    def test_zero_completed_is_not_proof_of_empty_device(self):
        result = self.run_audit()
        self.assertEqual(result["status"], "EA_NO_COMPLETED_DOWNLOADS_NOT_DEVICE_PROOF")
        self.assertEqual(result["pageFilesReadAndHashed"], 0)
        self.assert_denied(result)

    def test_legacy_without_receipt_requires_physical_reading(self):
        self.add_completed(receipt=False)
        result = self.run_audit()
        self.assertEqual(result["status"], "EA_LEGACY_OR_NONASCII_IDS_REQUIRE_DEVICE_READING")
        self.assertEqual(result["legacyChapters"], 1)
        self.assert_denied(result)

    def test_nonascii_identifiers_flag_platform_path_uncertainty(self):
        self.add_completed(manga="作品")
        result = self.run_audit()
        self.assertEqual(result["nonAsciiIdentifierChapters"], 1)
        self.assertEqual(result["status"], "EA_LEGACY_OR_NONASCII_IDS_REQUIRE_DEVICE_READING")

    def test_missing_page_and_receipt_detected(self):
        folder = self.add_completed()
        (folder / "page-00001.bin").unlink()
        self.fail_code("EA_STOP_BAD_RECEIPT")

    def test_internal_sparse_page_detected(self):
        folder = self.add_completed(count=3)
        (folder / "page-00001.bin").unlink()
        self.fail_code("EA_STOP_SPARSE_PAGES")

    def test_invalid_page_filename_not_ignored(self):
        folder = self.add_completed()
        (folder / "page-evil.bin").write_bytes(b"evil")
        self.fail_code("EA_STOP_INVALID_PAGE_FILENAME")

    def test_empty_and_oversized_page_refused(self):
        folder = self.add_completed()
        (folder / "page-00000.bin").write_bytes(b"")
        self.fail_code("EA_STOP_FILE_SIZE_OR_LINKS")
        with (folder / "page-00000.bin").open("wb") as stream:
            stream.truncate(65 * 1024 * 1024)
        self.fail_code("EA_STOP_FILE_SIZE_OR_LINKS")

    def test_symlinked_page_and_receipt_refused(self):
        folder = self.add_completed()
        (folder / "page-00000.bin").unlink()
        (folder / "page-00000.bin").symlink_to("page-00001.bin")
        self.fail_code("EA_STOP_UNSAFE_PAGE")
        (folder / "page-00000.bin").unlink()
        (folder / "page-00000.bin").write_bytes(b"image")
        (folder / ".webreader-completion-v1").unlink()
        (folder / ".webreader-completion-v1").symlink_to("page-00000.bin")
        self.fail_code("EA_STOP_UNSAFE_RECEIPT")

    def test_symlinked_root_or_database_refused(self):
        self.add_completed()
        destination = Path(self.tmp.name) / "other"
        destination.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(AuditRejected) as exc:
            audit_snapshot(destination)
        self.assertEqual(exc.exception.code, "EA_STOP_SYMLINK")
        self.db.rename(self.app / "saved.sqlite")
        self.db.symlink_to("saved.sqlite")
        self.fail_code("EA_STOP_SYMLINK")

    def test_nonempty_wal_refused_without_checkpointing(self):
        self.add_completed()
        (self.app / "library.sqlite-wal").write_bytes(b"unfinished WAL")
        self.fail_code("EA_STOP_NONEMPTY_WAL_NEEDS_CONSISTENT_SQLITE_SNAPSHOT")

    def test_nonempty_rollback_journal_refused_without_writes(self):
        self.add_completed()
        journal = self.app / "library.sqlite-journal"
        original = b"copied journal could need rollback"
        journal.write_bytes(original)
        self.fail_code("EA_STOP_NONEMPTY_JOURNAL_NEEDS_CONSISTENT_SQLITE_SNAPSHOT")
        self.assertEqual(journal.read_bytes(), original)

    def test_symlinked_rollback_journal_refused(self):
        self.add_completed()
        (self.app / "library.sqlite-journal").symlink_to("library.sqlite")
        self.fail_code("EA_STOP_SYMLINK")

    def test_empty_rollback_journal_does_not_modify_copy(self):
        self.add_completed()
        journal = self.app / "library.sqlite-journal"
        journal.touch()
        result = self.run_audit()
        self.assertEqual(result["completedChapters"], 1)
        self.assertEqual(journal.stat().st_size, 0)
        self.assert_denied(result)

    def test_same_length_page_change_alters_digest_without_attesting_origin(self):
        folder = self.add_completed()
        before = self.run_audit()
        page = folder / "page-00000.bin"
        original = page.read_bytes()
        page.write_bytes(b"X" + original[1:])
        after = self.run_audit()
        self.assertNotEqual(before["offlineContentSHA256"], after["offlineContentSHA256"])
        self.assertEqual(before["sqliteSHA256"], after["sqliteSHA256"])
        # A hash without an external trusted baseline does not detect
        # malicious alteration by itself or prove image decodability.
        self.assertEqual(before["status"], after["status"])
        self.assert_denied(after)

    def test_future_database_schema_refused(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("PRAGMA user_version=2")
        self.fail_code("EA_STOP_UNSUPPORTED_SCHEMA")

    def test_join_mismatch_cannot_silently_skip_completed_record(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT INTO downloads VALUES(1,999,'completed')")
        self.downloads.mkdir()
        self.fail_code("EA_STOP_COMPLETED_ROW_JOIN_MISMATCH")

    def test_sanitized_path_collisions_rejected(self):
        self.add_completed(source="a/b", identifier=1)
        self.add_completed(source="a?b", identifier=2)
        self.fail_code("EA_STOP_SANITIZED_PATH_COLLISION")

    def test_wrong_receipt_size_rejected(self):
        folder = self.add_completed()
        (folder / ".webreader-completion-v1").write_bytes(b"WR-OFFLINE-COMPLETE-V1:123\n")
        self.fail_code("EA_STOP_BAD_RECEIPT")

    def test_cli_never_exposes_user_paths_and_never_authorizes(self):
        folder = self.add_completed()
        (folder / "page-00000.bin").unlink()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--snapshot", str(self.root)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(str(self.root), result.stdout + result.stderr)
        output = json.loads(result.stdout)
        self.assertFalse(output["installationAuthorized"])
        self.assertFalse(output["restorationAuthorized"])
        self.assertFalse(output["automaticUpdaterEnabled"])

    def test_static_failsafe_has_no_destructive_operators(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "shutil.rmtree", "os.remove(", ".unlink(", "os.system(",
            "subprocess.run(", "appinst", "sqlite3_backup_step",
            "UPDATE downloads", "DELETE FROM", "restoreBackup(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("immutable=1", source)
        self.assertIn("EA_STOP_NONEMPTY_WAL_NEEDS_CONSISTENT_SQLITE_SNAPSHOT", source)
        self.assertIn("EA_STOP_NONEMPTY_JOURNAL_NEEDS_CONSISTENT_SQLITE_SNAPSHOT", source)


if __name__ == "__main__":
    unittest.main()
