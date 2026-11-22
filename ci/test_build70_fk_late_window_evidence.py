#!/usr/bin/env python3
"""FK hostile late-window tests using the real lab Swift FD verifier."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
LAB = HERE / 'labs' / 'webreader-ev-fd' / 'ci'
sys.path[:0] = [str(HERE), str(LAB)]
from build70_fa_full_schema_shadow import seed_full_v1, validate_shadow_pair, capture_legacy
from build70_fb_full_shadow_copy_bridge import FBShadowCopyBridge, FBInterrupted
from build70_fj_paired_readonly_reconciliation import paired_audit, FJUnsafe
import build70_fk_late_window_evidence as fk
from build70_fk_late_window_evidence import late_window_audit


class FKLateWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('swiftc'):
            raise unittest.SkipTest('Swift compiler missing')
        cls.compiler = tempfile.TemporaryDirectory(prefix='wr_fk_native_')
        cls.binary = Path(cls.compiler.name) / 'native'
        comp = subprocess.run(['swiftc', str(LAB/'build70_ev_fd_quarantine.swift'),
                               '-o', str(cls.binary)], capture_output=True, text=True, timeout=120)
        if comp.returncode:
            raise RuntimeError(comp.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.compiler.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wr_fk_disposable_')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        seed_full_v1(self.root)
        validate_shadow_pair(self.root)
        self.app = self.root/'synthetic_app'
        self.chapter = self.app/'Downloads/s/m/c'
        self.chapter.mkdir(parents=True)
        self.page = self.chapter/'page-00000.bin'
        self.original = b'FK synthetic byte stream only'
        self.page.write_bytes(self.original)
        (self.app/'Quarantine').mkdir()
        self.lab = FBShadowCopyBridge(self.root, self.binary, sealed_only=True)
        self.addCleanup(self.lab.close)
        self.legacy_before = capture_legacy(self.lab.db)

    def copy(self, *, interrupt=None):
        if interrupt:
            with self.assertRaises(FBInterrupted):
                self.lab.prepare_single(1, confirmed=True, crash_at=interrupt)
        else:
            self.assertEqual(self.lab.prepare_single(1, confirmed=True), (1,))
        snap=self.lab.db.execute('SELECT snapshot_name FROM offline_copy_journal').fetchone()[0]
        return self.app/'Quarantine'/snap

    def audit(self, **kwargs):
        return late_window_audit(self.root, self.binary, **kwargs)

    def safe_flags(self, report):
        self.assertFalse(report.can_delete or report.can_restore or report.can_purge or report.can_mark_downloaded)
        self.assertTrue(report.late_race_window_remains)
        self.assertFalse(report.source_inode_cas_available)

    def unchanged(self):
        self.assertEqual(capture_legacy(self.lab.db), self.legacy_before)
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE internal_id=1').fetchone(),(1,))
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM downloads').fetchone(),(1,))

    def test_01_sealed_copy_is_observation_not_delete_permission(self):
        self.copy();result=self.audit()
        self.assertEqual((result.entries,result.observations,result.requires_review),(1,1,0))
        self.assertIn(('late_observation_only',1),result.reasons)
        self.safe_flags(result);self.unchanged()
        self.assertEqual(self.page.read_bytes(),self.original)

    def test_02_no_journal_stays_review(self):
        result=self.audit()
        self.assertEqual((result.entries,result.observations,result.requires_review),(0,0,1))
        self.safe_flags(result)

    def test_03_prepared_after_intent_stays_review(self):
        self.copy(interrupt='after_intent');result=self.audit()
        self.assertEqual(result.observations,0);self.safe_flags(result);self.unchanged()

    def test_04_prepared_after_snapshot_stays_review(self):
        self.copy(interrupt='after_snapshot');result=self.audit()
        self.assertEqual(result.observations,0);self.safe_flags(result);self.unchanged()

    def test_05_needs_review_stays_review(self):
        self.copy();self.lab.db.execute("UPDATE offline_copy_journal SET state='needs_review'")
        self.assertEqual(self.audit().observations,0)

    def test_06_source_swap_after_pair_is_detected_without_foreign_move(self):
        self.copy();moved=self.chapter.with_name('c_pinned_original')
        def swap(_):
            self.chapter.rename(moved);self.chapter.mkdir()
            (self.chapter/'page-00000.bin').write_bytes(b'FOREIGN PAGE')
        out=self.audit(after_paired=swap)
        self.assertEqual(out.observations,0)
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'FOREIGN PAGE')
        self.assertEqual((moved/'page-00000.bin').read_bytes(),self.original)
        self.unchanged()

    def test_07_copy_swap_after_pair_is_detected(self):
        snap=self.copy();old=snap.with_name('moved_'+snap.name)
        def swap(_):
            snap.rename(old);snap.mkdir()
            (snap/'page-00000.bin').write_bytes(b'FOREIGN')
        self.assertEqual(self.audit(after_paired=swap).observations,0)
        self.assertEqual((snap/'page-00000.bin').read_bytes(),b'FOREIGN')
        self.assertEqual((old/'page-00000.bin').read_bytes(),self.original)

    def test_08_source_corruption_after_pair_is_detected(self):
        self.copy()
        out=self.audit(after_paired=lambda _:self.page.write_bytes(b'mutated source'))
        self.assertEqual(out.observations,0)

    def test_09_snapshot_corruption_after_pair_is_detected(self):
        snap=self.copy()
        out=self.audit(after_paired=lambda _:(snap/'page-00000.bin').write_bytes(b'mutated copy'))
        self.assertEqual(out.observations,0)

    def test_10_private_plan_injection_after_pair_is_rejected(self):
        self.copy()
        def inject(_):
            (self.chapter/'_download-plan.json').write_bytes(b'Authorization: secret')
        self.assertEqual(self.audit(after_paired=inject).observations,0)
        self.assertIn((self.chapter/'_download-plan.json').read_bytes(),[b'Authorization: secret'])

    def test_11_journal_state_change_after_pair_is_detected(self):
        self.copy()
        def change(_):self.lab.db.execute("UPDATE offline_copy_journal SET state='needs_review'")
        result=self.audit(after_paired=change)
        self.assertEqual(result.observations,0)
        self.assertIn(('journal_drift_after_pair',1),result.reasons)

    def test_12_reason_change_after_pair_is_detected(self):
        self.copy()
        result=self.audit(after_paired=lambda _:self.lab.db.execute(
            "UPDATE offline_copy_journal SET reason='unexpected'"))
        self.assertEqual(result.observations,0)

    def test_13_timestamp_change_after_pair_is_detected(self):
        self.copy()
        self.assertEqual(self.audit(after_paired=lambda _:self.lab.db.execute(
            "UPDATE offline_copy_journal SET updated_at='2099'" )).observations,0)

    def test_14_downloaded_bit_change_after_pair_is_detected(self):
        self.copy()
        self.assertEqual(self.audit(after_paired=lambda _:self.lab.db.execute(
            'UPDATE chapters SET downloaded=0')).observations,0)

    def test_15_late_directory_swap_between_native_checks_is_detected(self):
        self.copy();moved=self.chapter.with_name('c_before_last_check')
        def swap(_):self.chapter.rename(moved);self.chapter.mkdir()
        self.assertEqual(self.audit(after_first_late_fd=swap).observations,0)
        self.unchanged()

    def test_16_late_sql_owner_change_is_detected(self):
        self.copy()
        self.assertEqual(self.audit(after_first_late_fd=lambda _:self.lab.db.execute(
            "UPDATE downloads SET state='paused'")).observations,0)

    def test_17_second_fd_detects_inplace_data_change_after_sql(self):
        self.copy()
        self.assertEqual(self.audit(after_late_sql=lambda _:self.page.write_bytes(b'changed')).observations,0)

    def test_18_final_sql_detects_journal_change_after_late_sql(self):
        self.copy()
        out=self.audit(after_late_sql=lambda _:self.lab.db.execute(
            "UPDATE offline_copy_journal SET reason='adversarial'"))
        self.assertEqual(out.observations,0)
        self.assertIn(('late_final_db_drift',1),out.reasons)

    def test_19_last_native_then_mutation_is_unobservable_and_still_denied(self):
        self.copy()
        def mutate(_):self.page.write_bytes(b'changed AFTER final native verification')
        out=self.audit(after_last_native=mutate)
        self.assertEqual(out.observations,1)  # Evidence can be stale at return.
        self.safe_flags(out)
        self.assertEqual(paired_audit(self.root,self.binary).paired_observations,0)

    def test_20_last_native_then_directory_swap_still_denied(self):
        self.copy();moved=self.chapter.with_name('c_original')
        def swap(_):
            self.chapter.rename(moved);self.chapter.mkdir()
            (self.chapter/'page-00000.bin').write_bytes(b'foreign')
        out=self.audit(after_last_native=swap)
        self.assertEqual(out.observations,1)
        self.safe_flags(out)
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'foreign')
        self.assertEqual((moved/'page-00000.bin').read_bytes(),self.original)

    def test_21_post_native_uncommitted_wal_drift_is_not_visible(self):
        self.copy();writer=sqlite3.connect(self.app/'shadow_library_v2.sqlite',timeout=.1,isolation_level=None)
        try:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE offline_copy_journal SET reason='not_committed'")
            out=self.audit()
            self.assertEqual(out.observations,1)
            self.safe_flags(out)
            writer.execute('COMMIT')
            self.assertEqual(self.audit().observations,0)
        finally:
            if writer.in_transaction:writer.rollback()
            writer.close()

    def test_22_metadata_owner_mismatch_fails_closed(self):
        self.copy()
        self.lab.db.execute("UPDATE offline_copy_journal SET source_manga_id='intruder'")
        self.assertEqual(self.audit().observations,0)

    def test_23_source_symlink_fails_closed(self):
        self.copy();moved=self.chapter.with_name('real_folder')
        self.chapter.rename(moved);self.chapter.symlink_to(moved,target_is_directory=True)
        self.assertEqual(self.audit().observations,0)

    def test_24_destination_symlink_fails_closed(self):
        snap=self.copy();moved=snap.with_name('real_snapshot')
        snap.rename(moved);snap.symlink_to(moved,target_is_directory=True)
        self.assertEqual(self.audit().observations,0)

    def test_25_budget_zero_blocks_even_previously_valid_pair(self):
        self.copy()
        with patch.object(fk,'MAX_FK_ENTRIES',0):
            out=self.audit()
        self.assertEqual(out.observations,0);self.safe_flags(out)

    def test_26_marker_missing_refuses_audit(self):
        self.copy();(self.root/'.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(FJUnsafe):self.audit()

    def test_27_future_schema_refuses_audit(self):
        self.copy();self.lab.db.execute('PRAGMA user_version=3')
        with self.assertRaises(FJUnsafe):self.audit()

    def test_28_untrusted_native_verifier_symlink_refused(self):
        self.copy();fake=self.root/'fake'
        fake.symlink_to(self.binary)
        with self.assertRaises(FJUnsafe):late_window_audit(self.root,fake)

    def test_29_verifier_failure_between_readings_never_approved(self):
        self.copy()
        with patch.object(fk,'_native_verify',return_value=False):
            out=self.audit()
        self.assertEqual(out.observations,0)
        self.safe_flags(out)

    def test_30_review_does_not_change_journal_or_legacy(self):
        self.copy()
        rows=self.lab.db.execute('SELECT * FROM offline_copy_journal').fetchall()
        self.audit()
        self.assertEqual(rows,self.lab.db.execute('SELECT * FROM offline_copy_journal').fetchall())
        self.unchanged()

    def test_31_source_hardlink_or_extra_leaf_rejected(self):
        self.copy();os.link(self.page,self.chapter/'alias.bin')
        self.assertEqual(self.audit().observations,0)

    def test_32_receipt_corruption_rejected(self):
        (self.chapter/'.webreader-completion-v1').write_bytes(b'WR-OFFLINE-COMPLETE-V1:1\n')
        snap=self.copy()
        (snap/'.webreader-completion-v1').write_bytes(b'WR-OFFLINE-COMPLETE-V1:0\n')
        self.assertEqual(self.audit().observations,0)

    def test_33_non_utf8_or_invalid_json_native_output_not_trusted(self):
        self.copy()
        fake=self.root/'fake-verifier'
        fake.write_bytes(b'#!/bin/sh\necho garbage\n')
        fake.chmod(0o700)
        out=late_window_audit(self.root,fake)
        self.assertEqual(out.observations,0);self.safe_flags(out)

    def test_34_fj_mutation_after_its_final_fd_can_be_detected_by_fk(self):
        self.copy();n=0
        original=fk.paired_audit
        def wrapped(root,binary):
            result=original(root,binary)
            self.page.write_bytes(b'mutated between FJ and FK')
            return result
        with patch.object(fk,'paired_audit',side_effect=wrapped):
            out=self.audit()
        self.assertEqual(out.observations,0)

    def test_35_no_foreign_delete_or_sql_retirement_symbols(self):
        file=Path(fk.__file__).read_text()
        for token in ('os.unlink(', 'os.rename(', 'shutil.rmtree(', 'DELETE FROM ',
                      'UPDATE chapters ', 'UPDATE downloads ', 'FileManager.removeItem('):
            self.assertNotIn(token,file)
        self.assertNotIn('can_delete: bool = True',file)
        self.assertNotIn('can_purge: bool = True',file)

    def test_36_sqlite_journal_aba_without_durable_version_cannot_be_excluded(self):
        self.copy();before=self.lab.db.execute('SELECT * FROM offline_copy_journal').fetchone()
        def aba(_):
            self.lab.db.execute("UPDATE offline_copy_journal SET state='needs_review'")
            self.lab.db.execute("UPDATE offline_copy_journal SET state='copy_verified'")
        out=self.audit(after_first_late_fd=aba)
        self.assertEqual(out.observations,1)
        self.safe_flags(out)
        self.assertEqual(self.lab.db.execute('SELECT * FROM offline_copy_journal').fetchone(),before)


if __name__=='__main__': unittest.main()
