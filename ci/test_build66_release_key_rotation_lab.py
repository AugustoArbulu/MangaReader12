#!/usr/bin/env python3
"""Offline two-key rotation security tests with disposable EC P-256 keys."""
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from build66_release_key_pinning_gate import public_key_spki_sha256
from build66_release_key_rotation_lab import (
    RotationCandidateRejected, inspect_rotation_candidate
)


def encode(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf8")


class RotationCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="wr66-rotation-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.keys = {}
        for name in ("old", "new", "attacker"):
            private = cls.root / (name + "-private.pem")
            public = cls.root / (name + "-public.pem")
            subprocess.run(
                ["openssl", "ecparam", "-name", "prime256v1", "-genkey",
                 "-noout", "-out", str(private)],
                check=True, capture_output=True
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                check=True, capture_output=True
            )
            cls.keys[name] = (private, public.read_bytes())
        cls.old_pin = public_key_spki_sha256(cls.keys["old"][1])
        cls.new_pin = public_key_spki_sha256(cls.keys["new"][1])

    def setUp(self):
        self.claims = {
            "schemaVersion": 1,
            "purpose": "WEBREADER-RELEASE-KEY-ROTATION-QA",
            "generation": 1,
            "activateAtBuild": 67,
            "fromSPKI": self.old_pin,
            "toSPKI": self.new_pin,
        }

    def sign(self, private_key, payload, suffix):
        file = self.root / ("message-" + suffix)
        signature = self.root / ("signature-" + suffix)
        file.write_bytes(payload)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(private_key),
             "-out", str(signature), str(file)],
            check=True, capture_output=True
        )
        return base64.b64encode(signature.read_bytes()).decode("ascii")

    def wrapped(self, *, claims=None, old_signer="old", new_signer="new"):
        data = encode(self.claims if claims is None else claims)
        return encode({
            "schemaVersion": 1, "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(data).decode("ascii"),
            "oldSignature": self.sign(self.keys[old_signer][0], data, "old"),
            "newSignature": self.sign(self.keys[new_signer][0], data, "new"),
        })

    def validate(self, envelope=None, old_pem=None, new_pem=None, pin=None,
                 generation=0, installed_build=65):
        return inspect_rotation_candidate(
            self.wrapped() if envelope is None else envelope,
            self.keys["old"][1] if old_pem is None else old_pem,
            self.keys["new"][1] if new_pem is None else new_pem,
            self.old_pin if pin is None else pin,
            current_generation=generation, installed_build=installed_build,
        )

    def denied(self, **kwargs):
        with self.assertRaises(RotationCandidateRejected):
            self.validate(**kwargs)

    def test_dual_signed_rotation_only_a_candidate(self):
        result = self.validate()
        self.assertTrue(result["dual_signature_chain_verified"])
        self.assertTrue(result["independent_operator_review_required"])
        self.assertFalse(result["revocation_checked"])
        self.assertFalse(result["production_key_rotated"])
        self.assertFalse(result["installation_authorized"])
        self.assertFalse(result["installation_performed"])
        self.assertEqual(result["candidate_generation"], 1)

    def test_wrong_pinned_old_key_rejected(self):
        self.denied(pin="0" * 64)

    def test_missing_pinned_old_key_rejected(self):
        self.denied(pin="")

    def test_key_substitution_rejected(self):
        self.denied(old_pem=self.keys["attacker"][1])

    def test_wrong_successor_key_rejected(self):
        self.denied(new_pem=self.keys["attacker"][1])

    def test_same_old_and_new_key_rejected(self):
        self.denied(new_pem=self.keys["old"][1])

    def test_wrong_old_signature_rejected(self):
        self.denied(envelope=self.wrapped(old_signer="attacker"))

    def test_wrong_new_signature_rejected(self):
        self.denied(envelope=self.wrapped(new_signer="attacker"))

    def test_previous_generation_rejected(self):
        self.denied(generation=1)

    def test_skipped_generation_rejected(self):
        self.denied(generation=-1)

    def test_activation_at_installed_build_rejected(self):
        self.denied(installed_build=67)

    def test_negative_current_generation_rejected(self):
        self.denied(generation=-1)

    def test_boolean_generation_rejected(self):
        self.denied(generation=True)

    def test_noninteger_activation_rejected(self):
        claims = dict(self.claims, activateAtBuild="67")
        self.denied(envelope=self.wrapped(claims=claims))

    def test_wrong_current_spki_in_signed_payload(self):
        claims = dict(self.claims, fromSPKI="0" * 64)
        self.denied(envelope=self.wrapped(claims=claims))

    def test_wrong_new_spki_in_signed_payload(self):
        claims = dict(self.claims, toSPKI="0" * 64)
        self.denied(envelope=self.wrapped(claims=claims))

    def test_extra_install_field_rejected(self):
        claims = dict(self.claims, install=True)
        self.denied(envelope=self.wrapped(claims=claims))

    def test_wrong_purpose_rejected(self):
        claims = dict(self.claims, purpose="INSTALL")
        self.denied(envelope=self.wrapped(claims=claims))

    def test_corrupted_old_signature_rejected(self):
        body = json.loads(self.wrapped())
        sig = base64.b64decode(body["oldSignature"])
        body["oldSignature"] = base64.b64encode(sig[:-1] + bytes([sig[-1] ^ 1])).decode()
        self.denied(envelope=encode(body))

    def test_corrupted_new_signature_rejected(self):
        body = json.loads(self.wrapped())
        sig = base64.b64decode(body["newSignature"])
        body["newSignature"] = base64.b64encode(sig[:-1] + bytes([sig[-1] ^ 1])).decode()
        self.denied(envelope=encode(body))

    def test_mismatch_wrapper_version_rejected(self):
        body = json.loads(self.wrapped())
        body["schemaVersion"] = 2
        self.denied(envelope=encode(body))

    def test_malformed_wrapper_rejected(self):
        self.denied(envelope=b"{}")

    def test_duplicate_json_key_rejected(self):
        raw = self.wrapped()
        self.denied(envelope=b'{"schemaVersion":1,' + raw[1:])

    def test_untrusted_algorithm_rejected(self):
        body = json.loads(self.wrapped())
        body["algorithm"] = "none"
        self.denied(envelope=encode(body))

    def test_payload_tamper_breaks_signatures(self):
        body = json.loads(self.wrapped())
        claims = dict(self.claims, generation=2)
        body["payload"] = base64.b64encode(encode(claims)).decode()
        self.denied(envelope=encode(body))

    def test_oversized_envelope_rejected(self):
        self.denied(envelope=b"x" * 8193)


if __name__ == "__main__":
    unittest.main()
