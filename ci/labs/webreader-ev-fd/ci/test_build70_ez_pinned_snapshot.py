#!/usr/bin/env python3
"""EZ: source-fd-pinned, copy-only Swift experiment on disposable fixtures.

Never touches an app library. No physical device, automatic deletion, or install.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid

from build70_ev_recoverable_quarantine_lab import QuarantineLab

HERE=Path(__file__).resolve().parent

class EZCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=shutil.which('swiftc')
        if not compiler:
            raise unittest.SkipTest('Swift toolchain required')
        cls.tempbin=tempfile.TemporaryDirectory(prefix='webreader_ez_swift_')
        cls.binary=Path(cls.tempbin.name)/'ez_native'
        subprocess.run([compiler,str(HERE/'build70_ev_fd_quarantine.swift'),'-o',str(cls.binary)],check=True,capture_output=True,text=True,timeout=120)

    @classmethod
    def tearDownClass(cls): cls.tempbin.cleanup()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='webreader_ez_lab_')
        self.root=Path(self.tmp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        self.lab=QuarantineLab(self.root)
        self.chapter=self.lab.seed()
        self.dest='ev_'+uuid.uuid4().hex
        self.q=self.lab.app/'Quarantine'/self.dest
        observed=self.run_native('inspect')
        self.identity=(observed['device'],observed['inode'])

    def tearDown(self):
        self.lab.close();self.tmp.cleanup()

    def command(self,action,*,env=None,root=None,identity=None,dest=None):
        args=[str(self.binary),action,str(root or self.root),'s','m','c',dest or self.dest]
        if identity is not None:args.extend(identity)
        return subprocess.run(args,capture_output=True,text=True,timeout=15,env=env)

    def run_native(self,action='snapshot',*,expect_success=True,env=None,identity=None,root=None):
        if identity is None and action!='inspect':identity=self.identity
        r=self.command(action,env=env,root=root,identity=identity)
        if expect_success:
            self.assertEqual(r.returncode,0,r.stderr)
            return json.loads(r.stdout)
        self.assertNotEqual(r.returncode,0,r.stdout)
        return r.stderr

    def assert_original(self):
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM downloads').fetchone(),(1,))
        self.assertEqual(self.lab.db.execute('SELECT downloaded FROM chapters WHERE id=1').fetchone(),(1,))

    def test_copy_preserves_source_and_sqlite(self):
        result=self.run_native()
        self.assertEqual(result['status'],'copy_verified')
        self.assertEqual((result['pages'],result['bytes']),(1,len(b'page-content-preserve')))
        self.assertEqual((self.q/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assert_original()

    def test_multiple_pages_copy_exact(self):
        second=os.urandom(256*1024+17)
        (self.chapter/'page-00001.bin').write_bytes(second)
        result=self.run_native()
        self.assertEqual(result['pages'],2)
        self.assertEqual((self.q/'page-00001.bin').read_bytes(),second)
        self.assert_original()

    def test_existing_destination_is_never_overwritten(self):
        self.q.mkdir();(self.q/'foreign.txt').write_bytes(b'foreign kept')
        self.run_native(expect_success=False)
        self.assertEqual((self.q/'foreign.txt').read_bytes(),b'foreign kept')
        self.assert_original()

    def test_destination_symlink_is_never_followed(self):
        target=self.lab.app/'unrelated';target.mkdir();(target/'foreign.txt').write_bytes(b'keep')
        self.q.symlink_to(target,target_is_directory=True)
        self.run_native(expect_success=False)
        self.assertEqual((target/'foreign.txt').read_bytes(),b'keep')
        self.assert_original()

    def test_reject_unmarked_root(self):
        (self.root/'.webreader_ev_disposable_marker').unlink()
        self.run_native(expect_success=False)
        self.assertFalse(self.q.exists());self.assert_original()

    def test_bad_identity_does_not_create_snapshot(self):
        bad=(self.identity[0],str(int(self.identity[1])+1))
        self.run_native(expect_success=False,identity=bad)
        self.assertFalse(self.q.exists());self.assert_original()

    def test_reject_source_symlink(self):
        kept=self.chapter.with_name('kept');self.chapter.rename(kept)
        self.chapter.symlink_to(kept,target_is_directory=True)
        self.run_native(expect_success=False)
        self.assertFalse(self.q.exists())
        self.assertEqual((kept/'page-00000.bin').read_bytes(),b'page-content-preserve')

    def test_reject_page_symlink(self):
        page=self.chapter/'page-00000.bin';page.rename(self.chapter/'foreign.bin')
        page.symlink_to(self.chapter/'foreign.bin')
        self.run_native(expect_success=False)
        self.assertFalse(self.q.exists())
        self.assertEqual((self.chapter/'foreign.bin').read_bytes(),b'page-content-preserve')

    def test_reject_page_hardlink(self):
        os.link(self.chapter/'page-00000.bin',self.chapter/'page-00001.bin')
        self.run_native(expect_success=False)
        self.assertFalse(self.q.exists());self.assert_original()

    def test_reject_unfamiliar_file_and_subfolder(self):
        (self.chapter/'private.notes').write_bytes(b'do not copy')
        self.run_native(expect_success=False)
        self.assertFalse(self.q.exists());self.assert_original()

    def test_reject_empty_source(self):
        (self.chapter/'page-00000.bin').unlink()
        self.run_native(expect_success=False)
        self.assertFalse(self.q.exists())

    def test_copy_again_never_merges_existing_snapshot(self):
        self.run_native();before=(self.q/'page-00000.bin').read_bytes()
        self.run_native(expect_success=False)
        self.assertEqual((self.q/'page-00000.bin').read_bytes(),before)
        self.assert_original()

    def test_crash_mid_copy_retains_both_original_and_partial_copy(self):
        (self.chapter/'page-00001.bin').write_bytes(b'NEXT PAGE STILL OWNED')
        env=dict(os.environ,WEBREADER_EZ_CRASH_AFTER_FIRST_PAGE='1')
        r=self.command('snapshot',env=env,identity=self.identity)
        self.assertEqual(r.returncode,86,r.stderr)
        self.assertEqual((self.q/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertFalse((self.q/'page-00001.bin').exists())
        self.assertEqual((self.chapter/'page-00001.bin').read_bytes(),b'NEXT PAGE STILL OWNED')
        self.assert_original()

    def _paused(self):
        env=dict(os.environ,WEBREADER_EZ_RACE_GATE='1')
        args=[str(self.binary),'snapshot',str(self.root),'s','m','c',self.dest,*self.identity]
        proc=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ready=self.root/'.ez_before_copy_ready'
        until=time.monotonic()+7
        while not ready.exists() and time.monotonic()<until:
            if proc.poll() is not None:break
            time.sleep(.01)
        if not ready.exists():
            stdout, stderr = proc.communicate(timeout=7)
            self.fail(f'race gate unavailable: {proc.returncode} {stdout} {stderr}')
        self.assertEqual(ready.read_bytes(),b'READY\n')
        return proc

    def _release(self,proc):
        (self.root/'.ez_before_copy_go').write_bytes(b'GO')
        stdout,stderr=proc.communicate(timeout=10)
        return proc.returncode,stdout,stderr

    def test_paused_benign_copies_original(self):
        proc=self._paused()
        code,out,err=self._release(proc)
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['status'],'copy_verified')
        self.assert_original()

    def test_source_name_swap_does_not_move_or_copy_foreign_content(self):
        proc=self._paused()
        original=self.chapter.with_name('saved_original');self.chapter.rename(original)
        self.chapter.mkdir();(self.chapter/'page-00000.bin').write_bytes(b'FOREIGN_KEEP')
        code,_,err=self._release(proc)
        self.assertNotEqual(code,0)
        self.assertIn('snapshot source path changed',err)
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'FOREIGN_KEEP')
        self.assertEqual((original/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual((self.q/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM downloads').fetchone(),(1,))

    def test_source_replaced_with_symlink_does_not_move_foreign_symlink(self):
        proc=self._paused()
        original=self.chapter.with_name('saved_original');self.chapter.rename(original)
        self.chapter.symlink_to(original,target_is_directory=True)
        code,_,_=self._release(proc)
        self.assertNotEqual(code,0)
        self.assertTrue(self.chapter.is_symlink())
        self.assertEqual((original/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual((self.q/'page-00000.bin').read_bytes(),b'page-content-preserve')

    def test_page_swap_during_gate_refuses_snapshot_certification(self):
        proc=self._paused()
        old=self.chapter/'page-00000.bin'
        old.rename(self.chapter/'saved_original_page')
        old.write_bytes(b'FOREIGN_KEEP')
        code,_,err=self._release(proc)
        self.assertNotEqual(code,0);self.assertIn('page changed before opening',err)
        self.assertEqual(old.read_bytes(),b'FOREIGN_KEEP')
        self.assertEqual((self.chapter/'saved_original_page').read_bytes(),b'page-content-preserve')
        self.assertFalse((self.q/'page-00000.bin').exists())

    def test_quarantine_parent_reparented_after_open_is_detected(self):
        proc=self._paused()
        original=self.lab.app/'Quarantine';moved=self.lab.app/'Quarantine_displaced'
        original.rename(moved);original.mkdir()
        code,_,err=self._release(proc)
        self.assertNotEqual(code,0);self.assertIn('opened directory',err)
        self.assertEqual((moved/self.dest/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertFalse((original/self.dest).exists());self.assert_original()

    def test_original_chapter_retained_after_journal_failure(self):
        self.run_native()
        self.lab.db.execute('CREATE TRIGGER deny_delete BEFORE DELETE ON downloads '
                            "BEGIN SELECT RAISE(ABORT, 'no commit'); END;")
        with self.assertRaises(Exception):
            with self.lab.db:self.lab.db.execute('DELETE FROM downloads WHERE chapter_id=1')
        self.assert_original()
        self.assertTrue((self.q/'page-00000.bin').exists())


if __name__=='__main__': unittest.main(verbosity=2)
