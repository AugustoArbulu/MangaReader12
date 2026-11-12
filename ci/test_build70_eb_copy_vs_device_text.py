#!/usr/bin/env python3
"""Synthetic EB external-copy versus existing Build70 text protocol tests."""
import sqlite3
from pathlib import Path
import tempfile
import unittest

from build70_eb_copy_vs_device_text import audit_eb, EBRejected
from build70_dj_continuity_report_compare import (
    COUNT_LABELS, DB_HEALTH, FOOTER, HEADER, IOS_VERSION, NOTE,
)
from build70_do_preupgrade_baseline_audit import (
    FIELDS, OFFLINE_FOOTER, OFFLINE_INTRO,
)


def counts(total=1, build=70):
    numbers = (1, 2, 1, 1, 0, total, 1, 0, 0)
    return "\n".join([
        HEADER, f"Build observada: {build} • iOS: {IOS_VERSION}",
        NOTE, DB_HEALTH,
        *(label + ": " + str(n) for label, n in zip(COUNT_LABELS, numbers)),
        *FOOTER,
    ]).encode()


def offline(total=1, offset=0, valid=None, sealed=None, pages=None):
    scanned = min(64, total - offset) if total else 0
    valid = scanned if valid is None else valid
    sealed = valid if sealed is None else sealed
    pages = valid * 2 if pages is None else pages
    fields = (
        total, offset, offset + 64 if offset + 64 < total else 0,
        scanned, valid, sealed, valid - sealed, scanned - valid,
        total - scanned, pages,
    )
    return "\n".join([
        *OFFLINE_INTRO,
        *(label + ": " + str(n) for label, n in zip(FIELDS, fields)),
        *OFFLINE_FOOTER,
    ]).encode()


class EBTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "copy"
        self.app = self.root / "Library" / "Application Support" / "MangaReader12"
        self.app.mkdir(parents=True)
        self.db = self.app / "library.sqlite"
        with sqlite3.connect(self.db) as con:
            con.executescript("""
            PRAGMA user_version=1;
            CREATE TABLE manga(internal_id INTEGER PRIMARY KEY,
                               source_id TEXT, source_manga_id TEXT);
            CREATE TABLE chapters(internal_id INTEGER PRIMARY KEY,
                                  manga_id INTEGER, source_chapter_id TEXT);
            CREATE TABLE downloads(internal_id INTEGER PRIMARY KEY,
                                   chapter_id INTEGER, state TEXT);
            """)

    def add(self, i=1, receipt=True):
        with sqlite3.connect(self.db) as con:
            con.execute("INSERT INTO manga VALUES(?,?,?)", (i, "src", f"m{i}"))
            con.execute("INSERT INTO chapters VALUES(?,?,?)", (i, i, "chapter"))
            con.execute("INSERT INTO downloads VALUES(?,?,'completed')", (i, i))
        folder = self.app / "Downloads" / "src" / f"m{i}" / "chapter"
        folder.mkdir(parents=True)
        for j in range(2):
            (folder / f"page-{j:05d}.bin").write_bytes(bytes([255, 216, i % 256, j, 255, 217]))
        if receipt:
            (folder / ".webreader-completion-v1").write_bytes(b"WR-OFFLINE-COMPLETE-V1:2\n")
        return folder

    def audit(self, total=1, batches=None, count_text=None):
        return audit_eb(
            self.root, counts(total) if count_text is None else count_text,
            [offline(total)] if batches is None else batches,
        )

    def assert_denied(self, r):
        for key in ("installationAuthorized", "restorationAuthorized",
                    "automaticUpdaterEnabled", "readyToInstallIPA",
                    "readyToDistributeIPA", "originalOfflineImageBytesCompared",
                    "reportsAuthenticatedAsPhysicalDeviceData",
                    "copyProvenToComeFromSameDevice",
                    "fullDataContainerExternallyBackedUp"):
            self.assertIs(r[key], False)

    def test_positive_counts_only_never_authenticates(self):
        self.add()
        r = self.audit()
        self.assertEqual(r["status"], "EB_COPIED_BYTES_AND_DEVICE_TEXT_TOTALS_AGREE_NOT_ATTESTED")
        self.assertEqual(r["copiedPageFilesReadAndHashed"], 2)
        self.assert_denied(r)

    def test_modified_bytes_with_equal_counts_are_not_detected(self):
        folder = self.add()
        first = self.audit()
        page = folder / "page-00000.bin"
        data = page.read_bytes()
        page.write_bytes(b"?" + data[1:])
        second = self.audit()
        self.assertEqual(first["status"], second["status"])
        self.assert_denied(second)

    def test_reported_total_mismatch_stops(self):
        self.add()
        r = self.audit(total=2, batches=[offline(2)])
        self.assertEqual(r["status"], "EB_STOP_COMPLETED_CHAPTER_COUNTS_DIFFER")

    def test_reported_page_or_receipt_count_mismatch_stops(self):
        self.add()
        self.assertEqual(
            self.audit(batches=[offline(1, pages=1)])["status"],
            "EB_STOP_PAGE_OR_RECEIPT_COUNTS_DIFFER",
        )
        self.assertEqual(
            self.audit(batches=[offline(1, sealed=0)])["status"],
            "EB_STOP_PAGE_OR_RECEIPT_COUNTS_DIFFER",
        )

    def test_reported_bad_pages_have_priority(self):
        self.add()
        r = self.audit(batches=[offline(1, valid=0, sealed=0, pages=0)])
        self.assertEqual(r["status"], "EB_STOP_DEVICE_TEXT_REPORTS_MISSING_OR_UNSAFE_PAGES")

    def test_legacy_agreement_needs_physical_read(self):
        self.add(receipt=False)
        r = self.audit(batches=[offline(1, sealed=0)])
        self.assertEqual(r["status"], "EB_LEGACY_OR_UNICODE_REQUIRES_PHYSICAL_READING")
        self.assert_denied(r)

    def test_zero_downloads_not_device_proof(self):
        r = self.audit(total=0)
        self.assertEqual(r["status"], "EB_ZERO_DOWNLOADS_REPORTED_NOT_DEVICE_PROOF")
        self.assert_denied(r)

    def test_multibatch_incomplete_and_complete(self):
        for i in range(1, 66):
            self.add(i)
        partial = self.audit(total=65, batches=[offline(65, pages=128)])
        self.assertEqual(partial["status"], "EB_PARTIAL_DEVICE_TEXT_BATCHES_NOT_COMPARABLE")
        full = self.audit(total=65, batches=[
            offline(65, pages=128), offline(65, offset=64, pages=2)
        ])
        self.assertEqual(full["status"], "EB_COPIED_BYTES_AND_DEVICE_TEXT_TOTALS_AGREE_NOT_ATTESTED")

    def test_invalid_build70_text_rejected(self):
        self.add()
        with self.assertRaises(EBRejected) as cm:
            self.audit(count_text=counts(1, build=71))
        self.assertEqual(str(cm.exception), "EB_STOP_NONCANONICAL_BUILD70_REPORT_TEXT")

    def test_sidecars_rejected_not_modified(self):
        self.add()
        for suffix in ("-wal", "-journal"):
            sidecar = self.app / ("library.sqlite" + suffix)
            sidecar.write_bytes(b"not checkpointed")
            with self.assertRaises(EBRejected) as cm:
                self.audit()
            self.assertEqual(str(cm.exception), "EB_STOP_EXTERNAL_COPY_UNSAFE_OR_INCOMPLETE")
            self.assertEqual(sidecar.read_bytes(), b"not checkpointed")
            sidecar.unlink()


if __name__ == "__main__":
    unittest.main()
