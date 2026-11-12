#!/usr/bin/env python3
"""EC tests: synthetic whole-tree copies, never real user content."""
from pathlib import Path
import hashlib
import os
from unittest import mock
import shutil
import sqlite3
import tempfile
import unittest

from build70_ec_full_container_dual_copy import (
    ECRejected, audit_tree, compare_copies,
)

class ECDualCopyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.first, self.second = base / "baseline", base / "candidate"
        app = self.first / "Library" / "Application Support" / "MangaReader12"
        app.mkdir(parents=True)
        self.app = app
        db = app / "library.sqlite"
        with sqlite3.connect(db) as conn:
            conn.executescript("""
                PRAGMA user_version=1;
                CREATE TABLE manga(internal_id INTEGER PRIMARY KEY,
                    source_id TEXT, source_manga_id TEXT);
                CREATE TABLE chapters(internal_id INTEGER PRIMARY KEY,
                    manga_id INTEGER, source_chapter_id TEXT);
                CREATE TABLE downloads(internal_id INTEGER PRIMARY KEY,
                    chapter_id INTEGER, state TEXT);
                INSERT INTO manga VALUES(1,'asura','m1');
                INSERT INTO chapters VALUES(1,1,'ch1');
                INSERT INTO downloads VALUES(1,1,'completed');
            """)
        chapter = app / "Downloads" / "asura" / "m1" / "ch1"
        chapter.mkdir(parents=True)
        (chapter / "page-00000.bin").write_bytes(b"page content A")
        (chapter / "page-00001.bin").write_bytes(b"page content B")
        (chapter / ".webreader-completion-v1").write_bytes(
            b"WR-OFFLINE-COMPLETE-V1:2\n")
        self.prefs = self.first / "Library" / "Preferences"
        self.prefs.mkdir()
        (self.prefs / "app.plist").write_bytes(b"preferences")
        (self.first / "Documents").mkdir()
        (self.first / "Documents" / ".hidden-empty").touch()
        shutil.copytree(self.first, self.second)

    def test_identical_full_copies_never_prove_device(self):
        r = compare_copies(self.first, self.second)
        self.assertEqual(r["status"], "EC_TWO_EXTERNAL_COPIES_IDENTICAL_NOT_DEVICE_PROOF")
        self.assertTrue(r["copiesByteIdenticalHere"])
        self.assertEqual(len(r["fullTreeSHA256"]), 64)
        for k in ("originOfEitherCopyAuthenticated", "originalIPadDataAttested",
                  "wholeBackupRestorabilityProven", "readyToInstallIPA",
                  "installationAuthorized", "restorationAuthorized",
                  "automaticUpdaterEnabled"):
            self.assertIs(r[k], False)

    def test_changed_preferences_detected_with_same_offline_pages(self):
        (self.second / "Library" / "Preferences" / "app.plist").write_bytes(
            b"preferenceS")
        r = compare_copies(self.first, self.second)
        self.assertEqual(r["status"], "EC_STOP_EXTERNAL_COPIES_DIFFER")
        self.assertFalse(r["copiesByteIdenticalHere"])
        self.assertIsNone(r["fullTreeSHA256"])

    def test_missing_extra_empty_file_is_detected(self):
        (self.second / "Documents" / ".hidden-empty").unlink()
        r = compare_copies(self.first, self.second)
        self.assertEqual(r["status"], "EC_STOP_EXTERNAL_COPIES_DIFFER")

    def test_identical_data_with_renamed_noncritical_file_differs(self):
        old = self.second / "Library" / "Preferences" / "app.plist"
        old.rename(old.with_name("other.plist"))
        r = compare_copies(self.first, self.second)
        self.assertEqual(r["status"], "EC_STOP_EXTERNAL_COPIES_DIFFER")

    def test_symlinked_file_never_followed(self):
        p = self.second / "Documents" / "unsafe"
        p.symlink_to(self.second / "Library" / "Preferences" / "app.plist")
        with self.assertRaises(ECRejected) as caught:
            compare_copies(self.first, self.second)
        self.assertEqual(caught.exception.code, "EC_STOP_SYMLINK")

    def test_symlinked_directory_never_followed(self):
        (self.second / "Documents" / "link").symlink_to(self.prefs, target_is_directory=True)
        with self.assertRaises(ECRejected) as caught:
            audit_tree(self.second)
        self.assertEqual(caught.exception.code, "EC_STOP_SYMLINK")

    def test_identical_path_and_nested_path_refused(self):
        with self.assertRaises(ECRejected) as caught:
            compare_copies(self.first, self.first)
        self.assertEqual(caught.exception.code, "EC_STOP_COPIES_NOT_DISTINCT")
        nested = self.first / "nested"
        nested.mkdir()
        with self.assertRaises(ECRejected) as caught:
            compare_copies(self.first, nested)
        self.assertEqual(caught.exception.code, "EC_STOP_COPIES_NOT_DISTINCT")

    def test_missing_offline_page_rejected_before_full_copy_match(self):
        (self.second / "Library" / "Application Support" / "MangaReader12" /
         "Downloads" / "asura" / "m1" / "ch1" / "page-00001.bin").unlink()
        with self.assertRaises(ECRejected) as caught:
            compare_copies(self.first, self.second)
        self.assertEqual(caught.exception.code, "EC_STOP_OFFLINE_COPY_INVALID")

    def test_nonempty_wal_rejected_before_comparison(self):
        (self.second / "Library" / "Application Support" / "MangaReader12" /
         "library.sqlite-wal").write_bytes(b"pending WAL")
        with self.assertRaises(ECRejected) as caught:
            compare_copies(self.first, self.second)
        self.assertEqual(caught.exception.code, "EC_STOP_OFFLINE_COPY_INVALID")

    def test_empty_file_is_included_and_deterministic(self):
        a = audit_tree(self.first)
        b = audit_tree(self.first)
        self.assertEqual(a, b)
        self.assertGreater(a["files"], 4)
        self.assertEqual(a["sha256"], b["sha256"])

    def test_additional_file_with_same_length_is_detected(self):
        (self.second / "Documents" / ".hidden-empty").write_bytes(b"x")
        r = compare_copies(self.first, self.second)
        self.assertEqual(r["status"], "EC_STOP_EXTERNAL_COPIES_DIFFER")

    def test_root_symlink_rejected_even_with_valid_target(self):
        link = self.first.parent / "alias"
        link.symlink_to(self.first, target_is_directory=True)
        with self.assertRaises(ECRejected) as caught:
            audit_tree(link)
        self.assertEqual(caught.exception.code, "EC_STOP_UNSAFE_ROOT")

    def test_in_place_empty_file_swap_is_detected(self):
        target = self.first / "Documents" / ".hidden-empty"
        actual_open = os.open
        exchanged = [False]

        def swap_before_fd_open(name, flags, *args, **kwargs):
            if name == ".hidden-empty" and kwargs.get("dir_fd") is not None and not exchanged[0]:
                exchanged[0] = True
                target.rename(target.with_name(".old-hidden-empty"))
                target.write_bytes(b"")
            return actual_open(name, flags, *args, **kwargs)

        with mock.patch("build70_ec_full_container_dual_copy.os.open",
                        side_effect=swap_before_fd_open):
            with self.assertRaises(ECRejected) as caught:
                audit_tree(self.first)
        self.assertTrue(exchanged[0])
        self.assertEqual(caught.exception.code, "EC_STOP_FILE_CHANGED")

    def test_file_size_change_before_open_is_detected(self):
        target = self.first / "Library" / "Preferences" / "app.plist"
        actual_open = os.open
        swapped = [False]

        def change_before_fd_open(name, flags, *args, **kwargs):
            if name == "app.plist" and kwargs.get("dir_fd") is not None and not swapped[0]:
                swapped[0] = True
                target.write_bytes(b"new")
            return actual_open(name, flags, *args, **kwargs)

        with mock.patch("build70_ec_full_container_dual_copy.os.open",
                        side_effect=change_before_fd_open):
            with self.assertRaises(ECRejected) as caught:
                audit_tree(self.first)
        self.assertTrue(swapped[0])
        self.assertEqual(caught.exception.code, "EC_STOP_FILE_CHANGED")

    def test_special_file_rejected(self):
        import socket
        path = self.second / "Documents" / "special.sock"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(path))
            with self.assertRaises(ECRejected) as caught:
                audit_tree(self.second)
            self.assertEqual(caught.exception.code, "EC_STOP_UNSAFE_ENTRY")
        finally:
            listener.close()

    def test_fd_code_anchors_children_and_hashes_zero_bytes(self):
        source = (Path(__file__).resolve().parent /
                  "build70_ec_full_container_dual_copy.py").read_text()
        for token in ("os.scandir(directory_fd)", "dir_fd=directory_fd",
                      'getattr(os, "O_NOFOLLOW", 0)', "_hash_file(", "os.fstat(fd)"):
            self.assertIn(token, source)
        self.assertEqual(audit_tree(self.first)["sha256"], audit_tree(self.first)["sha256"])

    def test_static_no_write_install_or_network(self):
        source = (Path(__file__).resolve().parent /
                  "build70_ec_full_container_dual_copy.py").read_text()
        for forbidden in (
            "shutil.copy", "shutil.rmtree", ".unlink(", ".write_bytes(",
            ".write_text(", "requests.get(", "urlopen(", "appinst",
            "subprocess.run(", "sqlite3.connect(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"installationAuthorized": False', source)
        self.assertIn('"readyToDistributeIPA": False', source)

if __name__ == "__main__":
    unittest.main()
