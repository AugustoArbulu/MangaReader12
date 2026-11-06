#!/usr/bin/env python3
"""Build60 disposable gate tests. ONLY a fake appinst and non-installable data."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).with_name("webreader_chimera_disposable_gate.c")
V1 = "WebReader-Appinst-Disposable-v1-iOS12-unsigned.ipa"
V2 = "WebReader-Appinst-Disposable-v2-iOS12-unsigned.ipa"
CONSENT = "I-CONFIRM-DISPOSABLE-ONLY"


class DisposableGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin":
            raise unittest.SkipTest("macOS + Xcode CommonCrypto required")
        if os.geteuid() == 0:
            raise unittest.SkipTest("Nonroot only")
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr-build60-")
        cls.root = Path(cls.tmp.name).resolve()
        cls.v1, cls.v2 = cls.root / V1, cls.root / V2
        cls.v1.write_bytes(b"PK\x03\x04" + b"INERT_V1_NOT_AN_IPA" * 500)
        cls.v2.write_bytes(b"PK\x03\x04" + b"INERT_V2_NOT_AN_IPA" * 500)
        cls.v1.chmod(0o600)
        cls.v2.chmod(0o600)
        cls.sha1 = hashlib.sha256(cls.v1.read_bytes()).hexdigest()
        cls.sha2 = hashlib.sha256(cls.v2.read_bytes()).hexdigest()
        cls.fake = cls.root / "fake-appinst"
        cls.fake.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$1" >> "$WRD_TEST_LOG"\n'
            'exit "$WRD_FAKE_EXIT"\n'
        )
        cls.fake.chmod(0o700)
        cls.bin = cls.root / "disposable-gate"
        command = [
            "xcrun", "clang", "-std=c11", "-Os", "-Wall", "-Wextra",
            "-Werror", "-Wno-deprecated-declarations",
            '-DWRD_TEST_ROOT="' + str(cls.root) + '"',
            '-DWRD_TEST_APPINST="' + str(cls.fake) + '"',
            '-DWRD_SHA_V1="' + cls.sha1 + '"',
            '-DWRD_SHA_V2="' + cls.sha2 + '"',
            str(SOURCE), "-o", str(cls.bin)
        ]
        result = subprocess.run(command, text=True, capture_output=True, timeout=35)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.log = cls.root / "appinst-calls.txt"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.log.unlink(missing_ok=True)

    def run_gate(self, *args, fail=False, input_text=None):
        env = dict(os.environ, WRD_TEST_LOG=str(self.log),
                   WRD_FAKE_EXIT=("13" if fail else "0"))
        return subprocess.run(
            [str(self.bin), *args], capture_output=True, text=True,
            timeout=15, env=env, input=input_text
        )

    def test_selftest_cannot_launch_appinst(self):
        r = self.run_gate("selftest")
        self.assertEqual(r.returncode, 0)
        self.assertIn("only fixed disposable", r.stdout)
        self.assertFalse(self.log.exists())

    def test_inspect_both_versions_without_install(self):
        for v in ("1", "2"):
            r = self.run_gate("inspect-v" + v)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("VERIFIED", r.stdout)
        self.assertFalse(self.log.exists())

    def test_user_confirmation_required(self):
        for args in [
            ("install-v1",), ("install-v2",), ("install-v1", "yes"),
            ("install-v2", "I-CONFIRM-INSTALL"),
            ("install-webreader", CONSENT), ("install-v3", CONSENT),
            ("inspect-v1", CONSENT), ("run-disposable-qa",),
        ]:
            with self.subTest(args=args):
                r = self.run_gate(*args)
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse(self.log.exists())

    def test_valid_confirmed_disposable_only(self):
        for version, pathname in [("1", self.v1), ("2", self.v2)]:
            with self.subTest(version=version):
                r = self.run_gate("install-v" + version, CONSENT)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("APPINST_SUCCESS", r.stdout)
                self.assertEqual(self.log.read_text().splitlines()[-1],
                                 str(pathname))
        self.assertEqual(self.log.read_text().splitlines(),
                         [str(self.v1), str(self.v2)])

    def test_single_session_v1_to_v2_with_explicit_next(self):
        r = self.run_gate(
            "run-disposable-qa", CONSENT, input_text="NEXT\n"
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("BOTH_VERIFIED", r.stdout)
        self.assertIn("V1_APPINST_SUCCESS", r.stdout)
        self.assertIn("V2_APPINST_SUCCESS", r.stdout)
        self.assertEqual(
            self.log.read_text().splitlines(), [str(self.v1), str(self.v2)]
        )

    def test_single_session_refuses_implicit_transition(self):
        r = self.run_gate(
            "run-disposable-qa", CONSENT, input_text="CANCEL\n"
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("STOPPED", r.stderr)
        self.assertEqual(self.log.read_text().splitlines(), [str(self.v1)])

    def test_modified_ipa_denied(self):
        original = self.v2.read_bytes()
        try:
            self.v2.write_bytes(original + b"MUTATED")
            r = self.run_gate("install-v2", CONSENT)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("SHA-256 mismatch", r.stderr)
            self.assertFalse(self.log.exists())
        finally:
            self.v2.write_bytes(original)
            self.v2.chmod(0o600)

    def test_symlink_and_hardlink_denied(self):
        original = self.v2.read_bytes()
        target = self.root / "real.ipa"
        try:
            self.v2.rename(target)
            self.v2.symlink_to(target)
            r = self.run_gate("install-v2", CONSENT)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(self.log.exists())
            self.v2.unlink()
            os.link(target, self.v2)
            r = self.run_gate("install-v2", CONSENT)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(self.log.exists())
        finally:
            self.v2.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            self.v2.write_bytes(original)
            self.v2.chmod(0o600)

    def test_group_writable_file_denied(self):
        try:
            self.v1.chmod(0o622)
            self.assertNotEqual(
                self.run_gate("install-v1", CONSENT).returncode, 0)
            self.assertFalse(self.log.exists())
        finally:
            self.v1.chmod(0o600)

    def test_appinst_failure_not_reported_as_success(self):
        r = self.run_gate("install-v1", CONSENT, fail=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("INSTALL_FAILED", r.stderr)
        self.assertTrue(self.log.exists())


if __name__ == "__main__":
    unittest.main()
