#!/usr/bin/env python3
"""Host-only manual release receipt tests with ephemeral EC-P256 fixtures."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from build66_manual_review_receipt import (
    ManualReleaseRejected, prepare_manual_review
)
from build66_release_key_pinning_gate import public_key_spki_sha256
from test_build66_signed_release_preflight import synthetic_ipa


def encode(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


class ManualReviewReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="wr66-manual-review-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.private = cls.root / "private-ephemeral.pem"
        cls.public = cls.root / "public-ephemeral.pem"
        subprocess.run(
            ["openssl", "ecparam", "-name", "prime256v1",
             "-genkey", "-noout", "-out", str(cls.private)],
            check=True, capture_output=True
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private),
             "-pubout", "-out", str(cls.public)],
            check=True, capture_output=True
        )
        cls.public_bytes = cls.public.read_bytes()
        cls.pin = public_key_spki_sha256(cls.public_bytes)

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.work.cleanup)
        self.folder = Path(self.work.name)
        self.ipa = self.folder / "WebReader-Build66-iOS12-adhoc.ipa"
        self.ipa.write_bytes(synthetic_ipa())
        raw = self.ipa.read_bytes()
        self.payload = {
            "schemaVersion": 2, "application": "WebReader",
            "bundleId": "com.example.MangaReader12",
            "applicationIdentifier":
                "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
            "channel": "development", "build": 66, "minimumIOS": "12.0",
            "ipaUrl":
                "https://github.com/AugustoArbulu/MangaReader12/releases/"
                "download/build66/WebReader-Build66-iOS12-adhoc.ipa",
            "ipaSize": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "releaseNotes": ["QA ONLY; no production publisher key"],
            "publishedAt": "2026-11-07T04:00:00Z",
        }
        self.envelope = self.sign()

    def sign(self):
        payload = encode(self.payload)
        data = self.folder / "payload.json"
        signature = self.folder / "signature.der"
        data.write_bytes(payload)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private),
             "-out", str(signature), str(data)],
            check=True, capture_output=True
        )
        return encode({
            "schemaVersion": 2,
            "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(payload).decode("ascii"),
            "signature": base64.b64encode(signature.read_bytes()).decode("ascii")
        })

    def review(self, **changes):
        args = {
            "envelope_json": self.envelope,
            "public_pem": self.public_bytes,
            "trusted_spki_sha256": self.pin,
            "staged_ipa_path": self.ipa,
            "installed_build": 65,
        }
        args.update(changes)
        return prepare_manual_review(**args)

    def denied(self, **changes):
        with self.assertRaises(ManualReleaseRejected):
            self.review(**changes)

    def test_signed_v2_release_prepares_manual_review_only(self):
        r = self.review()
        self.assertEqual(r.build, 66)
        self.assertEqual(r.asset_name, "WebReader-Build66-iOS12-adhoc.ipa")
        self.assertEqual(r.expected_sha256, self.payload["sha256"])
        self.assertTrue(r.independent_key_pin_match)
        self.assertTrue(r.signed_manifest_and_ipa_match)
        self.assertFalse(r.native_codesign_verified)
        self.assertFalse(r.publisher_authenticated_on_device)
        self.assertFalse(r.installed_app_identity_verified)
        self.assertFalse(r.user_approved_manual_install)
        self.assertFalse(r.installation_authorized)
        self.assertFalse(r.installation_performed)
        self.assertTrue(r.manual_rehash_required_after_transfer)
        self.assertTrue(r.user_should_keep_existing_app_and_data)

    def test_receipt_never_discloses_host_path(self):
        receipt = repr(self.review())
        self.assertNotIn(str(self.folder), receipt)

    def test_string_path_supported_but_not_trusted(self):
        self.assertEqual(self.review(staged_ipa_path=str(self.ipa)).build, 66)

    def test_pin_not_derived_from_manifest(self):
        self.denied(trusted_spki_sha256="0" * 64)

    def test_missing_pin(self):
        self.denied(trusted_spki_sha256=None)

    def test_fake_key_rejected(self):
        self.denied(public_pem=b"not-a-public-key")

    def test_unsigned_content_rejected(self):
        self.denied(envelope_json=b'{"build":66}')

    def test_tampered_signature_rejected(self):
        raw = json.loads(self.envelope)
        raw["signature"] = base64.b64encode(b"fake signature").decode()
        self.denied(envelope_json=encode(raw))

    def test_manifest_with_injected_install_command_rejected(self):
        self.payload["installerCommand"] = "/usr/bin/appinst"
        self.denied(envelope_json=self.sign())

    def test_identity_other_than_installed_app_rejected(self):
        self.payload["applicationIdentifier"] = "ATTACKER"
        self.denied(envelope_json=self.sign())

    def test_wrong_ipa_hash_rejected(self):
        self.ipa.write_bytes(self.ipa.read_bytes() + b"tampered")
        self.denied()

    def test_old_build_rejected(self):
        self.denied(installed_build=66)

    def test_weird_build_types_rejected(self):
        for val in (None, True, False, "65", 0, -1, 2_147_483_647):
            with self.subTest(val=val):
                self.denied(installed_build=val)

    def test_bad_release_filename_rejected(self):
        for name in (
            "WebReader-iOS12-unsigned.ipa",
            "WebReader-Build67-iOS12-adhoc.ipa",
            "WebReader-Build66-iOS12-adhoc.ipa.exe",
            "WebReader-Build066-iOS12-adhoc.ipa",
            "build66.ipa", "../bad.ipa", "WebReader-Build66-iOS12-ADHOC.ipa",
        ):
            with self.subTest(name=name):
                self.denied(staged_ipa_path=self.folder / name)

    def test_unsupported_release_url_rejected(self):
        self.payload["ipaUrl"] = "https://example.org/WebReader-Build66-iOS12-adhoc.ipa"
        self.denied(envelope_json=self.sign())

    def test_wrong_channel_rejected(self):
        self.payload["channel"] = "stable"
        self.denied(envelope_json=self.sign())

    def test_v1_untrusted_release_rejected(self):
        self.payload["schemaVersion"] = 1
        self.payload.pop("applicationIdentifier")
        self.payload["ipaUrl"] = self.payload["ipaUrl"].replace(
            "WebReader-Build66-iOS12-adhoc.ipa",
            "WebReader-iOS12-unsigned.ipa"
        )
        self.denied(envelope_json=self.sign())

    def test_missing_file_rejected(self):
        self.ipa.unlink()
        self.denied()

    def test_symlink_ipa_rejected(self):
        link = self.folder / "WebReader-Build66-iOS12-adhoc.ipa"
        other = self.folder / "original.ipa"
        self.ipa.rename(other)
        link.symlink_to(other)
        self.denied()

    def test_unexpected_path_object_rejected(self):
        for bad in (None, 0, True, ["ipa"], b"ipa"):
            with self.subTest(bad=type(bad).__name__):
                self.denied(staged_ipa_path=bad)

    def test_do_not_have_approval_method(self):
        r = self.review()
        self.assertFalse(hasattr(r, "install"))
        self.assertFalse(hasattr(r, "authorize"))

    def test_manual_receipt_immutable(self):
        r = self.review()
        with self.assertRaises((AttributeError, TypeError)):
            r.installation_authorized = True


if __name__ == "__main__":
    unittest.main()
