#!/usr/bin/env python3
"""FJ read-only combined evidence, real Swift FD verifier and synthetic v2 DB."""
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
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(HERE))
from build70_fa_full_schema_shadow import seed_full_v1, validate_shadow_pair, capture_legacy
from build70_fb_full_shadow_copy_bridge import FBShadowCopyBridge, FBInterrupted
from build70_fj_paired_readonly_reconciliation import paired_audit, FJUnsafe
import build70_fj_paired_readonly_reconciliation as fj


class FJPairedReadOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which('swiftc') is None:
            raise unittest.SkipTest('Swift compiler unavailable')
        cls.compiler = tempfile.TemporaryDirectory(prefix='wr_fj_compiler_')
        cls.binary = Path(cls.compiler.name) / 'fd_native'
        c = subprocess.run(['swiftc', str(LAB/'build70_ev_fd_quarantine.swift'),
                            '-o', str(cls.binary)], capture_output=True, text=True, timeout=120)
        if c.returncode:
            raise RuntimeError(c.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.compiler.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wr_fj_synthetic_')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        seed_full_v1(self.root)
        validate_shadow_pair(self.root)
        self.app = self.root/'synthetic_app'
        self.chapter = self.app/'Downloads'/'s'/'m'/'c'
        self.chapter.mkdir(parents=True)
        self.page = self.chapter/'page-00000.bin'
        self.original = b'FJ synthetic completed page - do not delete'
        self.page.write_bytes(self.original)
        (self.app/'Quarantine').mkdir()
        self.lab = FBShadowCopyBridge(self.root, self.binary, sealed_only=True)
        self.addCleanup(self.lab.close)
        self.legacy_before = capture_legacy(self.lab.db)

    def make_copy(self, *, crash_at=None):
        if crash_at is not None:
            with self.assertRaises(FBInterrupted):
                self.lab.prepare_single(1, confirmed=True, crash_at=crash_at)
        else:
            self.assertEqual(self.lab.prepare_single(1, confirmed=True), (1,))
        name = self.lab.db.execute('SELECT snapshot_name FROM offline_copy_journal').fetchone()[0]
        return self.app/'Quarantine'/name

    def run_audit(self, **kwargs):
        return paired_audit(self.root, self.binary, **kwargs)

    def unchanged_rows(self):
        self.assertEqual(capture_legacy(self.lab.db), self.legacy_before)
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM downloads').fetchone(), (1,))
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE internal_id=1').fetchone(), (1,))
        self.assertEqual(self.page.read_bytes(), self.original)

    def test_01_valid_pair_is_only_observed_not_authorized(self):
        self.make_copy()
        report=self.run_audit()
        self.assertEqual((report.entries,report.paired_observations,report.requires_review),(1,1,0))
        self.assertEqual(report.reasons,(('paired_observation_only',1),))
        self.assertFalse(report.can_delete or report.can_restore or report.can_purge or report.can_mark_downloaded)
        self.unchanged_rows()

    def test_02_receipt_and_pages_are_verified(self):
        (self.chapter/'.webreader-completion-v1').write_bytes(b'WR-OFFLINE-COMPLETE-V1:1\n')
        self.make_copy()
        self.assertEqual(self.run_audit().paired_observations,1)
        self.unchanged_rows()

    def test_03_prepared_with_no_copy_requires_review(self):
        self.make_copy(crash_at='after_intent')
        self.assertEqual(self.run_audit().requires_review,1)
        self.unchanged_rows()

    def test_04_copy_created_but_sql_not_committed_requires_review(self):
        self.make_copy(crash_at='after_snapshot')
        self.assertEqual(self.run_audit().paired_observations,0)
        self.unchanged_rows()

    def test_05_needs_review_cannot_be_certified(self):
        self.make_copy()
        self.lab.db.execute("UPDATE offline_copy_journal SET state='needs_review'")
        self.assertEqual(self.run_audit().requires_review,1)

    def test_06_journal_owner_mismatch_requires_review(self):
        self.make_copy()
        self.lab.db.execute("UPDATE offline_copy_journal SET source_id='unexpected'")
        self.assertEqual(self.run_audit().requires_review,1)

    def test_07_sql_download_state_mismatch_requires_review(self):
        self.make_copy()
        self.lab.db.execute("UPDATE downloads SET state='paused'")
        self.assertEqual(self.run_audit().requires_review,1)

    def test_08_sql_downloaded_bit_mismatch_requires_review(self):
        self.make_copy()
        self.lab.db.execute('UPDATE chapters SET downloaded=0')
        self.assertEqual(self.run_audit().requires_review,1)

    def test_09_snapshot_page_corruption_detected(self):
        dest=self.make_copy()
        (dest/'page-00000.bin').write_bytes(b'different bytes')
        self.assertEqual(self.run_audit().paired_observations,0)
        self.unchanged_rows()

    def test_10_source_page_corruption_detected(self):
        self.make_copy()
        self.page.write_bytes(b'changed after snapshot')
        self.assertEqual(self.run_audit().paired_observations,0)

    def test_11_missing_snapshot_detected(self):
        dest=self.make_copy()
        dest.rename(dest.with_name('hold_'+dest.name))
        self.assertEqual(self.run_audit().paired_observations,0)
        self.unchanged_rows()

    def test_12_source_basename_swap_does_not_copy_foreign(self):
        self.make_copy()
        moved=self.chapter.with_name('c_original')
        self.chapter.rename(moved)
        self.chapter.mkdir()
        (self.chapter/'page-00000.bin').write_bytes(b'foreign page')
        self.assertEqual(self.run_audit().paired_observations,0)
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'foreign page')
        self.assertEqual((moved/'page-00000.bin').read_bytes(),self.original)

    def test_13_source_symlink_is_rejected(self):
        self.make_copy()
        moved=self.chapter.with_name('original_folder')
        self.chapter.rename(moved)
        self.chapter.symlink_to(moved,target_is_directory=True)
        self.assertEqual(self.run_audit().paired_observations,0)

    def test_14_snapshot_symlink_is_rejected(self):
        dest=self.make_copy()
        moved=dest.with_name('moved_copy')
        dest.rename(moved)
        dest.symlink_to(moved,target_is_directory=True)
        self.assertEqual(self.run_audit().paired_observations,0)

    def test_15_hardlinked_page_after_snapshot_is_rejected(self):
        self.make_copy()
        os.link(self.page,self.chapter/'alias.bin')
        self.assertEqual(self.run_audit().paired_observations,0)

    def test_16_private_plan_appearing_after_copy_is_rejected(self):
        self.make_copy()
        (self.chapter/'_download-plan.json').write_bytes(b'FI fake token=deadbeef')
        self.assertEqual(self.run_audit().paired_observations,0)

    def test_17_db_drift_between_fd_and_next_sql_is_rejected(self):
        self.make_copy()
        def drift(_):
            self.lab.db.execute("UPDATE offline_copy_journal SET state='needs_review'")
        result=self.run_audit(after_first_native=drift)
        self.assertEqual(result.paired_observations,0)
        self.assertIn(('journal_or_owner_changed',1),result.reasons)

    def test_18_file_drift_between_two_fd_checks_is_rejected(self):
        dest=self.make_copy()
        def drift(_): (dest/'page-00000.bin').write_bytes(b'adversarial replacement')
        result=self.run_audit(after_second_sql=drift)
        self.assertEqual(result.paired_observations,0)
        self.assertIn(('second_fd_verification_failed',1),result.reasons)
        self.unchanged_rows()

    def test_19_source_inplace_drift_after_first_check_is_rejected(self):
        self.make_copy()
        def drift(_): self.page.write_bytes(b'adversarial source changed')
        self.assertEqual(self.run_audit(after_first_native=drift).paired_observations,0)

    def test_20_db_row_insertion_during_observation_refuses_all(self):
        self.make_copy()
        def drift(_):
            self.lab.db.execute("UPDATE offline_copy_journal SET reason='changed'")
        result=self.run_audit(after_second_sql=drift)
        self.assertEqual(result.paired_observations,0)
        self.assertIn(('journal_membership_or_state_changed',1),result.reasons)

    def test_21_marked_root_is_required(self):
        self.make_copy()
        (self.root/'.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(FJUnsafe): self.run_audit()

    def test_22_future_db_schema_rejected_without_migration(self):
        self.make_copy()
        self.lab.db.execute('PRAGMA user_version=3')
        with self.assertRaises(FJUnsafe): self.run_audit()

    def test_23_untrusted_binary_symlink_refused(self):
        self.make_copy()
        fake=self.root/'fake-swift'
        fake.symlink_to(self.binary)
        with self.assertRaises(FJUnsafe): paired_audit(self.root,fake)

    def test_24_bounded_native_budget_never_authorizes(self):
        self.make_copy()
        with patch.object(fj,'MAX_NATIVE_CHECKS',0):
            result=self.run_audit()
        self.assertEqual(result.requires_review,1)
        self.assertIn(('audit_budget_exceeded',1),result.reasons)

    def test_25_journal_snapshot_name_not_matching_operation_is_untrusted(self):
        dest=self.make_copy()
        self.lab.db.execute("UPDATE offline_copy_journal SET operation_id='"+'f'*32+"'")
        self.assertEqual(self.run_audit().paired_observations,0)

    def test_26_absent_shadow_or_unsafe_file_refused(self):
        self.make_copy()
        self.lab.close()
        self.shadow=self.app/'shadow_library_v2.sqlite'
        if self.shadow.exists():
            self.shadow.rename(self.app/'reserved_original.sqlite')
        with self.assertRaises(FJUnsafe):self.run_audit()

    def test_27_wal_uncommitted_journal_drift_does_not_leak(self):
        self.make_copy()
        writer=sqlite3.connect(self.app/'shadow_library_v2.sqlite', isolation_level=None, timeout=.1)
        try:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE offline_copy_journal SET state='needs_review'")
            x=self.run_audit()
            self.assertEqual(x.paired_observations,1)  # last committed DB view only
            writer.execute('COMMIT')
            self.assertEqual(self.run_audit().paired_observations,0)
        finally:
            if writer.in_transaction:writer.rollback()
            writer.close()

    def test_28_unexpected_schema_columns_fail_closed(self):
        self.make_copy()
        self.lab.db.execute('ALTER TABLE offline_copy_journal ADD COLUMN surprising TEXT')
        with self.assertRaises(FJUnsafe):self.run_audit()

    def test_29_auditor_does_not_change_journal_or_legacy_rows(self):
        self.make_copy()
        before=self.lab.db.execute('SELECT * FROM offline_copy_journal').fetchall()
        first=self.run_audit();second=self.run_audit()
        self.assertEqual(first,second)
        self.assertEqual(self.lab.db.execute('SELECT * FROM offline_copy_journal').fetchall(),before)
        self.unchanged_rows()

    def test_30_binary_with_invalid_json_cannot_certify(self):
        self.make_copy()
        stub=self.root/'fake-executable'
        stub.write_text('#!/bin/sh\necho garbage\n')
        stub.chmod(0o700)
        result=paired_audit(self.root,stub)
        self.assertEqual(result.requires_review,1)


if __name__=='__main__': unittest.main()
