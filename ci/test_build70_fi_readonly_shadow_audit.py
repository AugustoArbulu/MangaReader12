#!/usr/bin/env python3
"""FI synthetic-only validation against the full legacy v1 shadow/v2 journal."""
from __future__ import annotations
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build70_fi_readonly_shadow_audit import (
    FIUnsafe, inspect_synthetic_shadow, FISummary
)
LAB_CI = Path(__file__).resolve().parent / 'labs' / 'webreader-ev-fd' / 'ci'
sys.path.insert(0, str(LAB_CI))
from build70_fa_full_schema_shadow import seed_full_v1
from build70_ey_shadow_schema_migration import make_shadow, migrate_shadow
from build70_fb_full_shadow_copy_bridge import COPY_DDL


class FISyntheticAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        seed_full_v1(self.root)
        self.shadow = make_shadow(self.root)
        migrate_shadow(self.root)
        with self.open_write() as db:
            db.executescript(COPY_DDL)
        self.op = 'a'*32
        self.snapshot = 'ev_'+'a'*32

    def open_write(self):
        db = sqlite3.connect(self.shadow)
        db.execute('PRAGMA foreign_keys=ON')
        return closing(db)

    def insert(self, state='copy_verified', *, chapter=1, source='s', manga='m', leaf='c'):
        with self.open_write() as db:
            db.execute('''INSERT INTO offline_copy_journal(
                operation_id, chapter_id, source_id, source_manga_id,
                source_chapter_id, snapshot_name, source_device, source_inode,
                state, consent) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (self.op, chapter, source, manga, leaf, self.snapshot,
                 '1', '2', state, 'synthetic_confirmation'))
            db.commit()

    def test_valid_record_is_metadata_only_never_deletion(self):
        self.insert()
        x = inspect_synthetic_shadow(self.root)
        self.assertEqual((x.entries, x.copy_verified_metadata_only, x.requires_review),(1,1,0))
        self.assertFalse(x.can_delete or x.can_restore or x.can_purge)
        self.assertEqual(x.state_counts,(('copy_verified',1),))

    def test_prepared_requires_review(self):
        self.insert('prepared')
        self.assertEqual(inspect_synthetic_shadow(self.root).requires_review,1)

    def test_needs_review_remains_untrusted(self):
        self.insert('needs_review')
        self.assertEqual(inspect_synthetic_shadow(self.root).copy_verified_metadata_only,0)

    def test_owner_drift_requires_review(self):
        self.insert(source='different')
        self.assertEqual(inspect_synthetic_shadow(self.root).requires_review,1)

    def test_download_state_drift_requires_review(self):
        self.insert()
        with self.open_write() as db:
            db.execute("UPDATE downloads SET state='paused' WHERE chapter_id=1")
            db.commit()
        self.assertEqual(inspect_synthetic_shadow(self.root).requires_review,1)

    def test_download_flag_drift_requires_review(self):
        self.insert()
        with self.open_write() as db:
            db.execute('UPDATE chapters SET downloaded=0 WHERE internal_id=1')
            db.commit()
        self.assertEqual(inspect_synthetic_shadow(self.root).requires_review,1)

    def test_missing_copy_table_is_review_not_zero_success(self):
        with self.open_write() as db:
            db.execute('DROP TABLE offline_copy_journal')
            db.commit()
        x=inspect_synthetic_shadow(self.root)
        self.assertTrue(x.missing_journal)
        self.assertEqual(x.requires_review,1)

    def test_missing_marker_refused(self):
        (self.root/'.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(FIUnsafe):inspect_synthetic_shadow(self.root)

    def test_symlinked_shadow_refused(self):
        copy=self.root/'outside-shadow.sqlite'
        self.shadow.rename(copy)
        self.shadow.symlink_to(copy)
        with self.assertRaises(FIUnsafe):inspect_synthetic_shadow(self.root)

    def test_hardlinked_shadow_refused(self):
        os.link(self.shadow, self.root/'duplicate.sqlite')
        with self.assertRaises(FIUnsafe):inspect_synthetic_shadow(self.root)

    def test_future_schema_refused(self):
        with self.open_write() as db:
            db.execute('PRAGMA user_version=3')
            db.commit()
        with self.assertRaises(FIUnsafe):inspect_synthetic_shadow(self.root)

    def test_readonly_connection_denies_writes(self):
        self.insert()
        db = sqlite3.connect(self.shadow.as_uri()+'?mode=ro',uri=True)
        try:
            db.execute('PRAGMA query_only=ON')
            with self.assertRaises(sqlite3.OperationalError):
                db.execute('DELETE FROM downloads')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM downloads').fetchone(),(1,))
        finally:db.close()

    def test_wal_uncommitted_writer_invisible_and_commit_visible(self):
        self.insert('prepared')
        with self.open_write() as db:
            self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone(),('wal',))
            db.commit()
        writer = sqlite3.connect(self.shadow, isolation_level=None)
        try:
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE offline_copy_journal SET state='copy_verified' WHERE chapter_id=1")
            # A separate read-only snapshot sees only the last committed state.
            before=inspect_synthetic_shadow(self.root)
            self.assertEqual(before.state_counts,(('prepared',1),))
            writer.execute('COMMIT')
            after=inspect_synthetic_shadow(self.root)
            self.assertEqual(after.copy_verified_metadata_only,1)
        finally:
            if writer.in_transaction:writer.rollback()
            writer.close()

    def test_wal_reader_holds_consistent_snapshot_over_writer_commit(self):
        self.insert('prepared')
        with self.open_write() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.commit()
        reader=sqlite3.connect(self.shadow.as_uri()+'?mode=ro',uri=True,isolation_level=None)
        writer=sqlite3.connect(self.shadow,isolation_level=None)
        try:
            reader.execute('PRAGMA query_only=ON')
            reader.execute('BEGIN')
            self.assertEqual(reader.execute('SELECT state FROM offline_copy_journal').fetchone(),('prepared',))
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE offline_copy_journal SET state='copy_verified' WHERE chapter_id=1")
            writer.execute('COMMIT')
            self.assertEqual(reader.execute('SELECT state FROM offline_copy_journal').fetchone(),('prepared',))
            reader.execute('COMMIT')
            self.assertEqual(reader.execute('SELECT state FROM offline_copy_journal').fetchone(),('copy_verified',))
        finally:
            if writer.in_transaction:writer.rollback()
            if reader.in_transaction:reader.rollback()
            reader.close();writer.close()

    def test_missing_file_does_not_get_created(self):
        self.shadow.unlink()
        with self.assertRaises(FIUnsafe):inspect_synthetic_shadow(self.root)
        self.assertFalse(self.shadow.exists())

    def test_broken_journal_columns_refused(self):
        with self.open_write() as db:
            db.execute('ALTER TABLE offline_copy_journal ADD COLUMN malicious TEXT')
            db.commit()
        with self.assertRaises(FIUnsafe):inspect_synthetic_shadow(self.root)

    def test_snapshot_data_not_reopened_or_validated_as_files(self):
        self.insert()
        # No Quarantine folder or snapshot files exists: cannot authorize any destructive action.
        self.assertFalse((self.root/'synthetic_app/Quarantine').exists())
        self.assertEqual(inspect_synthetic_shadow(self.root).copy_verified_metadata_only,1)
        self.assertFalse(inspect_synthetic_shadow(self.root).can_delete)

if __name__=='__main__':unittest.main()
