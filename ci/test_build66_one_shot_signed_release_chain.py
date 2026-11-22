#!/usr/bin/env python3
"""Build66 signed-release -> one-shot lab integration, entirely offline.

Uses temporary ECDSA keys and a synthetic unsigned IPA. This demonstrates
request binding; it does NOT authenticate an IPC peer or authorize installation.
"""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from build66_one_shot_diagnostic import (
    APP_BUNDLE_ID, INSTALLED_APPLICATION_IDENTIFIER, OneShotDiagnostic
)
from build66_signed_release_preflight import (
    SignedReleaseRejected, verify_signed_release
)
from test_build66_signed_release_preflight import synthetic_ipa


def encode(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")


class EndToEndOneShotLaboratoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="wr66-signed-once-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.private = cls.root / "test-only-private.pem"
        cls.public = cls.root / "test-only-public.pem"
        subprocess.run(
            ["openssl", "ecparam", "-name", "prime256v1", "-genkey",
             "-noout", "-out", str(cls.private)], check=True, capture_output=True)
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private),
             "-pubout", "-out", str(cls.public)], check=True, capture_output=True)
        cls.public_bytes = cls.public.read_bytes()

    def setUp(self):
        self.file = Path(self.temp.name) / (self.id().split(".")[-1] + ".ipa")
        self.file.write_bytes(synthetic_ipa())
        self.signed_data = self.make_signed_envelope()

    def make_signed_envelope(self):
        data = self.file.read_bytes()
        manifest = {
            "schemaVersion": 2,
            "application": "WebReader",
            "bundleId": APP_BUNDLE_ID,
            "applicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
            "channel": "development",
            "build": 66, "minimumIOS": "12.0",
            "ipaUrl": "https://github.com/AugustoArbulu/MangaReader12/releases/download/build66/WebReader-Build66-iOS12-adhoc.ipa",
            "ipaSize": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "releaseNotes": ["Offline test only"],
            "publishedAt": "2026-11-07T03:00:00Z",
        }
        payload = encode(manifest)
        message = self.root / (self.file.stem + "-payload")
        signature = self.root / (self.file.stem + "-sig")
        message.write_bytes(payload)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private),
             "-out", str(signature), str(message)], check=True, capture_output=True)
        return encode({
            "schemaVersion": 2, "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(payload).decode("ascii"),
            "signature": base64.b64encode(signature.read_bytes()).decode("ascii"),
        })

    def prepare_lab(self):
        report = verify_signed_release(
            self.signed_data, self.public_bytes, self.file, installed_build=65
        )
        self.assertTrue(report["signed_manifest_verified"])
        self.assertFalse(report["code_signature_verified"])
        lab = OneShotDiagnostic(
            target_build=report["build"], installed_build=65,
            manifest_sha256=hashlib.sha256(self.signed_data).hexdigest(),
            ipa_sha256=report["sha256"], ttl_seconds=30,
            entropy=lambda count: bytes([0x2A] * count), clock=lambda: 10.0
        )
        return lab, report

    def request(self, lab, report):
        return {
            "protocolVersion": 1, "operation": "CHECK_ONLY",
            "challenge": lab.challenge(),
            "manifestSHA256": hashlib.sha256(self.signed_data).hexdigest(),
            "ipaSHA256": report["sha256"], "targetBuild": report["build"],
            "bundleId": report["bundleId"],
            "applicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
        }

    def test_verified_update_binds_consistent_one_shot_diagnostic(self):
        lab, report = self.prepare_lab()
        result = lab.check_once(encode(self.request(lab, report)))
        self.assertTrue(result.request_consistent)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.peer_identity_authenticated)
        self.assertFalse(result.user_install_consent_verified)

    def test_replay_of_signed_update_request_rejected(self):
        lab, report = self.prepare_lab()
        raw = encode(self.request(lab, report))
        self.assertTrue(lab.check_once(raw).request_consistent)
        self.assertEqual(lab.check_once(raw).reason, "REPLAY_REJECTED")

    def test_altered_manifest_digest_rejected_after_signature_verification(self):
        lab, report = self.prepare_lab()
        req = self.request(lab, report)
        req["manifestSHA256"] = "0" * 64
        self.assertFalse(lab.check_once(encode(req)).request_consistent)

    def test_different_ipa_digest_rejected_after_signature_verification(self):
        lab, report = self.prepare_lab()
        req = self.request(lab, report)
        req["ipaSHA256"] = "0" * 64
        self.assertFalse(lab.check_once(encode(req)).request_consistent)

    def test_modified_ipa_cannot_get_verified_release_receipt(self):
        self.file.write_bytes(self.file.read_bytes() + b"CHANGED")
        with self.assertRaises(SignedReleaseRejected):
            self.prepare_lab()

    def test_tampered_signed_manifest_cannot_issue_verified_receipt(self):
        obj = json.loads(self.signed_data)
        sig = base64.b64decode(obj["signature"])
        obj["signature"] = base64.b64encode(sig[:-1] + bytes([sig[-1] ^ 1])).decode()
        self.signed_data = encode(obj)
        with self.assertRaises(SignedReleaseRejected):
            self.prepare_lab()


if __name__ == "__main__":
    unittest.main()
