#!/usr/bin/env python3
"""Host-only Phase R trust-format tests; ephemeral fixture private keys only."""
from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from build66_release_key_pinning_gate import public_key_spki_sha256
from build68_release_public_key_handoff import (
    P256_SPKI_PREFIX, PublicKeyHandoffRejected, prepare_public_key_handoff
)

ROOT = Path(__file__).resolve().parent.parent


class ReleasePublicKeyHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr68-ephemeral-public-handoff-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.keys = {}
        for curve in ("prime256v1", "secp384r1"):
            private = cls.root / (curve + ".key")
            public = cls.root / (curve + ".pub")
            subprocess.run([
                "openssl", "ecparam", "-name", curve, "-genkey",
                "-noout", "-out", str(private)
            ], check=True, capture_output=True, timeout=15)
            subprocess.run([
                "openssl", "pkey", "-in", str(private),
                "-pubout", "-out", str(public)
            ], check=True, capture_output=True, timeout=15)
            cls.keys[curve] = (private.read_bytes(), public.read_bytes())
        cls.good = cls.keys["prime256v1"][1]
        cls.pin = public_key_spki_sha256(cls.good)

    _UNSET = object()

    def verified(self, key=_UNSET, pin=_UNSET):
        return prepare_public_key_handoff(
            self.good if key is self._UNSET else key,
            self.pin if pin is self._UNSET else pin
        )

    def test_independently_pinned_p256_matches_swift_x963_format(self):
        record = self.verified()
        self.assertEqual(record.canonical_spki_sha256, self.pin)
        self.assertEqual(len(record.x963_public_key_hex), 130)
        self.assertTrue(record.x963_public_key_hex.startswith("04"))
        self.assertEqual(len(bytes.fromhex(record.x963_public_key_hex)), 65)
        self.assertEqual(record.algorithm, "ecdsa-p256-sha256")

    def test_spki_digest_and_point_are_from_same_canonical_der(self):
        process = subprocess.run(
            ["openssl", "pkey", "-pubin", "-outform", "DER"],
            input=self.good, check=True, capture_output=True, timeout=15
        )
        self.assertTrue(process.stdout.startswith(P256_SPKI_PREFIX))
        self.assertEqual(
            hashlib.sha256(process.stdout).hexdigest(),
            self.verified().canonical_spki_sha256
        )
        self.assertEqual(
            process.stdout[len(P256_SPKI_PREFIX):].hex(),
            self.verified().x963_public_key_hex
        )

    def test_wrong_pin_is_refused(self):
        with self.assertRaises(PublicKeyHandoffRejected):
            self.verified(pin="0" * 64)

    def test_missing_invalid_or_non_string_pin_is_refused(self):
        for invalid in (None, "", False, 1, b"a" * 64, "A" * 64,
                        "abcd", "f" * 65, "g" * 64):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(PublicKeyHandoffRejected):
                    self.verified(pin=invalid)

    def test_wrong_elliptic_curve_is_refused_even_with_same_format(self):
        with self.assertRaises(PublicKeyHandoffRejected):
            self.verified(key=self.keys["secp384r1"][1])

    def test_private_key_pem_not_accepted_as_public_material(self):
        with self.assertRaises(PublicKeyHandoffRejected):
            self.verified(key=self.keys["prime256v1"][0])

    def test_multiple_pem_blocks_are_not_accepted(self):
        for invalid in (self.good + self.good, self.good + b"extra",
                        b"extra\n" + self.good):
            with self.subTest(size=len(invalid)):
                with self.assertRaises(PublicKeyHandoffRejected):
                    self.verified(key=invalid)

    def test_non_bytes_and_malformed_public_material_refused(self):
        for invalid in (None, False, "", self.good.decode(), b"",
                        self.good[:-20], self.good.replace(b"BEGIN", b"START"),
                        b"A" * 4097):
            with self.subTest(kind=type(invalid).__name__):
                with self.assertRaises(PublicKeyHandoffRejected):
                    self.verified(key=invalid)

    def test_signature_key_unchanged_after_conversion(self):
        self.assertEqual(self.verified(), self.verified())
        self.assertEqual(public_key_spki_sha256(self.good), self.pin)

    def test_consent_install_and_production_flags_are_never_granted(self):
        record = self.verified()
        self.assertTrue(record.independent_pin_matched)
        self.assertFalse(record.production_key_configured)
        self.assertFalse(record.publisher_authenticated_on_device)
        self.assertFalse(record.signed_release_verified)
        self.assertFalse(record.peer_authenticated)
        self.assertFalse(record.installation_authorized)
        self.assertFalse(record.installation_performed)

    def test_receipt_is_immutable(self):
        record = self.verified()
        with self.assertRaises(FrozenInstanceError):
            record.installation_authorized = True

    def test_application_and_installer_remain_fail_closed(self):
        checker = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
        installer = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
        code = (ROOT / "ci/build68_release_public_key_handoff.py").read_text()
        self.assertIn("static let productionPublicKeyX963: Data? = nil", checker)
        self.assertIn("static let liveInstallationEnabled = false", installer)
        self.assertNotIn("posix_spawn(", code)
        self.assertNotIn("install(", code)
        self.assertNotIn("write_bytes(", code)
        self.assertNotIn("PRIVATE KEY-----", code)

    def test_trusted_pin_must_be_distinct_input(self):
        code = (ROOT / "ci/build68_release_public_key_handoff.py").read_text()
        self.assertIn("independent_spki_sha256", code)
        self.assertIn("hmac.compare_digest(canonical, independent_spki_sha256)", code)
        self.assertNotIn("independent_spki_sha256 = canonical", code)


if __name__ == "__main__":
    unittest.main()
