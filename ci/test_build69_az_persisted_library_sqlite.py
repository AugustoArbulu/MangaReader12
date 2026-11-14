#!/usr/bin/env python3
"""Build69 AZ: exercise the *actual* Swift schema v1 using temporary SQLite.

Represents an existing library across an in-place application-code upgrade.
No user data, iPad, real app container or real downloaded pages are touched.
This proves schema continuity only, not physical iOS/Filza preservation.
"""
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
DATABASE = (ROOT / "MangaReader12/Database/SQLiteDatabase.swift").read_text()
BACKUP = (ROOT / "MangaReader12/Core/BackupManager.swift").read_text()
DOWNLOAD = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()


def actual_schema_v1():
    match = re.search(
        r'private static let schemaV1 = """(.*?)"""',
        DATABASE, flags=re.DOTALL
    )
    if not match:
        raise AssertionError("Swift schema-v1 contract not found")
    return match.group(1)


class InstalledDataContinuity(unittest.TestCase):
    def test_existing_library_read_history_categories_and_offline_index_survive_reopen(self):
        self.assertIn("static let currentSchemaVersion = 1", DATABASE)
        self.assertIn("static let formatVersion = 1", BACKUP)
        self.assertIn('appendingPathComponent("MangaReader12", isDirectory: true)', DATABASE)
        self.assertIn('appendingPathComponent("library.sqlite", isDirectory: false)', DATABASE)
        self.assertIn('guard version < Self.currentSchemaVersion else { return }', DATABASE)

        with tempfile.TemporaryDirectory(prefix="wr69-az-synthetic-library-") as folder:
            home = Path(folder)
            support = home / "Application Support" / "MangaReader12"
            support.mkdir(parents=True)
            dbfile = support / "library.sqlite"
            offline = support / "Downloads" / "kei.weebcentral.en" / "onepiece" / "chapter-1"
            offline.mkdir(parents=True)
            sentinel = offline / "page-00000.bin"
            sentinel.write_bytes(b"offline-page-fixture; not real manga bytes")
            digest = sentinel.read_bytes()

            with sqlite3.connect(dbfile) as db:
                db.execute("PRAGMA foreign_keys=ON")
                db.executescript(actual_schema_v1())
                db.execute("PRAGMA user_version=1")
                db.execute(
                    "INSERT INTO manga(source_id,source_manga_id,title,date_added)"
                    " VALUES(?,?,?,?)",
                    ("kei.weebcentral.en", "onepiece", "One Piece", 1730000000)
                )
                manga_id = db.execute("SELECT internal_id FROM manga").fetchone()[0]
                db.execute(
                    "INSERT INTO library(manga_id,date_added) VALUES(?,?)",
                    (manga_id, 1730000000)
                )
                db.execute(
                    "INSERT INTO chapters(manga_id,source_chapter_id,name,is_read,"
                    "last_page_read,bookmarked,downloaded) VALUES(?,?,?,?,?,?,?)",
                    (manga_id, "chapter-1", "Chapter 1", 1, 24, 1, 1)
                )
                chapter_id = db.execute("SELECT internal_id FROM chapters").fetchone()[0]
                db.execute(
                    "INSERT INTO downloads(chapter_id,state,progress,local_path,updated_at)"
                    " VALUES(?,?,?,?,?)",
                    (chapter_id, "completed", 1.0, str(offline), 1730000100)
                )
                db.execute(
                    "INSERT INTO history(manga_id,chapter_id,last_read_at) VALUES(?,?,?)",
                    (manga_id, chapter_id, 1730001000)
                )
                db.execute("INSERT INTO categories(name) VALUES(?)", ("Romance",))
                category_id = db.execute("SELECT internal_id FROM categories").fetchone()[0]
                db.execute(
                    "INSERT INTO manga_categories(manga_id,category_id) VALUES(?,?)",
                    (manga_id, category_id)
                )
                db.commit()
                before = self.snapshot(db)
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

            # Same on-device documents/container is the prerequisite of a
            # proper in-place IPA update. Simulate reopening the existing DB,
            # rather than RESTORING a portable backup (which clears downloads).
            with sqlite3.connect(dbfile) as reopened:
                reopened.execute("PRAGMA foreign_keys=ON")
                self.assertEqual(reopened.execute("PRAGMA user_version").fetchone()[0], 1)
                after = self.snapshot(reopened)
                self.assertEqual(reopened.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(before, after)
                self.assertEqual(after["chapter"], ("chapter-1", 1, 24, 1, 1))
                self.assertEqual(after["download"], ("completed", str(offline)))
                self.assertEqual(after["category"], "Romance")
            self.assertTrue(sentinel.exists())
            self.assertEqual(sentinel.read_bytes(), digest)

    @staticmethod
    def snapshot(db):
        return {
            "manga": db.execute("SELECT source_id,source_manga_id,title FROM manga").fetchone(),
            "library": db.execute("SELECT COUNT(*) FROM library").fetchone()[0],
            "chapter": db.execute(
                "SELECT source_chapter_id,is_read,last_page_read,bookmarked,downloaded"
                " FROM chapters"
            ).fetchone(),
            "download": db.execute("SELECT state,local_path FROM downloads").fetchone(),
            "history": db.execute("SELECT COUNT(*) FROM history").fetchone()[0],
            "category": db.execute("SELECT name FROM categories").fetchone()[0],
            "links": db.execute("SELECT COUNT(*) FROM manga_categories").fetchone()[0],
        }

    def test_download_path_and_backup_remain_distinct_semantics(self):
        self.assertIn("enum OfflineDownloadPath", DOWNLOAD)
        self.assertIn("OfflineDownloadPath.chapterDirectory(", DOWNLOAD)
        self.assertIn('appendingPathComponent("Downloads", isDirectory: true)', DOWNLOAD)
        self.assertIn("func rebindCompletedPath(", DATABASE)
        self.assertIn("WHERE state = 'completed'", DATABASE)
        self.assertIn("try sanitizePortableSnapshot(at: snapshotURL)", BACKUP)
        self.assertIn("DELETE FROM downloads;", BACKUP)
        self.assertIn("UPDATE chapters SET downloaded = 0;", BACKUP)
        self.assertIn("try clearExcludedDownloadFiles()", BACKUP)


if __name__ == "__main__":
    unittest.main()
