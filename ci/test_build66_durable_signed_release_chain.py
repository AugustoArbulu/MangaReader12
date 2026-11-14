#!/usr/bin/env python3
"""End-to-end crash/restart/pinning lab with P-256 temporary signing keys."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

from build66_durable_one_shot_lab import DurableOneShotDiagnostic
from build66_release_key_pinning_gate import ReleaseKeyUntrusted, public_key_spki_sha256
from build66_durable_replay_journal import ReplayJournalUnavailable
from test_build66_signed_release_preflight import synthetic_ipa


def encode(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf8")


class DurableSignedReleaseChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="wr66-chain-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.private = cls.root / "ephemeral-private.pem"
        cls.public = cls.root / "ephemeral-public.pem"
        subprocess.run(
            ["openssl", "ecparam", "-name", "prime256v1",
             "-genkey", "-noout", "-out", str(cls.private)],
            check=True, capture_output=True
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private),
             "-pubout", "-out", str(cls.public)],
            check=True, capture_output=True
        )
        cls.key = cls.public.read_bytes()
        cls.pin = public_key_spki_sha256(cls.key)

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.work.cleanup)
        self.root_dir = Path(self.work.name)
        self.ipa = self.root_dir / "fixture.ipa"
        self.ipa.write_bytes(synthetic_ipa())
        self.ledger = self.root_dir / "protected-journal"
        self.ledger.mkdir(mode=0o700)
        self.clock = [100.0]
        self.manifest = self.signed()

    def signed(self):
        data = self.ipa.read_bytes()
        payload = encode({
            "schemaVersion": 2,
            "application": "WebReader",
            "bundleId": "com.example.MangaReader12",
            "applicationIdentifier":
                "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
            "channel": "development", "build": 66,
            "minimumIOS": "12.0",
            "ipaUrl": ("https://github.com/AugustoArbulu/MangaReader12/"
                       "releases/download/build66/WebReader-Build66-iOS12-adhoc.ipa"),
            "ipaSize": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "releaseNotes": ["Synthetic host test only"],
            "publishedAt": "2026-11-07T04:00:00Z",
        })
        msg = self.root_dir / "msg"
        sig = self.root_dir / "sig"
        msg.write_bytes(payload)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private),
             "-out", str(sig), str(msg)],
            check=True, capture_output=True
        )
        return encode({
            "schemaVersion": 2, "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(payload).decode(),
            "signature": base64.b64encode(sig.read_bytes()).decode(),
        })

    def new_run(self, **kwargs):
        options = dict(
            signed_envelope=self.manifest, public_key_pem=self.key,
            trusted_spki_sha256=self.pin,
            staged_ipa_path=self.ipa, installed_build=65,
            replay_directory=self.ledger,
            entropy=lambda count: b"\x7f" * count,
            clock=lambda: self.clock[0]
        )
        options.update(kwargs)
        return DurableOneShotDiagnostic(**options)

    def valid(self, run):
        return encode({
            "protocolVersion": 1, "operation": "CHECK_ONLY",
            "challenge": run.challenge(),
            "manifestSHA256": hashlib.sha256(self.manifest).hexdigest(),
            "ipaSHA256": hashlib.sha256(self.ipa.read_bytes()).hexdigest(),
            "targetBuild": 66,
            "bundleId": "com.example.MangaReader12",
            "applicationIdentifier":
                "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
        })

    def test_signed_release_and_pinned_key_to_one_shot(self):
        run = self.new_run()
        result = run.check_once(self.valid(run))
        self.assertTrue(result.request_consistent)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.installation_performed)
        self.assertFalse(result.peer_identity_authenticated)
        self.assertFalse(result.user_install_consent_verified)

    def test_second_run_cannot_replay_same_nonce_and_signed_release(self):
        first = self.new_run()
        self.assertTrue(first.check_once(self.valid(first)).request_consistent)
        second = self.new_run()
        self.assertEqual(
            second.check_once(self.valid(second)).reason,
            "PERSISTENT_REPLAY_REJECTED"
        )

    def test_invalid_request_consumes_durable_nonce_across_restart(self):
        first = self.new_run()
        self.assertFalse(first.check_once(b"not-json").request_consistent)
        second = self.new_run()
        self.assertEqual(
            second.check_once(self.valid(second)).reason,
            "PERSISTENT_REPLAY_REJECTED"
        )

    def test_expired_attempt_stays_spent_across_restart(self):
        first = self.new_run()
        self.clock[0] = 131.0
        self.assertEqual(first.check_once(self.valid(first)).reason, "EXPIRED_REJECTED")
        self.clock[0] = 100.0
        second = self.new_run()
        self.assertEqual(
            second.check_once(self.valid(second)).reason,
            "PERSISTENT_REPLAY_REJECTED"
        )

    def test_two_fresh_sessions_same_nonce_only_one_matches(self):
        one, two = self.new_run(), self.new_run()
        barrier = threading.Barrier(3)
        output = []
        guard = threading.Lock()

        def worker(session):
            barrier.wait()
            result = session.check_once(self.valid(session))
            with guard:
                output.append(result)

        threads = [
            threading.Thread(target=worker, args=(one,)),
            threading.Thread(target=worker, args=(two,))
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=3)
        self.assertEqual(len(output), 2)
        self.assertEqual(sum(r.request_consistent for r in output), 1)
        self.assertTrue(all(not r.installation_authorized for r in output))

    def test_independent_pin_mismatch_refuses_new_session(self):
        with self.assertRaises(ReleaseKeyUntrusted):
            self.new_run(trusted_spki_sha256="0" * 64)
        self.assertEqual(list(self.ledger.iterdir()), [])

    def test_missing_replay_directory_refuses_session(self):
        self.ledger.rmdir()
        with self.assertRaises(ReplayJournalUnavailable):
            self.new_run()

    def test_unprotected_replay_directory_refuses_session(self):
        self.ledger.chmod(0o755)
        with self.assertRaises(ReplayJournalUnavailable):
            self.new_run()

    def test_ipa_replacement_refuses_session(self):
        self.ipa.write_bytes(self.ipa.read_bytes() + b"WRONG")
        with self.assertRaises(ReleaseKeyUntrusted):
            self.new_run()

    def test_no_install_callback_or_network_side_effects(self):
        run = self.new_run()
        self.assertFalse(run.check_once(b'{"install":true}').installation_authorized)
        self.assertEqual(len(list(self.ledger.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
