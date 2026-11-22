#!/usr/bin/env python3
"""Build69 AP-AQ-AR: production protocol only; ephemeral keys and synthetic IPA.

The mocked macOS code seal in one unit test is NOT physical or native approval.
Real native codesign must run separately over the future approved IPA on macOS.
"""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from build66_release_key_pinning_gate import public_key_spki_sha256
from build66_signed_release_preflight import (
    SignedReleaseRejected, verify_signed_release
)
from build69_production_release_preflight import (
    ProductionPreflightRejected, review_production_release,
    _read_external_regular
)
from webreader_update_manifest import ManifestRejected, validate
from test_build66_signed_release_preflight import synthetic_ipa


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


class ProductionReleaseRehearsal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr69-production-offline-test-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.private = cls.root / "ephemeral-only-private.pem"
        cls.public = cls.root / "ephemeral-only-public.pem"
        subprocess.run([
            "openssl", "ecparam", "-name", "prime256v1", "-genkey",
            "-noout", "-out", str(cls.private)
        ], check=True, capture_output=True, timeout=15)
        subprocess.run([
            "openssl", "pkey", "-in", str(cls.private),
            "-pubout", "-out", str(cls.public)
        ], check=True, capture_output=True, timeout=15)
        cls.key = cls.public.read_bytes()
        cls.pin = public_key_spki_sha256(cls.key)

    def setUp(self):
        self.ipa = self.root / "WebReader-Build69-iOS12-adhoc.ipa"
        self.ipa.write_bytes(synthetic_ipa(build="69"))
        self.fields = {
            "schemaVersion": 2, "application": "WebReader",
            "bundleId": "com.example.MangaReader12",
            "applicationIdentifier": "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
            "channel": "production",
            "build": 69, "minimumIOS": "12.0",
            "ipaUrl": "https://github.com/AugustoArbulu/MangaReader12/"
                      "releases/download/build69/WebReader-Build69-iOS12-adhoc.ipa",
            "ipaSize": self.ipa.stat().st_size,
            "sha256": hashlib.sha256(self.ipa.read_bytes()).hexdigest(),
            "releaseNotes": ["synthetic offline production contract test"],
            "publishedAt": "2026-11-08T22:00:00Z",
        }

    def envelope(self, fields=None):
        payload = canonical(self.fields if fields is None else fields)
        msg = self.root / "ephemeral-payload.json"
        signature = self.root / "ephemeral-signature.der"
        msg.write_bytes(payload)
        subprocess.run([
            "openssl", "dgst", "-sha256", "-sign", str(self.private),
            "-out", str(signature), str(msg)
        ], check=True, capture_output=True, timeout=15)
        data = {
            "schemaVersion": (self.fields if fields is None else fields)["schemaVersion"],
            "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(payload).decode("ascii"),
            "signature": base64.b64encode(signature.read_bytes()).decode("ascii"),
        }
        return canonical(data)

    def test_genuine_production_signature_requires_explicit_channel(self):
        signed = self.envelope()
        self.assertEqual(validate(signed, self.key, installed_build=68,
                                  expected_channel="production")["build"], 69)
        with self.assertRaises(ManifestRejected):
            validate(signed, self.key, installed_build=68)
        with self.assertRaises(ManifestRejected):
            validate(signed, self.key, installed_build=68,
                     expected_channel="staging")

    def test_dev_manifest_cannot_be_promoted_even_with_same_public_key(self):
        dev = self.envelope(dict(self.fields, channel="development"))
        self.assertEqual(validate(dev, self.key, installed_build=68)["build"], 69)
        with self.assertRaises(ManifestRejected):
            validate(dev, self.key, installed_build=68,
                     expected_channel="production")

    def test_v1_production_is_rejected_even_with_valid_signature(self):
        legacy = dict(self.fields, schemaVersion=1)
        legacy.pop("applicationIdentifier")
        legacy["ipaUrl"] = ("https://github.com/AugustoArbulu/MangaReader12/"
                            "releases/download/build69/WebReader-iOS12-unsigned.ipa")
        with self.assertRaises(ManifestRejected):
            validate(self.envelope(legacy), self.key, installed_build=68,
                     expected_channel="production")

    def test_production_manifest_bound_to_same_ipa_snapshot(self):
        r = verify_signed_release(
            self.envelope(), self.key, self.ipa, installed_build=68,
            expected_channel="production"
        )
        self.assertTrue(r["signed_manifest_verified"])
        self.assertTrue(r["ipa_metadata_matches_manifest"])
        self.assertTrue(r["single_snapshot_checked"])
        self.assertFalse(r["code_signature_verified"])
        self.assertFalse(r["install_authorized"])
        with self.assertRaises(SignedReleaseRejected):
            verify_signed_release(self.envelope(), self.key, self.ipa,
                                  installed_build=68)  # defaults to development

    def test_changed_ipa_rejected(self):
        signed = self.envelope()
        self.ipa.write_bytes(self.ipa.read_bytes() + b"modified")
        with self.assertRaises(SignedReleaseRejected):
            verify_signed_release(signed, self.key, self.ipa,
                                  installed_build=68, expected_channel="production")

    def test_preflight_rejects_missing_or_wrong_independent_pin(self):
        signed = self.envelope()
        for pin in (None, "", "f" * 64, self.pin.upper()):
            with self.subTest(pin=pin):
                with self.assertRaises(ProductionPreflightRejected):
                    review_production_release(
                        public_key_pem=self.key, independent_spki_sha256=pin,
                        manifest_v2=signed, ipa_path=self.ipa, installed_build=68
                    )

    def test_preflight_rejects_legacy_baseline_or_dev_release(self):
        with self.assertRaises(ProductionPreflightRejected):
            review_production_release(
                public_key_pem=self.key, independent_spki_sha256=self.pin,
                manifest_v2=self.envelope(), ipa_path=self.ipa,
                installed_build=67
            )
        with self.assertRaises(ProductionPreflightRejected):
            review_production_release(
                public_key_pem=self.key, independent_spki_sha256=self.pin,
                manifest_v2=self.envelope(dict(self.fields, channel="development")),
                ipa_path=self.ipa, installed_build=68
            )

    def test_preflight_unit_contract_mock_does_not_authorize_installation(self):
        # Synthetic ZIP cannot have a real Apple code seal. Only the adapter
        # contract is mocked, never claimed as an actual code-signature result.
        fake_seal = {
            "adHocSignatureIntegrityVerified": True,
            "thinArm64ExecutableVerified": True,
            "installedApplicationIdentifierMatch": True
        }
        with mock.patch(
            "build69_production_release_preflight.audit_code_signature_snapshot",
            return_value=fake_seal
        ) as native:
            receipt = review_production_release(
                public_key_pem=self.key, independent_spki_sha256=self.pin,
                manifest_v2=self.envelope(), ipa_path=self.ipa, installed_build=68
            )
        self.assertEqual(native.call_count, 1)
        self.assertEqual(receipt["status"], "offline_review_only")
        self.assertEqual(receipt["publicSPKISHA256"], self.pin)
        self.assertEqual(receipt["build"], 69)
        self.assertFalse(receipt["publicKeyProvisionedOnDevice"])
        self.assertFalse(receipt["ownerPublicationApprovalRecorded"])
        self.assertFalse(receipt["githubReleasePublished"])
        self.assertFalse(receipt["mainModified"])
        self.assertFalse(receipt["installationAuthorized"])
        self.assertFalse(receipt["installationPerformed"])

    def test_without_real_codesign_synthetic_archive_must_fail(self):
        with self.assertRaises(ProductionPreflightRejected):
            review_production_release(
                public_key_pem=self.key, independent_spki_sha256=self.pin,
                manifest_v2=self.envelope(), ipa_path=self.ipa, installed_build=68
            )

    def test_public_input_reader_disallows_symlinks_and_source_tree(self):
        external = self.root / "release-public.pem"
        external.write_bytes(self.key)
        self.assertEqual(_read_external_regular(external, 4096), self.key)
        linked = self.root / "linked.pem"
        linked.symlink_to(external)
        with self.assertRaises(ProductionPreflightRejected):
            _read_external_regular(linked, 4096)
        with self.assertRaises(ProductionPreflightRejected):
            _read_external_regular(external, 20)


if __name__ == "__main__":
    unittest.main()
