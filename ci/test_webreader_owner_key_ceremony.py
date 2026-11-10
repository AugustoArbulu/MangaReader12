#!/usr/bin/env python3
"""Phase CO: disposable local P-256 test keys ONLY; never production material.

The real owner CLI is never invoked with --create in CI and no generated
private key is committed, exported as an artifact, or uploaded to GitHub.
"""
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from webreader_owner_key_ceremony import (
    OwnerCeremonyRejected, REPO_ROOT, FILE_NAMES, PRIVATE_NAME,
    PUBLIC_NAME, FINGERPRINT_NAME, create_owner_identity, main
)


class OwnerCeremonySafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wr-owner-disposable-test-")
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name)
        if os.name == "posix":
            self.output.chmod(0o700)
        self.password = "disposable-test-only-strong-password-never-for-production"

    def test_disposable_key_is_encrypted_and_matches_public_fingerprint(self):
        result = create_owner_identity(output_directory=self.output, passphrase=self.password)
        self.assertEqual(result.public_key_curve, "secp256r1")
        self.assertFalse(result.key_enrolled_in_app)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.installation_performed)
        self.assertEqual({item.name for item in self.output.iterdir()}, set(FILE_NAMES))
        private_pem = (self.output / PRIVATE_NAME).read_bytes()
        public_pem = (self.output / PUBLIC_NAME).read_bytes()
        fingerprint = (self.output / FINGERPRINT_NAME).read_text("ascii").strip()
        self.assertTrue(private_pem.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"))
        self.assertNotIn(b"-----BEGIN EC PRIVATE KEY-----", private_pem)
        self.assertNotIn(self.password.encode(), private_pem)
        with self.assertRaises((ValueError, TypeError)):
            serialization.load_pem_private_key(private_pem, password=b"wrong-password")
        loaded = serialization.load_pem_private_key(
            private_pem, password=self.password.encode()
        )
        self.assertIsInstance(loaded, ec.EllipticCurvePrivateKey)
        self.assertIsInstance(loaded.curve, ec.SECP256R1)
        actual_public = serialization.load_pem_public_key(public_pem)
        self.assertEqual(loaded.public_key().public_numbers(), actual_public.public_numbers())
        spki = actual_public.public_bytes(serialization.Encoding.DER,
                                          serialization.PublicFormat.SubjectPublicKeyInfo)
        self.assertEqual(result.public_spki_sha256, hashlib.sha256(spki).hexdigest())
        self.assertEqual(fingerprint, result.public_spki_sha256)
        if os.name == "posix":
            for name in FILE_NAMES:
                self.assertEqual(stat.S_IMODE((self.output/name).stat().st_mode), 0o600)

    def test_can_never_overwrite_existing_private_key(self):
        payload = b"preexisting owner bytes must remain intact"
        original = self.output / PRIVATE_NAME
        original.write_bytes(payload)
        with self.assertRaises(OwnerCeremonyRejected):
            create_owner_identity(output_directory=self.output, passphrase=self.password)
        self.assertEqual(original.read_bytes(), payload)
        self.assertEqual({x.name for x in self.output.iterdir()}, {PRIVATE_NAME})

    def test_malformed_passphrase_fails_before_key_generation(self):
        cases = ("", "weak", "a" * 15, "a" * 513, "a\n" + "b"*20, "a\x00" + "b"*20,
                 42, None, True)
        for secret in cases:
            with self.subTest(secret_type=type(secret).__name__):
                with mock.patch("webreader_owner_key_ceremony.ec.generate_private_key",
                                side_effect=AssertionError("key generation must not run")):
                    with self.assertRaises(OwnerCeremonyRejected):
                        create_owner_identity(
                            output_directory=self.output, passphrase=secret
                        )
        self.assertEqual(list(self.output.iterdir()), [])

    def test_missing_and_untrusted_output_path_rejected(self):
        missing = self.output / "missing"
        with self.assertRaises(OwnerCeremonyRejected):
            create_owner_identity(output_directory=missing, passphrase=self.password)
        with self.assertRaises(OwnerCeremonyRejected):
            create_owner_identity(output_directory=REPO_ROOT / "ci", passphrase=self.password)
        alias = self.output.parent / (self.output.name + "-alias")
        try:
            alias.symlink_to(self.output, target_is_directory=True)
        except (OSError, NotImplementedError):
            pass  # Windows restricted accounts may forbid symlinks.
        else:
            self.addCleanup(alias.unlink)
            with self.assertRaises(OwnerCeremonyRejected):
                create_owner_identity(output_directory=alias, passphrase=self.password)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_posix_private_directory_permissions_are_required(self):
        if os.name != "posix":
            self.skipTest("POSIX-only filesystem owner/mode")
        self.output.chmod(0o755)
        with self.assertRaises(OwnerCeremonyRejected):
            create_owner_identity(output_directory=self.output, passphrase=self.password)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_check_mode_never_calls_keygen_or_getpass(self):
        with mock.patch("webreader_owner_key_ceremony.ec.generate_private_key",
                        side_effect=AssertionError("no generation")), mock.patch(
                            "webreader_owner_key_ceremony.getpass.getpass",
                            side_effect=AssertionError("no prompt")
                        ):
            self.assertEqual(main(["--check"]), 0)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_owner_create_rejects_automated_noninteractive_terminal(self):
        with mock.patch("webreader_owner_key_ceremony.sys.stdin.isatty", return_value=False), \
             mock.patch("webreader_owner_key_ceremony.ec.generate_private_key",
                        side_effect=AssertionError("no headless keygen")):
            with self.assertRaises(SystemExit) as error:
                main(["--create", "--output-dir", str(self.output)])
        self.assertIn("interactive owner terminal", str(error.exception))
        self.assertEqual(list(self.output.iterdir()), [])

    def test_no_network_install_private_export_or_repository_mutation_path(self):
        source = (REPO_ROOT / "ci/webreader_owner_key_ceremony.py").read_text()
        for forbidden in ("urllib", "requests", "socket.", "appinst(",
                          "WRINST1", "os.system", "subprocess", "git push",
                          "install_authorized=True", "installation_authorized=True",
                          "http://", "https://", "github_token", "private_key.pem;"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("serialization.BestAvailableEncryption", source)
        self.assertIn("os.O_EXCL", source)
        self.assertIn("sys.stdin.isatty()", source)

if __name__ == "__main__":
    unittest.main()
