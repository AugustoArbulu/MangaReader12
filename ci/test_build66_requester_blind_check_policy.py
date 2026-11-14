#!/usr/bin/env python3
"""Offline signed v2 requester-blind CHECK_ONLY laboratory regression tests."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

from build66_release_key_pinning_gate import (
    ReleaseKeyUntrusted, public_key_spki_sha256
)
from build66_requester_blind_check_policy import (
    REQUEST, RequesterBlindCheck
)
from test_build66_signed_release_preflight import synthetic_ipa


def encode(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf8")


class RequesterBlindCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="wr66-blind-check-")
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
        cls.pem = cls.public.read_bytes()
        cls.pin = public_key_spki_sha256(cls.pem)

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.work.cleanup)
        self.workdir = Path(self.work.name)
        self.ipa = self.workdir / "candidate.ipa"
        self.ipa.write_bytes(synthetic_ipa())
        self.fields = self.signed_claims()
        self.manifest = self.envelope()

    def signed_claims(self):
        raw = self.ipa.read_bytes()
        return {
            "schemaVersion": 2, "application": "WebReader",
            "bundleId": "com.example.MangaReader12",
            "applicationIdentifier":
                "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
            "channel": "development", "build": 66, "minimumIOS": "12.0",
            "ipaUrl": ("https://github.com/AugustoArbulu/MangaReader12/"
                       "releases/download/build66/WebReader-Build66-iOS12-adhoc.ipa"),
            "ipaSize": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "releaseNotes": ["Synthetic QA only"],
            "publishedAt": "2026-11-07T04:00:00Z",
        }

    def envelope(self):
        message = encode(self.fields)
        src = self.workdir / "claims"
        sig = self.workdir / "sig"
        src.write_bytes(message)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private),
             "-out", str(sig), str(src)],
            check=True, capture_output=True
        )
        return encode({
            "schemaVersion": 2, "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(message).decode("ascii"),
            "signature": base64.b64encode(sig.read_bytes()).decode("ascii")
        })

    def engine(self, **changes):
        attrs = dict(
            trusted_manifest=self.manifest,
            pinned_p256_public_key=self.pem,
            independently_trusted_spki_sha256=self.pin,
            host_staged_ipa=self.ipa,
            host_installed_build=65
        )
        attrs.update(changes)
        return RequesterBlindCheck(**attrs)

    def test_check_only_returns_candidate_not_install_permission(self):
        result = self.engine().check_once(REQUEST)
        self.assertTrue(result.candidate_verified)
        self.assertEqual(result.candidate_build, 66)
        self.assertEqual(result.release_ipa_sha256, self.fields["sha256"])
        self.assertFalse(result.requester_authenticated)
        self.assertFalse(result.user_install_consent_verified)
        self.assertFalse(result.publisher_trust_root_configured_by_app)
        self.assertFalse(result.code_signature_verified)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.installation_performed)

    def test_install_command_rejected(self):
        self.assertFalse(self.engine().check_once(b"INSTALL\n").candidate_verified)

    def test_fake_ipa_path_rejected(self):
        self.assertFalse(self.engine().check_once(
            b'{"operation":"INSTALL","ipaPath":"/tmp/evil.ipa"}'
        ).candidate_verified)

    def test_fake_release_build_rejected(self):
        self.assertFalse(self.engine().check_once(
            b'{"operation":"CHECK","targetBuild":999}'
        ).candidate_verified)

    def test_client_provided_publisher_key_rejected(self):
        self.assertFalse(self.engine().check_once(
            b'{"operation":"CHECK","publicKey":"attacker"}'
        ).candidate_verified)

    def test_client_provided_signed_manifest_rejected(self):
        self.assertFalse(self.engine().check_once(self.manifest).candidate_verified)

    def test_client_claimed_authenticated_peer_rejected(self):
        self.assertFalse(self.engine().check_once(
            b'{"codeSignatureVerified":true,"requesterAuthenticated":true}'
        ).candidate_verified)

    def test_alternate_whitespace_rejected(self):
        self.assertFalse(self.engine().check_once(REQUEST + b"\n").candidate_verified)

    def test_nonbytes_rejected(self):
        self.assertFalse(self.engine().check_once("WR-CHECK-APPROVED-RELEASE-ONLY-V1\n").candidate_verified)

    def test_success_consumes_single_use_state(self):
        policy = self.engine()
        self.assertTrue(policy.check_once(REQUEST).candidate_verified)
        repeated = policy.check_once(REQUEST)
        self.assertFalse(repeated.candidate_verified)
        self.assertEqual(repeated.reason, "REPLAY_OR_DUPLICATE_REQUEST")

    def test_bad_request_also_consumes_single_use_state(self):
        policy = self.engine()
        self.assertFalse(policy.check_once(b"BAD").candidate_verified)
        self.assertEqual(policy.check_once(REQUEST).reason,
                         "REPLAY_OR_DUPLICATE_REQUEST")

    def test_concurrent_attempts_one_result_only(self):
        policy = self.engine()
        barrier = threading.Barrier(3)
        outcomes = []
        lock = threading.Lock()

        def request():
            barrier.wait()
            result = policy.check_once(REQUEST)
            with lock:
                outcomes.append(result)

        first = threading.Thread(target=request)
        second = threading.Thread(target=request)
        first.start()
        second.start()
        barrier.wait()
        first.join(timeout=3)
        second.join(timeout=3)
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(sum(int(out.candidate_verified) for out in outcomes), 1)
        self.assertTrue(all(not out.installation_authorized for out in outcomes))

    def test_wrong_pinned_public_key_refuses_engine_creation(self):
        with self.assertRaises(ReleaseKeyUntrusted):
            self.engine(independently_trusted_spki_sha256="0" * 64)

    def test_mutated_ipa_refuses_engine_creation(self):
        self.ipa.write_bytes(self.ipa.read_bytes() + b"CHANGED")
        with self.assertRaises(ReleaseKeyUntrusted):
            self.engine()

    def test_mismatched_signed_app_id_refuses_engine(self):
        self.fields["applicationIdentifier"] = "FAKE"
        self.manifest = self.envelope()
        with self.assertRaises(ReleaseKeyUntrusted):
            self.engine()

    def test_manifest_signed_for_old_build_refuses_engine(self):
        self.ipa.write_bytes(synthetic_ipa(build="65"))
        self.fields = self.signed_claims()
        self.fields["build"] = 65
        self.fields["ipaUrl"] = self.fields["ipaUrl"].replace("build66", "build65").replace(
            "Build66", "Build65"
        )
        self.manifest = self.envelope()
        with self.assertRaises(ReleaseKeyUntrusted):
            self.engine()


if __name__ == "__main__":
    unittest.main()
