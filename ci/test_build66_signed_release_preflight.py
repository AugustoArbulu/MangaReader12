#!/usr/bin/env python3
"""Fully offline signed-manifest-to-IPA binding tests; ephemeral keys only."""
import base64
import hashlib
import io
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

from build66_signed_release_preflight import SignedReleaseRejected, verify_signed_release


def encode(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")


def synthetic_ipa(bundle="com.example.MangaReader12", build="66",
                  minimum="12.0", executable="MangaReader12",
                  display="WebReader", include_executable=True):
    info = plistlib.dumps({
        "CFBundleIdentifier": bundle,
        "CFBundleVersion": build,
        "MinimumOSVersion": minimum,
        "CFBundleExecutable": executable,
        "CFBundleDisplayName": display,
    })
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Payload/MangaReader12.app/Info.plist", info)
        if include_executable:
            archive.writestr("Payload/MangaReader12.app/MangaReader12",
                             b"NOT-A-REAL-EXECUTABLE")
    return output.getvalue()


class SignedReleasePreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="wr66-signing-test-")
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.root = Path(cls.workspace.name)
        cls.private = cls.root / "ephemeral-private.pem"
        cls.public = cls.root / "ephemeral-public.pem"
        subprocess.run(
            ["openssl", "ecparam", "-name", "prime256v1", "-genkey",
             "-noout", "-out", str(cls.private)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private),
             "-pubout", "-out", str(cls.public)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.key = cls.public.read_bytes()

    def setUp(self):
        self.ipa = self.root / (self.id().split(".")[-1] + ".ipa")
        self.ipa.write_bytes(synthetic_ipa())
        self.manifest = self.fields()

    def fields(self):
        data = self.ipa.read_bytes()
        return {
            "schemaVersion": 1,
            "application": "WebReader",
            "bundleId": "com.example.MangaReader12",
            "channel": "development",
            "build": 66,
            "minimumIOS": "12.0",
            "ipaUrl": ("https://github.com/AugustoArbulu/MangaReader12/"
                       "releases/download/build66/WebReader-iOS12-unsigned.ipa"),
            "ipaSize": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "releaseNotes": ["Ephemeral test fixture, not a release"],
            "publishedAt": "2026-11-06T20:00:00Z",
        }

    def signed(self, fields=None):
        payload = encode(self.manifest if fields is None else fields)
        message = self.root / "fixture-payload.json"
        signature = self.root / "fixture-signature.der"
        message.write_bytes(payload)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private),
             "-out", str(signature), str(message)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return encode({
            "schemaVersion": (self.manifest if fields is None else fields)["schemaVersion"],
            "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(payload).decode("ascii"),
            "signature": base64.b64encode(signature.read_bytes()).decode("ascii"),
        })

    def accepted(self, **kwargs):
        return verify_signed_release(
            self.signed(), self.key, self.ipa, installed_build=65, **kwargs)

    def denied(self, envelope=None, key=None):
        with self.assertRaises(SignedReleaseRejected):
            verify_signed_release(
                self.signed() if envelope is None else envelope,
                self.key if key is None else key, self.ipa, installed_build=65)

    def test_matching_signed_manifest(self):
        result = self.accepted()
        self.assertEqual(result["build"], 66)
        self.assertTrue(result["signed_manifest_verified"])
        self.assertTrue(result["ipa_metadata_matches_manifest"])
        self.assertTrue(result["single_snapshot_checked"])
        self.assertFalse(result["code_signature_verified"])
        self.assertFalse(result["install_authorized"])
        self.assertFalse(result["installation_performed"])

    def make_v2(self):
        self.manifest["schemaVersion"] = 2
        self.manifest["applicationIdentifier"] = (
            "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
        )
        self.manifest["ipaUrl"] = (
            "https://github.com/AugustoArbulu/MangaReader12/"
            "releases/download/build66/WebReader-Build66-iOS12-adhoc.ipa"
        )

    def test_v2_signed_manifest_binds_to_archive(self):
        self.make_v2()
        result = self.accepted()
        self.assertEqual(result["build"], 66)
        self.assertTrue(result["single_snapshot_checked"])
        self.assertFalse(result["code_signature_verified"])

    def test_v2_reject_mismatched_installed_entitlement(self):
        self.make_v2()
        self.manifest["applicationIdentifier"] = "ATTACKER"
        self.denied()

    def test_v2_reject_unsigned_asset_name(self):
        self.make_v2()
        self.manifest["ipaUrl"] = self.manifest["ipaUrl"].replace(
            "WebReader-Build66-iOS12-adhoc.ipa", "WebReader-iOS12-unsigned.ipa"
        )
        self.denied()

    def test_invalid_unsigned_envelope(self):
        self.denied(envelope=b"{}")

    def test_signature_tampering(self):
        wrapped = json.loads(self.signed())
        sig = base64.b64decode(wrapped["signature"])
        wrapped["signature"] = base64.b64encode(sig[:-1] + bytes([sig[-1] ^ 1])).decode("ascii")
        self.denied(envelope=encode(wrapped))

    def test_untrusted_public_key(self):
        self.denied(key=b"X" * 200)

    def test_missing_pinned_key(self):
        self.denied(key=b"")

    def test_changed_ipa_after_manifest_signing(self):
        envelope = self.signed()
        data = bytearray(self.ipa.read_bytes())
        data[-1] ^= 1
        self.ipa.write_bytes(data)
        self.denied(envelope=envelope)

    def test_wrong_signed_hash(self):
        self.manifest["sha256"] = "0" * 64
        self.denied()

    def test_wrong_signed_size(self):
        self.manifest["ipaSize"] += 1
        self.denied()

    def test_signed_build_disagrees_with_ipa(self):
        self.manifest["build"] = 67
        self.manifest["ipaUrl"] = self.manifest["ipaUrl"].replace("build66", "build67")
        self.denied()

    def test_signed_ios_minimum_disagrees_with_ipa(self):
        self.manifest["minimumIOS"] = "12.1"
        self.denied()

    def test_equivalent_version_trailing_zero(self):
        self.manifest["minimumIOS"] = "12.0.0"
        self.assertEqual(self.accepted()["build"], 66)

    def test_wrong_bundle_inside_ipa(self):
        self.ipa.write_bytes(synthetic_ipa(bundle="com.attacker.app"))
        self.manifest = self.fields()
        self.denied()

    def test_wrong_executable_inside_ipa(self):
        self.ipa.write_bytes(synthetic_ipa(executable="OtherBinary"))
        self.manifest = self.fields()
        self.denied()

    def test_missing_executable_inside_ipa(self):
        self.ipa.write_bytes(synthetic_ipa(include_executable=False))
        self.manifest = self.fields()
        self.denied()

    def test_wrong_display_name_inside_ipa(self):
        self.ipa.write_bytes(synthetic_ipa(display="Imposter"))
        self.manifest = self.fields()
        self.denied()

    def test_signed_downgrade(self):
        self.ipa.write_bytes(synthetic_ipa(build="65"))
        self.manifest = self.fields()
        self.manifest["build"] = 65
        self.manifest["ipaUrl"] = self.manifest["ipaUrl"].replace("build66", "build65")
        self.denied()

    def test_replaced_path_after_read_cannot_change_snapshot_identity(self):
        # The hash and archive checks must inspect the same immutable bytes.
        # A later installer must *not* use this path: this test authorizes nothing.
        envelope = self.signed()
        real_zipfile = zipfile.ZipFile

        def replace_path_at_archive_parse(*args, **kwargs):
            self.ipa.write_bytes(b"REPLACED AFTER DESCRIPTOR READ")
            return real_zipfile(*args, **kwargs)

        with mock.patch("build66_ipa_preflight.zipfile.ZipFile",
                        side_effect=replace_path_at_archive_parse):
            result = verify_signed_release(
                envelope, self.key, self.ipa, installed_build=65)
        self.assertTrue(result["single_snapshot_checked"])
        self.assertEqual(result["sha256"], self.manifest["sha256"])
        self.assertNotEqual(
            hashlib.sha256(self.ipa.read_bytes()).hexdigest(),
            result["sha256"])

    def test_signed_ipa_with_extra_app_rejected(self):
        base = synthetic_ipa()
        rewritten = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(base)) as original:
            with zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as archive:
                for entry in original.infolist():
                    archive.writestr(entry, original.read(entry))
                archive.writestr("Payload/Another.app/Info.plist", b"extra")
        self.ipa.write_bytes(rewritten.getvalue())
        self.manifest = self.fields()
        self.denied()

    def test_signed_ipa_with_root_extra_file_rejected(self):
        base = synthetic_ipa()
        rewritten = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(base)) as original:
            with zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as archive:
                for entry in original.infolist():
                    archive.writestr(entry, original.read(entry))
                archive.writestr("unexpected.txt", b"extra")
        self.ipa.write_bytes(rewritten.getvalue())
        self.manifest = self.fields()
        self.denied()

    def test_ipa_symlink_rejected(self):
        real = self.root / "symlink-target.ipa"
        real.write_bytes(self.ipa.read_bytes())
        self.ipa.unlink()
        self.ipa.symlink_to(real)
        self.denied()

    def test_ad_hoc_release_asset_is_not_in_signed_protocol(self):
        self.manifest["ipaUrl"] = self.manifest["ipaUrl"].replace(
            "WebReader-iOS12-unsigned.ipa", "WebReader-Build66-iOS12-adhoc.ipa")
        self.denied()

    def test_untrusted_release_domain(self):
        self.manifest["ipaUrl"] = "https://example.net/build66/WebReader-iOS12-unsigned.ipa"
        self.denied()

    def test_mismatched_release_channel(self):
        self.manifest["channel"] = "production"
        self.denied()

    def test_ipa_invalid_zip(self):
        self.ipa.write_bytes(b"invalid archive")
        self.manifest = self.fields()
        self.denied()

    def test_unexpected_ios_target(self):
        with self.assertRaises(SignedReleaseRejected):
            self.accepted(installed_ios="13.0")


if __name__ == "__main__":
    unittest.main()
