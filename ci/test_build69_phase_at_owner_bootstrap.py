#!/usr/bin/env python3
"""Build69 AT public-only bootstrap: disposable key, hostile metadata, no writes."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from build66_release_key_pinning_gate import public_key_spki_sha256
from build69_publisher_bootstrap_review import (
    OwnerBootstrapRejected, review_owner_public_bootstrap
)

class PublicBootstrapOfflineTests(unittest.TestCase):
    _UNSET = object()
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr69-bootstrap-tests-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.values = {}
        for curve in ("prime256v1", "secp384r1"):
            private = cls.root / (curve + ".private.key")
            public = cls.root / (curve + ".public.pem")
            subprocess.run(
                ["openssl", "ecparam", "-genkey", "-name", curve,
                 "-noout", "-out", str(private)], capture_output=True,
                check=True, timeout=20
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                capture_output=True, check=True, timeout=20
            )
            cls.values[curve] = (private.read_bytes(), public.read_bytes())
        cls.good = cls.values["prime256v1"][1]
        cls.pin = public_key_spki_sha256(cls.good)

    def review(self, *, pub=_UNSET, pin=_UNSET, generation=1, revoked=(), baseline=68):
        return review_owner_public_bootstrap(
            public_pem=self.good if pub is self._UNSET else pub,
            independently_verified_pin=self.pin if pin is self._UNSET else pin,
            trust_generation=generation, revoked_pins=revoked,
            installed_build=baseline
        )

    def test_review_returns_public_data_only_not_authority(self):
        receipt = self.review()
        self.assertEqual(receipt["canonicalSPKISHA256"], self.pin)
        self.assertEqual(receipt["publicX963LengthBytes"], 65)
        self.assertTrue(receipt["publicX963Hex"].startswith("04"))
        self.assertEqual(receipt["proposedTrustGeneration"], 1)
        self.assertFalse(receipt["ownerIndependenceVerifiedByScript"])
        self.assertFalse(receipt["ownerExplicitApprovalRecorded"])
        self.assertFalse(receipt["sourceTreeChanged"])
        self.assertFalse(receipt["productionKeyProvisionedInApp"])
        self.assertFalse(receipt["publicationAuthorized"])
        self.assertFalse(receipt["githubReleasePublished"])
        self.assertFalse(receipt["chimeraInstallationAuthorized"])
        self.assertFalse(receipt["installationPerformed"])
        self.assertNotIn("PRIVATE KEY", repr(receipt))
        self.assertNotIn("private", receipt)

    def test_wrong_or_missing_independent_pin_rejected(self):
        for pin in ("0"*64, "", "f"*63, "a"*65, self.pin.upper(), False, None):
            with self.subTest(pin=str(pin)[:10]):
                with self.assertRaises(OwnerBootstrapRejected):
                    self.review(pin=pin)

    def test_wrong_curve_and_private_pem_rejected(self):
        for pem in (self.values["secp384r1"][1],
                    self.values["prime256v1"][0],
                    self.good + self.good, b""):
            with self.subTest(size=len(pem)):
                with self.assertRaises(OwnerBootstrapRejected):
                    self.review(pub=pem)

    def test_revoked_or_malformed_revocations_rejected(self):
        values = (
            (self.pin,), (self.pin, self.pin),
            ["a"*64], {"a"*64}, ("G"*64,), (1,),
            tuple("1"*64 for _ in range(65))
        )
        for value in values:
            with self.subTest(value=str(value)[:30]):
                with self.assertRaises(OwnerBootstrapRejected):
                    self.review(revoked=value)

    def test_policy_requires_initial_generation_and_accepted_baseline(self):
        for gen in (0, -1, 2, False, "1"):
            with self.subTest(generation=gen):
                with self.assertRaises(OwnerBootstrapRejected):
                    self.review(generation=gen)
        for baseline in (67, -1, True, "68"):
            with self.subTest(baseline=baseline):
                with self.assertRaises(OwnerBootstrapRejected):
                    self.review(baseline=baseline)

    def test_unrevoked_separate_pin_is_accepted_as_review_only(self):
        r = self.review(revoked=("0"*64,))
        self.assertEqual(r["revokedPublicPinCount"], 1)
        self.assertFalse(r["productionKeyProvisionedInApp"])

if __name__ == "__main__":
    unittest.main()
