#!/usr/bin/env python3
"""FA — exhaustive synthetic v1-shape preservation on a shadow-only DB."""
from pathlib import Path
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from build70_fa_full_schema_shadow import (
    TABLES, EXPECTED_INDEXES, seed_full_v1, validate_full_schema,
    validate_shadow_pair, capture_legacy,
)
from build70_ey_shadow_schema_migration import EYUnsafe, EYInjectedFault, make_shadow, migrate_shadow, validate_v2

class FullSchemaShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='webreader_fa_schema_')
        self.root=Path(self.tmp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        self.original=seed_full_v1(self.root)
        self.shadow=self.original.with_name('shadow_library_v2.sqlite')
        self.original_digest=hashlib.sha256(self.original.read_bytes()).hexdigest()

    def tearDown(self):self.tmp.cleanup()

    def assert_original_intact(self):
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(),self.original_digest)
        with closing(sqlite3.connect(f'{self.original.as_uri()}?mode=ro',uri=True)) as db:
            validate_full_schema(db,version=1)

    def test_all_eleven_tables_and_three_declared_indexes(self):
        with closing(sqlite3.connect(self.original)) as db:
            validate_full_schema(db,version=1)
            self.assertEqual(len(TABLES),11)
            self.assertEqual(len(EXPECTED_INDEXES),3)
            self.assertEqual({r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")},set(TABLES))

    def test_fixture_is_connected_and_preserves_flags(self):
        with closing(sqlite3.connect(self.original)) as db:
            self.assertEqual(db.execute('SELECT downloaded,is_read,last_page_read,bookmarked FROM chapters WHERE internal_id=1').fetchone(),(1,1,6,1))
            self.assertEqual(db.execute('SELECT manga_id FROM library').fetchone(),(1,))
            self.assertEqual(db.execute('SELECT count(*) FROM migration_map').fetchone(),(1,))
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_migrate_full_fixture_all_table_rows_and_sql_identical(self):
        self.assertEqual(validate_shadow_pair(self.root),self.shadow)
        self.assert_original_intact()
        with closing(sqlite3.connect(self.original)) as a, closing(sqlite3.connect(self.shadow)) as b:
            self.assertEqual(capture_legacy(a),capture_legacy(b))
            self.assertEqual(b.execute('PRAGMA user_version').fetchone(),(2,))

    def test_no_writes_to_orig_original_during_shadow_copy(self):
        validate_shadow_pair(self.root)
        self.assert_original_intact()
        with closing(sqlite3.connect(self.original)) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='offline_deletion_journal'").fetchone())

    def test_repeated_migration_is_idempotent(self):
        validate_shadow_pair(self.root)
        self.assertEqual(migrate_shadow(self.root),'already_v2')
        self.assert_original_intact()

    def test_wal_checkpoint_source_consistent_snapshot(self):
        c=sqlite3.connect(self.original)
        try:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('INSERT INTO categories(name,sort_order) VALUES(?,?)',('WAL second category',2))
            c.commit()
            # WAL may checkpoint at close: byte-level digest is not stable.
            # Keep source WAL connection open while SQLite backup takes consistent view.
            validate_shadow_pair(self.root)
            with closing(sqlite3.connect(self.shadow)) as s:
                self.assertEqual(s.execute("SELECT count(*) FROM categories WHERE name='WAL second category'").fetchone(),(1,))
        finally:c.close()
        with closing(sqlite3.connect(f'{self.original.as_uri()}?mode=ro',uri=True)) as db:
            validate_full_schema(db,version=1)
            self.assertEqual(db.execute("SELECT count(*) FROM categories WHERE name='WAL second category'").fetchone(),(1,))

    def test_after_table_failure_rolls_back_schema_and_version(self):
        make_shadow(self.root)
        with self.assertRaises(EYInjectedFault):migrate_shadow(self.root,'after_table')
        with closing(sqlite3.connect(self.shadow)) as db:
            validate_full_schema(db,version=1)
        self.assertEqual(migrate_shadow(self.root),'migrated')
        self.assert_original_intact()

    def test_after_version_failure_does_not_publish_v2(self):
        make_shadow(self.root)
        with self.assertRaises(EYInjectedFault):migrate_shadow(self.root,'after_version')
        with closing(sqlite3.connect(self.shadow)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone(),(1,))
            self.assertIsNone(db.execute("SELECT sql FROM sqlite_master WHERE name='offline_deletion_journal'").fetchone())
        self.assert_original_intact()

    def test_real_termination_before_commit_rolls_back_on_reopen(self):
        make_shadow(self.root)
        script=Path(__file__).with_name('build70_ey_shadow_schema_migration.py')
        result=subprocess.run([sys.executable,str(script),str(self.root),'--migrate-shadow','--fault','process_exit'],capture_output=True,timeout=8)
        self.assertEqual(result.returncode,86)
        with closing(sqlite3.connect(self.shadow)) as db:validate_full_schema(db,version=1)
        self.assert_original_intact()

    def test_old_app_version_one_cannot_open_v2(self):
        validate_shadow_pair(self.root)
        with closing(sqlite3.connect(self.shadow)) as db:
            self.assertGreater(db.execute('PRAGMA user_version').fetchone()[0],1)
        self.assert_original_intact()

    def test_reject_table_removed_from_v1_fixture(self):
        with closing(sqlite3.connect(self.original)) as db, db:db.execute('DROP TABLE repositories')
        with self.assertRaises(EYUnsafe):validate_shadow_pair(self.root)
        self.assertFalse(self.shadow.exists())

    def test_refuse_misleading_modified_columns(self):
        with closing(sqlite3.connect(self.original)) as db, db:
            db.execute('ALTER TABLE categories ADD COLUMN unknown_field TEXT')
        with self.assertRaises(EYUnsafe):validate_shadow_pair(self.root)
        self.assertFalse(self.shadow.exists())

    def test_refuse_foreign_key_violation(self):
        with closing(sqlite3.connect(self.original)) as db, db:
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute("INSERT INTO downloads(chapter_id,state,progress,local_path,updated_at) VALUES(999,'completed',0,NULL,1)")
        with self.assertRaises(EYUnsafe):validate_shadow_pair(self.root)

    def test_shadow_unsupported_newer_version_never_downgraded(self):
        make_shadow(self.root)
        with closing(sqlite3.connect(self.shadow)) as db, db:db.execute('PRAGMA user_version=900')
        before=self.shadow.read_bytes()
        with self.assertRaises(EYUnsafe):migrate_shadow(self.root)
        self.assertEqual(before,self.shadow.read_bytes())
        self.assert_original_intact()

    def test_snapshot_cannot_override_existing_shadow(self):
        self.shadow.write_bytes(b'foreign-data')
        with self.assertRaises(EYUnsafe):validate_shadow_pair(self.root)
        self.assertEqual(self.shadow.read_bytes(),b'foreign-data')

    def test_bad_marker_blocks_before_shadow(self):
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'INVALID')
        with self.assertRaises(EYUnsafe):validate_shadow_pair(self.root)
        self.assertFalse(self.shadow.exists())

    def test_sqlite_check_index_prevents_multiple_open_deletions(self):
        validate_shadow_pair(self.root)
        with closing(sqlite3.connect(self.shadow)) as db, db:
            db.execute('PRAGMA foreign_keys=ON')
            values=lambda op,state:(op,'ev_'+op,state)
            template='''INSERT INTO offline_deletion_journal
              (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,
              quarantine_name,source_device,source_inode,state,owner_confirmation,created_at,updated_at)
              VALUES (?,1,'s','m','c',?,'1','2',?,'explicit_confirmation_required',0,0)'''
            db.execute(template,values('a'*32,'prepared'))
            with self.assertRaises(sqlite3.IntegrityError):db.execute(template,values('b'*32,'needs_review'))
            db.execute("UPDATE offline_deletion_journal SET state='aborted' WHERE operation_id=?",('a'*32,))
            db.execute(template,values('b'*32,'prepared'))

    def test_shadow_does_not_modify_pinned_synthetic_download(self):
        validate_shadow_pair(self.root)
        with closing(sqlite3.connect(self.shadow)) as db:
            self.assertEqual(db.execute('SELECT state,local_path FROM downloads').fetchone(),('completed','/obsolete-fake-container'))
            self.assertEqual(db.execute('SELECT downloaded FROM chapters WHERE internal_id=1').fetchone(),(1,))
        self.assert_original_intact()

if __name__=='__main__':unittest.main()
