#!/usr/bin/env python3
"""EV continuation: compile/run REAL Swift POSIX fd probe on synthetic-only data.

No app integration, real users' chapters, network or iPad access.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build70_ev_recoverable_quarantine_lab import QuarantineLab


class NativeSwiftDescriptorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        swift = shutil.which("swiftc")
        if not swift:
            raise unittest.SkipTest("swiftc unavailable; native Swift must run on Swift host")
        cls.binaries = tempfile.TemporaryDirectory(prefix="webreader_ev_swift_")
        cls.binary = Path(cls.binaries.name) / "ev_fd_probe"
        subprocess.run([swift, str(HERE / "build70_ev_fd_quarantine.swift"), "-o", str(cls.binary)],
                       check=True, capture_output=True, text=True, timeout=180)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'binaries'):
            cls.binaries.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="webreader_ev_synthetic_")
        self.root = Path(self.tmp.name)
        (self.root / ".webreader_ev_disposable_marker").write_text("EV_SYNTHETIC_ONLY\n")
        self.lab = QuarantineLab(self.root)
        self.chapter = self.lab.seed()
        self.dest = 'ev_' + uuid.uuid4().hex

    def tearDown(self):
        self.lab.close()
        self.tmp.cleanup()

    def command(self, action, dev=None, ino=None, *, success=True, root=None, leaf='c', dest=None):
        args = [str(self.binary), action, str(root or self.root), 's', 'm',
                leaf, dest or self.dest]
        if dev is not None:
            args.extend([str(dev), str(ino)])
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result.stderr

    def inspect(self):
        p = self.command('inspect')
        self.assertEqual(p['status'], 'observed')
        return p['device'], p['inode']

    def test_inspect_and_stage_with_matching_persisted_identity(self):
        d, i = self.inspect()
        self.assertEqual(self.command('classify', d, i)['status'], 'at_source')
        self.assertEqual(self.command('stage', d, i)['status'], 'in_quarantine')
        self.assertFalse(self.chapter.exists())
        self.assertEqual((self.lab.app/'Quarantine'/self.dest/'page-00000.bin').read_bytes(),
                         b'page-content-preserve')
        self.assertEqual(self.command('classify', d, i)['status'], 'in_quarantine')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM downloads').fetchone()[0], 1,
                         'Swift probe must not touch SQLite')

    def test_stage_refuses_stale_identity_before_move(self):
        d, i = self.inspect()
        self.command('stage', d, str(int(i) + 1), success=False)
        self.assertTrue(self.chapter.exists())

    def test_different_quarantine_leaf_is_never_overwritten(self):
        d, i = self.inspect()
        prior = self.lab.app/'Quarantine'/self.dest
        prior.mkdir()
        (prior/'foreign.txt').write_text('foreign-data')
        self.command('stage', d, i, success=False)
        self.assertEqual((prior/'foreign.txt').read_text(), 'foreign-data')
        self.assertTrue(self.chapter.exists())

    def test_stage_rejects_leaf_symlink(self):
        moved = self.chapter.with_name('keep-real-folder')
        self.chapter.rename(moved)
        self.chapter.symlink_to(moved, target_is_directory=True)
        self.command('inspect', success=False)
        self.assertTrue((moved/'page-00000.bin').exists())

    def test_stage_rejects_ancestor_symlink(self):
        p = self.lab.app/'Downloads'/'s'
        displaced = self.lab.app/'displaced-source'
        p.rename(displaced)
        p.symlink_to(displaced, target_is_directory=True)
        self.command('inspect', success=False)
        self.assertTrue((displaced/'m'/'c'/'page-00000.bin').exists())

    def test_stage_rejects_page_symlink(self):
        file = self.chapter/'page-00000.bin'
        file.rename(self.chapter/'foreign.bin')
        file.symlink_to(self.chapter/'foreign.bin')
        self.command('inspect', success=False)
        self.assertTrue((self.chapter/'foreign.bin').exists())

    def test_stage_rejects_unknown_entries(self):
        (self.chapter/'foreign.txt').write_text('do not erase')
        self.command('inspect', success=False)
        self.assertTrue((self.chapter/'foreign.txt').is_file())

    def test_classify_requires_review_if_original_name_is_reused(self):
        d, i = self.inspect()
        self.command('stage', d, i)
        self.chapter.mkdir()
        (self.chapter/'foreign.txt').write_text('new content')
        self.assertEqual(self.command('classify', d, i)['status'], 'needs_review')
        self.assertTrue((self.chapter/'foreign.txt').exists())
        self.assertTrue((self.lab.app/'Quarantine'/self.dest/'page-00000.bin').exists())

    def test_classify_requires_review_if_quarantine_inode_replaced(self):
        d, i = self.inspect()
        self.command('stage', d, i)
        q = self.lab.app/'Quarantine'/self.dest
        q.rename(self.lab.app/'original-quarantine')
        q.mkdir()
        (q/'unknown.txt').write_text('foreign')
        self.assertEqual(self.command('classify', d, i)['status'], 'needs_review')
        self.assertTrue((self.lab.app/'original-quarantine'/'page-00000.bin').exists())

    def test_stage_has_no_implicit_restore_or_delete(self):
        d, i = self.inspect()
        self.command('stage', d, i)
        self.command('stage', d, i, success=False)
        self.assertTrue((self.lab.app/'Quarantine'/self.dest/'page-00000.bin').is_file())
        source = (HERE/'build70_ev_fd_quarantine.swift').read_text()
        self.assertNotIn('removeItem(', source)
        self.assertNotIn('unlinkat(', source)
        self.assertNotIn('rmdir(', source)

    def test_unmarked_root_is_refused(self):
        (self.root/'.webreader_ev_disposable_marker').unlink()
        self.command('inspect', success=False)
        self.assertTrue(self.chapter.exists())

    def test_altered_marker_is_refused(self):
        (self.root/'.webreader_ev_disposable_marker').write_text('EV_SYNTHETIC_ONLY!')
        self.command('inspect', success=False)
        self.assertTrue(self.chapter.exists())

    def test_bad_leaf_component_is_refused(self):
        self.command('inspect', success=False, leaf='..')
        self.assertTrue(self.chapter.exists())

    def test_missing_persisted_identity_cannot_stage(self):
        self.command('stage', success=False)
        self.assertTrue(self.chapter.exists())

    def test_check_sqlite_failure_retains_quarantine_bytes(self):
        d, i = self.inspect()
        self.command('stage', d, i)
        self.lab.db.execute('CREATE TRIGGER reject_delete BEFORE DELETE ON downloads '
                            'BEGIN SELECT RAISE(ABORT,\'synthetic failure\'); END')
        with self.assertRaises(Exception):
            with self.lab.db:
                self.lab.db.execute('DELETE FROM downloads WHERE chapter_id=1')
        self.assertEqual(self.command('classify', d, i)['status'], 'in_quarantine')
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM downloads').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
