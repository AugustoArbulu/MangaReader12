#!/usr/bin/env python3
"""DB host POSIX user boundary tests. No privileged operation on a device.

On Linux GitHub Actions, one test executes as OS user "nobody" through sudo
against a disposable helper-UID-owned fixture; it must fail if unavailable.
macOS uses same-UID negative cases but does not claim real separate-user QA.
"""
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from build70_db_host_uid_boundary import (
    DBFixtureRejected, PRIVATE, MARKER, LOCK, CREATED,
    run_host_fixture_client_probe,
)

ROOT = Path(__file__).resolve().parent
NEGATIVE = (
    "directory_open_denied", "marker_read_denied",
    "marker_write_denied", "marker_unlink_denied",
    "lock_unlink_denied", "extra_file_create_denied",
)
AUTHORITY = (
    "ios12_helper_uid_isolation_proven",
    "ios12_entitlements_verified",
    "ancestors_owned_by_independent_service",
    "storage_rollback_resistance_proven",
    "editor_trust_provisioned",
    "owner_install_consent_verified",
    "installation_authorized",
    "installation_performed",
)


class DBHostUidBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wr-db-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o755)  # other UID can traverse parent only
        self.private = self.root / PRIVATE
        self.private.mkdir(mode=0o700)
        self.private.chmod(0o700)
        (self.private / MARKER).write_bytes(b"PENDING-READ-ONLY-CHECK\n")
        (self.private / LOCK).write_bytes(b"")
        (self.private / MARKER).chmod(0o600)
        (self.private / LOCK).chmod(0o600)

    def assert_no_product_authority(self, value):
        for field in AUTHORITY:
            self.assertFalse(getattr(value, field), field)

    def test_same_uid_0700_can_still_mutate_own_journal(self):
        result = run_host_fixture_client_probe(self.private)
        self.assertFalse(result.distinct_host_uids_observed)
        self.assertEqual(result.client_euid, os.geteuid())
        self.assertEqual(result.synthetic_directory_owner_uid, os.geteuid())
        self.assertEqual(result.protected_directory_mode, "0o700")
        for field in NEGATIVE:
            self.assertFalse(getattr(result, field), field)
        self.assertFalse((self.private / MARKER).exists())
        self.assertFalse((self.private / LOCK).exists())
        self.assertTrue((self.private / CREATED).exists())
        self.assert_no_product_authority(result)
        with self.assertRaises(FrozenInstanceError):
            result.installation_authorized = True

    def test_world_writable_directory_allows_unlink_of_0600_file(self):
        self.private.chmod(0o777)
        result = run_host_fixture_client_probe(self.private)
        self.assertEqual(result.protected_directory_mode, "0o777")
        # File may be mode 0600 but the file owner can unlink regardless.
        self.assertFalse(result.marker_unlink_denied)
        self.assertFalse(result.lock_unlink_denied)
        self.assertFalse(result.extra_file_create_denied)
        self.assert_no_product_authority(result)

    def test_probe_rejects_arbitrary_paths_and_symlink_leaf(self):
        for bad in (self.root, Path("/"), Path("."), self.root / "somewhere",
                    self.root / PRIVATE / ".."):
            with self.subTest(bad=str(bad)), self.assertRaises(DBFixtureRejected):
                run_host_fixture_client_probe(bad)
        real = self.private
        real.rename(self.root / "real-dir")
        real.symlink_to(self.root / "real-dir", target_is_directory=True)
        with self.assertRaises(DBFixtureRejected):
            run_host_fixture_client_probe(real)

    def test_probe_rejects_parent_mode_other_than_0755(self):
        self.root.chmod(0o700)
        with self.assertRaises(DBFixtureRejected):
            run_host_fixture_client_probe(self.private)

    def test_result_always_denies_install_authority_after_owner_mutation(self):
        result = run_host_fixture_client_probe(self.private)
        self.assert_no_product_authority(result)
        self.assertFalse(result.ios12_helper_uid_isolation_proven)
        self.assertFalse(result.storage_rollback_resistance_proven)

    def test_nonexistent_marker_does_not_imply_safe_recovery(self):
        (self.private / MARKER).unlink()
        result = run_host_fixture_client_probe(self.private)
        self.assert_no_product_authority(result)
        self.assertFalse(result.distinct_host_uids_observed)

    @unittest.skipUnless(platform.system() == "Linux", "Linux-only separate UID runner")
    def test_real_linux_distinct_uid_cannot_open_or_modify_0700_journal(self):
        sudo = shutil.which("sudo")
        self.assertTrue(sudo, "Linux CI must provide sudo for real-UID negative test")
        # GitHub Linux runner has passwordless sudo. Fail, don't silently skip,
        # when a real OS-owned identity comparison cannot run.
        command = [
            sudo, "-n", "-u", "nobody", sys.executable,
            str(ROOT / "build70_db_host_uid_boundary.py"), str(self.private),
        ]
        child = subprocess.run(command, text=True, capture_output=True, timeout=15)
        self.assertEqual(child.returncode, 0, child.stderr)
        observation = json.loads(child.stdout.strip())
        self.assertNotEqual(observation["client_euid"], os.geteuid())
        self.assertEqual(observation["synthetic_directory_owner_uid"], os.geteuid())
        self.assertTrue(observation["distinct_host_uids_observed"])
        self.assertEqual(observation["protected_directory_mode"], "0o700")
        for field in NEGATIVE:
            self.assertTrue(observation[field], field)
        for field in AUTHORITY:
            self.assertFalse(observation[field], field)
        self.assertEqual((self.private / MARKER).read_bytes(),
                         b"PENDING-READ-ONLY-CHECK\n")
        self.assertEqual((self.private / LOCK).read_bytes(), b"")
        self.assertFalse((self.private / CREATED).exists())

    @unittest.skipUnless(platform.system() == "Linux", "Linux-only separate UID runner")
    def test_linux_world_writable_directory_allows_nonowner_to_erase_0600_marker(self):
        sudo = shutil.which("sudo")
        self.assertTrue(sudo)
        self.private.chmod(0o777)
        child = subprocess.run([
            sudo, "-n", "-u", "nobody", sys.executable,
            str(ROOT / "build70_db_host_uid_boundary.py"), str(self.private),
        ], text=True, capture_output=True, timeout=15)
        self.assertEqual(child.returncode, 0, child.stderr)
        observation = json.loads(child.stdout.strip())
        self.assertTrue(observation["distinct_host_uids_observed"])
        self.assertTrue(observation["marker_read_denied"])
        self.assertTrue(observation["marker_write_denied"])
        self.assertFalse(observation["marker_unlink_denied"])
        self.assertFalse(observation["lock_unlink_denied"])
        self.assertFalse(observation["extra_file_create_denied"])
        self.assertFalse((self.private / MARKER).exists())
        self.assertFalse((self.private / LOCK).exists())
        for field in AUTHORITY:
            self.assertFalse(observation[field], field)

    def test_no_network_installer_or_privilege_operation_in_probe(self):
        code = (ROOT / "build70_db_host_uid_boundary.py").read_text()
        for banned in (
            "subprocess", "sudo ", "setuid(", "setgid(", "posix_spawn(",
            "appinst(", "installApplication:", "socket.", "urllib", "requests."
        ):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, code)

    def test_probes_only_fixed_synthetic_journal_names(self):
        code = (ROOT / "build70_db_host_uid_boundary.py").read_text()
        self.assertIn('PRIVATE = "wr-db-helper-private"', code)
        self.assertIn('MARKER = "wr-da-check.pending"', code)
        self.assertIn('LOCK = "wr-da-review.lock"', code)
        self.assertIn("wr-db-fixture-", code)


if __name__ == "__main__":
    unittest.main()
