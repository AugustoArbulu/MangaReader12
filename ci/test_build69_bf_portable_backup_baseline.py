#!/usr/bin/env python3
"""Build69 BF: synthetic real schema-v1 .mr12backup portability tests.

No actual user backup or device is opened; all databases are in memory.
"""
import base64
import json
from pathlib import Path
import re
import sqlite3
import unittest

from build69_be_compare_upgrade_counts import (
    HEADER, PRIVACY, DATABASE, METRICS, FOOTER
)
from build69_bf_portable_backup_baseline import (
    PortableBaselineRejected,
    read_build68_portable_baseline,
    compare_portable_baseline_to_build69
)

ROOT = Path(__file__).resolve().parent.parent
DB_SOURCE = (ROOT / "MangaReader12/Database/SQLiteDatabase.swift").read_text("utf8")
SCHEMA = re.search(r'private static let schemaV1 = """(.*?)"""', DB_SOURCE, re.S).group(1)


def fake_backup(*, schema=1, extra=False, unsanitized=False):
    db = sqlite3.connect(":memory:")
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        db.execute(f"PRAGMA user_version={schema}")
        db.execute(
            "INSERT INTO manga(source_id,source_manga_id,title,date_added)"
            " VALUES(?,?,?,?)",
            ("private-source-secret", "secret-manga-id", "SECRET MANGA TITLE", 1730000000)
        )
        db.execute("INSERT INTO library(manga_id,date_added) VALUES(1,1730000000)")
        db.execute(
            "INSERT INTO chapters(manga_id,source_chapter_id,name,is_read,last_page_read,"
            "bookmarked,downloaded) VALUES(?,?,?,?,?,?,?)",
            (1, "secret-chapter-id", "SECRET CHAPTER NAME", 1, 42, 1, 0)
        )
        db.execute(
            "INSERT INTO history(manga_id,chapter_id,last_read_at) VALUES(1,1,1730000100)"
        )
        db.execute("INSERT INTO categories(name) VALUES('SECRET CATEGORY')")
        db.execute("INSERT INTO manga_categories(manga_id,category_id) VALUES(1,1)")
        # Simulate BackupManager.sanitizePortableSnapshot: no downloaded page metadata.
        db.execute("DELETE FROM downloads")
        db.execute("UPDATE chapters SET downloaded = 0")
        db.execute("DELETE FROM sources")
        if unsanitized:
            db.execute(
                "INSERT INTO downloads(chapter_id,state,progress,updated_at)"
                " VALUES(1,'completed',1.0,1730000120)"
            )
            db.execute("UPDATE chapters SET downloaded=1")
        db.commit()
        raw = db.serialize()
    finally:
        db.close()
    data = {
        "formatVersion": 1,
        "createdAt": 1730000000,
        "databaseBase64": base64.b64encode(raw).decode("ascii"),
        "preferences": {"reader.mode": {"kind": "string", "stringValue": "SECRET READER PREF"}}
    }
    if extra:
        data["unauthorized"] = True
    return json.dumps(data).encode("utf-8")


def after_fixture(*, missing_category=False):
    counts = {
        "Obras na biblioteca": 1,
        "Capítulos registrados": 1,
        "Capítulos lidos": 1,
        "Capítulos com página registrada": 1,
        "Capítulos favoritos": 1,
        "Downloads marcados completos no banco": 99,
        "Registros de histórico": 1,
        "Categorias": 0 if missing_category else 1,
        "Vínculos obra/categoria": 1,
    }
    return "\n".join([
        HEADER, "Build observada: 69 • iOS: 12.5.8", PRIVACY, DATABASE,
        *(name + ": " + str(counts[name]) for name in METRICS),
        *FOOTER
    ]).encode("utf8")


class PortableBaseline(unittest.TestCase):
    def test_original_build68_backup_can_supply_a_partial_baseline(self):
        r = read_build68_portable_baseline(fake_backup())
        self.assertEqual(r["status"], "PORTABLE_LIBRARY_COUNTS_NOT_OFFLINE_CHAPTER_BASELINE")
        self.assertEqual(r["metrics"]["Obras na biblioteca"], 1)
        self.assertEqual(r["metrics"]["Capítulos lidos"], 1)
        self.assertEqual(r["metrics"]["Categorias"], 1)
        self.assertEqual(r["metrics"]["Registros de histórico"], 1)
        self.assertIsNone(r["metrics"]["Downloads marcados completos no banco"])
        self.assertTrue(r["missingDownloadCount"])
        self.assertTrue(r["portableDownloadsResetConfirmed"])
        for field in (
            "buildAtExportAuthenticatedByTool", "offlineChapterImagesIncluded",
            "offlinePagesPreservedByBackup", "sensitiveValuesPrinted",
            "userLibraryModified", "restorationPerformed", "readyToInstall",
            "physicalUpgradeVerified"
        ):
            self.assertFalse(r[field], field)
        rendered = json.dumps(r)
        for secret in (
            "SECRET MANGA TITLE", "SECRET CATEGORY",
            "SECRET READER PREF", "secret-source", "secret-chapter-id"
        ):
            self.assertNotIn(secret, rendered)

    def test_compare_after_new_build_never_claims_download_integrity(self):
        r = compare_portable_baseline_to_build69(fake_backup(), after_fixture())
        self.assertEqual(r["status"], "LIBRARY_COUNTS_MATCH_OFFLINE_NOT_VERIFIED")
        self.assertFalse(r["downloadRecordCountComparable"])
        self.assertFalse(r["offlineDownloadedPagesVerified"])
        self.assertFalse(r["installationAuthorized"])
        offline = next(x for x in r["counts"] if "Downloads marcados" in x["metric"])
        self.assertIsNone(offline["before"])
        self.assertIsNone(offline["delta"])
        self.assertEqual(offline["after"], 99)
        self.assertEqual(offline["reason"], "NOT_INCLUDED_IN_PORTABLE_BACKUP")

    def test_decreased_category_count_requires_manual_review(self):
        r = compare_portable_baseline_to_build69(
            fake_backup(), after_fixture(missing_category=True)
        )
        self.assertEqual(r["status"], "POTENTIAL_LIBRARY_LOSS_STOP_REVIEW")
        self.assertEqual(r["decreasedLibraryMetricCount"], 1)
        self.assertFalse(r["physicalUpdateVerified"])

    def test_bad_source_backup_and_future_schema_fail_closed(self):
        valid = fake_backup()
        env = json.loads(valid)
        cases = [
            b"", b"{}", b"[]", b'{"formatVersion": 1, "formatVersion": 1}',
            fake_backup(extra=True), fake_backup(schema=2),
            fake_backup(unsanitized=True),
            valid.replace(b"SECRET READER PREF", b"SECRET READER PREF"),  # valid control
        ]
        for data in cases[:-1]:
            with self.subTest(data=data[:30]):
                with self.assertRaises(PortableBaselineRejected):
                    read_build68_portable_baseline(data)
        for altered in (
            {**env, "formatVersion": 2},
            {**env, "createdAt": float("nan")},
            {**env, "databaseBase64": "!!!"},
            {**env, "databaseBase64": base64.b64encode(b"not sqlite").decode()},
            {**env, "preferences": []},
            {**env, "createdAt": None, "databaseBase64": ""},
        ):
            with self.subTest(fields=list(altered)):
                with self.assertRaises(PortableBaselineRejected):
                    read_build68_portable_baseline(json.dumps(altered).encode())

    def test_future_build_report_must_be_well_formed(self):
        with self.assertRaises(PortableBaselineRejected):
            compare_portable_baseline_to_build69(
                fake_backup(), after_fixture().replace(b"Build observada: 69",
                                                      b"Build observada: 68")
            )


if __name__ == "__main__":
    unittest.main()
