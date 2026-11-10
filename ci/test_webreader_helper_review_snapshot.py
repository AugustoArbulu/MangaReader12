#!/usr/bin/env python3
"""CK: attack-oriented tests of a HOST-ONLY protected review copy.

This intentionally does NOT prove iOS12 peer identity, immutable installer
handle, verified Apple code seal, owner publication approval or permission
to execute appinst.
"""
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest

from webreader_helper_review_snapshot import (
    protected_review_snapshot, ReviewSnapshotRejected,
    ReviewSnapshotReceipt
)

DATA = b"PK\x03\x04" + b"REVIEW ONLY - NEVER A VALID IPHONE IPA" * 9000


class ProtectedReviewSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wr-ck-review-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.src = self.root / "untrusted-downloaded.ipa"
        self.src.write_bytes(DATA)
        self.src.chmod(0o600)
        self.staging = self.root / "protected"
        self.staging.mkdir(mode=0o700)
        self.digest = hashlib.sha256(DATA).hexdigest()

    def stage(self, **kw):
        args = dict(source_path=self.src, staging_directory=self.staging,
                    expected_sha256=self.digest, expected_size=len(DATA),
                    requested_build=71)
        args.update(kw)
        return protected_review_snapshot(**args)

    def test_success_is_an_inert_review_copy_not_install_authorization(self):
        receipt = self.stage()
        self.assertIsInstance(receipt, ReviewSnapshotReceipt)
        self.assertEqual(receipt.checked_sha256, self.digest)
        self.assertEqual(receipt.requested_build, 71)
        for key in (
            "independent_signature_verified", "publisher_identity_verified",
            "immutable_installer_handle_issued", "peer_authenticated",
            "user_consent_verified", "install_authorized",
            "installation_performed"
        ):
            with self.subTest(flag=key):
                self.assertFalse(getattr(receipt, key))
        copied = self.staging / receipt.review_basename
        self.assertTrue(copied.is_file())
        self.assertEqual(copied.read_bytes(), DATA)
        self.assertEqual(stat.S_IMODE(copied.stat().st_mode), 0o400)
        self.assertNotEqual(os.stat(self.src).st_ino, copied.stat().st_ino)
        self.assertEqual(stat.S_IMODE(self.src.stat().st_mode), 0o600)
        with self.assertRaises((AttributeError, TypeError)):
            receipt.install_authorized = True

    def test_replay_output_cannot_be_overwritten(self):
        receipt = self.stage()
        target = self.staging / receipt.review_basename
        with self.assertRaises(ReviewSnapshotRejected):
            self.stage()
        self.assertEqual(target.read_bytes(), DATA)

    def test_wrong_digest_or_size_or_build_never_accepted(self):
        for override in (
            dict(expected_sha256="0"*64), dict(expected_sha256=self.digest.upper()),
            dict(expected_sha256=self.digest[:-1]), dict(expected_size=len(DATA)+1),
            dict(expected_size=True), dict(expected_size=-1),
            dict(requested_build=0), dict(requested_build=True),
            dict(requested_build="71"),
        ):
            with self.subTest(override=override):
                # In failure modes a destination tombstone may intentionally remain.
                with tempfile.TemporaryDirectory(prefix="wr-ck-override-") as td:
                    destination = Path(td)
                    destination.chmod(0o700)
                    with self.assertRaises(ReviewSnapshotRejected):
                        self.stage(staging_directory=destination, **override)

    def test_symlink_and_hardlinked_source_are_denied(self):
        alias = self.root / "source-link.ipa"
        alias.symlink_to(self.src)
        with self.assertRaises(ReviewSnapshotRejected):
            self.stage(source_path=alias)
        alias.unlink()
        os.link(self.src, alias)
        try:
            with self.assertRaises(ReviewSnapshotRejected):
                self.stage()
        finally:
            alias.unlink()

    def test_symlink_or_world_readable_destination_is_denied(self):
        alias = self.root / "directory-alias"
        alias.symlink_to(self.staging, target_is_directory=True)
        with self.assertRaises(ReviewSnapshotRejected):
            self.stage(staging_directory=alias)
        self.staging.chmod(0o755)
        with self.assertRaises(ReviewSnapshotRejected):
            self.stage()

    def test_world_or_group_writable_source_denied(self):
        for mode in (0o622, 0o666, 0o642):
            self.src.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(ReviewSnapshotRejected):
                self.stage()
        self.src.chmod(0o600)

    def test_mutated_source_mid_copy_is_denied(self):
        def overwrite():
            with self.src.open("r+b") as f:
                f.seek(8)
                f.write(b"FAKE")
        with self.assertRaises(ReviewSnapshotRejected):
            self.stage(on_first_chunk=overwrite)
        # The failed copy is not silently retried over an existing path.
        with self.assertRaises(ReviewSnapshotRejected):
            self.stage()

    def test_source_path_replaced_during_copy_is_denied(self):
        replacement = self.root / "replacement.ipa"
        replacement.write_bytes(DATA)
        replacement.chmod(0o600)
        def replace_name():
            os.replace(replacement, self.src)
        with self.assertRaises(ReviewSnapshotRejected):
            self.stage(on_first_chunk=replace_name)

    def test_too_small_non_zip_source_cannot_fake_a_successful_sha(self):
        self.src.write_bytes(b"BAD")
        digest = hashlib.sha256(b"BAD").hexdigest()
        with self.assertRaises(ReviewSnapshotRejected):
            self.stage(expected_size=3, expected_sha256=digest)

    def test_no_appinst_or_privilege_in_prototype(self):
        text = (Path(__file__).with_name("webreader_helper_review_snapshot.py")
                .read_text())
        for disallowed in ("posix_spawn(", "subprocess.", "os.system(",
                           "appinst(", "sudo ", "ctypes.CDLL(", "URLSession("):
            self.assertNotIn(disallowed, text)
        self.assertIn("immutable_installer_handle_issued: bool = False", text)


if __name__ == "__main__":
    unittest.main()
