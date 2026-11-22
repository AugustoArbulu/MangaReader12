#!/usr/bin/env python3
"""Synthetic persistent journal for safe Swift copy-only trial."""
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from build70_ev_recoverable_quarantine_lab import QuarantineLab
from build70_ez_copy_journal_bridge import EZSnapshotJournal,EZUnsafe,EZInterrupted

HERE=Path(__file__).resolve().parent

class CopyJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=shutil.which('swiftc')
        if not compiler:raise unittest.SkipTest('no Swift toolchain')
        cls.binroot=tempfile.TemporaryDirectory(prefix='webreader_ez_bridge_bin_')
        cls.binary=Path(cls.binroot.name)/'copy_fd'
        subprocess.run([compiler,str(HERE/'build70_ev_fd_quarantine.swift'),'-o',str(cls.binary)],check=True,capture_output=True,text=True,timeout=120)

    @classmethod
    def tearDownClass(cls):cls.binroot.cleanup()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='webreader_ez_bridge_')
        self.root=Path(self.tmp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        lab=QuarantineLab(self.root)
        self.chapter=lab.seed();lab.close()
        self.j=EZSnapshotJournal(self.root,self.binary)

    def tearDown(self):self.j.close();self.tmp.cleanup()

    def row(self):
        return self.j.db.execute('SELECT op,chapter_id,dest,state FROM ez_snapshot_journal').fetchone()

    def assert_owner(self):
        self.assertEqual(self.j.db.execute('SELECT COUNT(*) FROM downloads').fetchone(),(1,))
        self.assertEqual(self.j.db.execute('SELECT downloaded FROM chapters WHERE id=1').fetchone(),(1,))
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'page-content-preserve')

    def test_verified_copy_does_not_mutate_library(self):
        result=self.j.start(1,confirmed=True)
        self.assertEqual(result['status'],'copy_verified')
        op,chapter,dest,state=self.row();self.assertEqual(state,'copy_verified')
        self.assertEqual((self.j.lab.app/'Quarantine'/dest/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assert_owner()

    def test_refuse_without_confirmation(self):
        with self.assertRaises(EZUnsafe):self.j.start(1)
        self.assertIsNone(self.row());self.assert_owner()

    def test_refuse_unknown_chapter(self):
        with self.assertRaises(EZUnsafe):self.j.start(500,confirmed=True)
        self.assertIsNone(self.row());self.assert_owner()

    def test_prepared_without_snapshot_recovers_as_review(self):
        with self.assertRaises(EZInterrupted):self.j.start(1,confirmed=True,crash_at='after_intent')
        self.assertEqual(self.row()[3],'prepared')
        self.assertEqual(self.j.recover_readonly(),[(1,'needs_review')])
        self.assert_owner()

    def test_interrupted_after_copy_reverifies_and_commits_journal(self):
        with self.assertRaises(EZInterrupted):self.j.start(1,confirmed=True,crash_at='after_snapshot')
        self.assertEqual(self.row()[3],'prepared')
        self.assertEqual(self.j.recover_readonly(),[(1,'copy_verified')])
        self.assertEqual(self.row()[3],'copy_verified')
        self.assert_owner()

    def test_recovery_after_commit_is_idempotent(self):
        with self.assertRaises(EZInterrupted):self.j.start(1,confirmed=True,crash_at='after_verification_commit')
        self.assertEqual(self.j.recover_readonly(),[(1,'copy_verified')])
        self.assertEqual(self.j.recover_readonly(),[(1,'copy_verified')])
        self.assert_owner()

    def test_corrupted_snapshot_requires_review(self):
        self.j.start(1,confirmed=True)
        dest=self.row()[2]
        (self.j.lab.app/'Quarantine'/dest/'page-00000.bin').write_bytes(b'CORRUPTED')
        self.assertEqual(self.j.recover_readonly(),[(1,'needs_review')])
        self.assert_owner()

    def test_replaced_snapshot_symlink_is_not_followed(self):
        self.j.start(1,confirmed=True)
        dest=self.row()[2]
        snapshot=self.j.lab.app/'Quarantine'/dest
        displaced=self.j.lab.app/'preserved_copy';snapshot.rename(displaced)
        snapshot.symlink_to(displaced,target_is_directory=True)
        self.assertEqual(self.j.recover_readonly(),[(1,'needs_review')])
        self.assertEqual((displaced/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assert_owner()

    def test_changed_origin_requires_review(self):
        self.j.start(1,confirmed=True)
        file=self.chapter/'page-00000.bin'
        file.write_bytes(b'CHANGED SOURCE DATA')
        self.assertEqual(self.j.recover_readonly(),[(1,'needs_review')])
        self.assertEqual(self.j.db.execute('SELECT COUNT(*) FROM downloads').fetchone(),(1,))
        self.assertEqual(self.j.db.execute('SELECT downloaded FROM chapters WHERE id=1').fetchone(),(1,))
        self.assertEqual(file.read_bytes(),b'CHANGED SOURCE DATA')

    def test_sqlite_trigger_rejects_state_update_but_keeps_original_and_copy(self):
        with self.assertRaises(EZInterrupted):self.j.start(1,confirmed=True,crash_at='after_snapshot')
        self.j.db.execute('''CREATE TRIGGER no_journal_change BEFORE UPDATE ON ez_snapshot_journal
             BEGIN SELECT RAISE(ABORT, 'synthetic journal error'); END''')
        with self.assertRaises(sqlite3.DatabaseError):self.j.recover_readonly()
        self.assertEqual(self.row()[3],'prepared');self.assert_owner()

    def test_no_duplicate_journal_for_one_chapter(self):
        self.j.start(1,confirmed=True)
        with self.assertRaises(EZUnsafe):self.j.start(1,confirmed=True)
        self.assertEqual(self.j.db.execute('SELECT COUNT(*) FROM ez_snapshot_journal').fetchone(),(1,))
        self.assert_owner()

    def test_missing_copy_blocks_reindex(self):
        with self.assertRaises(EZInterrupted):self.j.start(1,confirmed=True,crash_at='after_intent')
        with self.assertRaises(EZUnsafe):self.j.reindex_safe()
        self.assert_owner()

    def test_reopen_bridge_process_recovers_persisted_intent(self):
        with self.assertRaises(EZInterrupted):self.j.start(1,confirmed=True,crash_at='after_snapshot')
        self.j.close()
        with EZSnapshotJournal(self.root,self.binary) as reopened:
            self.assertEqual(reopened.recover_readonly(),[(1,'copy_verified')])
            self.assertEqual(reopened.db.execute('SELECT state FROM ez_snapshot_journal').fetchone(),('copy_verified',))
        self.j=EZSnapshotJournal(self.root,self.binary)
        self.assert_owner()

    def test_unknown_unmarked_dir_rejected(self):
        (self.root/'.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(Exception):EZSnapshotJournal(self.root,self.binary)


if __name__=='__main__':unittest.main(verbosity=2)
