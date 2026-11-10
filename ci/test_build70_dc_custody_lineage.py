#!/usr/bin/env python3
"""Build70/DC host-only lineage test, no network / appinst / installation.

A pretrusted *fixture* anchor + claimed client UID are not real identity.
The C inspector never opens files for writing. CI cross-compiles for iOS12
but NEVER executes this code on an iPad.
"""
from dataclasses import FrozenInstanceError
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class Receipt(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int),
        ("anchored_descendants_privately_owned_on_host", ctypes.c_bool),
        ("lock_file_privately_owned_on_host", ctypes.c_bool),
        ("marker_present", ctypes.c_bool),
        ("hypothetical_client_uid_differs_from_helper", ctypes.c_bool),
        ("anchor_ancestry_independently_attested", ctypes.c_bool),
        ("real_ios12_process_identity_attested", ctypes.c_bool),
        ("app_write_access_denied_on_ios12", ctypes.c_bool),
        ("helper_entitlements_checked_on_ios12", ctypes.c_bool),
        ("immune_to_root_or_same_uid_mutation", ctypes.c_bool),
        ("protected_from_journal_rollback", ctypes.c_bool),
        ("publisher_identity_verified", ctypes.c_bool),
        ("owner_install_consent_verified", ctypes.c_bool),
        ("installation_authorized", ctypes.c_bool),
        ("installation_performed", ctypes.c_bool),
    ]


class DCLineageHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpbuild = tempfile.TemporaryDirectory(prefix="wr-dc-compile-")
        cc = shutil.which("clang") or shutil.which("cc")
        if not cc:
            raise RuntimeError("compiler needed for host-only native inspection")
        output = Path(cls.tmpbuild.name) / (
            "dc.dylib" if sys.platform == "darwin" else "dc.so"
        )
        subprocess.run([
            cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-fPIC", "-shared",
            str(ROOT / "build70_dc_custody_lineage.c"), "-o", str(output),
        ], check=True, capture_output=True, text=True, timeout=30)
        cls.dll = ctypes.CDLL(str(output))
        cls.dll.wr_dc_inspect_host_only.argtypes = (ctypes.c_char_p, ctypes.c_uint32)
        cls.dll.wr_dc_inspect_host_only.restype = Receipt

    @classmethod
    def tearDownClass(cls):
        cls.tmpbuild.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wr-dc-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.base.chmod(0o700)
        self.vault = self.base / "wr-dc-private"
        self.vault.mkdir(mode=0o700)
        self.vault.chmod(0o700)
        self.state = self.vault / "state"
        self.state.mkdir(mode=0o700)
        self.state.chmod(0o700)
        self.lock = self.state / "wr-da-review.lock"
        self.lock.write_bytes(b"")
        self.lock.chmod(0o600)
        self.marker = self.state / "wr-da-check.pending"
        self.client = (os.geteuid() + 1) & 0xFFFFFFFF
        if self.client == 0:
            self.client = 1

    def inspect(self, *, base=None, client=None):
        value = os.fsencode(self.base if base is None else base)
        return self.assert_safe(self.dll.wr_dc_inspect_host_only(
            value, self.client if client is None else client
        ))

    def assert_safe(self, receipt):
        for field in (
            "anchor_ancestry_independently_attested",
            "real_ios12_process_identity_attested",
            "app_write_access_denied_on_ios12",
            "helper_entitlements_checked_on_ios12",
            "immune_to_root_or_same_uid_mutation",
            "protected_from_journal_rollback",
            "publisher_identity_verified",
            "owner_install_consent_verified",
            "installation_authorized", "installation_performed"
        ):
            self.assertFalse(getattr(receipt, field), field)
        return receipt

    def test_expected_host_metadata_never_install_authority(self):
        r = self.inspect()
        self.assertEqual(r.status, 1)
        self.assertTrue(r.anchored_descendants_privately_owned_on_host)
        self.assertTrue(r.lock_file_privately_owned_on_host)
        self.assertTrue(r.hypothetical_client_uid_differs_from_helper)
        self.assertFalse(r.marker_present)

    def test_presence_of_marked_journal_quarantines(self):
        self.marker.write_bytes(b"PENDING-READ-ONLY-CHECK\n")
        self.assertEqual(self.inspect().status, 2)
        self.assertTrue(self.inspect().marker_present)

    def test_empty_or_corrupt_marker_still_quarantines(self):
        for b in (b"", b"P", b"FORGED\n"):
            with self.subTest(contents=b):
                self.marker.write_bytes(b)
                self.assertEqual(self.inspect().status, 2)

    def test_symlink_marker_never_followed_and_quarantines(self):
        outside = self.base / "unrelated"
        outside.write_bytes(b"DO-NOT-TOUCH")
        self.marker.symlink_to(outside)
        r = self.inspect()
        self.assertEqual(r.status, 2)
        self.assertEqual(outside.read_bytes(), b"DO-NOT-TOUCH")

    def test_directory_marker_quarantines(self):
        self.marker.mkdir()
        self.assertEqual(self.inspect().status, 2)

    def test_symlinked_vault_rejected(self):
        self.vault.rename(self.base / "real-vault")
        self.vault.symlink_to(self.base / "real-vault", target_is_directory=True)
        self.assertEqual(self.inspect().status, 0)

    def test_symlinked_state_rejected(self):
        self.state.rename(self.vault / "real-state")
        self.state.symlink_to(self.vault / "real-state", target_is_directory=True)
        self.assertEqual(self.inspect().status, 0)

    def test_symlinked_lock_rejected(self):
        self.lock.rename(self.state / "real.lock")
        self.lock.symlink_to(self.state / "real.lock")
        self.assertEqual(self.inspect().status, 0)

    def test_hardlinked_lock_rejected(self):
        (self.state / "alias.lock").hardlink_to(self.lock)
        self.assertEqual(self.inspect().status, 0)

    def test_wrong_lock_modes_rejected(self):
        for mode in (0o777, 0o640, 0o400, 0o666):
            with self.subTest(mode=oct(mode)):
                self.lock.chmod(mode)
                self.assertEqual(self.inspect().status, 0)

    def test_nonzero_lock_content_rejected(self):
        self.lock.write_bytes(b"FALSETOKEN")
        self.assertEqual(self.inspect().status, 0)

    def test_vault_modes_rejected(self):
        for mode in (0o755, 0o775, 0o777, 0o1700):
            with self.subTest(mode=oct(mode)):
                self.vault.chmod(mode)
                self.assertEqual(self.inspect().status, 0)

    def test_state_modes_rejected(self):
        for mode in (0o755, 0o775, 0o777, 0o2700):
            with self.subTest(mode=oct(mode)):
                self.state.chmod(mode)
                self.assertEqual(self.inspect().status, 0)

    def test_base_modes_rejected(self):
        for mode in (0o755, 0o775, 0o777):
            with self.subTest(mode=oct(mode)):
                self.base.chmod(mode)
                self.assertEqual(self.inspect().status, 0)

    def test_untrusted_claim_same_uid_or_root_rejected(self):
        self.assertEqual(self.inspect(client=os.geteuid()).status, 0)
        self.assertEqual(self.inspect(client=0).status, 0)
        self.assertEqual(self.inspect(client=0).real_ios12_process_identity_attested, False)

    def test_bad_anchor_paths_rejected(self):
        for path in (
            "/",
            "relative/path",
            str(self.base) + "/",
            "/tmp/../tmp/example",
            str(self.base) + "/./child",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.inspect(base=path).status, 0)

    def test_symlinked_anchor_leaf_rejected(self):
        link = self.base.parent / (self.base.name + "-alias")
        link.symlink_to(self.base, target_is_directory=True)
        self.addCleanup(link.unlink)
        self.assertEqual(self.inspect(base=link).status, 0)

    def test_all_file_contents_and_modes_unchanged_by_probe(self):
        self.marker.write_bytes(b"MARKED-BUT-NOT-AN-IPA")
        before = {
            str(p): (p.read_bytes(), p.stat().st_mode & 0o777)
            for p in (self.lock, self.marker)
        }
        for _ in range(20):
            self.assertEqual(self.inspect().status, 2)
        after = {
            str(p): (p.read_bytes(), p.stat().st_mode & 0o777)
            for p in (self.lock, self.marker)
        }
        self.assertEqual(before, after)

    def test_same_uid_can_remove_lock_and_marker_after_inspection(self):
        self.marker.write_bytes(b"MARKED")
        self.assertEqual(self.inspect().status, 2)
        self.marker.unlink()
        self.lock.unlink()
        self.lock.write_bytes(b"")
        self.lock.chmod(0o600)
        r = self.inspect()
        self.assertEqual(r.status, 1)
        self.assertFalse(r.immune_to_root_or_same_uid_mutation)
        self.assertFalse(r.protected_from_journal_rollback)

    def test_replacement_of_lock_inode_after_review_is_unprevented(self):
        r = self.inspect()
        self.assertEqual(r.status, 1)
        self.lock.rename(self.state / "old.lock")
        self.lock.write_bytes(b"")
        self.lock.chmod(0o600)
        self.assertEqual(self.inspect().status, 1)
        self.assertFalse(r.app_write_access_denied_on_ios12)

    def test_host_ancestor_symlink_is_not_independently_proven(self):
        # O_NOFOLLOW protects the anchor *leaf*. Ancestors need independent
        # ownership, link and sandbox verification: this probe does not do it.
        alias_dir = self.base.parent / (self.base.name + "-outer")
        alias_dir.symlink_to(self.base, target_is_directory=True)
        self.addCleanup(alias_dir.unlink)
        # Pointing at a child of a symlink ancestor: POSIX open(base,NOFOLLOW)
        # can still traverse earlier components; this is deliberately NOT
        # proof of an independently trusted root.
        path = str(alias_dir) + "/wr-dc-private/.."
        self.assertEqual(self.inspect(base=path).status, 0)
        self.assertFalse(self.inspect().anchor_ancestry_independently_attested)

    def test_source_has_no_file_creation_or_installing_symbols(self):
        src = (ROOT / "build70_dc_custody_lineage.c").read_text()
        hdr = (ROOT / "build70_dc_custody_lineage.h").read_text()
        for banned in ("O_CREAT", "O_WRONLY", "O_RDWR", "unlink(", "rename(",
                       "fchmod(", "chmod(", "write(", "mkdir(", "socket(",
                       "objc_msgSend(", "appinst(", "posix_spawn(",
                       "installApplication:"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, src)
        for expected in ("WR_DC_HOST_METADATA_REVIEWED", "WR_DC_QUARANTINED",
                         "real_ios12_process_identity_attested",
                         "installation_authorized"):
            self.assertIn(expected, hdr)


if __name__ == "__main__":
    unittest.main()
