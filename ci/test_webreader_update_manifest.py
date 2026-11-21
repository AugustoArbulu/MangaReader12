#!/usr/bin/env python3
"""No-network regression suite for the future Chimera updater manifest policy.

Keys are randomly generated at test time; NO production signing keys exist.
"""
import base64
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from webreader_update_manifest import ManifestRejected, validate


def encode(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class ManifestProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="webreader-signing-fixture-")
        cls.root = Path(cls.tmp.name)
        cls.private = cls.root / "private.pem"
        cls.public = cls.root / "public.pem"
        subprocess.run(
            ["openssl", "ecparam", "-name", "prime256v1", "-genkey",
             "-noout", "-out", str(cls.private)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private),
             "-pubout", "-out", str(cls.public)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        cls.pinned = cls.public.read_bytes()
        cls.base = {
            "schemaVersion": 1, "application": "WebReader",
            "bundleId": "com.example.MangaReader12", "channel": "development",
            "build": 57, "minimumIOS": "12.0",
            "ipaUrl": "https://github.com/AugustoArbulu/MangaReader12/"
                      "releases/download/build57/WebReader-iOS12-unsigned.ipa",
            "ipaSize": 17300000, "sha256": "3" * 64,
            "releaseNotes": ["Offline test only, not an actual release"],
            "publishedAt": "2026-11-04T16:00:00Z"
        }

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def envelope(self, payload, sign=True):
        data = encode(payload)
        input_file = self.root / "payload.json"
        output_sig = self.root / "signature.der"
        input_file.write_bytes(data)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private),
             "-out", str(output_sig), str(input_file)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        blob = output_sig.read_bytes()
        if not sign:
            blob = bytearray(blob)
            blob[-1] ^= 1
        return encode({
            "schemaVersion": payload["schemaVersion"],
            "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(data).decode("ascii"),
            "signature": base64.b64encode(blob).decode("ascii")
        })

    def rejected(self, payload=None, tamper=False):
        with self.assertRaises(ManifestRejected):
            validate(self.envelope(payload or self.base, sign=not tamper),
                     self.pinned)

    def test_db5_production_cannot_accept_signed_v1(self):
        v1 = dict(self.base, channel="production")
        with self.assertRaises(ManifestRejected):
            validate(
                self.envelope(v1), self.pinned,
                installed_build=56, expected_channel="production"
            )
        v2 = dict(self.v2(), channel="production")
        accepted = validate(
            self.envelope(v2), self.pinned,
            installed_build=65, expected_channel="production"
        )
        self.assertEqual(accepted["schemaVersion"], 2)

    def test_db5_actual_gregorian_utc_calendar(self):
        for published in (
            "2026-02-29T01:02:03Z", "2024-02-30T01:02:03Z",
            "2026-13-01T01:02:03Z", "2026-00-01T01:02:03Z",
            "2026-11-31T01:02:03Z", "2026-11-01T24:02:03Z",
            "2026-11-01T01:60:03Z", "2026-11-01T01:02:60Z",
            "0000-01-01T00:00:00Z",
        ):
            with self.subTest(published=published):
                self.rejected(dict(self.v2(), publishedAt=published))
        valid = dict(self.v2(), publishedAt="2024-02-29T23:59:59Z")
        self.assertEqual(
            validate(self.envelope(valid), self.pinned,
                     installed_build=65)["build"], 66
        )

    def test_db5_signed_base64_padding_alias_rejected(self):
        # Generate a *genuinely signed* valid JSON payload with trailing
        # whitespace, ensuring == padding on its Base64 representation.
        # Replacing the final nonpadding symbol with an equivalent one
        # leaves the decoded bytes and ECDSA signature unchanged.
        raw = encode(self.base)
        while len(raw) % 3 != 1:
            raw += b" "
        path = self.root / "db5-canonical-payload.json"
        signature_path = self.root / "db5-canonical-signature.der"
        path.write_bytes(raw)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private),
             "-out", str(signature_path), str(path)],
            check=True, capture_output=True, timeout=15
        )
        envelope = {
            "schemaVersion": 1, "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(raw).decode("ascii"),
            "signature": base64.b64encode(signature_path.read_bytes()).decode("ascii"),
        }
        self.assertEqual(
            validate(encode(envelope), self.pinned)["build"], 57
        )
        canonical = envelope["payload"]
        self.assertTrue(canonical.endswith("=="))
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        position = len(canonical) - 3
        index = alphabet.index(canonical[position])
        self.assertEqual(index % 16, 0)
        alias = canonical[:position] + alphabet[index + 1] + canonical[position+1:]
        self.assertEqual(base64.b64decode(alias), raw)
        envelope["payload"] = alias
        with self.assertRaises(ManifestRejected):
            validate(encode(envelope), self.pinned)

    def test_valid_newer_signed_manifest(self):
        actual = validate(self.envelope(self.base), self.pinned)
        self.assertEqual(actual["build"], 57)

    def v2(self):
        newer = dict(self.base)
        newer["schemaVersion"] = 2
        newer["build"] = 66
        newer["applicationIdentifier"] = (
            "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
        )
        newer["ipaUrl"] = (
            "https://github.com/AugustoArbulu/MangaReader12/"
            "releases/download/build66/WebReader-Build66-iOS12-adhoc.ipa"
        )
        return newer

    def test_v2_valid_signed_adhoc_release(self):
        actual = validate(self.envelope(self.v2()), self.pinned, installed_build=65)
        self.assertEqual(actual["schemaVersion"], 2)
        self.assertEqual(actual["build"], 66)

    def test_v2_wrong_installed_application_identifier(self):
        self.rejected(dict(self.v2(), applicationIdentifier="ATTACKER"))

    def test_v2_missing_installed_application_identifier(self):
        invalid = self.v2()
        del invalid["applicationIdentifier"]
        self.rejected(invalid)

    def test_v2_wrong_release_asset(self):
        self.rejected(dict(
            self.v2(),
            ipaUrl=self.base["ipaUrl"].replace("build57", "build66")
        ))

    def test_v1_reject_v2_field_and_asset(self):
        self.rejected(dict(self.base, applicationIdentifier=self.v2()["applicationIdentifier"]))
        self.rejected(dict(self.base, ipaUrl=(
            "https://github.com/AugustoArbulu/MangaReader12/"
            "releases/download/build57/WebReader-Build57-iOS12-adhoc.ipa"
        )))

    def test_v2_reject_outer_inner_version_mismatch(self):
        envelope = json.loads(self.envelope(self.v2()))
        envelope["schemaVersion"] = 1
        with self.assertRaises(ManifestRejected):
            validate(encode(envelope), self.pinned, installed_build=65)

    def test_v2_reject_outer_version_three(self):
        envelope = json.loads(self.envelope(self.v2()))
        envelope["schemaVersion"] = 3
        with self.assertRaises(ManifestRejected):
            validate(encode(envelope), self.pinned, installed_build=65)

    def test_v2_reject_untrusted_release_path(self):
        self.rejected(dict(
            self.v2(),
            ipaUrl=("https://github.com/AugustoArbulu/MangaReader12/"
                    "releases/download/build66/WebReader-Build66-iOS12-adhoc.ipa?x=1")
        ))

    def test_tampered_signature(self):
        self.rejected(tamper=True)

    def test_wrong_signing_key(self):
        self.assertRaises(ManifestRejected, validate,
                          self.envelope(self.base), b"bad public key".ljust(120, b" "))

    def test_wrong_bundle_id(self):
        payload = dict(self.base, bundleId="com.example.WebReader")
        self.rejected(payload)

    def test_non_release_url(self):
        payload = dict(self.base, ipaUrl="https://api.github.com/repos/x/actions/artifacts/5/zip")
        self.rejected(payload)

    def test_untrusted_domain(self):
        payload = dict(self.base, ipaUrl="https://example.com/WebReader.ipa")
        self.rejected(payload)

    def test_downgrade(self):
        payload = dict(self.base, build=56)
        self.rejected(payload)

    def test_requires_ios13(self):
        payload = dict(self.base, minimumIOS="13.0")
        self.rejected(payload)

    def test_wrong_sha_or_size(self):
        self.rejected(dict(self.base, sha256="INVALID"))
        self.rejected(dict(self.base, ipaSize=0))
        self.rejected(dict(self.base, ipaSize=True))

    def test_unknown_field(self):
        self.rejected(dict(self.base, privilegedCommand="rm -rf /"))

    def test_duplicate_json_key(self):
        good = self.envelope(self.base)
        altered = good[:-1] + b',"signature":"again"}'
        with self.assertRaises(ManifestRejected):
            validate(altered, self.pinned)

    def test_wrong_envelope_algorithm(self):
        obj = json.loads(self.envelope(self.base))
        obj["algorithm"] = "none"
        with self.assertRaises(ManifestRejected):
            validate(encode(obj), self.pinned)

    def test_truncated_envelope(self):
        with self.assertRaises(ManifestRejected):
            validate(self.envelope(self.base)[:-5], self.pinned)

    def test_oversized_envelope(self):
        with self.assertRaises(ManifestRejected):
            validate(b"x" * (65 * 1024), self.pinned)


if __name__ == "__main__":
    unittest.main()
