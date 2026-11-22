#!/usr/bin/env python3
"""CP: disposable encrypted owner signatures against synthetic IPA v2.

No CI production keys, real Release publication, appinst or device writes.
Native Mach-O code seal must be audited later on macOS; signing alone does
not prove that the IPA could be installed or was created by this publisher.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from test_validate_webreader_ipa import make_ipa
from webreader_owner_key_ceremony import (
    create_owner_identity, PRIVATE_NAME, PUBLIC_NAME, FINGERPRINT_NAME
)
from webreader_owner_offline_v2_signer import (
    OwnerManifestRejected, sign_owner_candidate, main, _parse_ipa_snapshot
)


class OwnerManifestCPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="webreader-cp-disposable-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owner = self.root / "owner"
        self.owner.mkdir(mode=0o700)
        if os.name == "posix":
            self.owner.chmod(0o700)
        self.passphrase = "lab-only-ephemeral-password-never-production"
        self.identity = create_owner_identity(
            output_directory=self.owner, passphrase=self.passphrase
        )
        self.source, _ = make_ipa(self.root, build="71")
        self.ipa = self.root / "WebReader-Build71-iOS12-adhoc.ipa"
        self.source.rename(self.ipa)
        self.notes = self.root / "notes.json"
        self.notes.write_text('["Offline candidate only", "Sem instalação"]', encoding="utf-8")
        self.out = self.root / "channel-production-v2.json"
        self.pin = self.identity.public_spki_sha256

    def sign(self, **changes):
        opts = dict(
            owner_directory=self.owner,
            ipa_path=self.ipa,
            notes_path=self.notes,
            output=self.out,
            passphrase=self.passphrase,
            independent_spki_sha256=self.pin,
            published_at="2026-11-11T10:00:00Z",
            installed_build=70
        )
        opts.update(changes)
        return sign_owner_candidate(**opts)

    def test_signs_real_verifiable_production_v2_envelope_but_never_publishes(self):
        info = self.sign()
        self.assertEqual(info["status"], "OWNER_LOCAL_SIGNED_CANDIDATE_NO_RELEASE")
        self.assertEqual(info["build"], 71)
        self.assertEqual(info["ipaSHA256"], hashlib.sha256(self.ipa.read_bytes()).hexdigest())
        self.assertTrue(info["signedPayloadVerifiedInMemory"])
        self.assertFalse(info["publicPinIndependentOwnerAuthenticationProvenByTool"])
        self.assertFalse(info["nativeAppleIPACodeSealVerifiedByTool"])
        self.assertTrue(info["macOSNativeProductionPreflightStillRequired"])
        for flag in ("ownerPublicationApprovalRecorded", "productionTrustProvisionedOnIPad",
                     "releasePublished", "installationAuthorized", "installationPerformed"):
            self.assertFalse(info[flag])
        self.assertNotIn(self.passphrase.encode(), self.out.read_bytes())
        encrypted = (self.owner / PRIVATE_NAME).read_bytes()
        self.assertTrue(encrypted.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"))
        envelope = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(set(envelope), {"schemaVersion", "algorithm", "payload", "signature"})
        self.assertEqual(envelope["algorithm"], "ecdsa-p256-sha256")
        payload_raw = base64.b64decode(envelope["payload"], validate=True)
        payload = json.loads(payload_raw)
        self.assertEqual(payload["channel"], "production")
        self.assertEqual(payload["applicationIdentifier"],
                         "AR5SFJC432.com.example.MangaReader12.AR5SFJC432")
        self.assertEqual(payload["sha256"], info["ipaSHA256"])
        self.assertEqual(payload["ipaSize"], self.ipa.stat().st_size)
        self.assertEqual(payload["build"], 71)
        self.assertEqual(payload["minimumIOS"], "12.0")
        self.assertEqual(payload["ipaUrl"],
            "https://github.com/AugustoArbulu/MangaReader12/releases/download/"
            "build71/WebReader-Build71-iOS12-adhoc.ipa")
        public = serialization.load_pem_public_key((self.owner/PUBLIC_NAME).read_bytes())
        public.verify(base64.b64decode(envelope["signature"]), payload_raw,
                      ec.ECDSA(hashes.SHA256()))
        if shutil.which("openssl"):
            from webreader_update_manifest import validate
            checked = validate(self.out.read_bytes(),
                               (self.owner/PUBLIC_NAME).read_bytes(),
                               installed_build=70, installed_ios="12.5.8",
                               expected_channel="production")
            self.assertEqual(checked["build"], 71)
        self.assertEqual(info["signedManifestSHA256"],
                         hashlib.sha256(self.out.read_bytes()).hexdigest())
        with self.assertRaises(OwnerManifestRejected):
            self.sign()  # Existing manifest must not be overwritten.
        if os.name == "posix":
            self.assertEqual(self.out.stat().st_mode & 0o777, 0o600)

    def test_bad_or_forged_credentials_never_create_manifest(self):
        for changed in (
            {"passphrase": "totally-wrong-password"},
            {"passphrase": "too-short"},
            {"independent_spki_sha256": "0"*64},
            {"independent_spki_sha256": self.pin.upper()},
            {"independent_spki_sha256": None},
            {"installed_build": 71},
            {"installed_build": 69},
            {"installed_build": True},
            {"published_at": "not-a-time"},
            {"published_at": "2026-02-31T00:00:00Z"}
        ):
            with self.subTest(changed=changed), self.assertRaises(OwnerManifestRejected):
                self.sign(**changed)
            self.assertFalse(self.out.exists())

    def test_private_and_public_key_pairing_is_rechecked(self):
        # A wrong but still encrypted P256 key must not be able to sign for
        # a different public root, even if the supplied public pin matches.
        alternate = self.root / "alternate"
        alternate.mkdir(mode=0o700)
        if os.name == "posix":
            alternate.chmod(0o700)
        create_owner_identity(
            output_directory=alternate, passphrase=self.passphrase
        )
        (self.owner / PRIVATE_NAME).write_bytes((alternate / PRIVATE_NAME).read_bytes())
        with self.assertRaises(OwnerManifestRejected):
            self.sign()
        self.assertFalse(self.out.exists())

    def test_wrong_public_pin_file_and_modified_ipa_are_rejected(self):
        self.pin = "1"*64
        with self.assertRaises(OwnerManifestRejected):
            self.sign()
        self.pin = self.identity.public_spki_sha256
        (self.owner/FINGERPRINT_NAME).write_text("0"*64 + "\n")
        with self.assertRaises(OwnerManifestRejected):
            self.sign()
        (self.owner/FINGERPRINT_NAME).write_text(self.pin + "\n")
        self.ipa.write_bytes(b"not a zip")
        with self.assertRaises(OwnerManifestRejected):
            self.sign()
        self.assertFalse(self.out.exists())

    def test_bad_ipa_filename_and_wrong_channel_artifact(self):
        bogus = self.root / "wrong.ipa"
        bogus.write_bytes(self.ipa.read_bytes())
        with self.assertRaises(OwnerManifestRejected):
            self.sign(ipa_path=bogus)
        self.assertFalse(self.out.exists())

    def test_invalid_release_notes_and_output_path_refused(self):
        for data in ("{}", '[""]', "[] trailing", '["a", 1]', "null"):
            with self.subTest(notes=data):
                self.notes.write_text(data, encoding="utf-8")
                with self.assertRaises(OwnerManifestRejected):
                    self.sign()
                self.assertFalse(self.out.exists())
        self.notes.write_text('["valid"]')
        with self.assertRaises(OwnerManifestRejected):
            self.sign(output=self.root/"other-name.json")
        with self.assertRaises(OwnerManifestRejected):
            self.sign(output=Path("relative-output"))
        self.assertFalse(self.out.exists())

    def test_sign_rejects_automation_and_check_mode_never_opens_key(self):
        with mock.patch("webreader_owner_offline_v2_signer.sys.stdin.isatty",
                        return_value=False):
            with self.assertRaises(SystemExit):
                main(["--sign", "--owner-dir", str(self.owner),
                      "--ipa", str(self.ipa), "--notes-file", str(self.notes),
                      "--output", str(self.out),
                      "--independent-spki-sha256", self.pin,
                      "--published-at", "2026-11-11T10:00:00Z"])
        with mock.patch("webreader_owner_offline_v2_signer._external_regular",
                        side_effect=AssertionError("must not read keys")), \
             mock.patch("webreader_owner_offline_v2_signer.getpass.getpass",
                        side_effect=AssertionError("must not prompt")):
            self.assertEqual(main(["--check"]), 0)
        self.assertFalse(self.out.exists())

    def test_source_has_no_ipa_install_or_remote_publishing_action(self):
        src = (Path(__file__).parent / "webreader_owner_offline_v2_signer.py").read_text()
        for forbidden in ("subprocess", "appinst(", "WRINST1", "I-CONFIRM-INSTALL",
                          "requests.", "urllib.", "git push", "create_release",
                          "os.system", "install_authorized=True"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, src)
        self.assertIn("getpass.getpass(", src)
        self.assertIn("serialization.load_pem_private_key", src)
        self.assertIn("os.O_EXCL", src)


if __name__ == "__main__":
    unittest.main()
