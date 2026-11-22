#!/usr/bin/env python3
"""Offline P-256 public release key pin tests. No production signing key."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from build66_release_key_pinning_gate import (
    ReleaseKeyUntrusted, public_key_spki_sha256, verify_independently_pinned_v2
)
from test_build66_signed_release_preflight import synthetic_ipa


def encode(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf8")


class ReleaseKeyPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="wr66-ephemeral-key-pin-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.private = cls.root / "ephemeral-private.pem"
        cls.public = cls.root / "ephemeral-public.pem"
        subprocess.run(
            ["openssl", "ecparam", "-name", "prime256v1", "-genkey",
             "-noout", "-out", str(cls.private)],
            check=True, capture_output=True
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private),
             "-pubout", "-out", str(cls.public)],
            check=True, capture_output=True
        )
        cls.key = cls.public.read_bytes()
        cls.pin = public_key_spki_sha256(cls.key)

    def setUp(self):
        self.ipa = self.root / (self.id().split(".")[-1] + ".ipa")
        self.ipa.write_bytes(synthetic_ipa())
        self.manifest = self.signed_claims()

    def signed_claims(self):
        contents = self.ipa.read_bytes()
        return {
            "schemaVersion": 2, "application": "WebReader",
            "bundleId": "com.example.MangaReader12",
            "applicationIdentifier":
                "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
            "channel": "development", "build": 66,
            "minimumIOS": "12.0",
            "ipaUrl": ("https://github.com/AugustoArbulu/MangaReader12/"
                       "releases/download/build66/WebReader-Build66-iOS12-adhoc.ipa"),
            "ipaSize": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest(),
            "releaseNotes": ["ephemeral pin test fixture only"],
            "publishedAt": "2026-11-07T04:30:00Z",
        }

    def signed(self):
        payload = encode(self.manifest)
        src = self.root / (self.ipa.stem + ".message")
        sig = self.root / (self.ipa.stem + ".sig")
        src.write_bytes(payload)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private),
             "-out", str(sig), str(src)],
            check=True, capture_output=True
        )
        return encode({
            "schemaVersion": self.manifest["schemaVersion"],
            "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(payload).decode("ascii"),
            "signature": base64.b64encode(sig.read_bytes()).decode("ascii"),
        })

    def verified(self, *, envelope=None, pub=None, pin=None):
        return verify_independently_pinned_v2(
            self.signed() if envelope is None else envelope,
            self.key if pub is None else pub,
            self.pin if pin is None else pin,
            self.ipa, installed_build=65,
        )

    def test_verified_pinned_p256_v2_is_still_not_install_authorized(self):
        r = self.verified()
        self.assertEqual(r["build"], 66)
        self.assertTrue(r["pinned_spki_fingerprint_match"])
        self.assertTrue(r["signed_manifest_and_ipa_match"])
        self.assertFalse(r["publisher_trust_root_configured_by_app"])
        self.assertFalse(r["native_codesign_verified"])
        self.assertFalse(r["installation_authorized"])
        self.assertFalse(r["installation_performed"])

    def test_pin_is_stable_for_same_public_key(self):
        self.assertEqual(self.pin, public_key_spki_sha256(self.key))
        self.assertEqual(len(self.pin), 64)

    def test_wrong_fingerprint_rejected(self):
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified(pin="0" * 64)

    def test_missing_fingerprint_rejected(self):
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified(pin="")

    def test_uppercase_fingerprint_rejected(self):
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified(pin=self.pin.upper())

    def test_bool_fingerprint_rejected(self):
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified(pin=True)

    def test_wrong_public_key_rejected(self):
        bad_private = self.root / (self.ipa.stem + ".otherprivate")
        bad_pub = self.root / (self.ipa.stem + ".otherpublic")
        subprocess.run(
            ["openssl", "ecparam", "-name", "prime256v1", "-genkey",
             "-noout", "-out", str(bad_private)], check=True, capture_output=True
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(bad_private),
             "-pubout", "-out", str(bad_pub)], check=True, capture_output=True
        )
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified(pub=bad_pub.read_bytes())

    def test_missing_key_rejected(self):
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified(pub=b"")

    def test_garbage_key_rejected(self):
        with self.assertRaises(ReleaseKeyUntrusted):
            public_key_spki_sha256(b"X" * 200)

    def test_rsa_key_rejected_even_if_formatted(self):
        pem = self.root / (self.ipa.stem + ".rsa-private.pem")
        pub = self.root / (self.ipa.stem + ".rsa-public.pem")
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA",
             "-pkeyopt", "rsa_keygen_bits:2048",
             "-out", str(pem)], check=True, capture_output=True
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(pem),
             "-pubout", "-out", str(pub)], check=True, capture_output=True
        )
        with self.assertRaises(ReleaseKeyUntrusted):
            public_key_spki_sha256(pub.read_bytes())

    def test_v1_unsigned_asset_not_accepted_by_new_trust_gate(self):
        self.manifest.pop("applicationIdentifier")
        self.manifest["schemaVersion"] = 1
        self.manifest["ipaUrl"] = self.manifest["ipaUrl"].replace(
            "WebReader-Build66-iOS12-adhoc.ipa", "WebReader-iOS12-unsigned.ipa")
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified()

    def test_tampered_signed_payload_rejected(self):
        wrapped = json.loads(self.signed())
        wrapped["payload"] = base64.b64encode(b"{}").decode("ascii")
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified(envelope=encode(wrapped))

    def test_changed_ipa_rejected(self):
        envelope = self.signed()
        self.ipa.write_bytes(self.ipa.read_bytes() + b"CHANGED")
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified(envelope=envelope)

    def test_wrong_installation_identity_rejected(self):
        self.manifest["applicationIdentifier"] = "WRONG"
        with self.assertRaises(ReleaseKeyUntrusted):
            self.verified()

    def test_non_p256_curve_rejected(self):
        other_key = self.root / (self.ipa.stem + ".p384.pem")
        other_pub = self.root / (self.ipa.stem + ".p384.pub")
        subprocess.run(
            ["openssl", "ecparam", "-name", "secp384r1", "-genkey",
             "-noout", "-out", str(other_key)], check=True, capture_output=True
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(other_key),
             "-pubout", "-out", str(other_pub)], check=True, capture_output=True
        )
        with self.assertRaises(ReleaseKeyUntrusted):
            public_key_spki_sha256(other_pub.read_bytes())


if __name__ == "__main__":
    unittest.main()
