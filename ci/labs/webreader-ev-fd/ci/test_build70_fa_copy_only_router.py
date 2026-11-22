#!/usr/bin/env python3
"""FA — three non-destructive routes coordinated by native Swift copy lab."""
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from build70_ev_recoverable_quarantine_lab import QuarantineLab
from build70_fa_copy_only_router import FACopyOnlyRouter,FARouteUnsafe

class RouteSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=shutil.which('swiftc')
        if compiler is None:raise unittest.SkipTest('Swift required for native test')
        cls.tempbin=tempfile.TemporaryDirectory(prefix='fa_swift_build_')
        cls.binary=Path(cls.tempbin.name)/'synthetic_fd'
        subprocess.run([compiler,str(Path(__file__).with_name('build70_ev_fd_quarantine.swift')),'-o',str(cls.binary)],check=True,capture_output=True,timeout=120)

    @classmethod
    def tearDownClass(cls):cls.tempbin.cleanup()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='fa_router_')
        self.root=Path(self.tmp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        self.lab=QuarantineLab(self.root)
        self.first=self.lab.seed()
        self.lab.close()
        self.router=FACopyOnlyRouter(self.root,self.binary)

    def tearDown(self):
        self.router.close()
        self.tmp.cleanup()

    def seed_second(self):
        path=self.root/'synthetic_app'/'Downloads'/'s'/'m'/'other'
        path.mkdir(parents=True)
        (path/'page-00000.bin').write_bytes(b'SECOND_CHAPTER_PRESERVE')
        self.router.db.execute('INSERT INTO chapters VALUES(2,1)')
        self.router.db.execute("INSERT INTO downloads VALUES(2,'s','m','other')")
        return path

    def assert_unchanged(self):
        self.assertEqual((self.first/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual(self.router.db.execute('SELECT downloaded FROM chapters WHERE id=1').fetchone(),(1,))
        self.assertEqual(self.router.db.execute('SELECT COUNT(*) FROM downloads').fetchone(),(self.router.db.execute('SELECT COUNT(*) FROM chapters').fetchone()[0],))

    def test_single_requires_explicit_consent(self):
        with self.assertRaises(FARouteUnsafe):self.router.prepare_single(1)
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(0,))
        self.assert_unchanged()

    def test_bulk_requires_explicit_consent(self):
        with self.assertRaises(FARouteUnsafe):self.router.prepare_bulk()
        self.assert_unchanged()

    def test_reject_boolean_chapter_id(self):
        with self.assertRaises(FARouteUnsafe):self.router.prepare_single(True,confirmed=True)

    def test_reject_zero_and_negative(self):
        for bad in [0,-3,1.5,'1']:
            with self.subTest(bad=bad),self.assertRaises(FARouteUnsafe):self.router.prepare_single(bad,confirmed=True)

    def test_unknown_chapter_does_not_write(self):
        with self.assertRaises(FARouteUnsafe):self.router.prepare_single(123,confirmed=True)
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(0,))

    def test_single_uses_one_snapshot_no_retirement(self):
        self.assertEqual(self.router.prepare_single(1,confirmed=True),(1,))
        self.assertEqual(self.router.db.execute("SELECT state FROM ez_snapshot_journal").fetchone(),('copy_verified',))
        self.assert_unchanged()

    def test_single_second_attempt_requires_review(self):
        self.router.prepare_single(1,confirmed=True)
        with self.assertRaises(FARouteUnsafe):self.router.prepare_single(1,confirmed=True)
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(1,))
        self.assert_unchanged()

    def test_bulk_preflights_both_before_first_write(self):
        second=self.seed_second()
        (second/'unknown.txt').write_bytes(b'foreign')
        with self.assertRaises(Exception):self.router.prepare_bulk(confirmed=True)
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(0,))
        self.assertEqual(list((self.root/'synthetic_app'/'Quarantine').iterdir()),[])
        self.assert_unchanged()

    def test_bulk_two_chapters_copies_both(self):
        second=self.seed_second()
        self.assertEqual(self.router.prepare_bulk(confirmed=True),(1,2))
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(2,))
        self.assertEqual((second/'page-00000.bin').read_bytes(),b'SECOND_CHAPTER_PRESERVE')
        self.assert_unchanged()

    def test_active_job_blocks_single(self):
        self.router.running_ids=frozenset({1})
        with self.assertRaises(FARouteUnsafe):self.router.prepare_single(1,confirmed=True)
        self.assert_unchanged()

    def test_pending_job_blocks_single(self):
        self.router.pending_ids=frozenset({1})
        with self.assertRaises(FARouteUnsafe):self.router.prepare_single(1,confirmed=True)

    def test_active_job_blocks_even_other_bulk_chapters(self):
        self.seed_second()
        self.router.running_ids=frozenset({101})
        with self.assertRaises(FARouteUnsafe):self.router.prepare_bulk(confirmed=True)
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(0,))

    def test_collision_gate_rejects_casefold_alias(self):
        # SQLite case-sensitive UNIQUE permits the alias; app's canonical
        # path EQ guard must refuse it even without a physical alias.
        self.router.db.execute('INSERT INTO chapters VALUES(2,1)')
        self.router.db.execute("INSERT INTO downloads VALUES(2,'S','m','c')")
        with self.assertRaises(FARouteUnsafe):self.router.prepare_bulk(confirmed=True)
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(0,))

    def test_unrecognized_file_blocks_single(self):
        (self.first/'private.txt').write_bytes(b'private')
        with self.assertRaises(Exception):self.router.prepare_single(1,confirmed=True)
        self.assertEqual((self.first/'private.txt').read_bytes(),b'private')

    def test_symlink_file_blocks_single(self):
        (self.first/'page-00001.bin').symlink_to('page-00000.bin')
        with self.assertRaises(Exception):self.router.prepare_single(1,confirmed=True)
        self.assertFalse(list((self.root/'synthetic_app'/'Quarantine').iterdir()))

    def test_source_missing_reindex_requires_manual_review(self):
        self.first.rename(self.first.with_name('saved-chapter'))
        before=self.router.db.execute('SELECT count(*) FROM downloads').fetchone()
        outcome=self.router.reindex_preview()
        self.assertEqual(outcome[0].status,'needs_review')
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM downloads').fetchone(),before)

    def test_reindex_preview_has_no_database_writes(self):
        before=self.router.db.total_changes
        self.assertEqual(self.router.reindex_preview()[0].status,'source_present')
        self.assertEqual(self.router.db.total_changes,before)
        self.assert_unchanged()

    def test_reindex_reports_copy_verified(self):
        self.router.prepare_single(1,confirmed=True)
        before=self.router.db.total_changes
        self.assertEqual(self.router.reindex_preview()[0].status,'copy_verified')
        self.assertEqual(self.router.db.total_changes,before)

    def test_reindex_corrupt_copy_requires_review_without_state_change(self):
        self.router.prepare_single(1,confirmed=True)
        dest=self.router.db.execute('SELECT dest FROM ez_snapshot_journal').fetchone()[0]
        (self.root/'synthetic_app'/'Quarantine'/dest/'page-00000.bin').write_bytes(b'CORRUPT')
        self.assertEqual(self.router.reindex_preview()[0].status,'needs_review')
        self.assertEqual(self.router.db.execute('SELECT state FROM ez_snapshot_journal').fetchone(),('copy_verified',))
        self.assert_unchanged()

    def test_reindex_partial_intent_requires_review(self):
        self.router.db.execute("INSERT INTO ez_snapshot_journal(op,chapter_id,source,manga,leaf,dest,device,inode,state,confirmed) VALUES(?,?,?,?,?,?,?,?,?,?)",
                               ('a'*32,1,'s','m','c','ev_'+'a'*32,'1','2','prepared','synthetic_explicit_confirm'))
        self.assertEqual(self.router.reindex_preview()[0].status,'needs_review')
        self.assert_unchanged()

    def test_cannot_prepare_bulk_when_prior_snapshot_exists(self):
        self.seed_second()
        self.router.prepare_single(1,confirmed=True)
        with self.assertRaises(FARouteUnsafe):self.router.prepare_bulk(confirmed=True)
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(1,))

    def test_drift_during_bulk_preserves_completed_copy(self):
        second=self.seed_second()
        start=self.router.snapshots.start
        called=[]
        def fault(chapter,*,confirmed):
            called.append(chapter)
            if chapter==1:
                result=start(chapter,confirmed=confirmed)
                (second/'page-00000.bin').write_bytes(b'CHANGED_SECOND')
                return result
            return start(chapter,confirmed=confirmed)
        with patch.object(self.router.snapshots,'start',side_effect=fault):
            with self.assertRaises(FARouteUnsafe):self.router.prepare_bulk(confirmed=True)
        self.assertEqual(called,[1])
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(1,))
        self.assertEqual((second/'page-00000.bin').read_bytes(),b'CHANGED_SECOND')
        self.assert_unchanged()

    def test_injected_failure_at_second_keeps_first_and_originals(self):
        second=self.seed_second()
        start=self.router.snapshots.start
        def fault(chapter,*,confirmed):
            if chapter==2:raise RuntimeError('synthetic fault')
            return start(chapter,confirmed=confirmed)
        with patch.object(self.router.snapshots,'start',side_effect=fault):
            with self.assertRaises(FARouteUnsafe):self.router.prepare_bulk(confirmed=True)
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(1,))
        self.assertEqual((second/'page-00000.bin').read_bytes(),b'SECOND_CHAPTER_PRESERVE')
        self.assert_unchanged()

    def test_unmarked_root_does_not_run_any_route(self):
        (self.root/'.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(Exception):self.router.prepare_single(1,confirmed=True)
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM ez_snapshot_journal').fetchone(),(0,))

if __name__=='__main__':unittest.main()
