#!/usr/bin/env python3
"""ED tests with fictional SQLite v1, fictional offline pages and portable JSON."""
import base64
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from build70_ed_portable_vs_external_library import (
    compare_portable_to_copy, EDRejected,
)


class EDPortableLibraryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "extracted-data"
        self.app = self.root / "Library" / "Application Support" / "MangaReader12"
        self.app.mkdir(parents=True)
        self.db = self.app / "library.sqlite"
        swift = (Path(__file__).resolve().parent.parent /
                 "MangaReader12" / "Database" / "SQLiteDatabase.swift").read_text()
        schema = re.search(r'private static let schemaV1 = """(.*?)"""', swift, re.S)
        self.assertIsNotNone(schema)
        with sqlite3.connect(self.db) as con:
            con.executescript(schema.group(1))
            con.execute("PRAGMA user_version=1")
            self.assertEqual(con.execute("PRAGMA user_version").fetchone(), (1,))
            con.executescript("""
                INSERT INTO manga(internal_id,source_id,source_manga_id,
                    title,status,date_added) VALUES(1,'asura','fiction1','Obra fictícia','ongoing',1);
                INSERT INTO library(manga_id,date_added,last_checked) VALUES(1,1,2);
                INSERT INTO chapters(internal_id,manga_id,source_chapter_id,
                    name,is_read,last_page_read,bookmarked,downloaded)
                    VALUES(1,1,'chap1','Capítulo fictício',1,2,1,1);
                INSERT INTO categories(internal_id,name,sort_order)
                    VALUES(1,'Ficção',1);
                INSERT INTO manga_categories(manga_id,category_id) VALUES(1,1);
                INSERT INTO history(manga_id,chapter_id,last_read_at) VALUES(1,1,3);
                INSERT INTO downloads(chapter_id,state,progress,updated_at)
                    VALUES(1,'completed',1,4);
                INSERT INTO repositories(internal_id,name,url,enabled)
                    VALUES(1,'source-repo','https://example.test',1);
                INSERT INTO source_settings(source_id,key,value)
                    VALUES('asura','setting','private-value');
                INSERT INTO migration_map(internal_id,source_manga_id,
                    destination_manga_id,migrated_at) VALUES(1,1,1,5);
                INSERT INTO sources(source_id,name,version,lang,enabled,
                    manifest_json,installed_at,updated_at)
                    VALUES('asura','Asura','1','en',1,'{}',1,2);
            """)
        folder = self.app / "Downloads" / "asura" / "fiction1" / "chap1"
        folder.mkdir(parents=True)
        (folder / "page-00000.bin").write_bytes(b"fake image page one")
        (folder / "page-00001.bin").write_bytes(b"fake image page two")
        (folder / ".webreader-completion-v1").write_bytes(
            b"WR-OFFLINE-COMPLETE-V1:2\n")
        self.backup = self.export_portable()

    def export_portable(self):
        with sqlite3.connect(self.db) as live:
            portable = sqlite3.connect(":memory:")
            try:
                live.backup(portable)
                portable.executescript("""
                    DELETE FROM downloads;
                    UPDATE chapters SET downloaded=0;
                    DELETE FROM sources;
                """)
                payload = portable.serialize()
            finally:
                portable.close()
        return json.dumps({
            "formatVersion": 1, "createdAt": 1790000000.0,
            "databaseBase64": base64.b64encode(payload).decode("ascii"),
            "preferences": {},
        }, sort_keys=True).encode()

    def mutate(self, query):
        with sqlite3.connect(self.db) as con:
            con.execute(query)

    def compare(self, backup=None):
        return compare_portable_to_copy(
            self.root, self.backup if backup is None else backup)

    def assert_never_authorized(self, result):
        for key in (
            "readyToInstallIPA", "readyToDistributeIPA",
            "installationAuthorized", "restorationAuthorized",
            "automaticUpdaterEnabled", "fullBackupRestorabilityProven",
            "portableOriginAuthenticated", "externalCopyOriginAuthenticated",
            "physicalDeviceIdentityAttested", "offlineImageDecodingVerified",
        ):
            self.assertIs(result[key], False, key)

    def test_exact_library_rows_equal_but_not_attested(self):
        report = self.compare()
        self.assertEqual(report["status"], "ED_LIBRARY_ROWS_EQUAL_NOT_ATTESTED")
        self.assertEqual(report["tablesCompared"], 9)
        self.assertEqual(report["matchingTables"], 9)
        self.assertEqual(report["mismatchedTableNames"], [])
        self.assert_never_authorized(report)

    def test_last_page_progress_changed_same_counts_detected(self):
        self.mutate("UPDATE chapters SET last_page_read=3 WHERE internal_id=1")
        result = self.compare()
        self.assertEqual(result["status"], "ED_STOP_LIBRARY_ROWS_DIFFER")
        self.assertEqual(result["mismatchedTableNames"], ["chapters"])

    def test_bookmark_changed_same_counts_detected(self):
        self.mutate("UPDATE chapters SET bookmarked=0 WHERE internal_id=1")
        self.assertEqual(self.compare()["mismatchedTableNames"], ["chapters"])

    def test_read_state_changed_same_row_count_detected(self):
        self.mutate("UPDATE chapters SET is_read=0")
        self.assertEqual(self.compare()["mismatchedTableNames"], ["chapters"])

    def test_title_changed_same_count_detected_without_disclosure(self):
        self.mutate("UPDATE manga SET title='Segredo' WHERE internal_id=1")
        output = self.compare()
        self.assertEqual(output["mismatchedTableNames"], ["manga"])
        self.assertNotIn("Segredo", str(output))
        self.assertNotIn("Obra fictícia", str(output))

    def test_history_timestamp_changed_detected(self):
        self.mutate("UPDATE history SET last_read_at=100")
        self.assertEqual(self.compare()["mismatchedTableNames"], ["history"])

    def test_category_relationship_changed_detected(self):
        self.mutate("UPDATE manga_categories SET category_id=7")
        self.assertEqual(self.compare()["mismatchedTableNames"], ["manga_categories"])

    def test_repository_state_changed_detected(self):
        self.mutate("UPDATE repositories SET enabled=0")
        self.assertEqual(self.compare()["mismatchedTableNames"], ["repositories"])

    def test_source_settings_changed_detected(self):
        self.mutate("UPDATE source_settings SET value='other'")
        self.assertEqual(self.compare()["mismatchedTableNames"], ["source_settings"])

    def test_downloaded_flag_intentionally_excluded(self):
        self.mutate("UPDATE chapters SET downloaded=0")
        r = self.compare()
        self.assertEqual(r["status"], "ED_LIBRARY_ROWS_EQUAL_NOT_ATTESTED")
        self.assertTrue(r["downloadedFlagAndDownloadRowsExcluded"])

    def test_sources_intentionally_excluded(self):
        self.mutate("UPDATE sources SET name='New source name'")
        r = self.compare()
        self.assertEqual(r["status"], "ED_LIBRARY_ROWS_EQUAL_NOT_ATTESTED")
        self.assertTrue(r["installedSourcesExcludedByPortableSanitizer"])

    def test_schema_with_extra_column_rejected(self):
        self.mutate("ALTER TABLE chapters ADD COLUMN extra_field TEXT")
        with self.assertRaises(EDRejected) as caught:
            self.compare()
        self.assertEqual(caught.exception.code, "ED_STOP_UNSUPPORTED_SCHEMA")

    def test_portable_not_sanitized_rejected(self):
        with sqlite3.connect(self.db) as live:
            raw = live.serialize()
        raw_backup = json.dumps({
            "formatVersion":1,"createdAt":1790000000.0,"preferences":{},
            "databaseBase64":base64.b64encode(raw).decode("ascii")
        }).encode()
        with self.assertRaises(EDRejected) as caught:
            self.compare(raw_backup)
        self.assertEqual(caught.exception.code, "ED_STOP_PORTABLE_INVALID")

    def test_duplicate_json_key_rejected(self):
        bogus = b'{"formatVersion":1,"formatVersion":1}'
        with self.assertRaises(EDRejected) as caught:
            self.compare(bogus)
        self.assertEqual(caught.exception.code, "ED_STOP_PORTABLE_INVALID")

    def test_sqlite_changed_between_ea_and_memory_copy_is_rejected(self):
        from build69_production_release_preflight import (
            _read_external_regular as real_read)
        modified = [False]

        def tamper_before_read(path, limit):
            if Path(path) == self.db and not modified[0]:
                modified[0] = True
                with sqlite3.connect(self.db) as conn:
                    conn.execute("UPDATE manga SET title='tampered-after-audit'")
            return real_read(path, limit)

        with mock.patch(
            "build70_ed_portable_vs_external_library._read_external_regular",
            side_effect=tamper_before_read,
        ):
            with self.assertRaises(EDRejected) as caught:
                self.compare()
        self.assertTrue(modified[0])
        self.assertEqual(caught.exception.code, "ED_STOP_COPY_CHANGED")

    def test_sqlite_reads_are_bound_to_memory_copy(self):
        source = (Path(__file__).resolve().parent /
                  "build70_ed_portable_vs_external_library.py").read_text()
        self.assertIn('db.deserialize(raw)', source)
        self.assertIn('hashlib.sha256(raw).hexdigest()', source)
        self.assertNotIn('sqlite3.connect(uri', source)

    def test_offline_page_missing_rejected(self):
        page = self.app / "Downloads" / "asura" / "fiction1" / "chap1" / "page-00000.bin"
        page.unlink()
        with self.assertRaises(EDRejected) as caught:
            self.compare()
        self.assertEqual(caught.exception.code, "ED_STOP_EXTERNAL_COPY_INVALID")

    def test_nonempty_wal_rejected(self):
        path = self.app / "library.sqlite-wal"
        path.write_bytes(b"uncheckpointed")
        with self.assertRaises(EDRejected) as caught:
            self.compare()
        self.assertEqual(caught.exception.code, "ED_STOP_EXTERNAL_COPY_INVALID")

    def test_cli_failure_does_not_print_private_data(self):
        path = self.root.parent / "broken.mr12backup"
        path.write_bytes(b"bad")
        script = Path(__file__).resolve().parent / "build70_ed_portable_vs_external_library.py"
        result = subprocess.run([
            sys.executable, str(script), "--backup", str(path),
            "--snapshot", str(self.root)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(str(self.root), result.stdout)
        self.assertNotIn("Obra fictícia", result.stdout)
        self.assertNotIn("Capítulo fictício", result.stdout)

    def test_source_static_guards_and_no_restoration(self):
        source = (Path(__file__).resolve().parent /
                  "build70_ed_portable_vs_external_library.py").read_text()
        for needle in ('"installationAuthorized": False',
                       '"restorationAuthorized": False',
                       '"readyToDistributeIPA": False',
                       '"automaticUpdaterEnabled": False'):
            self.assertIn(needle, source)
        for forbidden in ("restoreBackup(", "appinst", ".unlink(", "shutil.rmtree",
                          "requests.get(", "subprocess.run(", ".write_bytes("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
