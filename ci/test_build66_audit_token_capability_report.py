#!/usr/bin/env python3
"""Strict Phase-D token report tests, all results remain non-authorizing."""
import unittest
from build66_audit_token_capability_report import (
    AuditTokenReportRejected, parse_audit_token_report
)

HEAD = "WEBREADER_BUILD66_AUDITTOKEN_CAPABILITY: non-root, read-only"
FINAL = "FINAL_INSTALL_AUTHORIZATION=DENIED"
SYMBOLS = (
    "SecCodeCreateWithAuditToken",
    "SecCodeCopyGuestWithAttributes",
    "SecCodeCreateWithPID",
)


def fixture(token="NONZERO", statuses=None):
    statuses = statuses or dict.fromkeys(SYMBOLS, "PRESENT")
    return ("\n".join([
        HEAD, f"PROBE UNIX_PEERTOKEN={token} AUTHORIZATION=DENIED",
        *[f"PROBE SECURITY_{name}={statuses[name]} AUTHORIZATION=DENIED"
          for name in SYMBOLS],
        FINAL
    ]) + "\n").encode("ascii")


class PhaseDAuditReportTests(unittest.TestCase):
    def only_observation(self, raw):
        result = parse_audit_token_report(raw)
        self.assertTrue(result.diagnostic_only)
        self.assertFalse(result.ios12_capability_verified)
        self.assertFalse(result.token_bound_to_verified_code)
        self.assertFalse(result.webreader_peer_authenticated)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.installation_performed)
        return result

    def invalid(self, raw):
        with self.assertRaises(AuditTokenReportRejected):
            parse_audit_token_report(raw)

    def test_nonzero_token_never_authenticates(self):
        self.assertEqual(self.only_observation(fixture()).token_socket_observation,
                         "NONZERO")

    def test_zero_token_never_authenticates(self):
        self.only_observation(fixture(token="ZERO"))

    def test_unavailable_token_never_authenticates(self):
        self.only_observation(fixture(token="UNAVAILABLE"))

    def test_transport_failure_never_authenticates(self):
        self.only_observation(fixture(token="TRANSPORT_FAILED"))

    def test_all_security_functions_missing_never_authenticates(self):
        self.only_observation(fixture(statuses=dict.fromkeys(SYMBOLS, "MISSING")))

    def test_framework_unavailable_never_authenticates(self):
        self.only_observation(fixture(
            statuses=dict.fromkeys(SYMBOLS, "FRAMEWORK_UNAVAILABLE")
        ))

    def test_mixed_symbols_never_authenticate(self):
        report = self.only_observation(fixture(statuses={
            SYMBOLS[0]: "MISSING", SYMBOLS[1]: "PRESENT",
            SYMBOLS[2]: "FRAMEWORK_UNAVAILABLE"
        }))
        self.assertEqual(len(report.security_symbol_observations), 3)

    def test_without_final_newline(self):
        self.only_observation(fixture().rstrip(b"\n"))

    def test_wrong_authorization_on_socket(self):
        self.invalid(fixture().replace(
            b"UNIX_PEERTOKEN=NONZERO AUTHORIZATION=DENIED",
            b"UNIX_PEERTOKEN=NONZERO AUTHORIZATION=ALLOWED"
        ))

    def test_wrong_authorization_on_symbol(self):
        self.invalid(fixture().replace(
            b"SECURITY_SecCodeCreateWithAuditToken=PRESENT AUTHORIZATION=DENIED",
            b"SECURITY_SecCodeCreateWithAuditToken=PRESENT AUTHORIZATION=ALLOWED"
        ))

    def test_authorized_final_marker(self):
        self.invalid(fixture().replace(
            b"FINAL_INSTALL_AUTHORIZATION=DENIED",
            b"FINAL_INSTALL_AUTHORIZATION=ALLOWED"
        ))

    def test_injected_install_command(self):
        self.invalid(fixture().replace(
            b"UNIX_PEERTOKEN=NONZERO",
            b"UNIX_PEERTOKEN=NONZERO INSTALL=YES"
        ))

    def test_untrusted_extra_line(self):
        self.invalid(fixture() + b"INSTALL NOW\n")

    def test_missing_symbol_line(self):
        data = fixture().decode("ascii").splitlines()
        self.invalid(("\n".join(data[:4] + data[5:]) + "\n").encode())

    def test_duplicate_symbol_line(self):
        data = fixture().decode("ascii").splitlines()
        data[4] = data[3]
        self.invalid(("\n".join(data) + "\n").encode())

    def test_wrong_header(self):
        self.invalid(fixture().replace(b"non-root", b"root"))

    def test_pid_in_output(self):
        self.invalid(fixture().replace(
            b"PROBE UNIX_PEERTOKEN=NONZERO",
            b"PROBE UNIX_PEERTOKEN=NONZERO PID=999"
        ))

    def test_token_bytes_in_output(self):
        self.invalid(fixture().replace(
            b"PROBE UNIX_PEERTOKEN=NONZERO",
            b"PROBE UNIX_PEERTOKEN=NONZERO TOKEN=abcd"
        ))

    def test_invalid_unknown_status(self):
        self.invalid(fixture(token="MATCH"))

    def test_unknown_symbol(self):
        self.invalid(fixture().replace(
            b"SecCodeCreateWithPID", b"SecCodeArbitraryInstall"
        ))

    def test_noncanonical_crlf(self):
        self.invalid(fixture().replace(b"\n", b"\r\n"))

    def test_double_trailing_newline(self):
        self.invalid(fixture() + b"\n")

    def test_invalid_utf8(self):
        self.invalid(fixture() + b"\xff")

    def test_empty(self):
        self.invalid(b"")

    def test_huge(self):
        self.invalid(b"x" * 1537)

    def test_nonbytes(self):
        self.invalid("text instead of bytes")


if __name__ == "__main__":
    unittest.main()
