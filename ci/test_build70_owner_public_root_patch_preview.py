#!/usr/bin/env python3
"""CG: ephemeral P-256 public-only patch proposal, no enrollment or installer."""
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

from build66_release_key_pinning_gate import public_key_spki_sha256
from build70_owner_public_root_patch_preview import (
    OwnerPublicProposalRejected, ROOT, KEY_SOURCE, TRUST_SOURCE,
    propose_public_root, write_external_proposal
)


class OwnerPublicSourceProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr70-public-proposal-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.directory = Path(cls.tmp.name)
        cls.private = cls.directory / "private.key"
        cls.public = cls.directory / "public.pem"
        subprocess.run([
            "openssl", "ecparam", "-name", "prime256v1",
            "-genkey", "-noout", "-out", str(cls.private)
        ], check=True, capture_output=True, timeout=20)
        subprocess.run([
            "openssl", "pkey", "-in", str(cls.private),
            "-pubout", "-out", str(cls.public)
        ], check=True, capture_output=True, timeout=20)
        cls.pub = cls.public.read_bytes()
        cls.pin = public_key_spki_sha256(cls.pub)

    def test_valid_public_proposal_contains_exactly_two_compiled_root_changes(self):
        before_key = (ROOT / KEY_SOURCE).read_bytes()
        before_trust = (ROOT / TRUST_SOURCE).read_bytes()
        patch, receipt = propose_public_root(
            public_pem=self.pub, independently_verified_pin=self.pin
        )
        self.assertEqual(patch.count("--- a/"), 2)
        self.assertEqual(patch.count("+++ b/"), 2)
        self.assertIn("WebReaderUpdateChecker.swift", patch)
        self.assertIn("WebReaderProductionPublisherTrust.swift", patch)
        self.assertIn("+    static let productionPublicKeyX963: Data? = Data([0x04", patch)
        self.assertIn(self.pin, patch)
        self.assertIn("+    static let productionTrustGeneration = 1", patch)
        self.assertNotIn("PRIVATE KEY", patch)
        self.assertFalse(receipt["privateKeyReadOrCreated"])
        self.assertFalse(receipt["proposedSourcePatchApplied"])
        self.assertFalse(receipt["productionTrustActivated"])
        self.assertFalse(receipt["installationAuthorized"])
        self.assertEqual((ROOT / KEY_SOURCE).read_bytes(), before_key)
        self.assertEqual((ROOT / TRUST_SOURCE).read_bytes(), before_trust)

    def test_write_external_patch_once_and_never_modify_repository(self):
        patch, _ = propose_public_root(
            public_pem=self.pub, independently_verified_pin=self.pin
        )
        with tempfile.TemporaryDirectory(prefix="wr70-patch-output-") as tmp:
            destination = Path(tmp) / "public-only.patch"
            write_external_proposal(patch, destination)
            self.assertEqual(destination.read_text(), patch)
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            with self.assertRaises(OwnerPublicProposalRejected):
                write_external_proposal(patch, destination)
            self.assertEqual(destination.read_text(), patch)

    def test_private_key_and_wrong_pin_never_produce_patch(self):
        for pub, pin in (
            (self.private.read_bytes(), self.pin),
            (self.pub, "0" * 64),
            (self.pub, None),
            (self.pub, self.pin.upper()),
            (b"", self.pin),
        ):
            with self.subTest(pub_size=len(pub), pin=pin):
                with self.assertRaises(OwnerPublicProposalRejected):
                    propose_public_root(
                        public_pem=pub, independently_verified_pin=pin
                    )

    def test_requires_physically_reported_build70_and_valid_source(self):
        for baseline in (69, -1, True, "70"):
            with self.subTest(baseline=baseline):
                with self.assertRaises(OwnerPublicProposalRejected):
                    propose_public_root(
                        public_pem=self.pub,
                        independently_verified_pin=self.pin,
                        installed_build=baseline
                    )
        with mock.patch(
            "build70_owner_public_root_patch_preview._source",
            return_value="unexpected content"
        ):
            with self.assertRaises(OwnerPublicProposalRejected):
                propose_public_root(
                    public_pem=self.pub, independently_verified_pin=self.pin
                )

    def test_output_cannot_be_under_repo_or_symlink(self):
        patch, _ = propose_public_root(
            public_pem=self.pub, independently_verified_pin=self.pin
        )
        with self.assertRaises(OwnerPublicProposalRejected):
            write_external_proposal(patch, ROOT / "ci/owner-root-should-not-exist.patch")
        with tempfile.TemporaryDirectory(prefix="wr70-public-output-") as tmp:
            dest = Path(tmp) / "safe.patch"
            link = Path(tmp) / "alias.patch"
            dest.write_text("keep-unchanged")
            link.symlink_to(dest)
            with self.assertRaises(OwnerPublicProposalRejected):
                write_external_proposal(patch, link)
            self.assertEqual(dest.read_text(), "keep-unchanged")

    def test_open_exclusive_collision_does_not_unlink_foreign_file(self):
        patch, _ = propose_public_root(
            public_pem=self.pub, independently_verified_pin=self.pin
        )
        with tempfile.TemporaryDirectory(prefix="wr70-exclusive-") as tmp:
            output = Path(tmp) / "proposal.patch"
            def collision(*args, **kwargs):
                output.write_text("someone-else's-file")
                raise FileExistsError("injected concurrent create")
            with mock.patch(
                "build70_owner_public_root_patch_preview.os.open",
                side_effect=collision
            ):
                with self.assertRaises(FileExistsError):
                    write_external_proposal(patch, output)
            self.assertEqual(output.read_text(), "someone-else's-file")

    def test_legacy_appinst_and_root_policy_are_left_off(self):
        source = (ROOT / "ci/build70_owner_public_root_patch_preview.py").read_text()
        self.assertIn("proposedSourcePatchApplied", source)
        self.assertNotIn("git push", source)
        self.assertNotIn("appinst(", source)
        self.assertNotIn("private_key", source)
        self.assertNotIn("secrets.GITHUB_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
