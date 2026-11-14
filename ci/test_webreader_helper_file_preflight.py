#!/usr/bin/env python3
"""Offline staged-file preflight adversarial fixtures. No installs, no network."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from webreader_helper_file_preflight import (
    FilePreflightRejected, inspect_prepared_ipa,
)

NAME = "WebReader-build57-12345678-1234-4ABC-9DEF-1234567890AB.ipa"
CONTENT = b"PK\x03\x04" + (b"WebReaderSyntheticTest" * 4096)


class FilePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / NAME
        self.path.write_bytes(CONTENT)
        self.digest = hashlib.sha256(CONTENT).hexdigest()

    def inspect(self, **kw):
        options = dict(expected_build=57, expected_size=len(CONTENT),
                       expected_sha256=self.digest)
        options.update(kw)
        return inspect_prepared_ipa(self.root, NAME, **options)

    def test_regular_staged_file_is_observation_not_install_permission(self):
        report = self.inspect()
        self.assertEqual(report.sha256, self.digest)
        self.assertEqual(report.file_size, len(CONTENT))
        self.assertFalse(report.installer_authorized)
        with self.assertRaises((AttributeError, TypeError)):
            report.installer_authorized = True

    def test_invalid_signed_metadata_is_rejected(self):
        for override in [dict(expected_build=True), dict(expected_build=0),
                         dict(expected_build=2**31), dict(expected_size=True),
                         dict(expected_size=0), dict(expected_size=512*1024*1024+1),
                         dict(expected_sha256=self.digest.upper()),
                         dict(expected_sha256="A"*64),
                         dict(expected_sha256="invalid")]:
            with self.subTest(override=override), self.assertRaises(FilePreflightRejected):
                self.inspect(**override)

    def test_filename_cannot_redirect_to_arbitrary_file(self):
        for leaf in ["../"+NAME, "/tmp/evil.ipa", "WebReader-build58-12345678-1234-4ABC-9DEF-1234567890AB.ipa",
                     "./"+NAME, "WebReader-build57-../../evil.ipa", "evil.ipa", None]:
            with self.subTest(leaf=leaf), self.assertRaises(FilePreflightRejected):
                inspect_prepared_ipa(self.root, leaf, expected_build=57,
                                     expected_size=len(CONTENT), expected_sha256=self.digest)

    def test_symlink_staged_file_rejected(self):
        other = self.root / "outside.ipa"
        other.write_bytes(CONTENT)
        self.path.unlink()
        self.path.symlink_to(other)
        with self.assertRaises(FilePreflightRejected):
            self.inspect()

    def test_symlink_root_directory_rejected(self):
        link = self.root.parent / (self.root.name + "-link")
        self.addCleanup(lambda: link.unlink(missing_ok=True))
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(FilePreflightRejected):
            inspect_prepared_ipa(link, NAME, expected_build=57,
                                 expected_size=len(CONTENT), expected_sha256=self.digest)

    def test_hardlink_rejected(self):
        os.link(self.path, self.root / "other.ipa")
        with self.assertRaises(FilePreflightRejected):
            self.inspect()

    def test_world_writable_file_rejected(self):
        self.path.chmod(0o666)
        with self.assertRaises(FilePreflightRejected):
            self.inspect()

    def test_world_writable_directory_rejected(self):
        self.root.chmod(0o777)
        with self.assertRaises(FilePreflightRejected):
            self.inspect()

    def test_byte_or_size_mismatch_rejected(self):
        self.path.write_bytes(CONTENT + b"x")
        with self.assertRaises(FilePreflightRejected):
            self.inspect()
        self.path.write_bytes(CONTENT[:-1] + b"Z")
        with self.assertRaises(FilePreflightRejected):
            self.inspect()

    def test_not_zip_prefix_rejected_even_if_digest_matches(self):
        content = b"NOTZIP" + CONTENT
        self.path.write_bytes(content)
        with self.assertRaises(FilePreflightRejected):
            self.inspect(expected_size=len(content), expected_sha256=hashlib.sha256(content).hexdigest())

    def test_replaced_filename_during_read_rejected(self):
        replacement = self.root / "replacement.ipa"
        replacement.write_bytes(CONTENT)
        with self.assertRaises(FilePreflightRejected):
            self.inspect(_test_after_first_chunk=lambda: os.replace(replacement, self.path))

    def test_mutated_file_during_read_rejected(self):
        def mutate():
            with self.path.open("r+b") as stream:
                stream.seek(8)
                stream.write(b"X")
        with self.assertRaises(FilePreflightRejected):
            self.inspect(_test_after_first_chunk=mutate)

    def test_fifo_rejected_without_blocking(self):
        self.path.unlink()
        os.mkfifo(self.path)
        with self.assertRaises(FilePreflightRejected):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
