#!/usr/bin/env python3
"""CI: lab-only immutable Release readback with real P-256 signature.

Mocked code-seal receipt is ONLY for Linux control-flow tests; native codesign
against a genuine signed Build70 IPA is separately mandatory on macOS.
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
from build70_immutable_public_release_readback import (
    PublicReadbackRejected, review_public_readback, _public_snapshot
)


def canonical(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


class ImmutablePublicReadbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr70-ci-readback-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.priv = cls.root / "throwaway-key.pem"
        cls.pub = cls.root / "throwaway-public.pem"
        subprocess.run(["openssl", "ecparam", "-name", "prime256v1",
                        "-genkey", "-noout", "-out", str(cls.priv)],
                       capture_output=True, check=True, timeout=20)
        subprocess.run(["openssl", "pkey", "-in", str(cls.priv),
                        "-pubout", "-out", str(cls.pub)],
                       capture_output=True, check=True, timeout=20)
        cls.public = cls.pub.read_bytes()
        cls.pin = public_key_spki_sha256(cls.public)
        cls.local = cls.root / "WebReader-Build71-iOS12-adhoc.ipa"
        cls.downloaded = cls.root / "readback-WebReader-Build71-iOS12-adhoc.ipa"
        cls.local.write_bytes(b"LAB: NOT A REAL IPA - DO NOT INSTALL")
        cls.downloaded.write_bytes(cls.local.read_bytes())
        cls.body = {
            "schemaVersion": 2, "application": "WebReader",
            "bundleId": "com.example.MangaReader12",
            "applicationIdentifier": "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
            "channel": "production",
            "build": 71,
            "minimumIOS": "12.0",
            "ipaUrl": "https://github.com/AugustoArbulu/MangaReader12/"
                      "releases/download/build71/WebReader-Build71-iOS12-adhoc.ipa",
            "ipaSize": cls.local.stat().st_size,
            "sha256": hashlib.sha256(cls.local.read_bytes()).hexdigest(),
            "releaseNotes": ["Synthetic immutable release metadata test"],
            "publishedAt": "2026-11-09T22:00:00Z",
        }
        message = cls.root / "payload"
        message.write_bytes(canonical(cls.body))
        signature = cls.root / "signature.der"
        subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(cls.priv),
                        "-out", str(signature), str(message)],
                       capture_output=True, check=True, timeout=20)
        cls.envelope = canonical({
            "schemaVersion": 2, "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(message.read_bytes()).decode(),
            "signature": base64.b64encode(signature.read_bytes()).decode(),
        })
        cls.release = {
            "tag_name": "build71",
            "html_url": "https://github.com/AugustoArbulu/MangaReader12/releases/tag/build71",
            "draft": False, "prerelease": False, "immutable": True,
            "published_at": "2026-11-09T23:00:00Z",
            "assets": [{
                "id": 123, "name": "WebReader-Build71-iOS12-adhoc.ipa",
                "state": "uploaded", "content_type": "application/octet-stream",
                "size": cls.local.stat().st_size,
                "digest": "sha256:" + cls.body["sha256"],
                "browser_download_url": cls.body["ipaUrl"],
            }],
        }

    def receipt(self, ipa_path):
        # Test-only mock. A real public release gate must run native codesign.
        return {
            "ipaSHA256": self.body["sha256"],
            "ipaSize": self.body["ipaSize"],
            "releaseURL": self.body["ipaUrl"],
            "publicSPKISHA256": self.pin,
            "nativeCodeSealVerified": True,
        }

    def run_gate(self, **kwargs):
        args = {
            "owner_public_pem": self.public,
            "independent_pin": self.pin,
            "private_manifest": self.envelope,
            "published_manifest": self.envelope,
            "local_ipa": self.local,
            "readback_ipa": self.downloaded,
            "release_rest_json": canonical(self.release),
            "installed_build": 70,
        }
        args.update(kwargs)
        with mock.patch(
            "build70_immutable_public_release_readback.review_production_release",
            side_effect=lambda **f: self.receipt(f["ipa_path"])
        ) as seal:
            result = review_public_readback(**args)
        return result, seal.call_count

    def test_valid_ephemeral_ecc_production_envelope_and_two_file_gate(self):
        receipt, count = self.run_gate()
        self.assertEqual(count, 2)
        self.assertEqual(receipt["build"], 71)
        self.assertTrue(receipt["releaseImmutableFlagMatched"])
        self.assertTrue(receipt["assetAPISHA256MatchedSignedPayload"])
        self.assertTrue(receipt["sourceAndReadbackNativeCodeSealsVerified"])
        for field in (
            "publicationHappenedInThisTool",
            "githubAPILiveVerifiedByThisTool",
            "publicDownloadOriginAuthenticatedByThisTool",
            "ownerPublicationApprovalRecordedByThisTool",
            "publicRootProvisionedOnInstalledIPadByThisTool",
            "automaticInstallationAuthorized",
            "installationPerformed",
        ):
            with self.subTest(field=field):
                self.assertFalse(receipt[field])

    def test_reject_missing_or_malformed_public_release_proof(self):
        scenarios = [
            {"immutable": False},
            {"immutable": None},
            {"immutable": "true"},
            {"draft": True},
            {"prerelease": True},
            {"tag_name": "build72"},
            {"html_url": "https://attacker.example/release"},
            {"published_at": None},
            {"published_at": "invalid"},
            {"assets": []},
            {"assets": [{**self.release["assets"][0], "state": "starter"}]},
            {"assets": [{**self.release["assets"][0], "size": 1}]},
            {"assets": [{**self.release["assets"][0], "digest": None}]},
            {"assets": [{**self.release["assets"][0], "digest": "sha256:" + "a"*64}]},
            {"assets": [{**self.release["assets"][0],
                         "browser_download_url": "https://evil.invalid/ipa"}]},
            {"assets": [{**self.release["assets"][0], "content_type": "text/html"}]},
            {"assets": [self.release["assets"][0], self.release["assets"][0]]},
        ]
        for case in scenarios:
            with self.subTest(case=case):
                with self.assertRaises(PublicReadbackRejected):
                    self.run_gate(release_rest_json=canonical({
                        **self.release, **case
                    }))
        with self.assertRaises(PublicReadbackRejected):
            self.run_gate(release_rest_json=(
                canonical(self.release)[:-1] + b',"immutable":false}'
            ))

    def test_reject_manifest_mismatch_wrong_key_pin_and_replay(self):
        changed = self.envelope + b"\n"
        with self.assertRaises(PublicReadbackRejected):
            self.run_gate(published_manifest=changed)
        with self.assertRaises(PublicReadbackRejected):
            self.run_gate(independent_pin="0"*64)
        with self.assertRaises(PublicReadbackRejected):
            self.run_gate(installed_build=71)
        with self.assertRaises(PublicReadbackRejected):
            self.run_gate(installed_build=68)
        with self.assertRaises(PublicReadbackRejected):
            self.run_gate(owner_public_pem=b"garbage")

    def test_reject_same_file_alias_and_symlink(self):
        with self.assertRaises(PublicReadbackRejected):
            self.run_gate(readback_ipa=self.local)
        link = self.root / "download-alias.ipa"
        link.symlink_to(self.local)
        try:
            with self.assertRaises(PublicReadbackRejected):
                self.run_gate(readback_ipa=link)
        finally:
            link.unlink()

    def test_two_separate_native_seal_audits_mandatory(self):
        # Proof that source and readback must both pass the real preflight.
        args = {
            "owner_public_pem": self.public,
            "independent_pin": self.pin,
            "private_manifest": self.envelope,
            "published_manifest": self.envelope,
            "local_ipa": self.local,
            "readback_ipa": self.downloaded,
            "release_rest_json": canonical(self.release),
            "installed_build": 70,
        }
        for fail_index in (1, 2):
            def failure(**kw):
                failure.calls += 1
                if failure.calls == fail_index:
                    raise RuntimeError("simulated native codesign error")
                return self.receipt(kw["ipa_path"])
            failure.calls = 0
            with mock.patch(
                "build70_immutable_public_release_readback.review_production_release",
                side_effect=failure
            ):
                with self.assertRaises((RuntimeError, PublicReadbackRejected)):
                    review_public_readback(**args)

    def test_real_native_preflight_rejects_synthetic_unsigned_ipa(self):
        # Ensures this test fixture never poses as a genuine signed app.
        with self.assertRaises(PublicReadbackRejected):
            review_public_readback(
                owner_public_pem=self.public,
                independent_pin=self.pin,
                private_manifest=self.envelope,
                published_manifest=self.envelope,
                local_ipa=self.local, readback_ipa=self.downloaded,
                release_rest_json=canonical(self.release),
                installed_build=70
            )


if __name__ == "__main__":
    unittest.main()
