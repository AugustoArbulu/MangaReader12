#!/usr/bin/env python3
"""CU adversarial host fixture; no iOS, no escalation, no appinst."""
from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path
import tempfile
import unittest

from build70_cu_helper_custody_audit import (
    CustodyAuditRejected, inspect_anchored_host_file
)


class CUCustodyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wr-cu-host-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.folder = self.root / "private"
        self.folder.mkdir(mode=0o700)
        self.folder.chmod(0o700)
        self.leaf = self.folder / "candidate.fake"
        self.content = b"CU_FAKE_NO_IPA_" * 64
        self.leaf.write_bytes(self.content)
        self.digest = hashlib.sha256(self.content).hexdigest()

    def inspect(self, **overrides):
        options = dict(anchor=self.root, components=("private",),
                       leaf="candidate.fake", expected_size=len(self.content),
                       expected_sha256=self.digest)
        options.update(overrides)
        return inspect_anchored_host_file(**options)

    def test_good_host_snapshot_does_not_authorize(self):
        receipt = self.inspect()
        self.assertTrue(receipt.fd_and_filename_agreed_at_review)
        self.assertEqual(receipt.ancestor_directory_descriptors_checked, 2)
        self.assertEqual(receipt.checked_sha256, self.digest)
        self.assertEqual(receipt.size, len(self.content))
        for name in (
            "chain_root_from_trusted_device_policy", "separate_helper_uid_verified_on_device",
            "client_write_access_excluded", "future_inode_mutation_excluded",
            "appinst_secondary_copy_protected", "final_installer_bytes_bound_to_verified_fd",
            "production_editor_identity_authenticated", "consent_from_trusted_owner_ui",
            "durable_antireplay_completed", "ios12_runtime_verified",
            "installation_authorized", "installation_performed"
        ):
            with self.subTest(name=name):
                self.assertFalse(getattr(receipt, name))
        with self.assertRaises(FrozenInstanceError):
            receipt.installation_authorized = True

    def test_anchor_mode_shared_denied(self):
        self.root.chmod(0o755)
        with self.assertRaises(CustodyAuditRejected):
            self.inspect()

    def test_child_mode_shared_denied(self):
        self.folder.chmod(0o775)
        with self.assertRaises(CustodyAuditRejected):
            self.inspect()

    def test_child_symlink_denied(self):
        self.folder.rename(self.root / "real")
        self.folder.symlink_to(self.root / "real", target_is_directory=True)
        with self.assertRaises(CustodyAuditRejected):
            self.inspect()

    def test_anchor_symlink_denied(self):
        alias = self.root.parent / "alias-cu"
        alias.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(alias.unlink)
        with self.assertRaises(CustodyAuditRejected):
            self.inspect(anchor=alias)

    def test_file_symlink_denied(self):
        self.leaf.rename(self.folder / "real.fake")
        self.leaf.symlink_to(self.folder / "real.fake")
        with self.assertRaises(CustodyAuditRejected):
            self.inspect()

    def test_file_hardlink_denied(self):
        second = self.folder / "extra.fake"
        second.hardlink_to(self.leaf)
        with self.assertRaises(CustodyAuditRejected):
            self.inspect()

    def test_file_group_writable_denied(self):
        self.leaf.chmod(0o620)
        with self.assertRaises(CustodyAuditRejected):
            self.inspect()

    def test_digest_different_denied(self):
        with self.assertRaises(CustodyAuditRejected):
            self.inspect(expected_sha256="0" * 64)

    def test_expected_size_different_denied(self):
        with self.assertRaises(CustodyAuditRejected):
            self.inspect(expected_size=len(self.content)+1)

    def test_root_path_not_traversed(self):
        for components in (("..",), ("private", ".."), ("private/child",),
                           ("private",)*6, ["private"]):
            with self.subTest(components=components), self.assertRaises(CustodyAuditRejected):
                self.inspect(components=components)
        for leaf in ("../candidate.fake", "candidate.fake/", "/candidate.fake", "bad.ipa"):
            with self.subTest(leaf=leaf), self.assertRaises(CustodyAuditRejected):
                self.inspect(leaf=leaf)

    def test_renamed_final_path_rejected(self):
        def swap():
            self.leaf.rename(self.folder / "old.fake")
            self.leaf.write_bytes(self.content)
        with self.assertRaises(CustodyAuditRejected):
            self.inspect(after_read=swap)

    def test_inplace_change_before_final_stat_rejected(self):
        def change():
            self.leaf.write_bytes(b"X" * len(self.content))
        with self.assertRaises(CustodyAuditRejected):
            self.inspect(after_read=change)

    def test_read_only_still_cannot_prove_future_immutability(self):
        self.leaf.chmod(0o400)
        receipt = self.inspect()
        self.assertFalse(receipt.future_inode_mutation_excluded)
        self.leaf.chmod(0o600)
        self.leaf.write_bytes(b"X" * len(self.content))
        self.assertNotEqual(hashlib.sha256(self.leaf.read_bytes()).hexdigest(), self.digest)

    def test_installer_compatibility_never_asserted(self):
        receipt = self.inspect()
        self.assertFalse(receipt.final_installer_bytes_bound_to_verified_fd)
        self.assertFalse(receipt.appinst_secondary_copy_protected)
        self.assertFalse(receipt.ios12_runtime_verified)


if __name__ == "__main__":
    unittest.main()
