#!/usr/bin/env python3
"""No-network, no-jailbreak rehearsal using synthetic ZIP-header bytes only."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from webreader_private_snapshot import (
    PrivateSnapshot, SnapshotRejected, prepare_private_snapshot,
)

LEAF = 'WebReader-build57-12345678-1234-4ABC-9DEF-1234567890AB.ipa'
PAYLOAD = b'PK\x03\x04' + b'FAKE_WEBREADER_FOR_HOST_ONLY' * 5000


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base = Path(t.name)
        self.source = self.base / 'source'
        self.private = self.base / 'private'
        self.source.mkdir(mode=0o700)
        self.private.mkdir(mode=0o700)
        self.path = self.source / LEAF
        self.path.write_bytes(PAYLOAD)
        self.digest = hashlib.sha256(PAYLOAD).hexdigest()

    def snapshot(self, **extra):
        args = dict(expected_build=57, expected_size=len(PAYLOAD),
                    expected_sha256=self.digest)
        args.update(extra)
        return prepare_private_snapshot(self.source, LEAF, self.private, **args)

    def test_private_copy_isolated_from_source_replacement(self):
        snap = self.snapshot()
        self.addCleanup(snap.remove_for_test)
        self.assertTrue(snap.verify_snapshot())
        self.assertFalse(snap.installer_authorized)
        self.path.unlink()
        self.path.write_bytes(b'malicious replacement')
        self.assertTrue(snap.verify_snapshot())

    def test_private_output_exclusive_permissions(self):
        snap = self.snapshot()
        self.addCleanup(snap.remove_for_test)
        files = list(self.private.iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o400)
        self.assertEqual(files[0].stat().st_nlink, 1)

    def test_explicit_cleanup_removes_only_snapshot(self):
        snap = self.snapshot()
        self.assertEqual(len(list(self.private.iterdir())), 1)
        snap.remove_for_test()
        self.assertEqual(list(self.private.iterdir()), [])
        with self.assertRaises(SnapshotRejected):
            snap.verify_snapshot()

    def test_source_data_mutated_during_copy_rejected(self):
        def mutate():
            with self.path.open('r+b') as f:
                f.seek(9)
                f.write(b'Z')
        with self.assertRaises(SnapshotRejected):
            self.snapshot(_test_after_first_chunk=mutate)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_source_filename_replaced_during_copy_rejected(self):
        def replace():
            other = self.source / 'other.ipa'
            other.write_bytes(PAYLOAD)
            os.replace(other, self.path)
        with self.assertRaises(SnapshotRejected):
            self.snapshot(_test_after_first_chunk=replace)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_incorrect_expected_hash_and_size_rejected(self):
        for extra in [dict(expected_size=len(PAYLOAD)+1),
                      dict(expected_sha256='f'*64),
                      dict(expected_build=58),
                      dict(expected_build=True),
                      dict(expected_size=True),
                      dict(expected_sha256=self.digest.upper())]:
            with self.subTest(extra=extra), self.assertRaises(SnapshotRejected):
                self.snapshot(**extra)
            self.assertEqual(list(self.private.iterdir()), [])

    def test_source_symlink_and_hardlink_rejected(self):
        target = self.source / 'other.ipa'
        target.write_bytes(PAYLOAD)
        self.path.unlink()
        self.path.symlink_to(target)
        with self.assertRaises(SnapshotRejected):
            self.snapshot()
        self.path.unlink()
        os.link(target, self.path)
        with self.assertRaises(SnapshotRejected):
            self.snapshot()

    def test_private_directory_not_private_rejected(self):
        self.private.chmod(0o777)
        with self.assertRaises(SnapshotRejected):
            self.snapshot()
        self.assertEqual(list(self.private.iterdir()), [])

    def test_private_root_symlink_rejected(self):
        alias = self.base / 'private-link'
        alias.symlink_to(self.private, target_is_directory=True)
        with self.assertRaises(SnapshotRejected):
            prepare_private_snapshot(
                self.source, LEAF, alias,
                expected_build=57, expected_size=len(PAYLOAD),
                expected_sha256=self.digest,
            )

    def test_same_source_destination_rejected(self):
        with self.assertRaises(SnapshotRejected):
            prepare_private_snapshot(
                self.source, LEAF, self.source,
                expected_build=57, expected_size=len(PAYLOAD),
                expected_sha256=self.digest,
            )

    def test_unsafe_source_directory_rejected(self):
        self.source.chmod(0o777)
        with self.assertRaises(SnapshotRejected):
            self.snapshot()

    def test_non_zip_header_rejected(self):
        raw = b'NOZIP' + PAYLOAD[5:]
        self.path.write_bytes(raw)
        with self.assertRaises(SnapshotRejected):
            self.snapshot(expected_size=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest())

    def test_digest_after_snapshot_detects_mutation_by_same_owner(self):
        snap = self.snapshot()
        self.addCleanup(snap.remove_for_test)
        file = next(self.private.iterdir())
        file.chmod(0o600)   # same-UID simulation, NOT an unprivileged external app
        with file.open('r+b') as f:
            f.seek(7)
            f.write(b'X')
        with self.assertRaises(SnapshotRejected):
            snap.verify_snapshot()

    def test_existing_destination_name_never_overwritten(self):
        predetermined = 'a'*32
        victim = self.private / ('verified-'+predetermined+'.ipa')
        victim.write_bytes(b'KEEP ME')
        with patch('webreader_private_snapshot.secrets.token_hex', return_value=predetermined):
            with self.assertRaises(SnapshotRejected):
                self.snapshot()
        self.assertEqual(victim.read_bytes(), b'KEEP ME')
        self.assertEqual(list(self.private.iterdir()), [victim])

    def test_existing_temporary_name_is_never_deleted(self):
        token = 'c'*32
        preexisting = self.private / ('.incoming-'+token+'.tmp')
        preexisting.write_bytes(b'KEEP TEMPORARY VICTIM')
        with patch('webreader_private_snapshot.secrets.token_hex', return_value=token):
            with self.assertRaises(SnapshotRejected):
                self.snapshot()
        self.assertEqual(preexisting.read_bytes(), b'KEEP TEMPORARY VICTIM')
        self.assertEqual(list(self.private.iterdir()), [preexisting])

    def test_cleanup_does_not_delete_a_replaced_filename(self):
        snap = self.snapshot()
        existing = next(self.private.iterdir())
        moved = self.private / 'moved-original.ipa'
        existing.rename(moved)
        existing.write_bytes(b'PRESERVE NEW FILE')
        snap.remove_for_test()
        self.assertEqual(existing.read_bytes(), b'PRESERVE NEW FILE')
        moved.unlink()

    def test_untrusted_filename_cannot_escape(self):
        for filename in ['../'+LEAF, LEAF+'/../other.ipa',
                         'WebReader-build57-no-uuid.ipa', '/tmp/file.ipa']:
            with self.subTest(filename=filename), self.assertRaises(SnapshotRejected):
                prepare_private_snapshot(
                    self.source, filename, self.private,
                    expected_build=57, expected_size=len(PAYLOAD),
                    expected_sha256=self.digest,
                )

    def test_same_source_byte_count_not_enough_if_hash_differs(self):
        self.path.write_bytes(PAYLOAD[:-1]+b'Z')
        with self.assertRaises(SnapshotRejected):
            self.snapshot()


if __name__ == '__main__':
    unittest.main()
