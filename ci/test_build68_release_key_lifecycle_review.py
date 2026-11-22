#!/usr/bin/env python3
"""Build68 Phase X: revocation/rotation fail-closed with ephemeral P-256 keys."""
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from build66_release_key_pinning_gate import public_key_spki_sha256
from build68_release_key_lifecycle_review import (
    LifecycleReviewDenied, inspect_unapplied_rotation
)


def encode(o):
    return json.dumps(o, separators=(",", ":"), sort_keys=True).encode("utf-8")


class LifecycleReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr68-lifecycle-keys-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.keys = {}
        for name in ("old", "next", "attacker"):
            private = cls.root / (name + ".private")
            public = cls.root / (name + ".public")
            subprocess.run([
                "openssl", "ecparam", "-name", "prime256v1",
                "-genkey", "-noout", "-out", str(private)
            ], capture_output=True, check=True, timeout=15)
            subprocess.run([
                "openssl", "pkey", "-in", str(private),
                "-pubout", "-out", str(public)
            ], capture_output=True, check=True, timeout=15)
            cls.keys[name] = (private, public.read_bytes())
        cls.old_pin = public_key_spki_sha256(cls.keys["old"][1])
        cls.new_pin = public_key_spki_sha256(cls.keys["next"][1])

    def sign(self, signer, data, suffix):
        body = self.root / ("rotation-" + suffix + ".data")
        sig = self.root / ("rotation-" + suffix + ".signature")
        body.write_bytes(data)
        subprocess.run([
            "openssl", "dgst", "-sha256", "-sign",
            str(self.keys[signer][0]), "-out", str(sig), str(body)
        ], capture_output=True, check=True, timeout=15)
        return base64.b64encode(sig.read_bytes()).decode("ascii")

    def rotation(self, *, generation=1, activate=68, from_pin=None,
                 to_pin=None, old_signer="old", next_signer="next",
                 extra=None):
        claims = {
            "schemaVersion": 1,
            "purpose": "WEBREADER-RELEASE-KEY-ROTATION-QA",
            "generation": generation,
            "activateAtBuild": activate,
            "fromSPKI": self.old_pin if from_pin is None else from_pin,
            "toSPKI": self.new_pin if to_pin is None else to_pin,
        }
        if extra:
            claims.update(extra)
        payload = encode(claims)
        return encode({
            "schemaVersion": 1, "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(payload).decode("ascii"),
            "oldSignature": self.sign(old_signer, payload, "old"),
            "newSignature": self.sign(next_signer, payload, "next"),
        })

    def check(self, *, envelope=None, old_pem=None, next_pem=None,
              pin=None, generation=0, installed=66, revoked=()):
        return inspect_unapplied_rotation(
            dual_signed_envelope=self.rotation() if envelope is None else envelope,
            old_public_pem=self.keys["old"][1] if old_pem is None else old_pem,
            proposed_public_pem=self.keys["next"][1] if next_pem is None else next_pem,
            independently_pinned_old_spki=self.old_pin if pin is None else pin,
            current_generation=generation, installed_build=installed,
            revoked_spki_pins=revoked,
        )

    def deny(self, **kwargs):
        with self.assertRaises(LifecycleReviewDenied):
            self.check(**kwargs)

    def test_real_dual_signature_is_review_candidate_only(self):
        r = self.check()
        self.assertEqual(r.old_spki_sha256, self.old_pin)
        self.assertEqual(r.successor_spki_sha256, self.new_pin)
        self.assertEqual(r.proposed_generation, 1)
        self.assertEqual(r.activates_at_build, 68)
        self.assertTrue(r.dual_signature_candidate_verified)
        self.assertTrue(r.current_key_not_revoked)
        self.assertTrue(r.successor_not_revoked)
        for attr in (
            "production_key_configured", "owner_independent_consent_verified",
            "revocation_list_anchored_to_device",
            "release_authenticated_on_ios12", "helper_peer_authenticated",
            "installation_authorized", "installation_performed"
        ):
            self.assertFalse(getattr(r, attr), attr)

    def test_revoked_existing_key_cannot_rotate_even_if_dually_signed(self):
        self.deny(revoked=(self.old_pin,))

    def test_revoked_successor_cannot_rotate_even_if_dually_signed(self):
        self.deny(revoked=frozenset((self.new_pin,)))

    def test_malformed_and_mutable_revocation_lists_rejected(self):
        invalid = [
            None, [], {self.old_pin}, {self.old_pin: True},
            ("f" * 63,), ("G" * 64,), (1,), (False,),
            (self.new_pin, self.new_pin), tuple("a" * 64 for _ in range(65)),
        ]
        for value in invalid:
            with self.subTest(value=str(value)[:40]):
                self.deny(revoked=value)

    def test_no_independent_pin_and_untrusted_old_key_rejected(self):
        self.deny(pin="")
        self.deny(pin="0" * 64)
        self.deny(old_pem=self.keys["attacker"][1])

    def test_invalid_signatures_are_refused(self):
        self.deny(envelope=self.rotation(old_signer="attacker"))
        self.deny(envelope=self.rotation(next_signer="attacker"))
        self.deny(envelope=self.rotation(old_signer="old",
                                        next_signer="attacker"))

    def test_substituted_successor_and_same_key_rejected(self):
        self.deny(next_pem=self.keys["attacker"][1])
        self.deny(next_pem=self.keys["old"][1])

    def test_generation_replay_downgrade_and_invalid_activation(self):
        self.deny(generation=1)
        self.deny(generation=-1)
        self.deny(generation=True)
        self.deny(generation=2_147_483_647)
        self.deny(installed=68)
        self.deny(installed=True)
        self.deny(installed=-1)
        self.deny(envelope=self.rotation(generation=2))
        self.deny(envelope=self.rotation(activate=66))

    def test_injected_operator_approval_cannot_authorize_key(self):
        self.deny(envelope=self.rotation(extra={"ownerApproved": True}))

    def test_legacy_malformed_extra_fields_rejected(self):
        for data in (
            b"", b"{}",
            encode({"schemaVersion": 1, "install": True}),
            self.rotation() + b"VALIDATED=YES",
            b'A' * 10000,
        ):
            with self.subTest(size=len(data)):
                self.deny(envelope=data)

    def test_no_production_key_changes_or_installer_invocations(self):
        source = (
            Path(__file__).resolve().parent / "build68_release_key_lifecycle_review.py"
        ).read_text()
        production = (
            Path(__file__).resolve().parent.parent /
            "MangaReader12/Core/WebReaderProductionPublisherTrust.swift"
        ).read_text()
        self.assertIn("independentlyProvisionedSPKISHA256: String? = nil",
                      production)
        self.assertIn("static let productionTrustGeneration = 0", production)
        self.assertNotIn("productionPublicKeyX963 =", source)
        for forbidden in (
            "install(", "appinst(", "URLSession",
            "posix_spawn(", "launchctl", "chown(", "chmod(", "socket."
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
