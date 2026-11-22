#!/usr/bin/env python3
"""Pure offline one-shot diagnostics; never imports or invokes an installer."""
import json
import threading
import unittest

from build66_one_shot_diagnostic import (
    DiagnosticResult, OneShotDiagnostic,
    INSTALLED_APPLICATION_IDENTIFIER, APP_BUNDLE_ID
)


def encode(payload):
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


class OneShotDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.moment = [10.0]
        self.s = OneShotDiagnostic(
            target_build=66, installed_build=65,
            manifest_sha256="a" * 64, ipa_sha256="b" * 64,
            ttl_seconds=30, clock=lambda: self.moment[0],
            entropy=lambda n: bytes.fromhex("01" * 16)
        )

    def valid(self):
        return {
            "protocolVersion": 1,
            "operation": "CHECK_ONLY",
            "challenge": self.s.challenge(),
            "manifestSHA256": "a" * 64,
            "ipaSHA256": "b" * 64,
            "targetBuild": 66,
            "bundleId": APP_BUNDLE_ID,
            "applicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER
        }

    def rejected(self, payload):
        result = self.s.check_once(payload if isinstance(payload, bytes) else encode(payload))
        self.assertFalse(result.request_consistent)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.installation_performed)
        self.assertFalse(result.peer_identity_authenticated)
        self.assertFalse(result.user_install_consent_verified)
        return result

    def test_matching_request_does_not_authorize_install(self):
        result = self.s.check_once(encode(self.valid()))
        self.assertTrue(result.request_consistent)
        self.assertEqual(result.reason, "DIAGNOSTIC_MATCH_NOT_AUTHORIZED")
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.peer_identity_authenticated)
        self.assertFalse(result.user_install_consent_verified)

    def test_success_consumes_challenge(self):
        raw = encode(self.valid())
        self.assertTrue(self.s.check_once(raw).request_consistent)
        self.assertEqual(self.rejected(raw).reason, "REPLAY_REJECTED")

    def test_mismatched_challenge_consumes_challenge(self):
        invalid = self.valid()
        invalid["challenge"] = "f" * 32
        self.assertEqual(self.rejected(invalid).reason, "CHALLENGE_REJECTED")
        self.assertEqual(self.rejected(self.valid()).reason, "REPLAY_REJECTED")

    def test_expiration(self):
        self.moment[0] = 41
        self.assertEqual(self.rejected(self.valid()).reason, "EXPIRED_REJECTED")

    def test_expiration_boundary(self):
        self.moment[0] = 40
        self.assertEqual(self.rejected(self.valid()).reason, "EXPIRED_REJECTED")

    def test_just_before_expiry(self):
        self.moment[0] = 39.999
        self.assertTrue(self.s.check_once(encode(self.valid())).request_consistent)

    def test_cannot_reuse_expired_session(self):
        self.moment[0] = 50
        self.rejected(self.valid())
        self.moment[0] = 12
        self.assertEqual(self.rejected(self.valid()).reason, "REPLAY_REJECTED")

    def test_wrong_manifest_digest(self):
        invalid = self.valid()
        invalid["manifestSHA256"] = "c" * 64
        self.assertEqual(self.rejected(invalid).reason, "REFERENCE_REJECTED")

    def test_wrong_ipa_digest(self):
        invalid = self.valid()
        invalid["ipaSHA256"] = "c" * 64
        self.assertEqual(self.rejected(invalid).reason, "REFERENCE_REJECTED")

    def test_wrong_build(self):
        invalid = self.valid()
        invalid["targetBuild"] = 67
        self.assertEqual(self.rejected(invalid).reason, "REFERENCE_REJECTED")

    def test_wrong_bundle(self):
        invalid = self.valid()
        invalid["bundleId"] = "com.attacker.app"
        self.assertEqual(self.rejected(invalid).reason, "REFERENCE_REJECTED")

    def test_wrong_entitlement(self):
        invalid = self.valid()
        invalid["applicationIdentifier"] = "ATTACKER"
        self.assertEqual(self.rejected(invalid).reason, "REFERENCE_REJECTED")

    def test_operation_install_rejected(self):
        invalid = self.valid()
        invalid["operation"] = "WRINST1"
        self.assertEqual(self.rejected(invalid).reason, "OPERATION_REJECTED")

    def test_any_install_path_field_rejected(self):
        invalid = self.valid()
        invalid["ipaPath"] = "/var/mobile/Documents/payload.ipa"
        self.assertEqual(self.rejected(invalid).reason, "FIELD_SET_REJECTED")

    def test_any_install_flag_field_rejected(self):
        invalid = self.valid()
        invalid["install"] = True
        self.assertEqual(self.rejected(invalid).reason, "FIELD_SET_REJECTED")

    def test_missing_field_rejected(self):
        invalid = self.valid()
        del invalid["ipaSHA256"]
        self.assertEqual(self.rejected(invalid).reason, "FIELD_SET_REJECTED")

    def test_duplicate_json_key_rejected(self):
        raw = encode(self.valid())
        assert raw.startswith(b"{")
        raw = b'{"bundleId":"bad",' + raw[1:]
        self.assertEqual(self.rejected(raw).reason, "MALFORMED_REJECTED")

    def test_duplicate_unicode_escaped_key_rejected(self):
        raw = encode(self.valid())
        raw = b'{"\\u0062undleId":"bad",' + raw[1:]
        self.assertEqual(self.rejected(raw).reason, "MALFORMED_REJECTED")

    def test_invalid_json_rejected(self):
        self.assertEqual(self.rejected(b'{"operation":').reason, "MALFORMED_REJECTED")

    def test_invalid_utf8_rejected(self):
        self.assertEqual(self.rejected(b"\xff").reason, "MALFORMED_REJECTED")

    def test_nonfinite_json_rejected(self):
        invalid = encode(self.valid()).replace(b'"targetBuild":66', b'"targetBuild":NaN')
        self.assertEqual(self.rejected(invalid).reason, "MALFORMED_REJECTED")

    def test_bool_build_rejected(self):
        invalid = self.valid()
        invalid["targetBuild"] = True
        self.assertEqual(self.rejected(invalid).reason, "REFERENCE_REJECTED")

    def test_bool_protocol_rejected(self):
        invalid = self.valid()
        invalid["protocolVersion"] = True
        self.assertEqual(self.rejected(invalid).reason, "OPERATION_REJECTED")

    def test_non_bytes_rejected(self):
        self.assertEqual(self.rejected("bad").reason, "FIELD_SET_REJECTED")

    def test_explicit_non_bytes_rejected(self):
        self.assertEqual(self.s.check_once("not bytes").reason, "SIZE_OR_TYPE_REJECTED")

    def test_oversized_message_rejected(self):
        self.assertEqual(self.rejected(b"x" * 2049).reason, "SIZE_OR_TYPE_REJECTED")

    def test_empty_message_rejected(self):
        self.assertEqual(self.rejected(b"").reason, "SIZE_OR_TYPE_REJECTED")

    def test_array_rejected(self):
        self.assertEqual(self.rejected(b"[]").reason, "FIELD_SET_REJECTED")

    def test_downgrade_reference_cannot_issue_session(self):
        with self.assertRaises(ValueError):
            OneShotDiagnostic(
                target_build=65, installed_build=65,
                manifest_sha256="a" * 64, ipa_sha256="b" * 64)

    def test_invalid_entropy_denies_session_creation(self):
        with self.assertRaises(ValueError):
            OneShotDiagnostic(
                target_build=66, installed_build=65,
                manifest_sha256="a" * 64, ipa_sha256="b" * 64,
                entropy=lambda _: b"bad")

    def test_invalid_reference_digest_denies_session_creation(self):
        with self.assertRaises(ValueError):
            OneShotDiagnostic(
                target_build=66, installed_build=65,
                manifest_sha256="invalid", ipa_sha256="b" * 64)

    def test_invalid_ttl_denies_session_creation(self):
        for bad in (0, 61, True, 30.1):
            with self.subTest(ttl=bad), self.assertRaises(ValueError):
                OneShotDiagnostic(
                    target_build=66, installed_build=65,
                    manifest_sha256="a" * 64, ipa_sha256="b" * 64,
                    ttl_seconds=bad)

    def test_concurrent_requests_only_one_can_match(self):
        barrier = threading.Barrier(3)
        values = []
        lock = threading.Lock()
        raw = encode(self.valid())

        def worker():
            barrier.wait()
            result = self.s.check_once(raw)
            with lock:
                values.append(result)

        one = threading.Thread(target=worker)
        two = threading.Thread(target=worker)
        one.start()
        two.start()
        barrier.wait()
        one.join(timeout=5)
        two.join(timeout=5)
        self.assertEqual(len(values), 2)
        self.assertEqual(sum(1 for v in values if v.request_consistent), 1)
        self.assertEqual(sum(1 for v in values if v.reason == "REPLAY_REJECTED"), 1)
        self.assertTrue(all(not v.installation_authorized for v in values))


if __name__ == "__main__":
    unittest.main()
