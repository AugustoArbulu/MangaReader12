#!/usr/bin/env python3
"""EX: synthetic journal + real Swift fd probe. No real app integration."""
from pathlib import Path
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build70_ev_recoverable_quarantine_lab import QuarantineLab
from build70_ex_persistent_journal_bridge import (
    EXJournalLab, EXUnsafe, EXInjectedInterruption,
)


class EXJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        swift = shutil.which('swiftc')
        if swift is None:
            raise unittest.SkipTest('swiftc missing, cannot claim native validation')
        cls.native_build = tempfile.TemporaryDirectory(prefix='ex_native_build_')
        cls.binary = Path(cls.native_build.name) / 'ex_swift_fd'
        subprocess.run([swift, str(HERE / 'build70_ev_fd_quarantine.swift'),
                        '-o', str(cls.binary)],
                       check=True, capture_output=True, text=True, timeout=180)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'native_build'):
            cls.native_build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ex_synthetic_fixture_')
        self.root = Path(self.tmp.name)
        (self.root / '.webreader_ev_disposable_marker').write_text('EV_SYNTHETIC_ONLY\n')
        self.lab = QuarantineLab(self.root)
        self.chapter = self.lab.seed()
        self.coordinator = EXJournalLab(self.root, self.binary)

    def tearDown(self):
        self.coordinator.close()
        self.lab.close()
        self.tmp.cleanup()

    def state(self, op):
        return self.coordinator.journal_row(op)[1]

    def all_ops(self):
        return self.coordinator.db.execute('SELECT op,state FROM ex_delete_journal').fetchall()

    def q_file(self, op):
        return self.lab.app / 'Quarantine' / ('ev_' + op) / 'page-00000.bin'

    def restart(self):
        self.coordinator.close()
        self.coordinator = EXJournalLab(self.root, self.binary)
        return self.coordinator.startup_reconcile()

    def interrupt(self, position):
        with self.assertRaises(EXInjectedInterruption):
            self.coordinator.stage_confirmed(1, confirmed=True, fail_at=position)
        return self.all_ops()[0][0]

    def test_success_requires_explicit_confirmation(self):
        with self.assertRaises(EXUnsafe):
            self.coordinator.stage_confirmed(1)
        self.assertEqual(self.all_ops(), [])
        self.assertTrue(self.chapter.is_dir())

    def test_commit_retains_real_swift_moved_pages_in_quarantine(self):
        op = self.coordinator.stage_confirmed(1,confirmed=True)
        self.assertFalse(self.chapter.exists())
        self.assertEqual(self.q_file(op).read_bytes(), b'page-content-preserve')
        self.assertEqual(self.state(op),'retired_quarantined')
        self.assertEqual(self.lab.db.execute('SELECT * FROM downloads').fetchall(),[])
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE id=1').fetchone(),(0,))
        self.assertEqual(self.restart(),[(op,'retired_quarantined')])
        self.assertEqual(self.q_file(op).read_bytes(),b'page-content-preserve')
        self.assertTrue(self.coordinator.reindex_guard())

    def test_interrupt_after_prepared_intent_marks_aborted_without_any_move(self):
        op = self.interrupt('after_intent')
        self.assertEqual(self.state(op),'prepared')
        self.assertEqual(self.restart(),[(op,'aborted')])
        self.assertTrue(self.chapter.is_dir())
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))
        self.assertFalse(self.q_file(op).exists())
        self.assertTrue(self.coordinator.reindex_guard())

    def test_interrupt_after_swift_move_requires_review_and_keeps_metadata(self):
        op = self.interrupt('after_stage')
        self.assertEqual(self.state(op),'prepared')
        self.assertEqual(self.restart(),[(op,'needs_review')])
        self.assertTrue(self.q_file(op).is_file())
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE id=1').fetchone(),(1,))

    def test_interrupt_after_recorded_quarantine_requires_review(self):
        op = self.interrupt('after_quarantine_state')
        self.assertEqual(self.state(op),'quarantined')
        self.assertEqual(self.restart(),[(op,'needs_review')])
        self.assertEqual(self.q_file(op).read_bytes(),b'page-content-preserve')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def test_interrupt_after_sqlite_commit_is_idempotently_complete(self):
        op = self.interrupt('after_sqlite_commit')
        self.assertEqual(self.state(op),'retired_quarantined')
        self.assertEqual(self.restart(),[(op,'retired_quarantined')])
        self.assertEqual(self.coordinator.startup_reconcile(),[(op,'retired_quarantined')])
        self.assertEqual(self.q_file(op).read_bytes(),b'page-content-preserve')

    def test_sqlite_delete_trigger_rolls_back_metadata_and_journal_together(self):
        self.lab.db.execute("CREATE TRIGGER ex_reject_delete BEFORE DELETE ON downloads "
                            "BEGIN SELECT RAISE(ABORT,'synthetic SQLite error'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.coordinator.stage_confirmed(1,confirmed=True)
        op = self.all_ops()[0][0]
        self.assertEqual(self.state(op),'quarantined')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE id=1').fetchone(),(1,))
        self.assertEqual(self.restart(),[(op,'needs_review')])
        self.assertEqual(self.q_file(op).read_bytes(),b'page-content-preserve')

    def test_sqlite_update_trigger_rolls_back_metadata_and_journal_together(self):
        self.lab.db.execute("CREATE TRIGGER ex_reject_update BEFORE UPDATE ON chapters "
                            "BEGIN SELECT RAISE(ABORT,'synthetic SQLite error'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.coordinator.stage_confirmed(1,confirmed=True)
        op = self.all_ops()[0][0]
        self.assertEqual(self.state(op),'quarantined')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE id=1').fetchone(),(1,))
        self.assertEqual(self.q_file(op).read_bytes(),b'page-content-preserve')

    def test_unresolved_operation_prevents_duplicate_stage_and_reindex(self):
        op = self.interrupt('after_stage')
        with self.assertRaises(EXUnsafe): self.coordinator.stage_confirmed(1,confirmed=True)
        with self.assertRaises(EXUnsafe): self.coordinator.reindex_guard()
        self.restart()
        with self.assertRaises(EXUnsafe): self.coordinator.reindex_guard()
        self.assertEqual(self.state(op),'needs_review')
        self.assertEqual(len(self.all_ops()),1)

    def test_quarantine_substitution_before_sqlite_retirement_is_rejected(self):
        def replace_quarantine(op):
            original = self.lab.app / 'Quarantine' / ('ev_'+op)
            original.rename(self.lab.app/'preserved_original_quarantine')
            original.mkdir()
            (original/'foreign.txt').write_bytes(b'KEEP_FOREIGN')
        with self.assertRaises(EXUnsafe):
            self.coordinator.stage_confirmed(1,confirmed=True,fault_hook=replace_quarantine)
        op = self.all_ops()[0][0]
        self.assertEqual(self.state(op),'quarantined')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE id=1').fetchone(),(1,))
        self.assertEqual((self.lab.app/'preserved_original_quarantine'/'page-00000.bin').read_bytes(),
                         b'page-content-preserve')
        self.assertEqual((self.lab.app/'Quarantine'/('ev_'+op)/'foreign.txt').read_bytes(), b'KEEP_FOREIGN')
        self.assertEqual(self.restart(),[(op,'needs_review')])

    def test_recovery_never_overwrites_new_source_directory(self):
        op = self.interrupt('after_stage')
        self.chapter.mkdir()
        (self.chapter / 'foreign.txt').write_bytes(b'KEEP_NEW_SOURCE')
        self.assertEqual(self.restart(),[(op,'needs_review')])
        self.assertEqual((self.chapter/'foreign.txt').read_bytes(),b'KEEP_NEW_SOURCE')
        self.assertEqual(self.q_file(op).read_bytes(),b'page-content-preserve')

    def test_recovery_never_overwrites_new_quarantine_directory(self):
        op = self.interrupt('after_intent')
        dest = self.lab.app/'Quarantine'/('ev_'+op)
        dest.mkdir()
        (dest/'foreign.txt').write_bytes(b'KEEP_QUARANTINE')
        self.assertEqual(self.restart(),[(op,'needs_review')])
        self.assertEqual((dest/'foreign.txt').read_bytes(),b'KEEP_QUARANTINE')
        self.assertTrue(self.chapter.is_dir())

    def test_source_inode_mismatch_goes_to_review_without_any_move(self):
        op = self.interrupt('after_intent')
        saved = self.chapter.with_name('safe_original')
        self.chapter.rename(saved)
        self.chapter.mkdir()
        (self.chapter/'foreign.txt').write_bytes(b'KEEP_NEW')
        self.assertEqual(self.restart(),[(op,'needs_review')])
        self.assertEqual((saved/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual((self.chapter/'foreign.txt').read_bytes(),b'KEEP_NEW')

    def test_symlinked_parent_blocks_reconciliation_without_following(self):
        op = self.interrupt('after_intent')
        original = self.lab.app/'Downloads'/'s'
        saved = self.lab.app/'saved_s'
        original.rename(saved)
        original.symlink_to(saved, target_is_directory=True)
        self.assertEqual(self.restart(),[(op,'needs_review')])
        self.assertTrue((saved/'m'/'c'/'page-00000.bin').is_file())

    def test_invalid_marker_prevents_resume_and_state_changes(self):
        op = self.interrupt('after_intent')
        (self.root/'.webreader_ev_disposable_marker').write_text('tampered')
        self.coordinator.close()
        with self.assertRaises(EXUnsafe): EXJournalLab(self.root,self.binary)
        (self.root/'.webreader_ev_disposable_marker').write_text('EV_SYNTHETIC_ONLY\n')
        self.coordinator = EXJournalLab(self.root,self.binary)
        self.assertEqual(self.state(op),'prepared')
        self.assertEqual(self.coordinator.startup_reconcile(),[(op,'aborted')])

    def test_reconcile_does_not_reopen_unsafe_retired_metadata(self):
        op = self.coordinator.stage_confirmed(1,confirmed=True)
        q = self.lab.app/'Quarantine'/('ev_'+op)
        q.rename(self.lab.app/'offline_keep')
        self.assertEqual(self.restart(),[(op,'needs_review')])
        self.assertEqual((self.lab.app/'offline_keep'/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(0,))

    def test_bulk_preflight_aborts_all_if_second_file_unsafe(self):
        self.lab.seed(2,leaf='d')
        (self.lab.app/'Downloads'/'s'/'m'/'d'/'foreign.txt').write_text('unknown')
        with self.assertRaises(EXUnsafe):
            self.coordinator.stage_bulk_confirmed([1,2],confirmed=True)
        self.assertEqual(self.all_ops(),[])
        self.assertTrue(self.chapter.is_dir())
        self.assertTrue((self.lab.app/'Downloads'/'s'/'m'/'d'/'page-00000.bin').exists())

    def test_bulk_uses_individual_journal_policy_and_keeps_both_in_quarantine(self):
        self.lab.seed(2,leaf='d')
        ops = self.coordinator.stage_bulk_confirmed([1,2],confirmed=True)
        self.assertEqual(len(ops),2)
        self.assertEqual(len(self.all_ops()),2)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(0,))
        self.assertTrue(all(self.q_file(op).is_file() for op in ops))
        self.assertEqual(len(self.restart()),2)

    def test_bulk_rejects_duplicate_and_oversized_without_mutation(self):
        for ids in ([1,1],[],range(130)):
            with self.assertRaises(EXUnsafe):
                self.coordinator.stage_bulk_confirmed(ids,confirmed=True)
        self.assertEqual(self.all_ops(),[])

    def test_recovery_is_idempotent_without_filesystem_mutations(self):
        op = self.interrupt('after_stage')
        before = self.q_file(op).stat()
        self.restart()
        first = self.state(op)
        self.coordinator.startup_reconcile()
        after = self.q_file(op).stat()
        self.assertEqual(first,'needs_review')
        self.assertEqual((before.st_dev,before.st_ino,before.st_size),
                         (after.st_dev,after.st_ino,after.st_size))

    def test_disposable_marker_is_not_permission_to_purge(self):
        src = (HERE/'build70_ex_persistent_journal_bridge.py').read_text()
        self.assertNotIn('shutil.rmtree(',src)
        self.assertNotIn('os.unlink(',src)
        self.assertNotIn('os.rename(',src)
        self.assertNotIn('removeItem(',src)
        self.assertNotIn('appinst',src.lower().split('class exjournallab',1)[1])
        self.assertTrue(self.chapter.is_dir())

    def test_real_os_process_exit_after_move_reconciles_on_new_process(self):
        # Distinct interpreter+SQLite connection. Exit bypasses all finally
        # blocks to emulate app-process termination after native rename.
        code = '''
import os, pathlib, sys
sys.path.insert(0,sys.argv[1])
from build70_ex_persistent_journal_bridge import EXJournalLab, EXInjectedInterruption
j=EXJournalLab(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))
try:
    j.stage_confirmed(1,confirmed=True,fail_at='after_stage')
except EXInjectedInterruption:
    os._exit(89)
os._exit(88)
'''
        child = subprocess.run([sys.executable,'-c',code,str(HERE),str(self.root),str(self.binary)],
                               capture_output=True,text=True,timeout=20)
        self.assertEqual(child.returncode,89,child.stderr)
        op = self.all_ops()[0][0]
        self.assertEqual(self.state(op),'prepared')
        self.assertEqual(self.restart(),[(op,'needs_review')])
        self.assertEqual(self.q_file(op).read_bytes(),b'page-content-preserve')


if __name__ == '__main__':
    unittest.main(verbosity=2)
