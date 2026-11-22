#!/usr/bin/env python3
"""Phase CN malicious/untrusted check-only trigger tests, NO installer."""
from dataclasses import FrozenInstanceError, replace
import unittest

from build70_cn_untrusted_check_only_gate import (
    CheckOnlyGate, CheckOnlyRejected, CHECK_ONLY_FRAME, MIN_CHECK_INTERVAL
)


class UntrustedCheckOnlySecurityTests(unittest.TestCase):
    def test_exact_frame_only_notice_no_installer_authority(self):
        gate = CheckOnlyGate()
        found = gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=100)
        self.assertTrue(found.check_notice_accepted)
        self.assertEqual(found.reason, "FIXED_READ_ONLY_VERSION_CHECK_NOTICE_ONLY")
        for key, value in vars(found).items():
            if key in ("check_notice_accepted", "reason", "source_caller_untrusted"):
                continue
            self.assertIs(value, False, key)
        with self.assertRaises(FrozenInstanceError):
            found.installation_authorized = True

    def test_wrong_frames_fail_before_rate_limit_or_effect(self):
        gate = CheckOnlyGate()
        for bad in (
            b"", b"WRCHK1\n", b"WRCHK2", b"WRCHK2\n\n",
            b"WRCHK2\nurl=https://example.com/release.ipa",
            b"WRCHK2\n../data", b"WRCHK2\nI-CONFIRM-INSTALL",
            b"WRINST1\n", b"WRCHK2\x00", b"WRCHK2\n" + b"A" * 1024,
            CHECK_ONLY_FRAME.decode(), bytearray(CHECK_ONLY_FRAME),
            None, True, 7
        ):
            with self.subTest(packet=repr(bad)[:80]):
                with self.assertRaises(CheckOnlyRejected):
                    gate.offer(bad, monotonic_seconds=1)
        self.assertTrue(gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=1)
                        .check_notice_accepted)

    def test_rate_limit_duplicate_untrusted_clients(self):
        gate = CheckOnlyGate()
        first = gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=100)
        self.assertTrue(first.check_notice_accepted)
        for t in (100, 100.01, 105, 159.9):
            finding = gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=t)
            self.assertFalse(finding.check_notice_accepted)
            self.assertFalse(finding.installation_authorized)
        self.assertTrue(gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=160)
                        .check_notice_accepted)
        self.assertFalse(gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=10)
                         .check_notice_accepted)

    def test_timestamp_malformed_cannot_bypass_rate_limit(self):
        gate = CheckOnlyGate()
        for t in (float("nan"), float("inf"), float("-inf"), -1,
                  True, "0", b"0", None, []):
            with self.subTest(time=repr(t)), self.assertRaises(CheckOnlyRejected):
                gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=t)
        self.assertTrue(gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=0)
                        .check_notice_accepted)

    def test_no_client_identity_required_or_assumed(self):
        gate = CheckOnlyGate()
        with self.assertRaises(TypeError):
            gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=0,
                       pid=42, bundle_id="com.example.MangaReader12")
        receipt = gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=0)
        self.assertTrue(receipt.source_caller_untrusted)
        self.assertFalse(receipt.publisher_identity_verified)
        self.assertFalse(receipt.installer_file_verified)

    def test_no_mutable_receipt_can_grant_authorization(self):
        gate = CheckOnlyGate()
        original = gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=0)
        tampered = replace(original, installation_authorized=True)
        self.assertTrue(tampered.installation_authorized)
        self.assertFalse(original.installation_authorized)
        self.assertFalse(gate.offer(CHECK_ONLY_FRAME, monotonic_seconds=1)
                         .installation_authorized)

    def test_source_has_no_privileged_process_or_ipc_actions(self):
        from pathlib import Path
        source = Path(__file__).with_name("build70_cn_untrusted_check_only_gate.py").read_text()
        self.assertEqual(CHECK_ONLY_FRAME, b"WRCHK2\n")
        self.assertGreaterEqual(MIN_CHECK_INTERVAL, 60.0)
        for forbidden in (
            "subprocess", "os.system", "posix_spawn", "appinst(",
            "WRINST1", "I-CONFIRM-INSTALL", "socket.", "urllib",
            "requests.", "chmod(", "open(", "fork(", "kill(",
            "PUBLISHER_KEY=", "VALID_INSTALL", "install_authorized = True"
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
