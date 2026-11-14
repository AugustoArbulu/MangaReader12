#!/usr/bin/env python3
"""FL: shadow-only SQLite monotonic event regression. No physical deletion."""
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing

HERE=Path(__file__).resolve().parent
LAB=HERE/'labs'/'webreader-ev-fd'/'ci'
sys.path[:0]=[str(HERE),str(LAB)]
from build70_fa_full_schema_shadow import seed_full_v1, validate_shadow_pair
from build70_fb_full_shadow_copy_bridge import FBShadowCopyBridge
from build70_fl_monotonic_shadow import (
    FLUnsafe, inspect_disposable_version_clock, migrate_disposable_copy,
    same_cooperative_generation,
)

class FLMonotonicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('swiftc'):
            raise unittest.SkipTest('Swift host compiler unavailable')
        cls.compiler=tempfile.TemporaryDirectory(prefix='wr_fl_native_')
        cls.binary=Path(cls.compiler.name)/'probe'
        p=subprocess.run(['swiftc',str(LAB/'build70_ev_fd_quarantine.swift'),
                          '-o',str(cls.binary)],capture_output=True,text=True,timeout=120)
        if p.returncode: raise RuntimeError(p.stderr)

    @classmethod
    def tearDownClass(cls):cls.compiler.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wr_fl_synthetic_')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        seed_full_v1(self.root)
        validate_shadow_pair(self.root)
        app=self.root/'synthetic_app'
        leaf=app/'Downloads/s/m/c'
        leaf.mkdir(parents=True)
        (leaf/'page-00000.bin').write_bytes(b'FL TEST ORIGINAL')
        (app/'Quarantine').mkdir()
        with FBShadowCopyBridge(self.root,self.binary,sealed_only=True) as bridge:
            bridge.prepare_single(1,confirmed=True)
        self.v2=app/'shadow_library_v2.sqlite'
        self.v3=migrate_disposable_copy(self.root)

    def snapshot(self):return inspect_disposable_version_clock(self.root)
    def sql(self,statement):
        with closing(sqlite3.connect(self.v3,isolation_level=None)) as db:
            return db.execute(statement).fetchall()
    def no_authority(self,obs):
        self.assertFalse(obs.can_delete or obs.can_restore or obs.can_purge or
                         obs.can_retire_database_rows or obs.is_source_inode_locked)

    def test_01_v2_is_unchanged(self):
        v2=sqlite3.connect(self.v2)
        try:
            self.assertEqual(v2.execute('PRAGMA user_version').fetchone(),(2,))
            self.assertEqual(v2.execute('SELECT state FROM offline_copy_journal').fetchone(),('copy_verified',))
            self.assertFalse(v2.execute("SELECT 1 FROM sqlite_master WHERE name='fl_journal_event'").fetchone())
        finally:v2.close()
        self.assertEqual(self.sql('PRAGMA user_version'),[(3,)])

    def test_02_baseline_event_and_no_delete(self):
        o=self.snapshot()
        self.assertEqual((o.operations,o.event_count,o.event_ceiling),(1,1,1))
        self.assertTrue(same_cooperative_generation(o,self.snapshot()))
        self.no_authority(o)

    def test_03_update_aba_changes_generation_despite_equal_row(self):
        before=self.snapshot()
        self.sql("UPDATE offline_copy_journal SET state='needs_review'")
        self.sql("UPDATE offline_copy_journal SET state='copy_verified'")
        after=self.snapshot()
        self.assertEqual(before.row_state,after.row_state)
        self.assertEqual(after.event_count,before.event_count+2)
        self.assertFalse(same_cooperative_generation(before,after))
        self.no_authority(after)

    def test_04_same_value_update_is_logged(self):
        a=self.snapshot()
        self.sql("UPDATE offline_copy_journal SET reason=reason")
        b=self.snapshot()
        self.assertEqual(a.row_state,b.row_state)
        self.assertFalse(same_cooperative_generation(a,b))

    def test_05_nonversioned_external_writer_can_bypass_triggers(self):
        a=self.snapshot()
        self.sql('DROP TRIGGER fl_journal_on_update')
        with self.assertRaises(FLUnsafe):self.snapshot()
        self.no_authority(a)

    def test_06_immutable_event_no_update_or_delete(self):
        with self.assertRaises(sqlite3.DatabaseError):self.sql("UPDATE fl_journal_event SET kind='delete'")
        with self.assertRaises(sqlite3.DatabaseError):self.sql('DELETE FROM fl_journal_event')
        self.assertEqual(self.snapshot().event_count,1)

    def test_07_readonly_connection_cannot_write(self):
        with closing(sqlite3.connect(self.v3.as_uri()+'?mode=ro',uri=True)) as db:
            with self.assertRaises(sqlite3.OperationalError):db.execute("UPDATE offline_copy_journal SET state='needs_review'")

    def test_08_uncommitted_wal_update_hidden_until_commit(self):
        before=self.snapshot()
        with closing(sqlite3.connect(self.v3,timeout=.4,isolation_level=None)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('BEGIN IMMEDIATE')
            try:
                writer.execute("UPDATE offline_copy_journal SET state='needs_review'")
                self.assertTrue(same_cooperative_generation(before,self.snapshot()))
                writer.execute('COMMIT')
            finally:
                if writer.in_transaction:writer.execute('ROLLBACK')
        self.assertFalse(same_cooperative_generation(before,self.snapshot()))

    def test_09_rollback_leaves_generation_unchanged(self):
        before=self.snapshot()
        with closing(sqlite3.connect(self.v3,isolation_level=None)) as writer:
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE offline_copy_journal SET state='needs_review'")
            writer.execute('ROLLBACK')
        self.assertTrue(same_cooperative_generation(before,self.snapshot()))

    def test_10_journal_delete_would_log_event_but_still_no_authority(self):
        a=self.snapshot()
        self.sql('DELETE FROM offline_copy_journal')
        b=self.snapshot()
        self.assertEqual((b.operations,b.event_count),(0,2))
        self.assertFalse(same_cooperative_generation(a,b))
        self.no_authority(b)

    def test_11_journal_insert_is_recorded(self):
        self.sql('DELETE FROM offline_copy_journal')
        # Re-inserting the same operation is legal in this synthetic v3 only.
        self.sql('''INSERT INTO offline_copy_journal
            (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,
             snapshot_name,source_device,source_inode,state,consent)
            SELECT operation_id,1,'s','m','c','ev_'||operation_id,'1','1',
                   'copy_verified','synthetic_confirmation'
            FROM fl_journal_event WHERE kind='baseline' ''')
        self.assertEqual(self.snapshot().event_count,3)

    def test_12_symlink_shadow_is_blocked(self):
        old=self.v3.with_name('old_v3.sqlite')
        # Close any WAL handles before changing the path.
        self.v3.rename(old)
        self.v3.symlink_to(old)
        with self.assertRaises(FLUnsafe):self.snapshot()

    def test_13_no_marker_is_fail_closed(self):
        (self.root/'.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(FLUnsafe):self.snapshot()

    def test_14_wrong_schema_is_blocked(self):
        self.sql('PRAGMA user_version=7')
        with self.assertRaises(FLUnsafe):self.snapshot()

    def test_15_second_migration_cannot_overwrite(self):
        with self.assertRaises(FileExistsError):migrate_disposable_copy(self.root)
        self.assertEqual(self.snapshot().event_count,1)

    def test_16_download_rows_are_not_retired(self):
        self.sql('SELECT * FROM downloads')
        self.snapshot()
        self.assertEqual(self.sql('SELECT count(*) FROM downloads'),[(1,)])
        self.assertEqual(self.sql('SELECT downloaded FROM chapters WHERE internal_id=1'),[(1,)])

if __name__=='__main__':unittest.main()
