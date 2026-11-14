#!/usr/bin/env python3
"""FL: bound per-page Swift FDs; copying ONLY disposable synthetic originals."""
from pathlib import Path
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

HERE=Path(__file__).resolve().parent
LAB=HERE/'labs'/'webreader-ev-fd'/'ci'
sys.path[:0]=[str(HERE),str(LAB)]
from build70_ev_recoverable_quarantine_lab import QuarantineLab

class FLDescriptorBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('swiftc'):raise unittest.SkipTest('Swift required')
        cls.compiler=tempfile.TemporaryDirectory(prefix='wr_fl_budget_compiler_')
        cls.binary=Path(cls.compiler.name)/'native'
        c=subprocess.run(['swiftc',str(LAB/'build70_ev_fd_quarantine.swift'),'-o',str(cls.binary)],
                         capture_output=True,text=True,timeout=120)
        if c.returncode:raise RuntimeError(c.stderr)
    @classmethod
    def tearDownClass(cls):cls.compiler.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wr_fl_budget_test_')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        self.lab=QuarantineLab(self.root)
        self.addCleanup(self.lab.close)
        self.chapter=self.lab.seed()
        self.name='ev_'+uuid.uuid4().hex
        q=self.lab.app/'Quarantine'
        self.snapshot=q/self.name
        obs=self.call('inspect',limit=None)
        self.id=(obs['device'],obs['inode'])

    def low_limit(self):
        resource.setrlimit(resource.RLIMIT_NOFILE,(48,48))

    def call(self,action,*,limit=48):
        args=[str(self.binary),action,str(self.root),'s','m','c',self.name]
        if action != 'inspect':args.extend(self.id)
        kw={'capture_output':True,'text':True,'timeout':40}
        if limit is not None:kw['preexec_fn']=self.low_limit
        completed=subprocess.run(args,**kw)
        self.assertEqual(completed.returncode,0,completed.stderr)
        return json.loads(completed.stdout)

    def add_pages(self,count):
        for index in range(1,count):
            (self.chapter/f'page-{index:05d}.bin').write_bytes((f'FL-{index:05d}').encode()*37)

    def test_01_snapshot_130_pages_with_max_48_fds(self):
        self.add_pages(130)
        observed=self.call('snapshot')
        self.assertEqual(observed['pages'],130)
        self.assertEqual((self.snapshot/'page-00129.bin').read_bytes(),
                         (b'FL-00129')*37)
        self.assertTrue((self.chapter/'page-00129.bin').exists())
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM downloads').fetchone(),(1,))

    def test_02_verify_130_pages_with_max_48_fds(self):
        self.add_pages(130)
        self.call('snapshot')
        verified=self.call('verifycopy')
        self.assertEqual(verified['pages'],130)
        self.assertEqual(verified['status'],'copy_verified')

    def test_03_verify_fails_on_corrupted_final_file_without_deleting(self):
        self.add_pages(130)
        self.call('snapshot')
        (self.snapshot/'page-00129.bin').write_bytes(b'ADVERSARIAL')
        args=[str(self.binary),'verifycopy',str(self.root),'s','m','c',self.name,*self.id]
        result=subprocess.run(args,capture_output=True,text=True,timeout=40,preexec_fn=self.low_limit)
        self.assertNotEqual(result.returncode,0)
        self.assertTrue((self.chapter/'page-00129.bin').exists())

    def test_04_fd_budget_is_scoped_inside_page_loops(self):
        src=(LAB/'build70_ev_fd_quarantine.swift').read_text()
        copy=src.split('private func ezCopySnapshot(',1)[1].split('// Read-only verification',1)[0]
        verify=src.split('private func ezVerifySnapshot(',1)[1].split('// END BUILD70_EZ',1)[0]
        self.assertIn('} // FL: close this page',copy)
        self.assertIn('} // FL: both verify FDs close',verify)
        self.assertNotIn('unlinkat(',copy+verify)

if __name__=='__main__':unittest.main()
