#!/usr/bin/env python3
"""Regression tests for host-only crash-closed replay markers; no installer."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from build66_durable_replay_journal import (
    DiagnosticReplayJournal, ReplayJournalUnavailable
)

GOOD = {
    "challenge": "01" * 16,
    "manifest_sha256": "a" * 64,
    "ipa_sha256": "b" * 64,
    "target_build": 66,
}


class DurableReplayJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wr66-durable-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "journal"
        self.root.mkdir(mode=0o700)
        self.store = DiagnosticReplayJournal(self.root)

    def marker_files(self):
        return list(self.root.iterdir())

    def test_first_reservation_is_durable_and_one_shot(self):
        self.assertTrue(self.store.reserve_once(**GOOD))
        files = self.marker_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), b"SPENT\n")
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.store.reserve_once(**GOOD))

    def test_restart_reopens_same_owner_private_state(self):
        self.assertTrue(self.store.reserve_once(**GOOD))
        another = DiagnosticReplayJournal(self.root)
        self.assertFalse(another.reserve_once(**GOOD))

    def test_separate_python_process_denies_replay(self):
        self.assertTrue(self.store.reserve_once(**GOOD))
        snippet = (
            "from build66_durable_replay_journal import DiagnosticReplayJournal;"
            "from pathlib import Path;"
            "import sys;"
            "root=Path(sys.argv[1]);"
            "s=DiagnosticReplayJournal(root);"
            "print(s.reserve_once(challenge='01'*16,"
            "manifest_sha256='a'*64,ipa_sha256='b'*64,target_build=66))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", snippet, str(self.root)],
            check=True, capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parent)
        )
        self.assertEqual(completed.stdout.strip(), "False")

    def test_two_independent_handles_race_only_one_wins(self):
        latch = threading.Barrier(3)
        results = []
        lock = threading.Lock()
        s2 = DiagnosticReplayJournal(self.root)

        def attempt(store):
            latch.wait()
            result = store.reserve_once(**GOOD)
            with lock:
                results.append(result)

        first = threading.Thread(target=attempt, args=(self.store,))
        second = threading.Thread(target=attempt, args=(s2,))
        first.start()
        second.start()
        latch.wait()
        first.join(timeout=3)
        second.join(timeout=3)
        self.assertCountEqual(results, [True, False])

    def test_existing_empty_marker_means_spent_after_crash(self):
        name = self.store._marker_name(**GOOD)
        (self.root / name).write_bytes(b"")
        self.assertFalse(self.store.reserve_once(**GOOD))

    def test_existing_partially_written_marker_means_spent(self):
        name = self.store._marker_name(**GOOD)
        (self.root / name).write_bytes(b"SP")
        self.assertFalse(self.store.reserve_once(**GOOD))

    def test_different_manifest_digest_uses_distinct_marker(self):
        self.assertTrue(self.store.reserve_once(**GOOD))
        changed = dict(GOOD, manifest_sha256="c" * 64)
        self.assertTrue(self.store.reserve_once(**changed))

    def test_different_ipa_digest_uses_distinct_marker(self):
        self.assertTrue(self.store.reserve_once(**GOOD))
        changed = dict(GOOD, ipa_sha256="c" * 64)
        self.assertTrue(self.store.reserve_once(**changed))

    def test_different_target_build_uses_distinct_marker(self):
        self.assertTrue(self.store.reserve_once(**GOOD))
        changed = dict(GOOD, target_build=67)
        self.assertTrue(self.store.reserve_once(**changed))

    def test_different_challenge_uses_distinct_marker(self):
        self.assertTrue(self.store.reserve_once(**GOOD))
        changed = dict(GOOD, challenge="02" * 16)
        self.assertTrue(self.store.reserve_once(**changed))

    def test_marker_filename_has_no_manifest_or_ipa_digest_literal(self):
        self.store.reserve_once(**GOOD)
        filename = self.marker_files()[0].name
        self.assertNotIn("a" * 64, filename)
        self.assertNotIn("b" * 64, filename)
        self.assertEqual(len(filename), 70)
        self.assertTrue(filename.endswith(".spent"))

    def test_reject_directory_symlink(self):
        link = Path(self.tmp.name) / "journal-link"
        link.symlink_to(self.root)
        with self.assertRaises(ReplayJournalUnavailable):
            DiagnosticReplayJournal(link)

    def test_missing_directory_is_rejected_and_not_created(self):
        missing = self.root / "uncreated"
        with self.assertRaises(ReplayJournalUnavailable):
            DiagnosticReplayJournal(missing)
        self.assertFalse(missing.exists())

    def test_world_readable_root_fails_closed(self):
        self.root.chmod(0o755)
        with self.assertRaises(ReplayJournalUnavailable):
            DiagnosticReplayJournal(self.root)

    def test_permissions_changed_after_init_fails_closed(self):
        self.root.chmod(0o777)
        with self.assertRaises(ReplayJournalUnavailable):
            self.store.reserve_once(**GOOD)
        self.assertEqual(self.marker_files(), [])

    def test_root_replaced_by_symlink_after_init_fails_closed(self):
        other = Path(self.tmp.name) / "other"
        other.mkdir(mode=0o700)
        self.root.rename(Path(self.tmp.name) / "renamed-original")
        self.root.symlink_to(other)
        with self.assertRaises(ReplayJournalUnavailable):
            self.store.reserve_once(**GOOD)
        self.assertEqual(list(other.iterdir()), [])

    def test_path_that_is_file_is_rejected(self):
        target = Path(self.tmp.name) / "not-directory"
        target.write_bytes(b"data")
        with self.assertRaises(ReplayJournalUnavailable):
            DiagnosticReplayJournal(target)

    def test_zero_length_challenge_rejected_without_marker(self):
        with self.assertRaises(ReplayJournalUnavailable):
            self.store.reserve_once(**dict(GOOD, challenge=""))
        self.assertEqual(self.marker_files(), [])

    def test_invalid_sha256_rejected_without_marker(self):
        with self.assertRaises(ReplayJournalUnavailable):
            self.store.reserve_once(**dict(GOOD, ipa_sha256="ZZ" * 32))
        self.assertEqual(self.marker_files(), [])

    def test_bool_build_rejected_without_marker(self):
        with self.assertRaises(ReplayJournalUnavailable):
            self.store.reserve_once(**dict(GOOD, target_build=True))
        self.assertEqual(self.marker_files(), [])

    def test_zero_build_rejected_without_marker(self):
        with self.assertRaises(ReplayJournalUnavailable):
            self.store.reserve_once(**dict(GOOD, target_build=0))

    def test_marker_creation_error_fails_closed(self):
        with mock.patch("build66_durable_replay_journal.os.open",
                        side_effect=OSError("injected open failure")):
            with self.assertRaises(ReplayJournalUnavailable):
                self.store.reserve_once(**GOOD)

    def test_fsync_error_does_not_unlink_reserved_marker(self):
        with mock.patch("build66_durable_replay_journal.os.fsync",
                        side_effect=OSError("injected durable-write failure")):
            with self.assertRaises(ReplayJournalUnavailable):
                self.store.reserve_once(**GOOD)
        self.assertEqual(len(self.marker_files()), 1)
        self.assertFalse(self.store.reserve_once(**GOOD))


if __name__ == "__main__":
    unittest.main()
