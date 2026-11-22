#!/usr/bin/env python3
"""FB: full 11-table synthetic schema + Swift metadata snapshots; no user data."""
from pathlib import Path
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from build70_fa_full_schema_shadow import seed_full_v1, validate_shadow_pair, capture_legacy
from build70_fb_full_shadow_copy_bridge import FBShadowCopyBridge,FBUnsafe,FBInterrupted

HERE=Path(__file__).resolve().parent

class FBIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        swiftc=shutil.which('swiftc')
        if not swiftc:raise unittest.SkipTest('Swift compiler required')
        cls.compiler=tempfile.TemporaryDirectory(prefix='fb_compiler_')
        cls.binary=Path(cls.compiler.name)/'fb_native'
        subprocess.run([swiftc,str(HERE/'build70_ev_fd_quarantine.swift'),'-o',str(cls.binary)],
                       check=True,capture_output=True,text=True,timeout=120)

    @classmethod
    def tearDownClass(cls):cls.compiler.cleanup()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='fb_full_shadow_')
        self.root=Path(self.tmp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        seed_full_v1(self.root)
        self.shadow=validate_shadow_pair(self.root)
        self.app=self.root/'synthetic_app'
        self.chapter=self.app/'Downloads'/'s'/'m'/'c'
        self.chapter.mkdir(parents=True)
        self.page=self.chapter/'page-00000.bin'
        self.page.write_bytes(b'page for synthetic FB')
        (self.app/'Quarantine').mkdir()
        self.lab=FBShadowCopyBridge(self.root,self.binary)
        self.baseline=self.legacy_rows()

    def tearDown(self):
        self.lab.close();self.tmp.cleanup()

    def legacy_rows(self):return capture_legacy(self.lab.db)
    def assert_original(self):
        self.assertEqual(self.page.read_bytes(),b'page for synthetic FB')
        self.assertEqual(self.legacy_rows(),self.baseline)
        with sqlite3.connect(self.app/'legacy_library_v1.sqlite') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone(),(1,))
            self.assertEqual(db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def dest(self):
        return self.app/'Quarantine'/self.lab.db.execute('SELECT snapshot_name FROM offline_copy_journal WHERE chapter_id=1').fetchone()[0]

    def add_receipt(self,n=1):
        (self.chapter/'.webreader-completion-v1').write_bytes(f'WR-OFFLINE-COMPLETE-V1:{n}\n'.encode())

    def add_plan(self,source='s',manga='m',chapter='c',page_count=1):
        plan={'schemaVersion':1,'sourceID':source,
              'manifest':{'id':source,'name':'Synthetic','version':'1.0','lang':'en',
                          'author':'Fixture','script':'https://example.invalid/script.js',
                          'apiVersion':1,'minAppVersion':'1.0','domains':['example.invalid'],
                          'nsfw':False},
              'manga':{'id':manga,'title':'Synthetic','altTitles':[],
                       'status':'unknown','genres':[]},
              'chapter':{'id':chapter,'name':'Synthetic chapter'},
              'pages':[{'index':i,'imageUrl':'https://example.invalid/page',
                        'headers':{}} for i in range(page_count)],
              'queueOrder':0}
        (self.chapter/'_download-plan.json').write_bytes(json.dumps(plan).encode())

    def test_new_copy_journal_exists_inside_shadow_v2_only(self):
        self.assertEqual(self.lab.db.execute('PRAGMA user_version').fetchone(),(2,))
        with sqlite3.connect(self.app/'legacy_library_v1.sqlite') as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='offline_copy_journal'").fetchone())
        self.assertEqual(self.lab.db.execute("SELECT count(*) FROM offline_copy_journal").fetchone(),(0,))
        self.assert_original()

    def test_copy_only_single_preserves_original_and_full_schema(self):
        self.assertEqual(self.lab.prepare_single(1,confirmed=True),(1,))
        self.assertEqual((self.dest()/'page-00000.bin').read_bytes(),self.page.read_bytes())
        self.assertEqual(self.lab.db.execute('SELECT state FROM offline_copy_journal').fetchone(),('copy_verified',))
        self.assert_original()

    def test_receipt_valid_copy_and_verify(self):
        self.add_receipt();self.lab.prepare_single(1,confirmed=True)
        self.assertEqual((self.dest()/'.webreader-completion-v1').read_bytes(),(self.chapter/'.webreader-completion-v1').read_bytes())
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))
        self.assert_original()

    def test_plan_valid_copy_and_verify(self):
        self.add_plan();self.lab.prepare_single(1,confirmed=True)
        self.assertEqual((self.dest()/'_download-plan.json').read_bytes(),(self.chapter/'_download-plan.json').read_bytes())
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))
        self.assert_original()

    def test_plan_partial_prefix_with_more_pages(self):
        self.add_plan(page_count=3);self.lab.prepare_single(1,confirmed=True)
        self.assertEqual(self.lab.reindex_preview(),((1,'copy_verified'),))

    def test_explicit_consent(self):
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone(),(0,))
        self.assert_original()

    def test_unrecognized_chapter_blocks(self):
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(99,confirmed=True)
        self.assert_original()

    def test_preexisting_journal_blocks_second_attempt(self):
        self.lab.prepare_single(1,confirmed=True)
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)
        self.assert_original()

    def test_invalid_receipt_count_refused_before_intent(self):
        self.add_receipt(2)
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone(),(0,))
        self.assertFalse(any((self.app/'Quarantine').iterdir()))

    def test_receipt_symlink_refused(self):
        external=self.app/'foreign';external.write_bytes(b'foreign')
        (self.chapter/'.webreader-completion-v1').symlink_to(external)
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)
        self.assertEqual(external.read_bytes(),b'foreign')

    def test_receipt_hardlink_refused(self):
        self.add_receipt()
        os.link(self.chapter/'.webreader-completion-v1', self.app/'linked_receipt')
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_plan_wrong_owner_refused(self):
        self.add_plan(manga='not_this_title')
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)
        self.assertFalse(any((self.app/'Quarantine').iterdir()))

    def test_plan_malformed_json_refused(self):
        (self.chapter/'_download-plan.json').write_bytes(b'{"malformed"')
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_plan_oversized_refused(self):
        (self.chapter/'_download-plan.json').write_bytes(b'A'*(16*1024*1024+1))
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_plan_and_receipt_simultaneously_refused(self):
        self.add_plan();self.add_receipt()
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_sparse_pages_refused(self):
        (self.chapter/'page-00002.bin').write_bytes(b'sparse')
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_foreign_file_refused(self):
        (self.chapter/'secrets.txt').write_bytes(b'sensitive')
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_crash_after_intent_marks_review_without_deletion(self):
        with self.assertRaises(FBInterrupted):self.lab.prepare_single(1,confirmed=True,crash_at='after_intent')
        self.assertEqual(self.lab.db.execute('SELECT state FROM offline_copy_journal').fetchone(),('prepared',))
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assert_original()

    def test_crash_after_snapshot_recovers_copy_verified(self):
        self.add_receipt()
        with self.assertRaises(FBInterrupted):self.lab.prepare_single(1,confirmed=True,crash_at='after_snapshot')
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))
        self.assertEqual(self.lab.db.execute('SELECT state FROM offline_copy_journal').fetchone(),('copy_verified',))
        self.assert_original()

    def test_crash_after_commit_idempotent(self):
        with self.assertRaises(FBInterrupted):self.lab.prepare_single(1,confirmed=True,crash_at='after_commit')
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))
        self.assert_original()

    def test_corrupt_copy_requires_review(self):
        self.lab.prepare_single(1,confirmed=True)
        (self.dest()/'page-00000.bin').write_bytes(b'corrupt')
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assert_original()

    def test_corrupt_receipt_copy_requires_review(self):
        self.add_receipt();self.lab.prepare_single(1,confirmed=True)
        (self.dest()/'.webreader-completion-v1').write_bytes(b'INVALID')
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assert_original()

    def test_owner_drift_requires_review_without_retiring(self):
        self.lab.prepare_single(1,confirmed=True)
        self.lab.db.execute("UPDATE downloads SET state='failed' WHERE chapter_id=1")
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assertEqual(self.page.read_bytes(),b'page for synthetic FB')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def test_reindex_never_changes_database(self):
        before=self.lab.db.total_changes
        self.assertEqual(self.lab.reindex_preview(),((1,'source_present'),))
        self.assertEqual(self.lab.db.total_changes,before)
        self.assert_original()

    def test_reindex_corrupt_receipt_needs_review(self):
        self.add_receipt(2)
        self.assertEqual(self.lab.reindex_preview(),((1,'needs_review'),))
        self.assert_original()

    def test_bulk_preflight_all_before_first_write(self):
        second=self.app/'Downloads'/'s'/'m'/'c2';second.mkdir()
        (second/'page-00000.bin').write_bytes(b'second')
        (second/'_download-plan.json').write_bytes(b'INVALID')
        self.lab.db.execute("INSERT INTO downloads(chapter_id,state,progress,local_path,updated_at) VALUES(2,'failed',0.5,NULL,11)")
        with self.assertRaises(FBUnsafe):self.lab.prepare_bulk(confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone(),(0,))
        self.assertFalse(any((self.app/'Quarantine').iterdir()))

    def test_bulk_two_chapters_with_receipt_and_plan(self):
        self.add_receipt()
        second=self.app/'Downloads'/'s'/'m'/'c2';second.mkdir()
        (second/'page-00000.bin').write_bytes(b'second')
        self.add_plan(page_count=2,chapter='c2')
        (self.chapter/'_download-plan.json').replace(second/'_download-plan.json')
        self.lab.db.execute("INSERT INTO downloads(chapter_id,state,progress,local_path,updated_at) VALUES(2,'failed',0.5,NULL,11)")
        self.assertEqual(self.lab.prepare_bulk(confirmed=True),(1,2))
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone(),(2,))
        self.assertEqual((second/'page-00000.bin').read_bytes(),b'second')
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),(2,'copy_verified')))

    def test_bulk_blocks_active_job(self):
        self.lab.running_ids=frozenset({1})
        with self.assertRaises(FBUnsafe):self.lab.prepare_bulk(confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone(),(0,))

    def test_bulk_collision_rejected(self):
        self.lab.db.execute("INSERT INTO manga VALUES(2,'S','m','Colliding',NULL,NULL,'unknown',NULL,NULL,13)")
        self.lab.db.execute("INSERT INTO chapters VALUES(3,2,'c','Collision',3.0,NULL,NULL,0,0,0,0)")
        self.lab.db.execute("INSERT INTO downloads VALUES(3,3,'failed',0.0,NULL,13)")
        with self.assertRaises(FBUnsafe):self.lab.prepare_bulk(confirmed=True)

    def test_copy_journal_foreign_key(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.db.execute('''INSERT INTO offline_copy_journal
                (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,snapshot_name,source_device,source_inode,state,consent)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',('a'*32,999,'s','m','c','ev_'+'a'*32,'1','2','prepared','synthetic_confirmation'))

    def test_copy_journal_path_injection_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.db.execute('''INSERT INTO offline_copy_journal
                (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,snapshot_name,source_device,source_inode,state,consent)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',('a'*32,1,'s','m','c','ev_'+'a'*31+'/', '1','2','prepared','synthetic_confirmation'))

    def test_copy_unauthorized_extra_root_rejected(self):
        (self.root/'.webreader_ev_disposable_marker').unlink()
        with self.assertRaises(Exception):self.lab.prepare_single(1,confirmed=True)
        self.assertFalse(any((self.app/'Quarantine').iterdir()))

    def test_receipt_extra_newline_rejected(self):
        self.add_receipt()
        (self.chapter/'.webreader-completion-v1').write_bytes(b'WR-OFFLINE-COMPLETE-V1:1\n\n')
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_receipt_oversized_rejected(self):
        (self.chapter/'.webreader-completion-v1').write_bytes(b'A'*65)
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_plan_structurally_invalid_page_rejected(self):
        self.add_plan()
        plan=json.loads((self.chapter/'_download-plan.json').read_text())
        plan['pages']=[{'index':0}]
        (self.chapter/'_download-plan.json').write_text(json.dumps(plan))
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_plan_wrong_manifest_source_rejected(self):
        self.add_plan()
        plan=json.loads((self.chapter/'_download-plan.json').read_text())
        plan['manifest']['id']='wrong'
        (self.chapter/'_download-plan.json').write_text(json.dumps(plan))
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_plan_queued_order_wrong_type_rejected(self):
        self.add_plan()
        plan=json.loads((self.chapter/'_download-plan.json').read_text())
        plan['queueOrder']='not-int'
        (self.chapter/'_download-plan.json').write_text(json.dumps(plan))
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_plan_insufficient_planned_pages_rejected(self):
        (self.chapter/'page-00001.bin').write_bytes(b'NEXT')
        self.add_plan(page_count=1)
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)

    def test_two_pages_receipt_count_correct(self):
        (self.chapter/'page-00001.bin').write_bytes(b'NEXT')
        self.add_receipt(2)
        self.lab.prepare_single(1,confirmed=True)
        self.assertEqual((self.dest()/'page-00001.bin').read_bytes(),b'NEXT')
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))

    def test_original_plan_changed_after_copy_requires_review(self):
        self.add_plan();self.lab.prepare_single(1,confirmed=True)
        self.add_plan(page_count=2)
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def test_original_page_same_length_changed_after_copy_requires_review(self):
        self.lab.prepare_single(1,confirmed=True)
        self.page.write_bytes(b'X'*len(self.page.read_bytes()))
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE internal_id=1').fetchone(),(1,))

    def test_source_directory_reparented_after_copy_requires_review(self):
        self.lab.prepare_single(1,confirmed=True)
        original=self.chapter.with_name('saved_synthetic_chapter')
        self.chapter.rename(original)
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assertEqual((original/'page-00000.bin').read_bytes(),b'page for synthetic FB')

    def test_snapshot_replaced_by_symlink_requires_review(self):
        self.lab.prepare_single(1,confirmed=True)
        path=self.dest()
        saved=path.with_name('saved_snapshot')
        path.rename(saved)
        path.symlink_to(saved,target_is_directory=True)
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assertEqual((saved/'page-00000.bin').read_bytes(),b'page for synthetic FB')
        self.assert_original()

    def test_process_style_restart_reopens_shadow_and_recovers(self):
        self.add_receipt()
        with self.assertRaises(FBInterrupted):
            self.lab.prepare_single(1,confirmed=True,crash_at='after_snapshot')
        self.lab.close()
        self.lab=FBShadowCopyBridge(self.root,self.binary)
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))
        self.assert_original()

    def test_sqlite_trigger_reject_intent_before_native_copy(self):
        self.lab.db.execute('''CREATE TRIGGER deny_intent BEFORE INSERT ON offline_copy_journal
            BEGIN SELECT RAISE(ABORT,'synthetic lock'); END''')
        with self.assertRaises(sqlite3.Error):self.lab.prepare_single(1,confirmed=True)
        self.assertFalse(any((self.app/'Quarantine').iterdir()))
        self.assert_original()

    def test_sqlite_trigger_reject_commit_after_snapshot_preserves_both(self):
        self.lab.db.execute('''CREATE TRIGGER deny_verified BEFORE UPDATE OF state ON offline_copy_journal
            WHEN new.state='copy_verified' BEGIN SELECT RAISE(ABORT,'synthetic commit failure'); END''')
        with self.assertRaises(sqlite3.Error):self.lab.prepare_single(1,confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT state FROM offline_copy_journal').fetchone(),('prepared',))
        self.assertTrue(self.dest().is_dir())
        self.assert_original()
        self.lab.db.execute('DROP TRIGGER deny_verified')
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))

    def test_copy_journal_duplicate_chapter_rejected(self):
        self.lab.prepare_single(1,confirmed=True)
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.db.execute('''INSERT INTO offline_copy_journal
                (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,
                 snapshot_name,source_device,source_inode,state,consent)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                ('a'*32,1,'s','m','c','ev_'+'a'*32,'1','2','prepared','synthetic_confirmation'))
        self.assert_original()

    def test_pending_worker_blocks_bulk(self):
        self.lab.pending_ids=frozenset({42})
        with self.assertRaises(FBUnsafe):self.lab.prepare_bulk(confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone(),(0,))

    def test_reindex_copy_state_does_not_modify_metadata(self):
        self.lab.prepare_single(1,confirmed=True)
        before=self.lab.db.total_changes
        self.assertEqual(self.lab.reindex_preview(),((1,'copy_verified'),))
        self.assertEqual(self.lab.db.total_changes,before)
        self.assert_original()

    def test_copy_journal_unknown_state_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.db.execute('''INSERT INTO offline_copy_journal
                (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,
                 snapshot_name,source_device,source_inode,state,consent)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                ('a'*32,1,'s','m','c','ev_'+'a'*32,'1','2','purged','synthetic_confirmation'))
        self.assert_original()

    def _race_snapshotmeta(self):
        import uuid, time
        dest='ev_'+uuid.uuid4().hex
        observed=self.lab._native('inspectmeta','s','m','c',dest)
        env=dict(os.environ,WEBREADER_EZ_RACE_GATE='1')
        args=[str(self.binary),'snapshotmeta',str(self.root),'s','m','c',dest,
              observed['device'],observed['inode']]
        proc=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ready=self.root/'.ez_before_copy_ready'
        until=time.monotonic()+8
        while not ready.exists() and time.monotonic()<until:
            if proc.poll() is not None:break
            time.sleep(.01)
        if not ready.exists():
            out,err=proc.communicate(timeout=8)
            self.fail(f'FB native race gate unavailable: {out} {err}')
        return proc,dest

    def _release_race(self,proc):
        (self.root/'.ez_before_copy_go').write_bytes(b'GO')
        return proc.communicate(timeout=12)

    def test_swift_metadata_copy_source_swap_never_uses_foreign_basename(self):
        self.add_receipt()
        proc,dest=self._race_snapshotmeta()
        original=self.chapter.with_name('saved_original')
        self.chapter.rename(original)
        self.chapter.mkdir()
        (self.chapter/'page-00000.bin').write_bytes(b'FOREIGN_NOT_OWNED')
        out,err=self._release_race(proc)
        self.assertNotEqual(proc.returncode,0,(out,err))
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'FOREIGN_NOT_OWNED')
        self.assertEqual((original/'page-00000.bin').read_bytes(),b'page for synthetic FB')
        self.assertEqual((self.app/'Quarantine'/dest/'page-00000.bin').read_bytes(),
                         b'page for synthetic FB')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone(),(0,))

    def test_swift_metadata_copy_plan_mutation_at_gate_never_certifies(self):
        self.add_plan()
        proc,dest=self._race_snapshotmeta()
        plan=json.loads((self.chapter/'_download-plan.json').read_text())
        plan['sourceID']='foreign-owner'
        (self.chapter/'_download-plan.json').write_text(json.dumps(plan))
        out,err=self._release_race(proc)
        self.assertNotEqual(proc.returncode,0,(out,err))
        self.assertEqual(self.page.read_bytes(),b'page for synthetic FB')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone(),(0,))
if __name__=='__main__':unittest.main(verbosity=2)
