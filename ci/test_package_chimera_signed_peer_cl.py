#!/usr/bin/env python3
"""CL Linux tests for non-root, non-installing iOS12 signed-peer runner policy."""
from pathlib import Path
import unittest
from unittest import mock

from package_chimera_signed_peer_cl import (
    report_shell, HEX40, OUT, CHECKSUM, NAMES, INSTALL, RUNNER, package
)

A = "a" * 40
B = "b" * 40

class Ios12SignedPeerLabPolicy(unittest.TestCase):
    def test_shell_is_explicit_three_peer_readonly_probes(self):
        source = report_shell(A, B)
        self.assertTrue(source.startswith(b"#!/bin/sh\nset -eu"))
        for marker in (
            b'if [ "$(id -u)" -eq 0 ]; then',
            b"REFUSE_ROOT",
            b"NONROOT READ_ONLY", b"ADHOC_HOST_BUILT_NOT_EDITORIAL",
            b"APP_PEER_AUTHENTICATED=NO",
            b"run_case a ", b"run_case b ", b"run_case c ",
            b"FINAL_INSTALL_AUTHORIZATION=DENIED",
            b"ALLOWED_PIN=" + A.encode(),
            b"FOREIGN_PIN=" + B.encode()
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        for denied in (
            b"/usr/bin/appinst", b"WRINST1", b"install-confirmed",
            b"curl ", b"wget ", b"ssh ", b"sudo ", b"launchctl",
            b"/var/mobile/", b"RELEASE_URL=", b"INSTALL_GRANTED"
        ):
            self.assertNotIn(denied, source)

    def test_hashes_must_be_independently_extracted_canonical_and_distinct(self):
        for bad in (
            ("A" * 40, B), ("a" * 39, B), ("z" * 40, B),
            (A, "z" * 40), (A, A), (A, 5), ("", B)
        ):
            with self.subTest(bad=bad), self.assertRaises(
                (ValueError, TypeError)
            ):
                report_shell(*bad)

    def test_package_does_not_modify_existing_artifacts(self):
        # Outputs may be absent or already present in CI. This test checks
        # policy with mocks, never writes or loads an actual IPA.
        with mock.patch("package_chimera_signed_peer_cl.OUT") as target:
            target.exists.return_value = True
            with self.assertRaises(ValueError):
                package(A, B)
        with mock.patch("package_chimera_signed_peer_cl.CHECKSUM") as sha:
            sha.exists.return_value = True
            with self.assertRaises(ValueError):
                package(A, B)

    def test_only_three_binaries_and_one_runner_defined(self):
        self.assertEqual(set(NAMES), {"server", "allowed", "foreign"})
        self.assertEqual(len(set(INSTALL.values())), 3)
        self.assertTrue(RUNNER.startswith("./usr/local/bin/"))
        self.assertTrue(OUT.name.endswith(".deb"))
        self.assertEqual(CHECKSUM.name, OUT.name + ".sha256")


if __name__ == "__main__":
    unittest.main()
