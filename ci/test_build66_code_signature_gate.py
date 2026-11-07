#!/usr/bin/env python3
"""macOS-only synthetic codesign identity tests. NO real iOS IPA or device.

Fixture executables are compiled for macOS, not iOS, solely to exercise Apple's
native signature seal and the exact installed application-identifier entitlement.
Every manifest signing key is ephemeral; never reuse it for production updates.
"""
import base64
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
import zipfile

from build66_code_signature_gate import (
    CodeSignatureRejected, INSTALLED_APPLICATION_IDENTIFIER,
    audit_code_signature_snapshot, audit_signed_release_with_code_signature,
)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf8")


class CodeSignatureGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = tempfile.TemporaryDirectory(prefix="wr66-macos-codesign-")
        cls.addClassCleanup(cls.parent.cleanup)
        cls.root = Path(cls.parent.name)
        cls.private = cls.root / "manifest-test-private.pem"
        cls.public = cls.root / "manifest-test-public.pem"
        subprocess.run(
            ["openssl", "ecparam", "-name", "prime256v1", "-genkey",
             "-noout", "-out", str(cls.private)], check=True,
            capture_output=True)
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private),
             "-pubout", "-out", str(cls.public)], check=True,
            capture_output=True)
        cls.pinned = cls.public.read_bytes()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.work.cleanup)
        self.directory = Path(self.work.name)
        self.ipa = self.directory / "test.ipa"

    def create_fixture(self, identifier=INSTALLED_APPLICATION_IDENTIFIER,
                       *, sign=True, tamper=False, extra_entitlement=False):
        payload = self.directory / "staging" / "Payload"
        app = payload / "MangaReader12.app"
        app.mkdir(parents=True)
        info = {
            "CFBundleIdentifier": "com.example.MangaReader12",
            "CFBundleExecutable": "MangaReader12",
            "CFBundleDisplayName": "WebReader",
            "CFBundleVersion": "66",
            "MinimumOSVersion": "12.0",
        }
        (app / "Info.plist").write_bytes(plistlib.dumps(info))
        source = self.directory / "fixture.c"
        source.write_text("int main(void) { return 0; }\n", encoding="utf8")
        subprocess.run(
            ["clang", "-arch", "arm64", "-mmacosx-version-min=11.0",
             str(source), "-o", str(app / "MangaReader12")],
            check=True, capture_output=True)
        entitlements = {"application-identifier": identifier}
        if extra_entitlement:
            entitlements["get-task-allow"] = True
        entitlement_file = self.directory / "fixture.entitlements"
        entitlement_file.write_bytes(plistlib.dumps(entitlements))
        if sign:
            subprocess.run(
                ["/usr/bin/codesign", "--force", "--sign", "-",
                 "--timestamp=none", "--entitlements", str(entitlement_file),
                 str(app)],
                check=True, capture_output=True)
        if tamper:
            binary = app / "MangaReader12"
            binary.write_bytes(binary.read_bytes() + b"TAMPERED")
        with zipfile.ZipFile(self.ipa, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(payload.parent.rglob("*")):
                archive.write(path, path.relative_to(payload.parent.parent).as_posix())
        return self.ipa.read_bytes()

    def envelope(self, data, **overrides):
        manifest = {
            "schemaVersion": 1, "application": "WebReader",
            "bundleId": "com.example.MangaReader12", "channel": "development",
            "build": 66, "minimumIOS": "12.0",
            "ipaUrl": ("https://github.com/AugustoArbulu/MangaReader12/"
                       "releases/download/build66/WebReader-iOS12-unsigned.ipa"),
            "ipaSize": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "releaseNotes": ["Synthetic macOS codesign fixture only"],
            "publishedAt": "2026-11-06T23:00:00Z",
        }
        manifest.update(overrides)
        message = self.directory / "manifest-message.json"
        signature = self.directory / "manifest-signature.der"
        payload = encode(manifest)
        message.write_bytes(payload)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private),
             "-out", str(signature), str(message)],
            check=True, capture_output=True)
        return encode({
            "schemaVersion": 1,
            "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(payload).decode("ascii"),
            "signature": base64.b64encode(signature.read_bytes()).decode("ascii"),
        })

    def audit(self, data, *, envelope=None, key=None):
        return audit_signed_release_with_code_signature(
            self.envelope(data) if envelope is None else envelope,
            self.pinned if key is None else key, self.ipa, installed_build=65
        )

    def test_signed_manifest_and_matching_ad_hoc_entitlement(self):
        data = self.create_fixture()
        report = self.audit(data)
        self.assertTrue(report["adHocSignatureIntegrityVerified"])
        self.assertTrue(report["installedApplicationIdentifierMatch"])
        self.assertTrue(report["signed_manifest_verified"])
        self.assertEqual(report["applicationIdentifier"],
                         INSTALLED_APPLICATION_IDENTIFIER)
        self.assertFalse(report["publisherAuthenticatedByCodeSignature"])
        self.assertFalse(report["deviceInstallationCompatibilityProven"])
        self.assertFalse(report["installationAuthorized"])
        self.assertFalse(report["installationPerformed"])
        self.assertNotIn("ipa_snapshot", report)

    def test_missing_adhoc_signature_rejected(self):
        data = self.create_fixture(sign=False)
        with self.assertRaises(CodeSignatureRejected):
            self.audit(data)

    def test_wrong_installed_application_identifier_rejected(self):
        data = self.create_fixture(identifier="WRONG.com.example.MangaReader12")
        with self.assertRaises(CodeSignatureRejected):
            self.audit(data)

    def test_extra_entitlement_rejected(self):
        data = self.create_fixture(extra_entitlement=True)
        with self.assertRaises(CodeSignatureRejected):
            self.audit(data)

    def test_mutated_executable_after_signing_rejected(self):
        data = self.create_fixture(tamper=True)
        with self.assertRaises(CodeSignatureRejected):
            self.audit(data)

    def test_untrusted_manifest_key_rejected(self):
        data = self.create_fixture()
        with self.assertRaises(CodeSignatureRejected):
            self.audit(data, key=b"bad" * 100)

    def test_signed_manifest_wrong_hash_rejected(self):
        data = self.create_fixture()
        with self.assertRaises(CodeSignatureRejected):
            self.audit(data, envelope=self.envelope(data, sha256="a" * 64))

    def test_modified_ipa_path_after_manifest_signing_rejected(self):
        data = self.create_fixture()
        envelope = self.envelope(data)
        self.ipa.write_bytes(data + b"changed")
        with self.assertRaises(CodeSignatureRejected):
            self.audit(data, envelope=envelope)

    def test_snapshot_digest_mismatch_rejected(self):
        data = self.create_fixture()
        with self.assertRaises(CodeSignatureRejected):
            audit_code_signature_snapshot(data, "0" * 64, len(data))

    def test_snapshot_size_mismatch_rejected(self):
        data = self.create_fixture()
        with self.assertRaises(CodeSignatureRejected):
            audit_code_signature_snapshot(
                data, hashlib.sha256(data).hexdigest(), len(data) + 1)


if __name__ == "__main__":
    unittest.main()
