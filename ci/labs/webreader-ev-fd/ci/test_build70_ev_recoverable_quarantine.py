#!/usr/bin/env python3
"""Synthetic-only EV fault matrix; never loads real WebReader user content."""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from build70_ev_recoverable_quarantine_lab import QuarantineLab,Unsafe,InjectedCrash


class RecoverableQuarantineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='webreader_ev_disposable_')
        (Path(self.tmp.name)/'.webreader_ev_disposable_marker').write_text('EV_SYNTHETIC_ONLY\n')
        self.lab=QuarantineLab(self.tmp.name)
        self.chapter=self.lab.seed()

    def tearDown(self):
        self.lab.close();self.tmp.cleanup()

    def row_exists(self):
        return self.lab.db.execute('SELECT COUNT(*) FROM downloads').fetchone()[0]==1

    def test_success_retains_recoverable_pages_in_quarantine(self):
        op=self.lab.stage()
        self.assertFalse(self.chapter.exists())
        self.assertFalse(self.row_exists())
        self.assertEqual((self.lab.app/'Quarantine'/('ev_'+op)/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual(self.lab.recover(),[(op,'retired_quarantined')])
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters').fetchone()[0],0)

    def test_crash_after_intent_rolls_back_without_content_loss(self):
        with self.assertRaises(InjectedCrash): self.lab.stage(fail_at='after_intent')
        self.lab.close();self.lab=QuarantineLab(self.tmp.name)
        self.assertEqual(self.lab.recover()[0][1],'aborted')
        self.assertTrue(self.row_exists());self.assertTrue(self.chapter.exists())

    def test_crash_after_rename_keeps_quarantine_for_review(self):
        with self.assertRaises(InjectedCrash): self.lab.stage(fail_at='after_rename')
        self.assertFalse(self.chapter.exists())
        self.lab.close();self.lab=QuarantineLab(self.tmp.name)
        self.assertEqual(self.lab.recover()[0][1],'needs_review')
        self.assertFalse(self.chapter.exists())
        self.assertEqual(next((self.lab.app/'Quarantine').iterdir()).joinpath('page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertTrue(self.row_exists())

    def test_crash_after_quarantine_record_holds_for_review(self):
        with self.assertRaises(InjectedCrash): self.lab.stage(fail_at='after_quarantine_record')
        self.lab.close();self.lab=QuarantineLab(self.tmp.name)
        self.assertEqual(self.lab.recover()[0][1],'needs_review')
        self.assertTrue(self.row_exists());self.assertFalse(self.chapter.exists())
        self.assertEqual(next((self.lab.app/'Quarantine').iterdir()).joinpath('page-00000.bin').read_bytes(),b'page-content-preserve')

    def test_crash_after_sqlite_commit_keeps_quarantine(self):
        with self.assertRaises(InjectedCrash): self.lab.stage(fail_at='after_sqlite_commit')
        self.lab.close();self.lab=QuarantineLab(self.tmp.name)
        self.assertEqual(self.lab.recover()[0][1],'retired_quarantined')
        self.assertFalse(self.row_exists())
        self.assertEqual(len(list((self.lab.app/'Quarantine').iterdir())),1)

    def test_sqlite_trigger_failure_rolls_back_and_keeps_quarantine(self):
        self.lab.db.execute('CREATE TRIGGER synthetic_error BEFORE UPDATE ON chapters BEGIN SELECT RAISE(ABORT,\'synthetic failure\'); END')
        with self.assertRaises(sqlite3.DatabaseError):self.lab.stage()
        self.assertTrue(self.row_exists())
        self.lab.db.execute('DROP TRIGGER synthetic_error')
        self.assertEqual(self.lab.recover()[0][1],'needs_review')
        self.assertFalse(self.chapter.exists())
        self.assertEqual(next((self.lab.app/'Quarantine').iterdir()).joinpath('page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters').fetchone()[0],1)

    def test_parent_symlink_fails_closed(self):
        source=self.lab.app/'Downloads'/'s'; displaced=self.lab.app/'real_source'
        source.rename(displaced);source.symlink_to(displaced,target_is_directory=True)
        with self.assertRaises((Unsafe,OSError)): self.lab.stage()
        self.assertTrue((displaced/'m'/'c'/'page-00000.bin').is_file())
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM delete_intents').fetchone()[0],0)

    def test_leaf_symlink_fails_closed(self):
        original=self.chapter.with_name('preserved');self.chapter.rename(original)
        self.chapter.symlink_to(original,target_is_directory=True)
        with self.assertRaises((Unsafe,OSError)):self.lab.stage()
        self.assertTrue((original/'page-00000.bin').exists())

    def test_page_symlink_blocks_operation(self):
        page=self.chapter/'page-00000.bin'
        page.rename(self.chapter/'saved.bin')
        page.symlink_to(self.chapter/'saved.bin')
        with self.assertRaises(Unsafe):self.lab.stage()
        self.assertTrue((self.chapter/'saved.bin').exists())

    def test_recovery_idempotent(self):
        with self.assertRaises(InjectedCrash):self.lab.stage(fail_at='after_rename')
        self.assertEqual(self.lab.recover()[0][1],'needs_review')
        self.assertEqual(self.lab.recover()[0][1],'needs_review')
        self.assertTrue(self.row_exists());self.assertFalse(self.chapter.exists())
        self.assertEqual(next((self.lab.app/'Quarantine').iterdir()).joinpath('page-00000.bin').read_bytes(),b'page-content-preserve')

    def test_foreign_or_nested_content_blocks_operation(self):
        (self.chapter/'foreign.txt').write_text('do not erase')
        with self.assertRaises(Unsafe):self.lab.stage()
        self.assertTrue((self.chapter/'foreign.txt').exists());self.assertTrue(self.row_exists())

    def test_foreign_swap_after_crash_requires_review(self):
        with self.assertRaises(InjectedCrash):self.lab.stage(fail_at='after_rename')
        q=next((self.lab.app/'Quarantine').iterdir())
        q.rename(self.lab.app/'displaced_original')
        q.mkdir();(q/'foreign.txt').write_text('valuable foreign data')
        self.assertEqual(self.lab.recover()[0][1],'needs_review')
        self.assertTrue(self.row_exists())
        self.assertTrue((q/'foreign.txt').exists())
        self.assertTrue((self.lab.app/'displaced_original'/'page-00000.bin').exists())

    def test_mismatched_source_identity_requires_review(self):
        with self.assertRaises(InjectedCrash):self.lab.stage(fail_at='after_intent')
        original=self.chapter.with_name('not_touched');self.chapter.rename(original)
        self.chapter.mkdir();(self.chapter/'page-00000.bin').write_bytes(b'foreign')
        self.assertEqual(self.lab.recover()[0][1],'needs_review')
        self.assertTrue(self.row_exists())
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'foreign')


if __name__=='__main__':
    unittest.main(verbosity=2)
