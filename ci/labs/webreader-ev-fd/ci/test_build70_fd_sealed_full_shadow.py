#!/usr/bin/env python3
"""FD: confidential completed-chapter snapshot; actual Swift + full SQLite shadow.

Only synthetic fixture directories. Never touches real iOS app, a user database,
updater, IPA, or network. No deletion of source pages or snapshot files.
"""
from pathlib import Path
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
import time
import uuid
from unittest.mock import patch

from build70_fa_full_schema_shadow import seed_full_v1, validate_shadow_pair, capture_legacy
from build70_fb_full_shadow_copy_bridge import FBShadowCopyBridge, FBUnsafe, FBInterrupted

HERE = Path(__file__).resolve().parent


class FDSealedSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('swiftc'):
            raise unittest.SkipTest('Swift toolchain unavailable')
        cls.compiler = tempfile.TemporaryDirectory(prefix='wr_fd_native_')
        cls.binary = Path(cls.compiler.name) / 'wr_fd_lab'
        subprocess.run(['swiftc', str(HERE / 'build70_ev_fd_quarantine.swift'),
                        '-o', str(cls.binary)], check=True, text=True,
                       capture_output=True, timeout=120)

    @classmethod
    def tearDownClass(cls):
        cls.compiler.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='wr_fd_sealed_')
        self.root = Path(self.temp.name)
        (self.root / '.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        seed_full_v1(self.root)
        validate_shadow_pair(self.root)
        self.app = self.root / 'synthetic_app'
        self.chapter = self.app / 'Downloads' / 's' / 'm' / 'c'
        self.chapter.mkdir(parents=True)
        self.page = self.chapter / 'page-00000.bin'
        self.page.write_bytes(b'FD synthetic offline page bytes')
        (self.app / 'Quarantine').mkdir()
        self.lab = FBShadowCopyBridge(self.root, self.binary, sealed_only=True)
        self.original_rows = capture_legacy(self.lab.db)

    def tearDown(self):
        self.lab.close()
        self.temp.cleanup()

    def copy_directory(self):
        dest = self.lab.db.execute('SELECT snapshot_name FROM offline_copy_journal').fetchone()[0]
        return self.app / 'Quarantine' / dest

    def assert_unchanged(self):
        self.assertEqual(self.page.read_bytes(), b'FD synthetic offline page bytes')
        self.assertEqual(capture_legacy(self.lab.db), self.original_rows)
        with sqlite3.connect(self.app / 'legacy_library_v1.sqlite') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone(), (1,))
            self.assertEqual(db.execute('SELECT count(*) FROM downloads').fetchone(), (1,))

    def receipt(self, count=1):
        (self.chapter / '.webreader-completion-v1').write_text(
            f'WR-OFFLINE-COMPLETE-V1:{count}\n')

    def plan(self, secret='opaque_token_in_url'):
        p = {'schemaVersion': 1, 'sourceID': 's',
             'manga': {'id': 'm', 'title': 'Synthetic', 'altTitles': [],
                       'status': 'unknown', 'genres': [], 'url': 'https://example.invalid/private/' + secret},
             'chapter': {'id': 'c', 'name': 'Chapter'},
             'pages': [{'index': 0, 'imageUrl': 'https://example.invalid/page?sig=' + secret,
                        'headers': {}}],
             'manifest': {'id': 's', 'name': 'Demo', 'version': '1.0', 'lang': 'en',
                          'author': 'Lab', 'script': 'https://example.invalid/script.js',
                          'apiVersion': 1, 'minAppVersion': '1.0',
                          'domains': ['example.invalid'], 'nsfw': False}, 'queueOrder': 0}
        path = self.chapter / '_download-plan.json'
        path.write_text(json.dumps(p))
        return path

    def test_01_completed_without_receipt_snapshot_verified(self):
        self.assertEqual(self.lab.prepare_single(1, confirmed=True), (1,))
        self.assertEqual((self.copy_directory() / 'page-00000.bin').read_bytes(), self.page.read_bytes())
        self.assertEqual(self.lab.recover(), ((1,'copy_verified'),))
        self.assert_unchanged()

    def test_02_completed_receipt_snapshot_verified(self):
        self.receipt()
        self.assertEqual(self.lab.prepare_single(1, confirmed=True), (1,))
        self.assertEqual((self.copy_directory() / '.webreader-completion-v1').read_bytes(),
                         (self.chapter / '.webreader-completion-v1').read_bytes())
        self.assertEqual(self.lab.recover(), ((1,'copy_verified'),))
        self.assert_unchanged()

    def test_03_url_token_in_plan_denied_before_journal(self):
        self.plan()
        with self.assertRaises(FBUnsafe):
            self.lab.prepare_single(1, confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone()[0],0)
        self.assertFalse(list((self.app/'Quarantine').iterdir()))
        self.assertTrue((self.chapter/'_download-plan.json').exists())
        self.assert_unchanged()

    def test_04_plan_with_header_denied_before_journal(self):
        path = self.plan()
        p = json.loads(path.read_text())
        p['pages'][0]['headers'] = {'Authorization': 'Bearer sample-fake-secret'}
        path.write_text(json.dumps(p))
        with self.assertRaises(FBUnsafe):
            self.lab.prepare_single(1,confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone()[0],0)
        self.assert_unchanged()

    def test_05_empty_header_plan_still_denied(self):
        self.plan('even_without_headers')
        with self.assertRaises(FBUnsafe): self.lab.prepare_single(1,confirmed=True)
        self.assertFalse(list((self.app/'Quarantine').iterdir()))

    def test_06_invalid_json_plan_denied_without_parsing(self):
        (self.chapter/'_download-plan.json').write_bytes(b'broken synthetic payload')
        with self.assertRaises(FBUnsafe): self.lab.prepare_single(1,confirmed=True)
        self.assert_unchanged()

    def test_07_receipt_and_plan_denied(self):
        self.receipt();self.plan()
        with self.assertRaises(FBUnsafe): self.lab.prepare_single(1,confirmed=True)
        self.assert_unchanged()

    def test_08_failed_row_blocked_even_with_valid_pages(self):
        self.lab.db.execute("UPDATE downloads SET state='failed' WHERE chapter_id=1")
        self.lab.db.execute('UPDATE chapters SET downloaded=0 WHERE internal_id=1')
        with self.assertRaises(FBUnsafe): self.lab.prepare_single(1,confirmed=True)
        self.assertFalse(list((self.app/'Quarantine').iterdir()))
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone()[0],0)

    def test_09_paused_row_blocked_even_with_valid_pages(self):
        self.lab.db.execute("UPDATE downloads SET state='paused' WHERE chapter_id=1")
        self.lab.db.execute('UPDATE chapters SET downloaded=0 WHERE internal_id=1')
        with self.assertRaises(FBUnsafe): self.lab.prepare_single(1,confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone()[0],0)

    def test_10_mismatched_downloaded_flag_blocked(self):
        self.lab.db.execute('UPDATE chapters SET downloaded=0 WHERE internal_id=1')
        with self.assertRaises(FBUnsafe): self.lab.prepare_single(1,confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone()[0],0)

    def test_11_drift_before_intent_blocked(self):
        previous=self.lab._persist_intent
        def inject(plan,dest):
            self.lab.db.execute("UPDATE downloads SET state='paused' WHERE chapter_id=1")
            self.lab.db.execute('UPDATE chapters SET downloaded=0 WHERE internal_id=1')
            return previous(plan,dest)
        with patch.object(self.lab,'_persist_intent',side_effect=inject):
            with self.assertRaises(FBUnsafe): self.lab.prepare_single(1,confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone()[0],0)
        self.assertFalse(list((self.app/'Quarantine').iterdir()))

    def test_12_drift_after_snapshot_requires_review(self):
        self.lab.prepare_single(1,confirmed=True)
        self.lab.db.execute("UPDATE downloads SET state='failed' WHERE chapter_id=1")
        self.lab.db.execute('UPDATE chapters SET downloaded=0 WHERE internal_id=1')
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assertTrue(self.page.exists())
        self.assertEqual((self.copy_directory()/'page-00000.bin').read_bytes(),self.page.read_bytes())

    def test_13_corrupt_copy_requires_review(self):
        self.receipt()
        self.lab.prepare_single(1,confirmed=True)
        (self.copy_directory()/'page-00000.bin').write_bytes(b'corrupt')
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assert_unchanged()

    def test_14_crash_after_intent_preserves_original(self):
        with self.assertRaises(FBInterrupted): self.lab.prepare_single(1,confirmed=True,crash_at='after_intent')
        self.assertEqual(self.lab.recover(),((1,'needs_review'),))
        self.assert_unchanged()

    def test_15_crash_after_snapshot_recovers(self):
        with self.assertRaises(FBInterrupted): self.lab.prepare_single(1,confirmed=True,crash_at='after_snapshot')
        self.assertEqual(self.lab.recover(),((1,'copy_verified'),))
        self.assert_unchanged()

    def test_16_reindex_is_read_only(self):
        before=self.lab.db.total_changes
        self.assertEqual(self.lab.reindex_preview(),((1,'source_present'),))
        self.assertEqual(self.lab.db.total_changes,before)
        self.assert_unchanged()

    def test_17_untrusted_plan_in_reindex_requires_review(self):
        self.plan()
        self.assertEqual(self.lab.reindex_preview(),((1,'needs_review'),))
        self.assert_unchanged()

    def test_18_bulk_preflight_denies_partial_second_chapter(self):
        second=self.app/'Downloads'/'s'/'m'/'c2';second.mkdir()
        (second/'page-00000.bin').write_bytes(b'fake second')
        (second/'_download-plan.json').write_text('{"headers":"secret"}')
        self.lab.db.execute("INSERT INTO downloads(chapter_id,state,progress,local_path,updated_at) VALUES (2,'failed',0.5,NULL,11)")
        with self.assertRaises(FBUnsafe):self.lab.prepare_bulk(confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone()[0],0)
        self.assertFalse(list((self.app/'Quarantine').iterdir()))

    def test_19_explicit_user_confirmation_required(self):
        with self.assertRaises(FBUnsafe): self.lab.prepare_single(1)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM offline_copy_journal').fetchone()[0],0)

    def test_20_copy_destination_already_occupied(self):
        self.lab.prepare_single(1,confirmed=True)
        with self.assertRaises(FBUnsafe):self.lab.prepare_single(1,confirmed=True)
        self.assert_unchanged()


    def test_21_reopen_after_commit_retains_verified_copy(self):
        self.receipt()
        self.lab.prepare_single(1, confirmed=True)
        self.lab.close()
        self.lab = FBShadowCopyBridge(self.root, self.binary, sealed_only=True)
        self.assertEqual(self.lab.recover(), ((1, 'copy_verified'),))
        self.assertEqual(self.lab.recover(), ((1, 'copy_verified'),))
        self.assert_unchanged()

    def test_22_symlinked_plan_refused_without_following(self):
        outside = self.app / 'sensitive_outside'
        outside.write_text('dummy-private-token')
        (self.chapter / '_download-plan.json').symlink_to(outside)
        with self.assertRaises(FBUnsafe):
            self.lab.prepare_single(1, confirmed=True)
        self.assertEqual(outside.read_text(), 'dummy-private-token')
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM offline_copy_journal').fetchone()[0], 0)

    def test_23_successful_bulk_of_two_completed_chapters(self):
        second = self.app / 'Downloads' / 's' / 'm' / 'c2'
        second.mkdir()
        (second / 'page-00000.bin').write_bytes(b'other completed synthetic page')
        self.lab.db.execute("INSERT INTO downloads(chapter_id,state,progress,local_path,updated_at) VALUES (2,'completed',1.0,NULL,11)")
        self.lab.db.execute('UPDATE chapters SET downloaded=1 WHERE internal_id=2')
        self.assertEqual(self.lab.prepare_bulk(confirmed=True), (1, 2))
        self.assertEqual(self.lab.recover(), ((1,'copy_verified'), (2,'copy_verified')))
        self.assertEqual((second/'page-00000.bin').read_bytes(),b'other completed synthetic page')
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM downloads').fetchone()[0],2)
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM offline_copy_journal').fetchone()[0],2)

    def test_24_receipt_count_mismatch_no_intent_or_snapshot(self):
        self.receipt(2)
        with self.assertRaises(FBUnsafe): self.lab.prepare_single(1, confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM offline_copy_journal').fetchone()[0],0)
        self.assertFalse(list((self.app/'Quarantine').iterdir()))
        self.assert_unchanged()

    def test_25_completed_row_with_running_job_is_denied(self):
        self.lab.running_ids = frozenset({1})
        with self.assertRaises(FBUnsafe): self.lab.prepare_single(1, confirmed=True)
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM offline_copy_journal').fetchone()[0],0)
        self.assert_unchanged()


    def test_26_plan_injected_midcopy_never_certifies(self):
        observed=self.lab._native('inspectmeta','s','m','c','ev_'+uuid.uuid4().hex)
        dest='ev_'+uuid.uuid4().hex
        env=dict(os.environ, WEBREADER_EZ_RACE_GATE='1')
        args=[str(self.binary),'snapshotsealed',str(self.root),'s','m','c',dest,
              observed['device'],observed['inode']]
        proc=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ready=self.root/'.ez_before_copy_ready'
        end=time.monotonic()+8
        while not ready.exists() and time.monotonic()<end:
            if proc.poll() is not None:break
            time.sleep(.01)
        if not ready.exists():
            out,err=proc.communicate(timeout=9)
            self.fail('Swift race hook did not become ready: '+out+err)
        self.plan('synthetic_private_url_token')
        (self.root/'.ez_before_copy_go').write_bytes(b'GO')
        out,err=proc.communicate(timeout=12)
        self.assertNotEqual(proc.returncode,0,(out,err))
        self.assertNotIn('synthetic_private_url_token',out+err)
        self.assertEqual(self.page.read_bytes(),b'FD synthetic offline page bytes')
        self.assertFalse((self.app/'Quarantine'/dest/'_download-plan.json').exists())
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM offline_copy_journal').fetchone()[0],0)

    def test_27_source_basename_swapped_after_open_refuses_certification(self):
        observed=self.lab._native('inspectmeta','s','m','c','ev_'+uuid.uuid4().hex)
        dest='ev_'+uuid.uuid4().hex
        args=[str(self.binary),'snapshotsealed',str(self.root),'s','m','c',dest,
              observed['device'],observed['inode']]
        proc=subprocess.Popen(args,env=dict(os.environ,WEBREADER_EZ_RACE_GATE='1'),
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ready=self.root/'.ez_before_copy_ready'
        deadline=time.monotonic()+8
        while not ready.exists() and time.monotonic()<deadline:
            if proc.poll() is not None:break
            time.sleep(.01)
        if not ready.exists():
            out,err=proc.communicate(timeout=9)
            self.fail('Swift race hook did not become ready: '+out+err)
        original=self.chapter.with_name('old_pinned_chapter')
        self.chapter.rename(original)
        self.chapter.mkdir()
        (self.chapter/'page-00000.bin').write_bytes(b'FOREIGN_NONOWNED_SYNTHETIC')
        (self.root/'.ez_before_copy_go').write_bytes(b'GO')
        out,err=proc.communicate(timeout=12)
        self.assertNotEqual(proc.returncode,0,(out,err))
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'FOREIGN_NONOWNED_SYNTHETIC')
        self.assertEqual((original/'page-00000.bin').read_bytes(),b'FD synthetic offline page bytes')
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM offline_copy_journal').fetchone()[0],0)


if __name__=='__main__':
    unittest.main()
