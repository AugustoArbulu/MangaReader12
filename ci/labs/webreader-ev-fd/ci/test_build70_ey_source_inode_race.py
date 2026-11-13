#!/usr/bin/env python3
"""EY: reproducible source-name race, using real standalone Swift POSIX code.

The expected result is detection + preservation of BOTH trees, NOT a proof
of race-free rename. This probe is synthetic-only, with a marker and test gate.
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

HERE = Path(__file__).resolve().parent


class SourceIdentityRaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('swiftc')
        if compiler is None:
            raise unittest.SkipTest('Swift compiler not available')
        cls.bin_tmp = tempfile.TemporaryDirectory(prefix='webreader_ey_native_')
        cls.binary = Path(cls.bin_tmp.name) / 'ey_swift_probe'
        subprocess.run([compiler, str(HERE/'build70_ev_fd_quarantine.swift'),
                        '-o', str(cls.binary)], check=True, timeout=180,
                       capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls): cls.bin_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='webreader_ey_race_')
        self.root = Path(self.tmp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        self.lab = QuarantineLab(self.root)
        self.chapter = self.lab.seed()
        self.dest = 'ev_'+uuid.uuid4().hex
        self.ready = self.root / '.ey_pre_rename_ready'
        self.go = self.root / '.ey_pre_rename_go'
        info = subprocess.run(self.args('inspect'),capture_output=True,text=True,check=True)
        self.identity = (json.loads(info.stdout)['device'],json.loads(info.stdout)['inode'])

    def tearDown(self):
        self.lab.close()
        self.tmp.cleanup()

    def args(self, action, identity=None):
        a = [str(self.binary),action,str(self.root),'s','m','c',self.dest]
        if identity: a += list(identity)
        return a

    def paused_process(self):
        env = dict(os.environ, WEBREADER_EY_RACE_GATE='1')
        proc = subprocess.Popen(self.args('stage', self.identity), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env)
        deadline = time.monotonic()+5.0
        while not self.ready.exists() and time.monotonic() < deadline:
            if proc.poll() is not None: break
            time.sleep(0.01)
        if not self.ready.exists():
            out,err = proc.communicate(timeout=8)
            self.fail(f'Native race gate failed: {proc.returncode} {out} {err}')
        self.assertEqual(self.ready.read_bytes(),b'READY\n')
        return proc

    def release(self, proc):
        self.go.write_bytes(b'GO')
        out, err = proc.communicate(timeout=9)
        return proc.returncode, out, err

    def test_benign_release_moves_same_inode_without_changing_sqlite(self):
        proc = self.paused_process()
        code, out, err = self.release(proc)
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['status'],'in_quarantine')
        self.assertFalse(self.chapter.exists())
        self.assertEqual((self.lab.app/'Quarantine'/self.dest/'page-00000.bin').read_bytes(),
                         b'page-content-preserve')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def test_replaced_source_name_is_moved_but_detected_and_never_deleted(self):
        proc = self.paused_process()
        saved = self.chapter.with_name('preserved_original_inode')
        self.chapter.rename(saved)
        self.chapter.mkdir()
        (self.chapter/'page-00000.bin').write_bytes(b'FOREIGN_DATA_KEEP')
        code, out, err = self.release(proc)
        self.assertNotEqual(code,0)
        self.assertIn('post-rename mismatch',err)
        self.assertEqual((saved/'page-00000.bin').read_bytes(),b'page-content-preserve')
        q=self.lab.app/'Quarantine'/self.dest
        self.assertEqual((q/'page-00000.bin').read_bytes(),b'FOREIGN_DATA_KEEP')
        self.assertFalse(self.chapter.exists())
        classify=subprocess.run(self.args('classify',self.identity),capture_output=True,text=True)
        self.assertEqual(classify.returncode,0,classify.stderr)
        self.assertEqual(json.loads(classify.stdout)['status'],'needs_review')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def test_symlink_swapped_to_source_is_moved_as_link_not_followed(self):
        proc=self.paused_process()
        saved=self.chapter.with_name('safe_original')
        self.chapter.rename(saved)
        self.chapter.symlink_to(saved,target_is_directory=True)
        code, _, err=self.release(proc)
        self.assertNotEqual(code,0)
        self.assertIn('post-rename mismatch',err)
        self.assertEqual((saved/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertTrue((self.lab.app/'Quarantine'/self.dest).is_symlink())
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def test_destination_created_during_pause_is_not_overwritten(self):
        proc=self.paused_process()
        dest=self.lab.app/'Quarantine'/self.dest
        dest.mkdir()
        (dest/'foreign.txt').write_bytes(b'KEEP_EXISTING_DEST')
        code,_,err=self.release(proc)
        self.assertNotEqual(code,0)
        self.assertIn('exclusive-rename',err)
        self.assertEqual((dest/'foreign.txt').read_bytes(),b'KEEP_EXISTING_DEST')
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'page-content-preserve')

    def test_source_replaced_with_regular_file_before_rename(self):
        proc=self.paused_process()
        saved=self.chapter.with_name('preserved_original_inode')
        self.chapter.rename(saved)
        self.chapter.write_bytes(b'FOREIGN_FILE_KEEP')
        code,_,err=self.release(proc)
        self.assertNotEqual(code,0)
        self.assertIn('post-rename mismatch',err)
        self.assertEqual((saved/'page-00000.bin').read_bytes(),b'page-content-preserve')
        self.assertEqual((self.lab.app/'Quarantine'/self.dest).read_bytes(),b'FOREIGN_FILE_KEEP')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def test_reparented_manga_folder_after_open_is_detected(self):
        proc=self.paused_process()
        manga=self.chapter.parent
        saved=manga.with_name('m_reparented')
        manga.rename(saved)
        manga.mkdir()
        code,_,err=self.release(proc)
        self.assertNotEqual(code,0)
        self.assertIn('opened directory',err)
        # The held descriptor can move the original chapter, but cannot
        # guarantee the path still has its original canonical parent.
        self.assertEqual((self.lab.app/'Quarantine'/self.dest/'page-00000.bin').read_bytes(),
                         b'page-content-preserve')
        self.assertTrue(saved.exists())
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def test_reparented_quarantine_after_open_is_detected(self):
        proc=self.paused_process()
        q=self.lab.app/'Quarantine'
        saved=self.lab.app/'Quarantine_displaced'
        q.rename(saved)
        q.mkdir()
        code,_,err=self.release(proc)
        self.assertNotEqual(code,0)
        self.assertIn('opened directory',err)
        self.assertEqual((saved/self.dest/'page-00000.bin').read_bytes(),
                         b'page-content-preserve')
        self.assertFalse((q/self.dest).exists())
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone(),(1,))

    def test_wrong_native_marker_blocks_even_while_gate_enabled(self):
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'BAD_MARKER')
        env=dict(os.environ, WEBREADER_EY_RACE_GATE='1')
        r=subprocess.run(self.args('stage',self.identity),capture_output=True,text=True,env=env,timeout=5)
        self.assertNotEqual(r.returncode,0)
        self.assertFalse(self.ready.exists())
        self.assertTrue((self.chapter/'page-00000.bin').exists())


if __name__ == '__main__': unittest.main()
