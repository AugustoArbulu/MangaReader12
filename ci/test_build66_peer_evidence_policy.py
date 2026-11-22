#!/usr/bin/env python3
"""Build66 peer evidence regressions; no sockets, privileged helper or device."""
import json
import unittest
from build66_peer_evidence_policy import (
    APP_IDENTIFIER, BUNDLE, evaluate_untrusted_peer_evidence
)


def encoded(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


class PeerEvidenceTests(unittest.TestCase):
    def observation(self):
        return dict(
            transport="unix", pid=123, uid=501, bundleId=BUNDLE,
            appIdentifier=APP_IDENTIFIER, hmacPairingPassed=False,
            codeSignatureValid=False, auditTokenClaimed=False
        )

    def assert_denied(self, raw, reason=None):
        actual = evaluate_untrusted_peer_evidence(
            raw if isinstance(raw, bytes) or raw is None else encoded(raw)
        )
        self.assertFalse(actual.requester_authenticated)
        self.assertFalse(actual.os_bound_audit_identity_verified)
        self.assertFalse(actual.running_code_identity_verified)
        self.assertFalse(actual.installation_authorized)
        self.assertFalse(actual.installation_performed)
        if reason is not None:
            self.assertEqual(actual.reason, reason)
        return actual

    def test_matching_pid_uid_and_bundle_remain_untrusted(self):
        self.assert_denied(self.observation(), "PID_UID_AND_SOCKET_CANNOT_AUTHORIZE")

    def test_tcp_loopback_has_no_privileged_identity(self):
        self.assert_denied(dict(self.observation(), transport="tcp-loopback"))

    def test_xpc_label_claim_is_not_kernel_attestation(self):
        self.assert_denied(dict(self.observation(), transport="xpc"))

    def test_hmac_pairing_is_not_code_identity(self):
        self.assert_denied(
            dict(self.observation(), hmacPairingPassed=True),
            "PAIRING_PROOF_IS_NOT_PEER_IDENTITY"
        )

    def test_signed_app_claim_is_not_peer_identity(self):
        self.assert_denied(
            dict(self.observation(), codeSignatureValid=True),
            "ADHOC_CODE_SEAL_DOES_NOT_AUTHENTICATE_PEER"
        )

    def test_self_reported_audit_token_cannot_prove_binding(self):
        self.assert_denied(
            dict(self.observation(), auditTokenClaimed=True),
            "SELF_ASSERTED_AUDIT_TOKEN_IS_NOT_EVIDENCE"
        )

    def test_every_claim_true_still_rejected(self):
        self.assert_denied(dict(
            self.observation(), auditTokenClaimed=True,
            hmacPairingPassed=True, codeSignatureValid=True
        ), "SELF_ASSERTED_AUDIT_TOKEN_IS_NOT_EVIDENCE")

    def test_unknown_transport(self):
        self.assert_denied(dict(self.observation(), transport="unknown"),
                           "NO_OBSERVABLE_TRANSPORT")

    def test_pid_unavailable(self):
        self.assert_denied(dict(self.observation(), pid=0), "PID_UNAVAILABLE")

    def test_wrong_bundle_claim(self):
        self.assert_denied(dict(self.observation(), bundleId="com.attacker.app"),
                           "CLAIMED_APPLICATION_MISMATCH")

    def test_wrong_app_identifier_claim(self):
        self.assert_denied(dict(self.observation(), appIdentifier="ATTACKER"),
                           "CLAIMED_APPLICATION_MISMATCH")

    def test_extra_install_opcode_field(self):
        self.assert_denied(dict(self.observation(), operation="INSTALL"),
                           "UNTRUSTED_REPORT_FIELDS")

    def test_extra_ipa_path(self):
        self.assert_denied(dict(self.observation(), ipaPath="/tmp/file.ipa"),
                           "UNTRUSTED_REPORT_FIELDS")

    def test_duplicate_json_key(self):
        raw = encoded(self.observation())
        self.assert_denied(b'{"pid":123,' + raw[1:], "UNTRUSTED_REPORT_MALFORMED")

    def test_escaped_duplicate_json_key(self):
        raw = encoded(self.observation())
        self.assert_denied(b'{"\\u0070id":123,' + raw[1:],
                           "UNTRUSTED_REPORT_MALFORMED")

    def test_oversized_report(self):
        self.assert_denied(b"a" * 1025, "UNTRUSTED_REPORT_SIZE")

    def test_empty_report(self):
        self.assert_denied(b"", "UNTRUSTED_REPORT_SIZE")

    def test_non_bytes_report(self):
        self.assert_denied(None, "UNTRUSTED_REPORT_SIZE")

    def test_invalid_utf8(self):
        self.assert_denied(b"\xff", "UNTRUSTED_REPORT_MALFORMED")

    def test_broken_json(self):
        self.assert_denied(b'{"pid":', "UNTRUSTED_REPORT_MALFORMED")

    def test_json_array_rejected(self):
        self.assert_denied(b"[]", "UNTRUSTED_REPORT_FIELDS")

    def test_missing_field(self):
        item = self.observation()
        del item["uid"]
        self.assert_denied(item, "UNTRUSTED_REPORT_FIELDS")

    def test_bool_pid_rejected(self):
        self.assert_denied(dict(self.observation(), pid=True),
                           "UNTRUSTED_REPORT_TYPES")

    def test_bool_uid_rejected(self):
        self.assert_denied(dict(self.observation(), uid=False),
                           "UNTRUSTED_REPORT_TYPES")

    def test_list_transport_rejected_safely(self):
        self.assert_denied(dict(self.observation(), transport=["unix"]),
                           "UNTRUSTED_REPORT_TYPES")

    def test_list_bundle_rejected_safely(self):
        self.assert_denied(dict(self.observation(), bundleId=[BUNDLE]),
                           "UNTRUSTED_REPORT_TYPES")

    def test_string_hmac_rejected(self):
        self.assert_denied(dict(self.observation(), hmacPairingPassed="true"),
                           "UNTRUSTED_REPORT_TYPES")

    def test_nonfinite_json_rejected(self):
        raw = encoded(self.observation()).replace(b'"uid":501', b'"uid":NaN')
        self.assert_denied(raw, "UNTRUSTED_REPORT_MALFORMED")


if __name__ == "__main__":
    unittest.main()
