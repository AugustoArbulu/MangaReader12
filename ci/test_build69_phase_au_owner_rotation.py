#!/usr/bin/env python3
"""Build69 AU adversarial owner rotation tests; ephemeral P256 keys only."""
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from build66_release_key_pinning_gate import public_key_spki_sha256
from build69_owner_rotation_review import OwnerRotationRejected, review_owner_rotation


def encode(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")


class OwnerRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr69-owner-rotation-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.keys = {}
        for name in ("old", "next", "attacker"):
            private = cls.root / (name + ".private.pem")
            public = cls.root / (name + ".public.pem")
            subprocess.run([
                "openssl", "ecparam", "-genkey", "-name", "prime256v1",
                "-noout", "-out", str(private)
            ], check=True, capture_output=True, timeout=15)
            subprocess.run([
                "openssl", "pkey", "-in", str(private),
                "-pubout", "-out", str(public)
            ], check=True, capture_output=True, timeout=15)
            cls.keys[name] = {"private": private, "public": public.read_bytes()}
        cls.old_pin = public_key_spki_sha256(cls.keys["old"]["public"])
        cls.next_pin = public_key_spki_sha256(cls.keys["next"]["public"])

    def sign(self, name, data, label):
        payload = self.root / (label + ".payload")
        sig = self.root / (label + ".signature")
        payload.write_bytes(data)
        subprocess.run([
            "openssl", "dgst", "-sha256", "-sign", str(self.keys[name]["private"]),
            "-out", str(sig), str(payload)
        ], check=True, capture_output=True, timeout=15)
        return base64.b64encode(sig.read_bytes()).decode("ascii")

    def envelope(self, *, next_pin=None, generation=2, activation=70,
                 old_signer="old", new_signer="next", extra=None):
        claims = {
            "schemaVersion": 1, "purpose": "WEBREADER-RELEASE-KEY-ROTATION-QA",
            "generation": generation, "activateAtBuild": activation,
            "fromSPKI": self.old_pin,
            "toSPKI": self.next_pin if next_pin is None else next_pin,
        }
        if extra:
            claims.update(extra)
        data = encode(claims)
        return encode({
            "schemaVersion": 1, "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(data).decode("ascii"),
            "oldSignature": self.sign(old_signer, data, "old-signature"),
            "newSignature": self.sign(new_signer, data, "next-signature"),
        })

    def review(self, *, signed=None, old_pem=None, next_pem=None,
               old_pin=None, successor_pin=None, current_generation=1,
               installed_build=69, revoked=()):
        return review_owner_rotation(
            old_public_pem=self.keys["old"]["public"] if old_pem is None else old_pem,
            successor_public_pem=self.keys["next"]["public"] if next_pem is None else next_pem,
            independent_old_spki=self.old_pin if old_pin is None else old_pin,
            independent_successor_spki=self.next_pin if successor_pin is None else successor_pin,
            dual_signed_envelope=self.envelope() if signed is None else signed,
            current_generation=current_generation, installed_build=installed_build,
            revoked_pins=revoked
        )

    def test_dual_signed_independently_pinned_review_is_never_activation(self):
        r = self.review()
        self.assertEqual(r["oldSPKISHA256"], self.old_pin)
        self.assertEqual(r["successorSPKISHA256"], self.next_pin)
        self.assertEqual(r["proposedGeneration"], 2)
        self.assertEqual(r["proposedActivationBuild"], 70)
        self.assertTrue(r["dualSignatureChainVerified"])
        self.assertTrue(r["successorMatchesProvidedIndependentPin"])
        self.assertTrue(r["manualRebootstrapRequiredIfOldKeyCompromised"])
        for name in (
            "ownerIndependentApprovalVerifiedByScript", "ownerPublicationApprovalRecorded",
            "revocationsUpdatedOnDevice", "successorTrustRootInstalledInApp",
            "automaticRecoveryFromRevokedKeyAllowed", "githubReleasePublished",
            "mainModified", "chimeraInstallationAuthorized", "installationPerformed"
        ):
            self.assertFalse(r[name], name)

    def test_requires_independently_pinned_successor(self):
        for pin in ("0"*64, "", "F"*64):
            with self.subTest(pin=pin):
                with self.assertRaises(OwnerRotationRejected):
                    self.review(successor_pin=pin)
        with self.assertRaises(OwnerRotationRejected):
            self.review(next_pem=self.keys["attacker"]["public"])

    def test_old_root_must_be_trusted_and_not_revoked(self):
        with self.assertRaises(OwnerRotationRejected):
            self.review(old_pin="0"*64)
        with self.assertRaises(OwnerRotationRejected):
            self.review(revoked=(self.old_pin,))
        with self.assertRaises(OwnerRotationRejected):
            self.review(revoked=(self.next_pin,))

    def test_both_real_signatures_required(self):
        with self.assertRaises(OwnerRotationRejected):
            self.review(signed=self.envelope(new_signer="attacker"))
        with self.assertRaises(OwnerRotationRejected):
            self.review(signed=self.envelope(old_signer="attacker"))

    def test_monotonic_replay_and_false_approval_rejected(self):
        for v in (0, 2, True, -1):
            with self.subTest(generation=v):
                with self.assertRaises(OwnerRotationRejected):
                    self.review(current_generation=v)
        with self.assertRaises(OwnerRotationRejected):
            self.review(signed=self.envelope(generation=3))
        with self.assertRaises(OwnerRotationRejected):
            self.review(signed=self.envelope(activation=69))
        with self.assertRaises(OwnerRotationRejected):
            self.review(signed=self.envelope(extra={"ownerApproved": True}))

if __name__ == "__main__":
    unittest.main()
