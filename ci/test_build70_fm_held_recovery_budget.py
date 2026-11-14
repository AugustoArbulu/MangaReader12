#!/usr/bin/env python3
"""FM adversarial regressions: only temporary EV-marked sample files."""
from pathlib import Path
from unittest.mock import patch
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
LAB = HERE / 'labs' / 'webreader-ev-fd' / 'ci'
sys.path[:0] = [str(HERE),str(LAB)]
from build70_fa_full_schema_shadow import seed_full_v1, validate_shadow_pair, capture_legacy
from build70_fb_full_shadow_copy_bridge import FBShadowCopyBridge, FBInterrupted
from build70_fl_monotonic_shadow import migrate_disposable_copy, inspect_disposable_version_clock
from build70_fj_paired_readonly_reconciliation import paired_audit
import build70_fm_held_recovery_budget as fm

class FMHeldRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('swiftc'):
            raise unittest.SkipTest('Swift compiler absent')
        cls.compiler = tempfile.TemporaryDirectory(prefix='fm_native_compiler_')
        cls.binary = Path(cls.compiler.name) / 'native_fm'
        c = subprocess.run(['swiftc',str(LAB/'build70_ev_fd_quarantine.swift'),
                            '-o',str(cls.binary)],capture_output=True,text=True,timeout=120)
        if c.returncode:
            raise RuntimeError(c.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.compiler.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='fm_disposable_')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        seed_full_v1(self.root)
        validate_shadow_pair(self.root)
        self.app = self.root / 'synthetic_app'
        self.chapter = self.app/'Downloads/s/m/c'
        self.chapter.mkdir(parents=True)
        self.page = self.chapter/'page-00000.bin'
        self.original = b'FM synthetic page image payload only' * 12
        self.page.write_bytes(self.original)
        (self.app/'Quarantine').mkdir()
        self.lab = FBShadowCopyBridge(self.root,self.binary,sealed_only=True)
        self.addCleanup(self.lab.close)
        self.legacy = capture_legacy(self.lab.db)
        self.snapshot = None

    def copied(self):
        self.assertEqual(self.lab.prepare_single(1,confirmed=True),(1,))
        name = self.lab.db.execute('SELECT snapshot_name FROM offline_copy_journal').fetchone()[0]
        self.snapshot = self.app/'Quarantine'/name
        migrate_disposable_copy(self.root)
        return self.snapshot

    def native(self,mode, expected=None):
        # This invokes only the disposable Swift binary, never the installed app.
        dest=self.snapshot.name if self.snapshot else 'ev_'+'0'*32
        args=[str(self.binary),mode,str(self.root),'s','m','c',dest]
        if expected is not None:args.extend(expected)
        return subprocess.run(args,text=True,capture_output=True,timeout=30)

    def identity(self):
        row = self.lab.db.execute('SELECT source_device,source_inode FROM offline_copy_journal').fetchone()
        return row

    def audit(self,**kw):return fm.audit_held_recovery(self.root,self.binary,**kw)

    def flags(self,report):
        self.assertFalse(report.can_delete or report.can_purge or report.can_restore or
                         report.can_retire_downloads or report.source_inode_cas_available or
                         report.source_stays_pinned_after_return)

    def unchanged(self):
        self.assertEqual(capture_legacy(self.lab.db),self.legacy)
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE internal_id=1').fetchone(),(1,))
        self.assertEqual(self.page.read_bytes(),self.original)

    def test_01_pinned_pair_verifies_existing_sealed_copy(self):
        self.copied()
        x=self.native('holdverifysealed',self.identity())
        self.assertEqual(x.returncode,0,x.stderr)
        self.assertIn('"copy_verified"',x.stdout)
        self.unchanged()

    def test_02_budget_reports_real_bytes_and_free_space(self):
        import json
        x=self.native('budgetsealed')
        self.assertEqual(x.returncode,0,x.stderr)
        j=json.loads(x.stdout)
        self.assertEqual((j['status'],j['bytes'],j['pages']),('observed',len(self.original),1))
        self.assertGreater(j['free_bytes'],fm.MIN_RESERVE)

    def test_03_recovery_two_held_reads_same_owner(self):
        self.copied()
        out=self.audit()
        self.assertEqual((out.entries,out.held_matches,out.needs_review),(1,1,0))
        self.assertEqual(out.observed_snapshot_bytes,len(self.original))
        self.flags(out);self.unchanged()

    def test_04_quota_preview_is_not_copy_authority(self):
        out=fm.preview_quota(self.root,self.binary,(('s','m','c'),))
        self.assertEqual(out.estimate_bytes,len(self.original))
        self.assertTrue(out.within_advisory_budget)
        self.assertFalse(out.can_copy or out.can_delete)
        self.assertFalse((self.app/'Quarantine'/('ev_'+('0'*32))).exists())

    def test_05_budget_empty_list_cannot_copy(self):
        q=fm.preview_quota(self.root,self.binary,())
        self.assertEqual((q.entries,q.estimate_bytes),(0,0))
        self.assertFalse(q.within_advisory_budget or q.can_copy)

    def test_06_duplicate_quota_owner_rejected(self):
        with self.assertRaises(fm.FMUnsafe):
            fm.preview_quota(self.root,self.binary,(('s','m','c'),('s','m','c')))

    def test_07_quota_owner_traversal_rejected(self):
        for name in ('..','/tmp','evil/slash',''):
            with self.subTest(name=name),self.assertRaises(fm.FMUnsafe):
                fm.preview_quota(self.root,self.binary,(('s','m',name),))

    def test_08_too_many_quota_entries_rejected(self):
        with self.assertRaises(fm.FMUnsafe):
            fm.preview_quota(self.root,self.binary,tuple(('s','m',f'c{n}') for n in range(17)))

    def test_09_invalid_non_tuple_selection_rejected(self):
        for invalid in ([['s','m','c']],(12,),None):
            with self.subTest(invalid=invalid),self.assertRaises((fm.FMUnsafe,TypeError)):
                fm.preview_quota(self.root,self.binary,invalid)

    def test_10_completed_plan_metadata_is_not_duplicated_or_budgeted(self):
        (self.chapter/'_download-plan.json').write_text('private URL token')
        self.assertNotEqual(self.native('budgetsealed').returncode,0)
        with self.assertRaises(fm.FMUnsafe):
            fm.preview_quota(self.root,self.binary,(('s','m','c'),))

    def test_11_receipt_mismatch_is_rejected(self):
        (self.chapter/'.webreader-completion-v1').write_bytes(b'WR-OFFLINE-COMPLETE-V1:2\n')
        self.assertNotEqual(self.native('budgetsealed').returncode,0)

    def test_12_valid_receipt_counted_in_budget(self):
        import json
        receipt=b'WR-OFFLINE-COMPLETE-V1:1\n'
        (self.chapter/'.webreader-completion-v1').write_bytes(receipt)
        j=json.loads(self.native('budgetsealed').stdout)
        self.assertEqual(j['bytes'],len(self.original)+len(receipt))

    def test_13_sparse_pages_rejected(self):
        (self.chapter/'page-00002.bin').write_bytes(b'gap')
        self.assertNotEqual(self.native('budgetsealed').returncode,0)

    def test_14_hardlinked_page_rejected(self):
        os.link(self.page,self.chapter/'page-00001.bin')
        self.assertNotEqual(self.native('budgetsealed').returncode,0)

    def test_15_symlink_source_rejected_no_outside_read(self):
        real=self.chapter.with_name('original')
        self.chapter.rename(real)
        self.chapter.symlink_to(real,target_is_directory=True)
        self.assertNotEqual(self.native('budgetsealed').returncode,0)
        self.assertEqual((real/'page-00000.bin').read_bytes(),self.original)

    def test_16_symlink_snapshot_rejected(self):
        self.copied()
        real=self.snapshot.with_name('safe_original')
        self.snapshot.rename(real); self.snapshot.symlink_to(real,target_is_directory=True)
        self.assertNotEqual(self.native('holdverifysealed',self.identity()).returncode,0)
        self.assertEqual((real/'page-00000.bin').read_bytes(),self.original)

    def test_17_snapshot_corruption_rejects_both_held_fds(self):
        self.copied();(self.snapshot/'page-00000.bin').write_bytes(b'BAD')
        out=self.audit()
        self.assertEqual(out.held_matches,0);self.flags(out);self.unchanged()

    def test_18_original_inplace_change_rejects_held_copy(self):
        self.copied();self.page.write_bytes(b'CHANGED')
        self.assertEqual(self.audit().held_matches,0)

    def test_19_v2_db_drift_after_v3_snapshot_never_matches(self):
        self.copied();self.lab.db.execute("UPDATE offline_copy_journal SET reason='diverged'")
        self.assertEqual(self.audit().held_matches,0)

    def test_20_v3_clock_aba_during_hold_is_detected(self):
        self.copied()
        def aba(_):
            with sqlite3.connect(self.app/'fl_shadow_v3.sqlite') as db:
                db.execute("UPDATE offline_copy_journal SET state='needs_review'")
                db.execute("UPDATE offline_copy_journal SET state='copy_verified'")
        out=self.audit(after_hold=aba)
        self.assertEqual(out.held_matches,0)
        self.assertIn('journal_or_cooperative_generation_drift',dict(out.reasons))

    def test_21_v3_trigger_missing_requires_manual_review(self):
        self.copied()
        with sqlite3.connect(self.app/'fl_shadow_v3.sqlite') as db:
            db.execute('DROP TRIGGER fl_journal_on_update')
        with self.assertRaises(Exception):self.audit()

    def test_22_future_v3_schema_rejected(self):
        self.copied()
        with sqlite3.connect(self.app/'fl_shadow_v3.sqlite') as db:
            db.execute('PRAGMA user_version=4')
        with self.assertRaises(Exception):self.audit()

    def test_23_v2_absent_journal_is_manual_review(self):
        # No v3 until manually migrated, never create a DB on inspection.
        with self.assertRaises(Exception):self.audit()
        self.assertFalse((self.app/'fl_shadow_v3.sqlite').exists())

    def test_24_v2_pending_journal_stays_review(self):
        with self.assertRaises(FBInterrupted):
            self.lab.prepare_single(1,confirmed=True,crash_at='after_intent')
        migrate_disposable_copy(self.root)
        out=self.audit()
        self.assertEqual(out.held_matches,0);self.flags(out)

    def test_25_quota_spoof_low_free_space_never_admitted(self):
        original=fm._call_native
        def fake(*args,**kwargs):
            r=original(*args,**kwargs)
            if args[2]=='budgetsealed':r['free_bytes']=0
            return r
        with patch.object(fm,'_call_native',side_effect=fake):
            x=fm.preview_quota(self.root,self.binary,(('s','m','c'),))
        self.assertFalse(x.within_advisory_budget or x.can_copy)

    def test_26_quota_exceed_fake_native_rejected(self):
        original=fm._call_native
        def fake(*args,**kwargs):
            r=original(*args,**kwargs)
            if args[2]=='budgetsealed':r['bytes']=fm.CHAPTER_QUOTA+1
            return r
        with patch.object(fm,'_call_native',side_effect=fake):
            with self.assertRaises(fm.FMUnsafe):
                fm.preview_quota(self.root,self.binary,(('s','m','c'),))

    def test_27_metadata_reversion_clock_still_detects_aba(self):
        self.copied();before=inspect_disposable_version_clock(self.root)
        def aba(_):
            with sqlite3.connect(self.app/'fl_shadow_v3.sqlite') as db:
                db.execute("UPDATE offline_copy_journal SET reason='A'")
                db.execute("UPDATE offline_copy_journal SET reason=''")
        out=self.audit(after_budget=aba)
        self.assertEqual(out.held_matches,0)
        self.assertGreater(inspect_disposable_version_clock(self.root).event_ceiling,before.event_ceiling)

    def test_28_last_observation_still_has_unavoidable_race(self):
        self.copied()
        out=self.audit(after_final=lambda _:(self.snapshot/'page-00000.bin').write_bytes(b'LATE'))
        self.assertEqual(out.held_matches,1)
        self.flags(out)
        self.assertEqual(paired_audit(self.root,self.binary).paired_observations,0)

    def test_29_no_del_or_purge_in_fm_code(self):
        code=Path(fm.__file__).read_text()
        for forbidden in ('os.unlink(', 'shutil.rmtree(', 'unlinkat(', 'renameat(',
                          'DELETE FROM downloads','UPDATE chapters SET downloaded', 'can_delete: bool = True'):
            self.assertNotIn(forbidden,code)

    def test_30_marked_root_absent_refuses_native_operations(self):
        (self.root/'.webreader_ev_disposable_marker').unlink()
        self.assertNotEqual(self.native('budgetsealed').returncode,0)
        with self.assertRaises(Exception):self.audit()

    def test_31_extra_page_after_copy_rejected(self):
        self.copied();(self.chapter/'page-00001.bin').write_bytes(b'unexpected')
        self.assertEqual(self.audit().held_matches,0)

    def test_32_snapshot_plan_injection_rejected(self):
        self.copied();(self.snapshot/'_download-plan.json').write_bytes(b'private')
        self.assertEqual(self.audit().held_matches,0)

    def test_33_directory_swap_between_process_reads_detected(self):
        self.copied();old=self.chapter.with_name('original_pinned')
        def mutate(_):
            self.chapter.rename(old);self.chapter.mkdir()
            self.page=self.chapter/'page-00000.bin';self.page.write_bytes(self.original)
        out=self.audit(after_hold=mutate)
        self.assertEqual(out.held_matches,0)
        self.assertEqual((old/'page-00000.bin').read_bytes(),self.original)

    def test_34_held_snapshot_no_mutation_of_sql(self):
        self.copied();rows=list(self.lab.db.execute('SELECT * FROM offline_copy_journal'))
        self.audit()
        self.assertEqual(rows,list(self.lab.db.execute('SELECT * FROM offline_copy_journal')))
        self.unchanged()

    def test_35_swift_budget_checks_no_data_creation(self):
        code=(LAB/'build70_ev_fd_quarantine.swift').read_text()
        segment=code.split('// BEGIN BUILD70_FM_PINNED_READONLY_QUOTA',1)[1].split('// END BUILD70_FM_PINNED_READONLY_QUOTA',1)[0]
        self.assertIn('openat(directory',segment)
        self.assertIn('O_RDONLY | O_NOFOLLOW',segment)
        self.assertIn('fstatvfs(quarantine',segment)
        self.assertNotIn('O_CREAT',segment)
        self.assertNotIn('unlinkat(',segment)

    def _race_after_held_directories(self, *, swap_snapshot=False):
        self.copied()
        env=os.environ.copy()
        env['WEBREADER_EZ_RACE_GATE']='1'
        args=[str(self.binary),'holdverifysealed',str(self.root),'s','m','c',
              self.snapshot.name,*self.identity()]
        process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 text=True,env=env)
        try:
            ready=self.root/'.ez_before_copy_ready'
            deadline=time.monotonic()+4
            while not ready.exists() and process.poll() is None and time.monotonic()<deadline:
                time.sleep(.015)
            self.assertTrue(ready.exists(), 'native held-FD gate was not reached')
            if swap_snapshot:
                replaced=self.snapshot.with_name('saved_snapshot_inode')
                self.snapshot.rename(replaced)
                self.snapshot.mkdir()
                foreign=self.snapshot/'page-00000.bin'
            else:
                replaced=self.chapter.with_name('saved_source_inode')
                self.chapter.rename(replaced)
                self.chapter.mkdir()
                foreign=self.chapter/'page-00000.bin'
            foreign.write_bytes(b'FOREIGN NEVER READ OR DELETED')
            (self.root/'.ez_before_copy_go').write_bytes(b'1')
            stdout,stderr=process.communicate(timeout=12)
            self.assertNotEqual(process.returncode,0,(stdout,stderr))
            self.assertEqual(foreign.read_bytes(),b'FOREIGN NEVER READ OR DELETED')
            self.assertEqual((replaced/'page-00000.bin').read_bytes(),self.original)
        finally:
            if process.poll() is None:
                process.kill();process.communicate(timeout=2)

    def test_36_swap_source_after_fds_open_is_rejected_without_foreign_read(self):
        self._race_after_held_directories(swap_snapshot=False)

    def test_37_swap_snapshot_after_fds_open_is_rejected_without_foreign_read(self):
        self._race_after_held_directories(swap_snapshot=True)

    def test_38_sparse_total_above_512mib_rejected_before_copy(self):
        self.page.write_bytes(b'x')
        for i in range(27):
            leaf=self.chapter/f'page-{i:05d}.bin'
            with leaf.open('wb') as h:
                h.truncate(19*1024*1024)
        self.assertNotEqual(self.native('budgetsealed').returncode,0)
        self.assertFalse(any((self.app/'Quarantine').iterdir()))

    def test_39_more_than_5000_pages_rejected(self):
        for i in range(1,5001):
            (self.chapter/f'page-{i:05d}.bin').write_bytes(b'x')
        self.assertNotEqual(self.native('budgetsealed').returncode,0)

    def test_40_aggregate_budget_caps_three_large_candidates(self):
        def synthetic(*args,**kwargs):
            return {'status':'observed','device':'1','inode':'2',
                    'pages':100,'bytes':480*1024*1024,
                    'free_bytes':4*1024*1024*1024}
        with patch.object(fm,'_call_native',side_effect=synthetic):
            r=fm.preview_quota(self.root,self.binary,
                 (('s','m','a'),('s','m','b'),('s','m','c')))
        self.assertFalse(r.within_advisory_budget or r.can_copy or r.can_delete)
        self.assertLessEqual(r.estimate_bytes,fm.BATCH_QUOTA)

if __name__ == '__main__':unittest.main()
