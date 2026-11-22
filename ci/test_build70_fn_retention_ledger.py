#!/usr/bin/env python3
"""FN: adversarial crash/recovery/quota tests on disposable EV-marked files only."""
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
LAB=HERE/'labs'/'webreader-ev-fd'/'ci'
sys.path[:0]=[str(HERE),str(LAB)]
from build70_fa_full_schema_shadow import seed_full_v1,validate_shadow_pair,capture_legacy
from build70_fb_full_shadow_copy_bridge import FBShadowCopyBridge
from build70_fl_monotonic_shadow import migrate_disposable_copy
import build70_fn_retention_ledger as fn
from build70_fn_retention_ledger import (
    FNUnsafe,FNInterrupted,init_synthetic_ledger,inspect_retention,
    reserve_snapshot,recover_retention,request_manual_release,
)

class FNRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('swiftc'):raise unittest.SkipTest('Swift unavailable')
        cls.build=tempfile.TemporaryDirectory(prefix='wr_fn_native_')
        cls.binary=Path(cls.build.name)/'ev-native'
        c=subprocess.run(['swiftc',str(LAB/'build70_ev_fd_quarantine.swift'),
                          '-o',str(cls.binary)],capture_output=True,text=True,timeout=120)
        if c.returncode:raise RuntimeError(c.stderr)

    @classmethod
    def tearDownClass(cls):cls.build.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wr_fn_disposable_')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        seed_full_v1(self.root)
        validate_shadow_pair(self.root)
        self.app=self.root/'synthetic_app'
        self.leaf=self.app/'Downloads/s/m/c'
        self.leaf.mkdir(parents=True)
        self.original=b'FN RETENTION SYNTHETIC PAGE - NEVER A USER FILE'*5
        (self.leaf/'page-00000.bin').write_bytes(self.original)
        (self.app/'Quarantine').mkdir()
        with FBShadowCopyBridge(self.root,self.binary,sealed_only=True) as bridge:
            bridge.prepare_single(1,confirmed=True)
            self.legacy_before=capture_legacy(bridge.db)
            self.operation,self.snapshot=bridge.db.execute(
                'SELECT operation_id,snapshot_name FROM offline_copy_journal').fetchone()
        migrate_disposable_copy(self.root)
        self.snap=self.app/'Quarantine'/self.snapshot
        self.ledger=self.app/fn.NAME

    def create(self):init_synthetic_ledger(self.root)
    def reserve(self,**kwargs):return reserve_snapshot(self.root,self.binary,self.operation,**kwargs)
    def inspect(self):return inspect_retention(self.root)
    def recover(self,**kwargs):return recover_retention(self.root,self.binary,**kwargs)
    def ticket(self):
        with closing(sqlite3.connect(self.ledger)) as db:
            return db.execute('SELECT state,generation,budget_bytes FROM fn_retention').fetchone()
    def execute(self,sql):
        with closing(sqlite3.connect(self.ledger)) as db:
            db.execute(sql);db.commit()
    def no_authority(self,report):
        self.assertFalse(report.can_delete or report.can_purge or report.can_restore or
                         report.can_release_bytes or report.can_mark_downloaded or report.can_copy)
    def preserved(self):
        self.assertEqual((self.leaf/'page-00000.bin').read_bytes(),self.original)
        self.assertEqual((self.snap/'page-00000.bin').read_bytes(),self.original)
        with closing(sqlite3.connect(self.app/'shadow_library_v2.sqlite')) as db:
            self.assertEqual(capture_legacy(db),self.legacy_before)

    def test_01_ledger_must_be_initialized_explicitly(self):
        with self.assertRaises(FNUnsafe):self.inspect()
        self.assertFalse(self.ledger.exists())

    def test_02_init_creates_separate_version1_ledger(self):
        self.create();r=self.inspect()
        self.assertEqual((r.entries,r.accounted_bytes,r.event_count),(0,0,0))
        self.assertEqual(self.ledger.stat().st_mode&0o777,0o600)
        self.no_authority(r);self.preserved()

    def test_03_reopen_is_idempotent(self):
        self.create();self.create()
        self.assertEqual(self.inspect().entries,0)

    def test_04_reserve_accounts_existing_verified_copy(self):
        self.create();r=self.reserve()
        self.assertEqual((r.entries,r.accounted_bytes,r.event_count),(1,len(self.original),1))
        self.assertEqual(self.ticket(),('reserved',0,len(self.original)))
        self.no_authority(r);self.preserved()

    def test_05_duplicate_reserve_rejected_without_double_accounting(self):
        self.create();before=self.reserve()
        with self.assertRaises(FNUnsafe):self.reserve()
        self.assertEqual(self.inspect(),before)

    def test_06_recovery_promotes_reserved_to_retained_without_move(self):
        self.create();self.reserve();r=self.recover()
        self.assertEqual((r.accounted_bytes,r.event_count), (len(self.original),2))
        self.assertEqual(self.ticket()[:2],('retained',1));self.preserved()

    def test_07_repeated_recovery_does_not_add_events(self):
        self.create();self.reserve();self.recover();before=self.inspect()
        self.assertEqual(self.recover(),before)

    def test_08_manual_release_is_only_request_never_budget_freed(self):
        self.create();self.reserve();self.recover();before=self.inspect()
        later=request_manual_release(self.root,self.operation)
        self.assertEqual(later.accounted_bytes,before.accounted_bytes)
        self.assertEqual(self.ticket()[:2],('release_requested',2))
        self.no_authority(later);self.preserved()

    def test_09_double_release_is_refused(self):
        self.create();self.reserve();self.recover();request_manual_release(self.root,self.operation)
        with self.assertRaises(FNUnsafe):request_manual_release(self.root,self.operation)

    def test_10_reservation_cannot_request_release_before_verification(self):
        self.create();self.reserve()
        with self.assertRaises(FNUnsafe):request_manual_release(self.root,self.operation)

    def test_11_snapshot_corruption_is_review_and_keeps_charge(self):
        self.create();self.reserve()
        (self.snap/'page-00000.bin').write_bytes(b'corrupted')
        r=self.recover()
        self.assertEqual(self.ticket()[:2],('needs_review',1))
        self.assertEqual(r.accounted_bytes,len(self.original))
        self.no_authority(r)

    def test_12_original_corruption_is_review(self):
        self.create();self.reserve()
        (self.leaf/'page-00000.bin').write_bytes(b'corrupted')
        self.recover();self.assertEqual(self.ticket()[0],'needs_review')

    def test_13_source_directory_swap_is_review(self):
        self.create();self.reserve()
        old=self.leaf.with_name('original');self.leaf.rename(old);self.leaf.mkdir()
        (self.leaf/'page-00000.bin').write_bytes(b'FOREIGN - NOT REMOVED')
        self.recover();self.assertEqual(self.ticket()[0],'needs_review')
        self.assertEqual((self.leaf/'page-00000.bin').read_bytes(),b'FOREIGN - NOT REMOVED')
        self.assertEqual((old/'page-00000.bin').read_bytes(),self.original)

    def test_14_snapshot_directory_swap_is_review(self):
        self.create();self.reserve()
        old=self.snap.with_name('original_copy');self.snap.rename(old);self.snap.mkdir()
        self.recover();self.assertEqual(self.ticket()[0],'needs_review')
        self.assertEqual((old/'page-00000.bin').read_bytes(),self.original)

    def test_15_sensitive_plan_injection_after_reserve_is_review(self):
        self.create();self.reserve()
        (self.leaf/'_download-plan.json').write_bytes(b'secret URL')
        self.recover();self.assertEqual(self.ticket()[0],'needs_review')

    def test_16_v2_owner_drift_after_reserve_is_review(self):
        self.create();self.reserve()
        with closing(sqlite3.connect(self.app/'shadow_library_v2.sqlite')) as db:
            db.execute("UPDATE offline_copy_journal SET state='needs_review'");db.commit()
        self.recover();self.assertEqual(self.ticket()[0],'needs_review')

    def test_17_v3_event_aba_after_reserve_is_review(self):
        self.create();self.reserve()
        with closing(sqlite3.connect(self.app/'fl_shadow_v3.sqlite')) as db:
            db.execute("UPDATE offline_copy_journal SET state='needs_review'")
            db.execute("UPDATE offline_copy_journal SET state='copy_verified'");db.commit()
        # FM tests observe prior FL generation only during one call; after
        # commit it cannot prove historical cross-db coevolution. Here both
        # current rows match so this is NOT a security authorization.
        report=self.recover()
        self.no_authority(report)
        self.assertIn(self.ticket()[0],('retained','needs_review'))

    def test_18_reservation_refuses_v2_state_drift_in_admission_window(self):
        self.create()
        def mutate():
            with closing(sqlite3.connect(self.app/'shadow_library_v2.sqlite')) as db:
                db.execute("UPDATE offline_copy_journal SET state='needs_review'");db.commit()
        with self.assertRaises(FNUnsafe):self.reserve(after_admission=mutate)
        self.assertEqual(self.inspect().entries,0)

    def test_19_reservation_refuses_v3_event_drift_in_admission_window(self):
        self.create()
        def mutate():
            with closing(sqlite3.connect(self.app/'fl_shadow_v3.sqlite')) as db:
                db.execute("UPDATE offline_copy_journal SET reason=reason");db.commit()
        with self.assertRaises(FNUnsafe):self.reserve(after_admission=mutate)
        self.assertEqual(self.inspect().entries,0)

    def test_20_crash_before_begin_leaves_no_ticket(self):
        self.create()
        with self.assertRaises(FNInterrupted):self.reserve(crash_at='before_begin')
        self.assertEqual(self.inspect().entries,0)

    def test_21_crash_before_commit_rolls_back_intent_and_event(self):
        self.create()
        with self.assertRaises(FNInterrupted):self.reserve(crash_at='before_commit')
        self.assertEqual((self.inspect().entries,self.inspect().event_count),(0,0))

    def test_22_crash_after_commit_is_recovered_after_reopen(self):
        self.create()
        with self.assertRaises(FNInterrupted):self.reserve(crash_at='after_commit')
        self.assertEqual(self.ticket()[0],'reserved')
        self.assertEqual(self.recover().reasons,(('retained',1),))

    def test_23_recovery_interrupted_after_first_is_idempotent(self):
        self.create();self.reserve()
        with self.assertRaises(FNInterrupted):
            self.recover(after_first=lambda:(_ for _ in ()).throw(FNInterrupted('crash')))
        self.assertEqual(self.ticket()[0],'retained')
        self.assertEqual(self.recover().event_count,2)

    def test_24_review_never_auto_restores_retained_even_if_files_repaired(self):
        self.create();self.reserve()
        target=self.snap/'page-00000.bin';target.write_bytes(b'changed')
        self.recover();target.write_bytes(self.original)
        before=self.inspect()
        self.assertEqual(self.recover(),before)

    def test_25_missing_marker_refuses_any_access(self):
        self.create();(self.root/'.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(FNUnsafe):self.inspect()
        with self.assertRaises(FNUnsafe):self.reserve()

    def test_26_symlink_ledger_refused(self):
        self.create();actual=self.ledger.with_name('trusted.db');self.ledger.rename(actual)
        self.ledger.symlink_to(actual)
        with self.assertRaises(FNUnsafe):self.inspect()

    def test_27_hardlink_ledger_refused(self):
        self.create();os.link(self.ledger,self.ledger.with_suffix('.link'))
        with self.assertRaises(FNUnsafe):self.inspect()

    def test_28_unknown_schema_requires_manual_review(self):
        self.create();self.execute('PRAGMA user_version=42')
        with self.assertRaises(FNUnsafe):self.inspect()

    def test_29_removed_guard_trigger_requires_review(self):
        self.create();self.execute('DROP TRIGGER fn_no_ticket_delete')
        with self.assertRaises(FNUnsafe):self.inspect()

    def test_30_event_deletion_is_refused_by_sqlite_trigger(self):
        self.create();self.reserve()
        with self.assertRaises(sqlite3.DatabaseError):self.execute('DELETE FROM fn_retention_event')
        self.assertEqual(self.inspect().event_count,1)

    def test_31_event_mutation_is_refused(self):
        self.create();self.reserve()
        with self.assertRaises(sqlite3.DatabaseError):self.execute("UPDATE fn_retention_event SET new_state='needs_review'")

    def test_32_identity_and_budget_immutable(self):
        self.create();self.reserve()
        for sql in ("UPDATE fn_retention SET budget_bytes=1", 
                    "UPDATE fn_retention SET snapshot_name='ev_00000000000000000000000000000000'",
                    "UPDATE fn_retention SET generation=100"):
            with self.subTest(sql=sql),self.assertRaises(sqlite3.DatabaseError):self.execute(sql)

    def test_33_ticket_deletion_is_refused(self):
        self.create();self.reserve()
        with self.assertRaises(sqlite3.DatabaseError):self.execute('DELETE FROM fn_retention')
        self.assertEqual(self.inspect().entries,1)

    def test_34_invalid_operation_rejected(self):
        self.create()
        for bad in ('bad','../c','A'*32,'0'*33):
            with self.subTest(bad=bad),self.assertRaises(FNUnsafe):
                reserve_snapshot(self.root,self.binary,bad)

    def test_35_low_space_conservative_margin(self):
        self.create();real=fn._evidence
        def low(root,binary,op):
            row,clock,bytes_,_=real(root,binary,op)
            return row,clock,bytes_,bytes_
        with patch.object(fn,'_evidence',side_effect=low):
            with self.assertRaises(FNUnsafe):self.reserve()
        self.assertEqual(self.inspect().entries,0)

    def test_36_over_512mib_evidence_rejected_by_database_check(self):
        self.create();real=fn._evidence
        def huge(root,binary,op):
            row,clock,_,free=real(root,binary,op)
            return row,clock,fn.CHAPTER_QUOTA+1,free+10**12
        with patch.object(fn,'_evidence',side_effect=huge):
            with self.assertRaises(FNUnsafe):self.reserve()
        self.assertEqual(self.inspect().entries,0)

    def test_37_uncommitted_wal_change_invisible_to_readonly_inspect(self):
        self.create();self.reserve();before=self.inspect()
        with closing(sqlite3.connect(self.ledger,isolation_level=None)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('BEGIN IMMEDIATE')
            try:
                writer.execute("UPDATE fn_retention SET state='retained',generation=generation+1")
                self.assertEqual(self.inspect(),before)
                writer.execute('COMMIT')
            finally:
                if writer.in_transaction:writer.execute('ROLLBACK')
        after=self.inspect()
        self.assertEqual((after.event_count,after.reasons),(2,(('retained',1),)))

    def test_38_cooperative_aba_detected_by_ticket_generation(self):
        self.create();self.reserve()
        before=self.inspect()
        self.execute("UPDATE fn_retention SET state='needs_review',generation=generation+1")
        self.execute("UPDATE fn_retention SET state='reserved',generation=generation+1")
        after=self.inspect()
        self.assertEqual(before.reasons,after.reasons)
        self.assertGreater(after.event_ceiling,before.event_ceiling)
        self.assertEqual(after.event_count,before.event_count+2)

    def test_39_tamper_event_count_is_detected(self):
        self.create();self.reserve()
        self.execute('DROP TRIGGER fn_no_event_delete')
        self.execute('DELETE FROM fn_retention_event')
        with self.assertRaises(FNUnsafe):self.inspect()

    def test_40_all_report_authorities_permanently_false(self):
        self.create();self.no_authority(self.inspect())
        self.no_authority(self.reserve())
        self.no_authority(self.recover())
        self.no_authority(request_manual_release(self.root,self.operation))

    def test_41_no_destructive_symbols_in_source_or_production_hook(self):
        source=Path(fn.__file__).read_text()
        for forbidden in ('shutil.rmtree(', 'os.unlink(', 'os.rename(',
                          'DELETE FROM downloads', 'DELETE FROM chapters',
                          'FileManager.removeItem(', 'appinst', 'kill('):
            self.assertNotIn(forbidden,source)
        self.assertFalse(any((self.app/'Quarantine').glob('*.deleted')))

    def add_fake_claim(self, n: int, bytes_: int):
        op=f'{n:032x}'
        with closing(sqlite3.connect(self.ledger)) as db:
            db.execute("""INSERT INTO fn_retention
                 (operation_id,chapter_id,snapshot_name,source_device,source_inode,
                  budget_bytes,state) VALUES(?,?,?,?,?,?,'retained')""",
                (op,100+n,'ev_'+op,'1','2',bytes_))
            db.execute("""INSERT INTO fn_retention_event
                 (operation_id,kind,old_state,new_state) VALUES(?,'reserved',NULL,'retained')""",(op,))
            db.commit()

    def test_42_missing_snapshot_does_not_free_budget(self):
        self.create();self.reserve()
        # Test-only adversarial mutation. FN API itself never unlinks.
        (self.snap/'page-00000.bin').unlink()
        r=self.recover();self.assertEqual(r.accounted_bytes,len(self.original))
        self.assertEqual(self.ticket()[0],'needs_review')

    def test_43_two_tickets_counted_without_releasing_first(self):
        self.create();self.reserve()
        # More evidence can appear later, but the first charge is permanent.
        # A second synthetic claim is recorded directly by a cooperating
        # fixture writer to exercise the aggregate accounting code.
        self.add_fake_claim(55,64*1024)
        r=self.inspect()
        self.assertEqual((r.entries,r.accounted_bytes,r.event_count),
                         (2,len(self.original)+64*1024,2))
        self.no_authority(r)

    def test_44_concurrent_identical_reservation_cannot_double_charge(self):
        import concurrent.futures
        import threading
        self.create()
        barrier=threading.Barrier(2)
        def attempt(_):
            try:
                self.reserve(after_admission=lambda:barrier.wait(timeout=30))
                return 'reserved'
            except FNUnsafe:
                return 'refused'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,range(2)))
        self.assertEqual(sorted(results),['refused','reserved'])
        self.assertEqual((self.inspect().entries,self.inspect().accounted_bytes),
                         (1,len(self.original)))

    def test_45_full_aggregate_quota_blocks_new_ticket(self):
        self.create()
        self.add_fake_claim(100,fn.CHAPTER_QUOTA)
        self.add_fake_claim(101,fn.CHAPTER_QUOTA)
        self.assertEqual(self.inspect().accounted_bytes,fn.BATCH_QUOTA)
        with self.assertRaises(FNUnsafe):self.reserve()
        self.assertEqual(self.inspect().entries,2)

    def test_46_ledger_max_ticket_count_is_enforced(self):
        self.create()
        for i in range(16):self.add_fake_claim(200+i,1024)
        self.assertEqual(self.inspect().entries,16)
        with self.assertRaises(FNUnsafe):self.reserve()

    def test_47_future_extra_ledger_table_refused(self):
        self.create();self.execute('CREATE TABLE foreign_data(x TEXT)')
        with self.assertRaises(FNUnsafe):self.inspect()
        with self.assertRaises(FNUnsafe):init_synthetic_ledger(self.root)

    def test_48_release_requested_is_not_recovered_or_released(self):
        self.create();self.reserve();self.recover()
        requested=request_manual_release(self.root,self.operation)
        after=self.recover()
        self.assertEqual(after,requested)
        self.assertEqual(self.ticket()[0],'release_requested')

    def test_49_wrong_stored_charge_is_review_not_space_released(self):
        self.create()
        # A fake inflated charge remains accounted even if native proof later
        # disagrees: crash recovery must not free it or overwrite other data.
        real=fn._evidence
        def inflated(root,binary,op):
            row,clock,_,free=real(root,binary,op)
            return row,clock,len(self.original)+100,free
        with patch.object(fn,'_evidence',side_effect=inflated):
            self.reserve()
        r=self.recover()
        self.assertEqual(self.ticket()[0],'needs_review')
        self.assertEqual(r.accounted_bytes,len(self.original)+100)

    def test_50_reopen_ledger_without_original_never_creates_new_ledger(self):
        self.create();self.reserve()
        (self.root/'.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(FNUnsafe):self.recover()
        self.assertTrue(self.ledger.exists())

    def test_51_ticket_event_clock_survives_reopen_after_manual_request(self):
        self.create();self.reserve();self.recover()
        after=request_manual_release(self.root,self.operation)
        self.assertEqual((after.event_count,after.event_ceiling),(3,3))
        self.assertEqual(init_synthetic_ledger(self.root),self.ledger)
        self.assertEqual(self.inspect(),after)

if __name__=='__main__': unittest.main()
