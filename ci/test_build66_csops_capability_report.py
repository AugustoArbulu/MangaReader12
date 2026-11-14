#!/usr/bin/env python3
"""Phase E negative tests. A successful csops report is still not authority."""
import unittest
from build66_csops_capability_report import parse_csops_report, CSOpsReportRejected

HEAD = "WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY: non-root, read-only"
TAIL = "FINAL_INSTALL_AUTHORIZATION=DENIED"
SYMS = ("SecCodeCreateWithAuditToken", "SecCodeCopyGuestWithAttributes",
        "SecCodeCreateWithPID")


def fake(socket="NONZERO", binding="MUTATION_REJECTED", statuses=None):
    statuses = statuses or ["PRESENT"] * 3
    return ("\n".join([
        HEAD,
        f"PROBE UNIX_PEERTOKEN={socket} AUTHORIZATION=DENIED",
        f"PROBE CSOPS_TOKEN_BINDING={binding} AUTHORIZATION=DENIED",
        *(f"PROBE SECURITY_{name}={status} AUTHORIZATION=DENIED"
          for name, status in zip(SYMS, statuses)),
        TAIL,
    ]) + "\n").encode()


class PhaseECSOpsTests(unittest.TestCase):
    def allowed_observation(self, data):
        r = parse_csops_report(data)
        self.assertTrue(r.diagnostic_only)
        self.assertFalse(r.ios12_runtime_verified)
        self.assertFalse(r.publisher_authenticated)
        self.assertFalse(r.webreader_peer_authenticated)
        self.assertFalse(r.installation_authorized)
        self.assertFalse(r.installation_performed)
        return r

    def rejected(self, data):
        with self.assertRaises(CSOpsReportRejected):
            parse_csops_report(data)

    def test_mutation_rejected_still_no_authorization(self):
        self.allowed_observation(fake())

    def test_mutation_accepted_unsafe_still_no_authorization(self):
        self.allowed_observation(fake(binding="MUTATION_ACCEPTED_UNSAFE"))

    def test_cross_pid_accepted_unsafe_still_no_authorization(self):
        self.allowed_observation(fake(binding="CROSS_PID_ACCEPTED_UNSAFE"))

    def test_call_denied_still_no_authorization(self):
        self.allowed_observation(fake(binding="CALL_DENIED"))

    def test_missing_csops_symbol_still_no_authorization(self):
        self.allowed_observation(fake(binding="SYMBOL_MISSING"))

    def test_token_fields_unavailable_still_no_authorization(self):
        self.allowed_observation(fake(binding="TOKEN_FIELDS_UNAVAILABLE"))

    def test_token_unavailable_and_csops_not_tested(self):
        self.allowed_observation(fake(socket="UNAVAILABLE", binding="NOT_TESTED"))

    def test_socket_failure_and_csops_not_tested(self):
        self.allowed_observation(fake(socket="TRANSPORT_FAILED", binding="NOT_TESTED"))

    def test_zero_token_and_csops_not_tested(self):
        self.allowed_observation(fake(socket="ZERO", binding="NOT_TESTED"))

    def test_mixed_security_statuses_not_authoritative(self):
        self.allowed_observation(fake(statuses=["MISSING", "PRESENT", "FRAMEWORK_UNAVAILABLE"]))

    def test_unavailable_token_cannot_have_successful_csops(self):
        self.rejected(fake(socket="UNAVAILABLE", binding="MUTATION_REJECTED"))

    def test_zero_token_cannot_have_successful_csops(self):
        self.rejected(fake(socket="ZERO", binding="MUTATION_REJECTED"))

    def test_nonzero_token_requires_csops_status(self):
        self.rejected(fake(binding="NOT_TESTED"))

    def test_empty_rejected(self):
        self.rejected(b"")

    def test_nonbytes_rejected(self):
        self.rejected(None)

    def test_invalid_utf8_rejected(self):
        self.rejected(fake() + b"\xff")

    def test_extra_line_rejected(self):
        self.rejected(fake() + b"INSTALL\n")

    def test_unsigned_footer_rejected(self):
        self.rejected(fake().replace(b"FINAL_INSTALL_AUTHORIZATION=DENIED",
                                     b"FINAL_INSTALL_AUTHORIZATION=ALLOWED"))

    def test_authorized_csops_line_rejected(self):
        self.rejected(fake().replace(b"CSOPS_TOKEN_BINDING=MUTATION_REJECTED AUTHORIZATION=DENIED",
                                     b"CSOPS_TOKEN_BINDING=MUTATION_REJECTED AUTHORIZATION=ALLOWED"))

    def test_token_bytes_leak_rejected(self):
        self.rejected(fake().replace(b"UNIX_PEERTOKEN=NONZERO",
                                     b"UNIX_PEERTOKEN=NONZERO TOKEN=abcdef"))

    def test_pid_leak_rejected(self):
        self.rejected(fake().replace(b"CSOPS_TOKEN_BINDING=MUTATION_REJECTED",
                                     b"CSOPS_TOKEN_BINDING=MUTATION_REJECTED PID=123"))

    def test_missing_symbol_rejected(self):
        rows = fake().decode().splitlines()
        self.rejected(("\n".join(rows[:5] + rows[6:]) + "\n").encode())

    def test_duplicate_symbol_rejected(self):
        rows = fake().decode().splitlines()
        rows[5] = rows[4]
        self.rejected(("\n".join(rows) + "\n").encode())

    def test_unknown_syscall_status_rejected(self):
        self.rejected(fake(binding="ROOT_REQUIRED"))

    def test_missing_header_rejected(self):
        self.rejected(fake().replace(b"WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY",
                                     b"WEBREADER_INSTALLER"))

    def test_crlf_rejected(self):
        self.rejected(fake().replace(b"\n", b"\r\n"))

    def test_double_trailing_newline_rejected(self):
        self.rejected(fake() + b"\n")

    def test_oversized_rejected(self):
        self.rejected(b"x" * 2049)

    def test_no_trailing_newline_allowed(self):
        self.allowed_observation(fake().rstrip(b"\n"))


if __name__ == "__main__":
    unittest.main()
