#!/usr/bin/env python3
"""Physical Chimera report security matrix (offline, no device I/O)."""
import unittest
from dataclasses import replace

from build66_ios12_physical_capability_policy import (
    IOS12_CHIMERA_MOBILE_OBSERVATION_2026_11_07,
    PhysicalCapabilityRejected, assess_physical_diagnostic,
)

ORIGINAL = IOS12_CHIMERA_MOBILE_OBSERVATION_2026_11_07


def payload(socket_status="UNAVAILABLE", csops_status="NOT_TESTED",
            security_status="MISSING"):
    return (f"""WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY: non-root, read-only
PROBE UNIX_PEERTOKEN={socket_status} AUTHORIZATION=DENIED
PROBE CSOPS_TOKEN_BINDING={csops_status} AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithAuditToken={security_status} AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCopyGuestWithAttributes={security_status} AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithPID={security_status} AUTHORIZATION=DENIED
FINAL_INSTALL_AUTHORIZATION=DENIED
""").encode("ascii")


class PhysicalCapabilityTests(unittest.TestCase):
    def safe(self, raw):
        result = assess_physical_diagnostic(raw, reported_user="mobile")
        self.assertFalse(result.ios12_runtime_peer_identity_available)
        self.assertFalse(result.per_message_sender_authenticated)
        self.assertFalse(result.release_publisher_authenticated)
        self.assertFalse(result.production_key_provisioned)
        self.assertFalse(result.safe_automatic_install_path_confirmed)
        self.assertFalse(result.device_report_attested)
        self.assertTrue(result.client_may_request_check_only)
        self.assertTrue(result.interactive_manual_install_remains_fallback)
        self.assertFalse(result.root_escalation_permitted_for_diagnostic)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.installation_performed)
        return result

    def denied(self, data, user="mobile"):
        with self.assertRaises(PhysicalCapabilityRejected):
            assess_physical_diagnostic(data, reported_user=user)

    def test_exact_real_ipad_transcript(self):
        result = self.safe(ORIGINAL)
        self.assertEqual(result.reason, "PEERTOKEN_UNAVAILABLE_CSOPS_NOT_TESTED")
        self.assertEqual(result.reported_socket_status, "UNAVAILABLE")
        self.assertEqual(result.reported_csops_status, "NOT_TESTED")
        self.assertEqual(len(result.reported_security_symbols), 3)
        self.assertTrue(all(status == "MISSING"
                            for _, status in result.reported_security_symbols))

    def test_physical_report_does_not_explain_errno(self):
        result = self.safe(ORIGINAL)
        self.assertNotIn("EPERM", result.reason)
        self.assertNotIn("ENOPROTOOPT", result.reason)

    def test_not_attested_even_with_kernel_status(self):
        result = self.safe(payload("NONZERO", "MUTATION_REJECTED", "PRESENT"))
        self.assertEqual(result.reason, "LAB_CHILD_BINDING_OBSERVED_NOT_APP_AUTHENTICATED")

    def test_negative_mutated_token_claim(self):
        result = self.safe(payload("NONZERO", "MUTATION_ACCEPTED_UNSAFE"))
        self.assertEqual(result.reason, "KERNEL_BINDING_NEGATIVE_TEST_FAILED")

    def test_negative_wrong_pid_claim(self):
        result = self.safe(payload("NONZERO", "CROSS_PID_ACCEPTED_UNSAFE"))
        self.assertEqual(result.reason, "KERNEL_BINDING_NEGATIVE_TEST_FAILED")

    def test_bad_transport_status(self):
        result = self.safe(payload("TRANSPORT_FAILED"))
        self.assertEqual(result.reason, "CONTROLLED_TRANSPORT_FAILED")

    def test_zero_kernel_token(self):
        result = self.safe(payload("ZERO"))
        self.assertEqual(result.reason, "ZERO_KERNEL_TOKEN_NOT_USABLE")

    def test_unsupported_call(self):
        result = self.safe(payload("NONZERO", "CALL_DENIED"))
        self.assertEqual(result.reason, "KERNEL_CODE_IDENTITY_NOT_CONFIRMED")

    def test_absent_symbol(self):
        self.safe(payload("NONZERO", "SYMBOL_MISSING"))

    def test_unavailable_token_cannot_be_verified(self):
        self.denied(payload("UNAVAILABLE", "MUTATION_REJECTED"))

    def test_zero_token_cannot_be_verified(self):
        self.denied(payload("ZERO", "MUTATION_REJECTED"))

    def test_nonzero_token_requires_a_csops_attempt(self):
        self.denied(payload("NONZERO", "NOT_TESTED"))

    def test_root_is_not_mobile(self):
        self.denied(ORIGINAL, user="root")

    def test_wrong_user(self):
        self.denied(ORIGINAL, user="daemon")

    def test_missing_user(self):
        self.denied(ORIGINAL, user="")

    def test_invalid_status(self):
        self.denied(payload("SUCCESS", "NOT_TESTED"))

    def test_unknown_symbol(self):
        self.denied(ORIGINAL.replace(
            b"Security_SecCodeCreateWithPID", b"Security_SecCodeExecute"))

    def test_duplicate_symbol(self):
        self.denied(ORIGINAL.replace(
            b"Security_SecCodeCreateWithPID",
            b"Security_SecCodeCreateWithAuditToken"))

    def test_claimed_install_authorization(self):
        self.denied(ORIGINAL.replace(b"AUTHORIZATION=DENIED",
                                     b"AUTHORIZATION=ALLOWED", 1))

    def test_forged_final_authorization(self):
        self.denied(ORIGINAL.replace(b"FINAL_INSTALL_AUTHORIZATION=DENIED",
                                     b"FINAL_INSTALL_AUTHORIZATION=ALLOWED"))

    def test_token_bytes_disclosed(self):
        self.denied(ORIGINAL.replace(b"UNIX_PEERTOKEN=UNAVAILABLE",
                                     b"UNIX_PEERTOKEN=UNAVAILABLE token=deadbeef"))

    def test_pid_disclosed(self):
        self.denied(ORIGINAL.replace(b"CSOPS_TOKEN_BINDING=NOT_TESTED",
                                     b"CSOPS_TOKEN_BINDING=NOT_TESTED pid=32"))

    def test_extra_lines(self):
        self.denied(ORIGINAL + b"INSTALL NOW\n")

    def test_truncated(self):
        self.denied(ORIGINAL[:55])

    def test_empty(self):
        self.denied(b"")

    def test_null(self):
        self.denied(None)

    def test_string_not_binary(self):
        self.denied(ORIGINAL.decode("utf8"))

    def test_invalid_utf8(self):
        self.denied(ORIGINAL + b"\xff")

    def test_huge_blob(self):
        self.denied(b"x" * 2049)

    def test_noncanonical_crlf(self):
        self.denied(ORIGINAL.replace(b"\n", b"\r\n"))

    def test_duplicate_footer(self):
        self.denied(ORIGINAL + b"FINAL_INSTALL_AUTHORIZATION=DENIED\n")

    def test_immutable_receipt(self):
        r = self.safe(ORIGINAL)
        with self.assertRaises((AttributeError, TypeError)):
            r.installation_authorized = True

    def test_forged_dataclass_is_not_a_trust_source(self):
        # This test explicitly documents why report objects must not be
        # accepted as installer authorization tokens.
        forged = replace(self.safe(ORIGINAL), installation_authorized=True)
        self.assertTrue(forged.installation_authorized)
        # Even a dataclass can be forged; NEVER pass this to an installer.


if __name__ == "__main__":
    unittest.main()
