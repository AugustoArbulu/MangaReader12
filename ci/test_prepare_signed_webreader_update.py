#!/usr/bin/env python3
"""Offline release signing test with synthetic unsigned IPA and ephemeral keys.

No production keys, real Releases, network, or package installation.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from prepare_signed_webreader_update import prepare, ReleasePreparationRejected
from test_validate_webreader_ipa import make_ipa
from webreader_update_manifest import validate, ManifestRejected

class ReleaseSignerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="webreader-ephemeral-release-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = self.root / "temp-private.pem"
        self.pub = self.root / "temp-public.pem"
        self.notes = self.root / "notes.json"
        self.out = self.root / "manifest.json"
        self.notes.write_text('["Offline synthetic IPA test only"]')
        self.ipa, _ = make_ipa(self.root, build="57")
        subprocess.run(["openssl", "ecparam", "-genkey", "-name", "prime256v1",
                        "-noout", "-out", str(self.key)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(self.key),
                        "-pubout", "-out", str(self.pub)], check=True, capture_output=True)

    def sign(self):
        return prepare(self.ipa, self.key, self.pub, self.notes, self.out,
                       "2026-11-05T03:00:00Z")

    def test_end_to_end_release_envelope(self):
        metadata = self.sign()
        self.assertFalse(metadata["published"])
        self.assertFalse(metadata["installation_performed"])
        self.assertEqual(metadata["build"], 57)
        self.assertEqual(os.stat(self.out).st_mode & 0o777, 0o600)
        manifest = validate(self.out.read_bytes(), self.pub.read_bytes())
        self.assertEqual(manifest["ipaSize"], self.ipa.stat().st_size)
        self.assertEqual(manifest["sha256"], metadata["ipa_sha256"])
        self.assertEqual(manifest["minimumIOS"], "12.0")
        self.assertTrue(manifest["ipaUrl"].endswith(
            "/build57/WebReader-iOS12-unsigned.ipa"))
        raw = json.loads(self.out.read_bytes())
        self.assertNotIn("privateKey", raw)
        payload = json.loads(base64.b64decode(raw["payload"]))
        self.assertNotIn("privateKey", payload)
        # Refuse overwriting an already published/staged manifest.
        with self.assertRaises(ReleasePreparationRejected):
            self.sign()

    def test_reject_downgrade(self):
        self.ipa, _ = make_ipa(self.root, build="56")
        with self.assertRaises(ReleasePreparationRejected):
            self.sign()
        self.assertFalse(self.out.exists())

    def test_reject_wrong_bundle(self):
        self.ipa, _ = make_ipa(self.root, bundle="com.example.Other", build="57")
        with self.assertRaises(ReleasePreparationRejected):
            self.sign()
        self.assertFalse(self.out.exists())

    def test_reject_wrong_public_key(self):
        wrong = self.root / "wrong-private.pem"
        subprocess.run(["openssl", "ecparam", "-genkey", "-name", "prime256v1",
                        "-noout", "-out", str(wrong)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(wrong),
                        "-pubout", "-out", str(self.pub)], check=True, capture_output=True)
        with self.assertRaises(ReleasePreparationRejected):
            self.sign()
        self.assertFalse(self.out.exists())

    def test_reject_non_p256_signing_public_key(self):
        rsa_private = self.root / "rsa-private.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA",
             "-pkeyopt", "rsa_keygen_bits:2048",
             "-out", str(rsa_private)],
            check=True, capture_output=True
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(rsa_private),
             "-pubout", "-out", str(self.pub)],
            check=True, capture_output=True
        )
        with self.assertRaises(ReleasePreparationRejected):
            self.sign()
        self.assertFalse(self.out.exists())

    def test_reject_insecure_private_key_permissions(self):
        self.key.chmod(0o644)
        with self.assertRaises(ReleasePreparationRejected):
            self.sign()
        self.assertFalse(self.out.exists())

    def test_reject_unsigned_manifest_tamper(self):
        self.sign()
        encoded = json.loads(self.out.read_bytes())
        obj = json.loads(base64.b64decode(encoded["payload"]))
        obj["ipaSize"] = 44
        encoded["payload"] = base64.b64encode(
            json.dumps(obj).encode()
        ).decode()
        with self.assertRaises(ManifestRejected):
            validate(json.dumps(encoded).encode(), self.pub.read_bytes())

    def test_reject_invalid_release_notes(self):
        self.notes.write_text('["", "bad"]')
        with self.assertRaises(ReleasePreparationRejected):
            self.sign()

if __name__ == "__main__":
    unittest.main()
