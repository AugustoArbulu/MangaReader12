#!/usr/bin/env python3
"""EY shadow migration: small, standalone, disposable SQLite fixtures only."""
from pathlib import Path
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from build70_ey_shadow_schema_migration import (
    EYUnsafe, EYInjectedFault, make_shadow, migrate_shadow, validate_v2
)

SCHEMA = '''
CREATE TABLE manga(
 internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_id TEXT NOT NULL,
 source_manga_id TEXT NOT NULL,
 title TEXT NOT NULL,
 UNIQUE(source_id,source_manga_id)
);
CREATE TABLE chapters(
 internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
 manga_id INTEGER NOT NULL,
 source_chapter_id TEXT NOT NULL,
 downloaded INTEGER NOT NULL DEFAULT 0,
 FOREIGN KEY(manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE
);
CREATE TABLE downloads(
 internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
 chapter_id INTEGER NOT NULL UNIQUE,
 state TEXT NOT NULL,
 local_path TEXT,
 FOREIGN KEY(chapter_id) REFERENCES chapters(internal_id) ON DELETE CASCADE
);
CREATE TABLE history(note TEXT);
INSERT INTO manga(internal_id,source_id,source_manga_id,title) VALUES(1,'s','m','sample');
INSERT INTO chapters(internal_id,manga_id,source_chapter_id,downloaded) VALUES(1,1,'c',1);
INSERT INTO downloads(chapter_id,state,local_path) VALUES(1,'completed','legacy-container-path');
INSERT INTO history(note) VALUES('must remain unchanged');
PRAGMA user_version=1;
'''


class ShadowMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='webreader-ey-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / '.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        self.app = self.root / 'synthetic_app'
        self.app.mkdir()
        self.legacy = self.app / 'legacy_library_v1.sqlite'
        self.shadow = self.app / 'shadow_library_v2.sqlite'
        with sqlite3.connect(self.legacy) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript(SCHEMA)
        self.initial_bytes = self.legacy.read_bytes()

    def contents(self, p):
        with sqlite3.connect(p) as db:
            return (
                db.execute('SELECT source_id,source_manga_id,title FROM manga').fetchall(),
                db.execute('SELECT source_chapter_id,downloaded FROM chapters').fetchall(),
                db.execute('SELECT state,local_path FROM downloads').fetchall(),
                db.execute('SELECT note FROM history').fetchall(),
            )

    def ensure_legacy_unchanged(self):
        self.assertEqual(self.legacy.read_bytes(),self.initial_bytes)
        with sqlite3.connect(self.legacy) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone(),(1,))
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='offline_deletion_journal'").fetchone())

    def test_shadow_migration_preserves_data_and_original_bytes(self):
        expected = self.contents(self.legacy)
        self.assertEqual(make_shadow(self.root),self.shadow)
        self.assertEqual(migrate_shadow(self.root),'migrated')
        with sqlite3.connect(self.shadow) as db:
            validate_v2(db)
            self.assertEqual(db.execute('SELECT count(*) FROM offline_deletion_journal').fetchone(),(0,))
        self.assertEqual(self.contents(self.shadow),expected)
        self.ensure_legacy_unchanged()

    def test_idempotent_second_migration_does_not_write_journal(self):
        make_shadow(self.root)
        migrate_shadow(self.root)
        self.assertEqual(migrate_shadow(self.root),'already_v2')
        with sqlite3.connect(self.shadow) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM offline_deletion_journal').fetchone(),(0,))

    def test_nonexistent_marker_blocks_even_read(self):
        (self.root / '.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(EYUnsafe): make_shadow(self.root)
        self.assertFalse(self.shadow.exists())

    def test_wrong_marker_blocks(self):
        (self.root / '.webreader_ev_disposable_marker').write_bytes(b'not-synthetic')
        with self.assertRaises(EYUnsafe): make_shadow(self.root)

    def test_symlinked_legacy_refused(self):
        target = self.app / 'real_legacy.sqlite'
        self.legacy.rename(target)
        self.legacy.symlink_to(target)
        with self.assertRaises(EYUnsafe): make_shadow(self.root)

    def test_preexisting_shadow_never_overwritten(self):
        self.shadow.write_bytes(b'foreign-database-do-not-clobber')
        with self.assertRaises(EYUnsafe): make_shadow(self.root)
        self.assertEqual(self.shadow.read_bytes(),b'foreign-database-do-not-clobber')

    def test_symlink_shadow_never_followed(self):
        target = self.app / 'protected.txt'
        target.write_bytes(b'KEEP')
        self.shadow.symlink_to(target)
        with self.assertRaises(EYUnsafe): make_shadow(self.root)
        self.assertEqual(target.read_bytes(),b'KEEP')

    def test_future_version_refused_before_backup(self):
        with sqlite3.connect(self.legacy) as db: db.execute('PRAGMA user_version=8')
        with self.assertRaises(EYUnsafe): make_shadow(self.root)
        self.assertFalse(self.shadow.exists())

    def test_missing_fk_refuses_unrecognized_legacy_schema(self):
        with sqlite3.connect(self.legacy) as db:
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute('ALTER TABLE downloads RENAME TO moved_downloads')
            db.execute('CREATE TABLE downloads(internal_id INTEGER PRIMARY KEY,chapter_id INTEGER,state TEXT,local_path TEXT)')
        with self.assertRaises(EYUnsafe): make_shadow(self.root)
        self.assertFalse(self.shadow.exists())

    def test_existing_fk_errors_refuse_to_copy(self):
        with sqlite3.connect(self.legacy) as db:
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute('INSERT INTO downloads(chapter_id,state) VALUES(999,\'completed\')')
        with self.assertRaises(EYUnsafe): make_shadow(self.root)

    def test_each_injected_failure_rolls_back_schema_and_version(self):
        for fault in ['before_create','after_table','after_unique_index','after_version']:
            with self.subTest(fault=fault):
                if self.shadow.exists(): self.shadow.unlink()
                make_shadow(self.root)
                with self.assertRaises(EYInjectedFault): migrate_shadow(self.root,fault=fault)
                with sqlite3.connect(self.shadow) as db:
                    self.assertEqual(db.execute('PRAGMA user_version').fetchone(),(1,))
                    self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='offline_deletion_journal'").fetchone())
                self.ensure_legacy_unchanged()
                self.assertEqual(migrate_shadow(self.root),'migrated')
                with sqlite3.connect(self.shadow) as db: validate_v2(db)

    def test_real_process_exit_inside_transaction_recovers_cleanly(self):
        make_shadow(self.root)
        command = [sys.executable,str(Path(__file__).with_name('build70_ey_shadow_schema_migration.py')),
                   str(self.root),'--migrate-shadow','--fault','process_exit']
        killed = subprocess.run(command, capture_output=True, text=True, timeout=6)
        self.assertEqual(killed.returncode,86,killed.stderr)
        with sqlite3.connect(self.shadow) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone(),(1,))
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='offline_deletion_journal'").fetchone())
        self.assertEqual(migrate_shadow(self.root),'migrated')
        self.ensure_legacy_unchanged()

    def test_new_index_blocks_two_unresolved_ops_per_chapter(self):
        make_shadow(self.root)
        migrate_shadow(self.root)
        with sqlite3.connect(self.shadow) as db:
            db.execute('PRAGMA foreign_keys=ON')
            for key,state in [('a'*32,'prepared'),('b'*32,'aborted')]:
                db.execute('''INSERT INTO offline_deletion_journal
                  (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,
                   quarantine_name,source_device,source_inode,state,owner_confirmation,created_at,updated_at)
                  VALUES(?,1,'s','m','c',?,'7','8',?,'explicit_confirmation_required',0,0)''',
                   (key,'ev_'+key,state))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO offline_deletion_journal
                  (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,
                   quarantine_name,source_device,source_inode,state,owner_confirmation,created_at,updated_at)
                  VALUES(?,1,'s','m','c',?,'7','8','needs_review','explicit_confirmation_required',0,0)''',
                   ('c'*32,'ev_'+'c'*32))

    def test_foreign_key_prevents_journal_for_unknown_chapter(self):
        make_shadow(self.root)
        migrate_shadow(self.root)
        with sqlite3.connect(self.shadow) as db:
            db.execute('PRAGMA foreign_keys=ON')
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO offline_deletion_journal
                  (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,
                   quarantine_name,source_device,source_inode,state,owner_confirmation,created_at,updated_at)
                  VALUES(?,999,'s','m','c',?,'7','8','prepared','explicit_confirmation_required',0,0)''',
                   ('d'*32,'ev_'+'d'*32))

    def test_quarantine_name_rejects_path_injection(self):
        make_shadow(self.root)
        migrate_shadow(self.root)
        with sqlite3.connect(self.shadow) as db:
            db.execute('PRAGMA foreign_keys=ON')
            for bad in ('ev_'+'a'*30+'/', 'ev_'+'a'*30+'g', 'ev_'+'a'*29+'..'):
                with self.subTest(bad=bad), self.assertRaises(sqlite3.IntegrityError):
                    db.execute('''INSERT INTO offline_deletion_journal
                       (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,
                        quarantine_name,source_device,source_inode,state,owner_confirmation,created_at,updated_at)
                       VALUES(?,1,'s','m','c',?,'7','8','prepared','explicit_confirmation_required',0,0)''',
                       ('e'*32,bad))

    def test_existing_shadow_version_3_is_refused_without_change(self):
        make_shadow(self.root)
        with sqlite3.connect(self.shadow) as db: db.execute('PRAGMA user_version=3')
        before = self.shadow.read_bytes()
        with self.assertRaises(EYUnsafe): migrate_shadow(self.root)
        self.assertEqual(self.shadow.read_bytes(),before)

    def test_shadow_wal_fixture_source_is_read_consistently(self):
        with sqlite3.connect(self.legacy) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute("INSERT INTO history(note) VALUES('committed in WAL')")
        make_shadow(self.root)
        with sqlite3.connect(self.shadow) as db:
            self.assertIn(('committed in WAL',),db.execute('SELECT note FROM history').fetchall())

    def test_second_copy_refused_without_writing_first_shadow(self):
        make_shadow(self.root)
        before = self.shadow.read_bytes()
        with self.assertRaises(EYUnsafe): make_shadow(self.root)
        self.assertEqual(self.shadow.read_bytes(),before)


if __name__ == '__main__': unittest.main()
