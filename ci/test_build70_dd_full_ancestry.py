#!/usr/bin/env python3
"""DD: hostile HOST ONLY full-ancestor walk.

All fixtures are disposable in a runner user's home directory; no source,
device or user library is modified. Paths/claimed UID are test configuration,
not an authenticated IPC request. This is NOT a proof of iOS12 sandboxing.
"""
from pathlib import Path
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
DENIED, REVIEWED, QUARANTINED = 0, 1, 2


class Receipt(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int),
        ("complete_host_ancestor_chain_observed", ctypes.c_bool),
        ("host_ancestors_without_group_or_other_write", ctypes.c_bool),
        ("host_descendant_dirs_owner_0700", ctypes.c_bool),
        ("host_lock_owner_0600_singlelink", ctypes.c_bool),
        ("marker_present", ctypes.c_bool),
        ("claimed_client_uid_differs", ctypes.c_bool),
        ("ios12_client_identity_proven", ctypes.c_bool),
        ("ios12_helper_identity_proven", ctypes.c_bool),
        ("ios12_app_write_access_denied", ctypes.c_bool),
        ("independently_protected_storage_attested", ctypes.c_bool),
        ("powerloss_or_rollback_safe", ctypes.c_bool),
        ("post_review_immutability_proven", ctypes.c_bool),
        ("editor_signature_trusted", ctypes.c_bool),
        ("owner_consent_verified", ctypes.c_bool),
        ("installation_authorized", ctypes.c_bool),
        ("installation_performed", ctypes.c_bool),
    ]


class DDHostFullAncestryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="wr-dd-compiler-")
        cc = shutil.which("clang") or shutil.which("cc")
        if not cc:
            raise RuntimeError("native C compiler required, cannot skip")
        library = Path(cls.build.name) / (
            "libdd.dylib" if sys.platform == "darwin" else "libdd.so"
        )
        subprocess.run(
            [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared",
             str(ROOT / "build70_dd_full_ancestry.c"), "-o", str(library)],
            check=True, text=True, capture_output=True, timeout=30
        )
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.wr_dd_inspect_host_ancestors.argtypes = (
            ctypes.c_char_p, ctypes.c_uint32
        )
        cls.lib.wr_dd_inspect_host_ancestors.restype = Receipt

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        # GitHub checkout can have a group-writable ancestor; stage disposable
        # fixtures in the runner HOME instead. Do not require anything on iPad.
        self.tmp = tempfile.TemporaryDirectory(
            prefix="wr-dd-host-", dir=Path.home()
        )
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.level = self.root / "level"
        self.level.mkdir(mode=0o755)
        self.level.chmod(0o755)
        self.base = self.level / "fixture"
        self.base.mkdir(mode=0o700)
        self.base.chmod(0o700)
        self.private = self.base / "wr-dd-private"
        self.private.mkdir(mode=0o700)
        self.private.chmod(0o700)
        self.state = self.private / "state"
        self.state.mkdir(mode=0o700)
        self.state.chmod(0o700)
        self.lock = self.state / "wr-da-review.lock"
        self.lock.write_bytes(b"")
        self.lock.chmod(0o600)
        self.marker = self.state / "wr-da-check.pending"
        self.hypothetical_client = os.geteuid() + 1 or 9

    def inspect(self, base=None, claim=None):
        path = self.base if base is None else base
        cpath = os.fsencode(str(path))
        result = self.lib.wr_dd_inspect_host_ancestors(
            cpath, self.hypothetical_client if claim is None else claim
        )
        for field in (
            "ios12_client_identity_proven", "ios12_helper_identity_proven",
            "ios12_app_write_access_denied",
            "independently_protected_storage_attested",
            "powerloss_or_rollback_safe", "post_review_immutability_proven",
            "editor_signature_trusted", "owner_consent_verified",
            "installation_authorized", "installation_performed",
        ):
            self.assertFalse(getattr(result, field), field)
        return result

    def test_host_entire_path_walk_is_successful_only_as_metadata(self):
        r = self.inspect()
        self.assertEqual(r.status, REVIEWED)
        self.assertTrue(r.complete_host_ancestor_chain_observed)
        self.assertTrue(r.host_ancestors_without_group_or_other_write)
        self.assertTrue(r.host_descendant_dirs_owner_0700)
        self.assertTrue(r.host_lock_owner_0600_singlelink)
        self.assertTrue(r.claimed_client_uid_differs)
        self.assertFalse(r.marker_present)

    def test_fixed_pending_marker_causes_quarantine(self):
        self.marker.write_bytes(b"PENDING-READ-ONLY-CHECK\n")
        r = self.inspect()
        self.assertEqual(r.status, QUARANTINED)
        self.assertTrue(r.marker_present)

    def test_empty_or_corrupt_marker_quarantines(self):
        for value in (b"", b"BROKEN", b"\x00\xFF"):
            with self.subTest(value=value):
                self.marker.write_bytes(value)
                self.assertEqual(self.inspect().status, QUARANTINED)

    def test_symlink_marker_is_quarantined_not_followed(self):
        sibling = self.root / "unrelated"
        sibling.write_bytes(b"DONT-MODIFY")
        self.marker.symlink_to(sibling)
        self.assertEqual(self.inspect().status, QUARANTINED)
        self.assertEqual(sibling.read_bytes(), b"DONT-MODIFY")

    def test_directory_named_as_marker_also_quarantines(self):
        self.marker.mkdir()
        self.assertEqual(self.inspect().status, QUARANTINED)

    def test_symlinked_ancestor_is_denied(self):
        real = self.root / "real-level"
        self.level.rename(real)
        self.level.symlink_to(real, target_is_directory=True)
        self.assertEqual(self.inspect().status, DENIED)

    def test_symlinked_anchor_leaf_is_denied(self):
        real = self.level / "real-fixture"
        self.base.rename(real)
        self.base.symlink_to(real, target_is_directory=True)
        self.assertEqual(self.inspect().status, DENIED)

    def test_symlinked_private_child_is_denied(self):
        real = self.base / "real-private"
        self.private.rename(real)
        self.private.symlink_to(real, target_is_directory=True)
        self.assertEqual(self.inspect().status, DENIED)

    def test_symlinked_state_directory_is_denied(self):
        real = self.private / "real-state"
        self.state.rename(real)
        self.state.symlink_to(real, target_is_directory=True)
        self.assertEqual(self.inspect().status, DENIED)

    def test_symlinked_lock_is_denied(self):
        real = self.state / "real.lock"
        self.lock.rename(real)
        self.lock.symlink_to(real)
        self.assertEqual(self.inspect().status, DENIED)

    def test_hardlinked_lock_is_denied(self):
        (self.state / "alias.lock").hardlink_to(self.lock)
        self.assertEqual(self.inspect().status, DENIED)

    def test_lock_with_content_is_denied(self):
        self.lock.write_bytes(b"NO")
        self.assertEqual(self.inspect().status, DENIED)

    def test_ancestor_world_writable_is_denied_even_with_sticky_bit(self):
        for mode in (0o777, 0o1777):
            with self.subTest(mode=oct(mode)):
                self.level.chmod(mode)
                self.assertEqual(self.inspect().status, DENIED)
        self.level.chmod(0o755)

    def test_ancestor_group_writable_is_denied(self):
        self.level.chmod(0o775)
        self.assertEqual(self.inspect().status, DENIED)

    def test_direct_private_dir_must_be_exactly_0700(self):
        for mode in (0o755, 0o775, 0o777, 0o400, 0o1700):
            with self.subTest(mode=oct(mode)):
                self.private.chmod(mode)
                self.assertEqual(self.inspect().status, DENIED)

    def test_state_dir_must_be_exactly_0700(self):
        for mode in (0o755, 0o775, 0o777, 0o400):
            with self.subTest(mode=oct(mode)):
                self.state.chmod(mode)
                self.assertEqual(self.inspect().status, DENIED)

    def test_lock_must_be_exactly_0600(self):
        for mode in (0o640, 0o400, 0o660, 0o777):
            with self.subTest(mode=oct(mode)):
                self.lock.chmod(mode)
                self.assertEqual(self.inspect().status, DENIED)

    def test_invalid_client_uid_claims_not_identity(self):
        self.assertEqual(self.inspect(claim=0).status, DENIED)
        self.assertEqual(self.inspect(claim=os.geteuid()).status, DENIED)
        # A fake distinct UID still gives only a host observation.
        self.assertEqual(self.inspect(claim=4294967294).status, REVIEWED)
        self.assertFalse(self.inspect().ios12_client_identity_proven)

    def test_invalid_base_literals_are_rejected(self):
        for name in ("/", "relative/path", str(self.base)+"/",
                     str(self.base)+"/./", "/tmp/../tmp/fixture",
                     str(self.base).replace("/level/", "//level/")):
            with self.subTest(name=name):
                self.assertEqual(self.inspect(base=name).status, DENIED)

    def test_no_file_mutation_during_host_inspection(self):
        self.marker.write_bytes(b"INCOMPLETE")
        sentinel = self.root / "untouched.fake"
        sentinel.write_bytes(b"DO NOT MODIFY")
        before = (self.lock.stat().st_size, self.lock.stat().st_mode,
                  self.marker.read_bytes(), sentinel.read_bytes())
        for _ in range(15):
            self.assertEqual(self.inspect().status, QUARANTINED)
        after = (self.lock.stat().st_size, self.lock.stat().st_mode,
                 self.marker.read_bytes(), sentinel.read_bytes())
        self.assertEqual(before, after)

    def test_same_uid_can_erase_marker_after_review_counterexample(self):
        self.marker.write_bytes(b"PENDING")
        self.assertEqual(self.inspect().status, QUARANTINED)
        self.marker.unlink()
        self.assertEqual(self.inspect().status, REVIEWED)
        self.assertFalse(self.inspect().post_review_immutability_proven)

    def test_same_uid_can_rename_ancestor_after_review_counterexample(self):
        self.assertEqual(self.inspect().status, REVIEWED)
        real = self.root / "other-level"
        self.level.rename(real)
        self.level.mkdir(mode=0o755)
        self.level.chmod(0o755)
        newbase = self.level / "fixture"
        newbase.mkdir(mode=0o700)
        (newbase / "wr-dd-private").mkdir(mode=0o700)
        (newbase / "wr-dd-private" / "state").mkdir(mode=0o700)
        newlock = newbase / "wr-dd-private" / "state" / "wr-da-review.lock"
        newlock.write_bytes(b"")
        newlock.chmod(0o600)
        self.assertEqual(self.inspect().status, REVIEWED)
        self.assertFalse(self.inspect().independently_protected_storage_attested)

    def test_no_download_process_or_installer_symbols_in_source(self):
        source = (ROOT / "build70_dd_full_ancestry.c").read_text()
        hdr = (ROOT / "build70_dd_full_ancestry.h").read_text()
        for prohibited in ("O_CREAT", "O_WRONLY", "O_RDWR", "unlink(",
                           "rename(", "chmod(", "mkdir(", "socket(",
                           "connect(", "appinst(", "posix_spawn(",
                           "objc_msgSend(", "installApplication:"):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, source)
        for field in ("installation_authorized", "installation_performed",
                      "ios12_client_identity_proven", "powerloss_or_rollback_safe"):
            self.assertIn(field, hdr)


if __name__ == "__main__":
    unittest.main()
