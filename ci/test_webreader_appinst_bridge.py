#!/usr/bin/env python3
"""macOS host tests for the proposed mobile-user appinst CLI bridge.

Compiled with a FAKE fixed appinst and synthetic staging root. No real IPA
installation, no shell invoked by the bridge, no iPhone and no root access.
"""
import hashlib
import os
import select
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).with_name("webreader_appinst_bridge.c")
CONTAINER = "12345678-1234-4ABC-9DEF-1234567890AB"
LEAF = "WebReader-build57-12345678-1234-4ABC-9DEF-1234567890AB.ipa"
PAYLOAD = b"PK\x03\x04" + b"CI_NON_INSTALLABLE_IPA_TEST_ONLY" * 4000


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin":
            raise unittest.SkipTest("Uses native CommonCrypto on macOS Actions")
        if os.geteuid() == 0:
            raise unittest.SkipTest("Mobile-user bridge deliberately refuses root")
        cls.temp = tempfile.TemporaryDirectory(prefix="wr-bridge-", dir="/tmp")
        cls.root = Path(cls.temp.name).resolve()
        cls.fake_appinst = cls.root / "fake_appinst.sh"
        cls.marker = cls.root / "fake-invocation.txt"
        cls.fake_appinst.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$#\" \"$1\" > \"$WEBREADER_FAKE_INSTALL_LOG\"\n"
            "exit \"$WEBREADER_FAKE_INSTALL_STATUS\"\n"
        )
        cls.fake_appinst.chmod(0o700)
        cls.binary = cls.root / "webreader-appinst-bridge"
        result = subprocess.run([
            "xcrun", "clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-Wno-deprecated-declarations",
            '-DWEBREADER_TEST_ROOT="' + str(cls.root) + '"',
            '-DWEBREADER_TEST_APPINST="' + str(cls.fake_appinst) + '"',
            "-DWEBREADER_FAKE_APPINST_QA=1",
            str(SOURCE), "-o", str(cls.binary)
        ], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError("Fake-only QA bridge compile failed:\n" + result.stderr)

        # Same C source, standard iOS-compatible build: NO installer API,
        # not even with the correct path, SHA or confirmation word.
        cls.read_only = cls.root / "webreader-bridge-readonly"
        restricted = subprocess.run([
            "xcrun", "clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-Wno-deprecated-declarations",
            '-DWEBREADER_TEST_ROOT="' + str(cls.root) + '"',
            str(SOURCE), "-o", str(cls.read_only)
        ], capture_output=True, text=True, timeout=30)
        if restricted.returncode:
            raise AssertionError("Read-only bridge compile failed:\n" + restricted.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.stage = (self.root / CONTAINER / "Library" /
                      "Application Support" / "WebReaderUpdates")
        self.stage.mkdir(parents=True, exist_ok=True)
        self.ipa = self.stage / LEAF
        self.ipa.write_bytes(PAYLOAD)
        self.ipa.chmod(0o600)
        self.digest = hashlib.sha256(PAYLOAD).hexdigest()
        self.marker.unlink(missing_ok=True)
        self.addCleanup(self.ipa.unlink, missing_ok=True)

    def cli(self, *args, extra_env=None):
        env = os.environ.copy()
        env["WEBREADER_FAKE_INSTALL_LOG"] = str(self.marker)
        env["WEBREADER_FAKE_INSTALL_STATUS"] = "0"
        if extra_env:
            env.update(extra_env)
        return subprocess.run([str(self.binary), *map(str, args)],
                              capture_output=True, text=True, timeout=8, env=env)

    def test_selftest_inert(self):
        proc = self.cli("selftest")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("FAKE_APPINST_BRIDGE_QA", proc.stdout)
        self.assertIn("FAKE_APPINST_AVAILABLE", proc.stdout)
        self.assertFalse(self.marker.exists())

    def test_inspect_checks_sha_without_installing(self):
        proc = self.cli("inspect", self.ipa, self.digest)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("IPA_BYTES_MATCH_SHA256", proc.stdout)
        self.assertFalse(self.marker.exists())

    def test_install_requires_explicit_confirmation(self):
        for args in [
            ("install", self.ipa, self.digest, "I-CONFIRM-INSTALL"),
            ("install-confirmed", self.ipa, self.digest),
            ("install-confirmed", self.ipa, self.digest, "YES"),
            ("install-confirmed", self.ipa, self.digest, "I-CONFIRM-INSTALL", "extra")
        ]:
            with self.subTest(args=args):
                self.assertNotEqual(self.cli(*args).returncode, 0)
                self.assertFalse(self.marker.exists())

    def test_standard_bridge_never_links_or_contains_installer(self):
        # This is the critical safety boundary of Phase CJ. The test
        # fixture's fake-only build is deliberately NOT a release binary.
        path = self.read_only
        binary = path.read_bytes()
        self.assertNotIn(b"/usr/bin/appinst", binary)
        self.assertNotIn(b"I-CONFIRM-INSTALL", binary)
        self.assertNotIn(b"WEBREADER_FAKE_APPINST_QA", binary)
        symbols = subprocess.run(
            ["nm", "-u", str(path)], check=True,
            capture_output=True, text=True, timeout=10
        ).stdout
        self.assertNotIn("posix_spawn", symbols)
        self.assertNotIn("waitpid", symbols)

        proc = subprocess.run(
            [str(path), "selftest"], capture_output=True, text=True, timeout=5
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("APPINST_CLI_DISABLED", proc.stdout)

        # Even a verified and legitimate-looking staging file does not
        # make a fixed confirmation string into helper-local consent.
        proc = subprocess.run(
            [str(path), "inspect", str(self.ipa), self.digest],
            capture_output=True, text=True, timeout=5
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for args in (
            ("install-confirmed", str(self.ipa), self.digest, "I-CONFIRM-INSTALL"),
            ("install-confirmed", str(self.ipa), self.digest, "YES"),
            ("install-confirmed", str(self.ipa), self.digest),
        ):
            with self.subTest(args=args):
                result = subprocess.run(
                    [str(path), *args],
                    capture_output=True, text=True, timeout=5
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("INSTALL_DISABLED", result.stderr)
                self.assertFalse(self.marker.exists())

    def test_standard_unix_socket_accepts_ping_but_never_install(self):
        folder = self.root / CONTAINER / "WR"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder.chmod(0o700)
        path = folder / "wri.sock"
        for message, expected, exit_code in (
            (b"WRPING1\\n", b"WRPONG1\\n", 0),
            (b"WRINST1\\n", b"WRFAIL1\\n", 1),
        ):
            # Decode the escaped fixture newline into the fixed eight bytes.
            wire = message.replace(b"\\n", b"\n")
            response = expected.replace(b"\\n", b"\n")
            with self.subTest(payload=wire):
                proc = subprocess.Popen(
                    [str(self.read_only), "serve-once", str(folder)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                try:
                    ready, _, _ = select.select([proc.stdout], [], [], 5)
                    self.assertTrue(ready, "socket server did not report READY")
                    self.assertIn(b"WRAPPINST_READY", proc.stdout.readline())
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(3)
                        client.connect(str(path))
                        client.sendall(wire)
                        self.assertEqual(client.recv(8), response)
                    proc.wait(timeout=5)
                    self.assertEqual(proc.returncode, exit_code)
                    self.assertFalse(self.marker.exists())
                    self.assertFalse(path.exists())
                finally:
                    if proc.poll() is None:
                        proc.kill()
                    proc.communicate(timeout=3)

    def test_fake_installer_cannot_be_built_without_both_test_macros(self):
        for extra in (
            ["-DWEBREADER_FAKE_APPINST_QA=1"],
            ["-DWEBREADER_FAKE_APPINST_QA=1",
             '-DWEBREADER_TEST_ROOT="' + str(self.root) + '"'],
            ["-DWEBREADER_FAKE_APPINST_QA=1",
             '-DWEBREADER_TEST_APPINST="' + str(self.fake_appinst) + '"'],
            ["-DWEBREADER_FAKE_APPINST_QA=1", "-DWEBREADER_PING_ONLY",
             '-DWEBREADER_TEST_ROOT="' + str(self.root) + '"',
             '-DWEBREADER_TEST_APPINST="' + str(self.fake_appinst) + '"'],
        ):
            with self.subTest(extra=extra):
                out = self.root / "forbidden-fake-test"
                attempt = subprocess.run(
                    ["xcrun", "clang", "-std=c11", *extra,
                     str(SOURCE), "-o", str(out)],
                    capture_output=True, text=True, timeout=25
                )
                self.assertNotEqual(attempt.returncode, 0)
                self.assertIn("error:", attempt.stderr)

    def test_explicit_install_calls_fake_fixed_appinst_once(self):
        proc = self.cli("install-confirmed", self.ipa, self.digest, "I-CONFIRM-INSTALL")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.marker.read_text().splitlines(), ["1", str(self.ipa)])
        self.assertIn("APPINST_COMPLETED", proc.stdout)

    def test_installer_nonzero_exit_does_not_claim_success(self):
        proc = self.cli("install-confirmed", self.ipa, self.digest,
                        "I-CONFIRM-INSTALL",
                        extra_env={"WEBREADER_FAKE_INSTALL_STATUS": "13"})
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("failed", proc.stderr)
        self.assertTrue(self.marker.exists())

    def test_bad_hash_or_size_never_calls_installer(self):
        for sha in [self.digest.upper(), "0"*64, "x", self.digest[:-1], ""]:
            with self.subTest(sha=sha[:12]):
                self.assertNotEqual(self.cli("install-confirmed", self.ipa, sha,
                                            "I-CONFIRM-INSTALL").returncode, 0)
                self.assertFalse(self.marker.exists())
        self.ipa.write_bytes(b"NOT-AN-IPA")
        self.assertNotEqual(self.cli("install-confirmed", self.ipa,
                                    hashlib.sha256(b"NOT-AN-IPA").hexdigest(),
                                    "I-CONFIRM-INSTALL").returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_rejects_altered_source(self):
        self.ipa.write_bytes(PAYLOAD + b"ADDED")
        self.assertNotEqual(self.cli("install-confirmed", self.ipa, self.digest,
                                    "I-CONFIRM-INSTALL").returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_rejects_other_app_or_relative_paths(self):
        extra = self.root / "bad.ipa"
        extra.write_bytes(PAYLOAD)
        for path in [extra, Path("relative.ipa"), self.root / "other" / LEAF]:
            with self.subTest(path=str(path)):
                self.assertNotEqual(self.cli("install-confirmed", path, self.digest,
                                            "I-CONFIRM-INSTALL").returncode, 0)
                self.assertFalse(self.marker.exists())

    def test_rejects_unknown_filename(self):
        alt = self.stage / "OTHER-build57.ipa"
        alt.write_bytes(PAYLOAD)
        self.assertNotEqual(self.cli("install-confirmed", alt, self.digest,
                                    "I-CONFIRM-INSTALL").returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_rejects_staged_symlink_and_hardlink(self):
        target = self.stage / "unrelated.ipa"
        target.write_bytes(PAYLOAD)
        self.ipa.unlink()
        self.ipa.symlink_to(target)
        self.assertNotEqual(self.cli("install-confirmed", self.ipa, self.digest,
                                    "I-CONFIRM-INSTALL").returncode, 0)
        self.ipa.unlink()
        os.link(target, self.ipa)
        self.assertNotEqual(self.cli("install-confirmed", self.ipa, self.digest,
                                    "I-CONFIRM-INSTALL").returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_rejects_group_writable_file(self):
        self.ipa.chmod(0o666)
        self.assertNotEqual(self.cli("install-confirmed", self.ipa, self.digest,
                                    "I-CONFIRM-INSTALL").returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_rejects_shell_metacharacters_in_filename(self):
        evil = self.stage / (LEAF + ";touch-evil")
        evil.write_bytes(PAYLOAD)
        self.assertNotEqual(self.cli("install-confirmed", evil, self.digest,
                                    "I-CONFIRM-INSTALL").returncode, 0)
        self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
