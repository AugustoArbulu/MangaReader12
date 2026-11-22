#!/usr/bin/env python3
"""Build66 Phase G strict peer transcript negatives; completely offline."""
import unittest
from build66_independent_peer_report import (
    IndependentPeerTranscriptRejected, parse_independent_peer_transcript
)

HEAD = "READY NONROOT SINGLE_CONNECTION AUTHORIZATION=DENIED"
TAIL = "FINAL_INSTALL_AUTHORIZATION=DENIED"


def make(status="MATCH_ONLY_NO_AUTH"):
    return ("\n".join([
        HEAD, f"RESULT {status} AUTHORIZATION=DENIED", TAIL
    ]) + "\n").encode("ascii")


class IndependentPeerReportTests(unittest.TestCase):
    def observed_only(self, raw, expect_match):
        report = parse_independent_peer_transcript(raw)
        self.assertEqual(report.exact_codehash_match_observed, expect_match)
        self.assertTrue(report.from_untrusted_text_only)
        self.assertFalse(report.kernel_binding_cryptographically_trusted_on_ios12)
        self.assertFalse(report.authenticated_webreader_peer)
        self.assertFalse(report.publisher_authenticated)
        self.assertFalse(report.installation_authorized)
        self.assertFalse(report.installation_performed)
        return report

    def rejected(self, raw):
        with self.assertRaises(IndependentPeerTranscriptRejected):
            parse_independent_peer_transcript(raw)

    def test_good_codehash_still_no_install(self):
        self.observed_only(make(), True)

    def test_mismatched_peer_denied(self):
        self.observed_only(make("MISMATCH_REJECTED"), False)

    def test_kernel_option_missing_denied(self):
        self.observed_only(make("TOKEN_UNAVAILABLE"), False)

    def test_csops_missing_denied(self):
        self.observed_only(make("CSOPS_MISSING"), False)

    def test_cdhash_missing_denied(self):
        self.observed_only(make("CDHASH_UNAVAILABLE"), False)

    def test_token_mutation_accepted_unsafe_denied(self):
        self.observed_only(make("TOKEN_MUTATION_UNSAFE"), False)

    def test_wrong_pid_accepted_unsafe_denied(self):
        self.observed_only(make("CROSS_PID_UNSAFE"), False)

    def test_bad_client_protocol_denied(self):
        self.observed_only(make("PROTOCOL_REJECTED"), False)

    def test_transport_failure_denied(self):
        self.observed_only(make("TRANSPORT_FAILED"), False)

    def test_missing_trailing_newline_is_allowed(self):
        self.observed_only(make().rstrip(b"\n"), True)

    def test_empty_rejected(self):
        self.rejected(b"")

    def test_nonbytes_rejected(self):
        self.rejected(None)

    def test_invalid_utf8_rejected(self):
        self.rejected(make() + b"\xff")

    def test_oversized_rejected(self):
        self.rejected(b"x" * 513)

    def test_noncanonical_crlf_rejected(self):
        self.rejected(make().replace(b"\n", b"\r\n"))

    def test_double_trailing_newline_rejected(self):
        self.rejected(make() + b"\n")

    def test_missing_ready_rejected(self):
        self.rejected(make().replace(b"READY", b"STARTED"))

    def test_missing_footer_rejected(self):
        self.rejected(make().replace(TAIL.encode(), b""))

    def test_forged_allowed_footer_rejected(self):
        self.rejected(make().replace(b"FINAL_INSTALL_AUTHORIZATION=DENIED",
                                     b"FINAL_INSTALL_AUTHORIZATION=ALLOWED"))

    def test_forged_allowed_result_rejected(self):
        self.rejected(make().replace(b"AUTHORIZATION=DENIED",
                                     b"AUTHORIZATION=ALLOWED", 1))

    def test_injected_install_line_rejected(self):
        self.rejected(make() + b"START_INSTALL\n")

    def test_arbitrary_path_in_status_rejected(self):
        self.rejected(make().replace(b"MATCH_ONLY_NO_AUTH",
                                     b"MATCH_ONLY_NO_AUTH IPA=/tmp/evil.ipa"))

    def test_pid_disclosure_in_status_rejected(self):
        self.rejected(make().replace(b"MATCH_ONLY_NO_AUTH",
                                     b"MATCH_ONLY_NO_AUTH PID=1234"))

    def test_token_disclosure_in_status_rejected(self):
        self.rejected(make().replace(b"MATCH_ONLY_NO_AUTH",
                                     b"MATCH_ONLY_NO_AUTH TOKEN=abcdef"))

    def test_unknown_status_rejected(self):
        self.rejected(make("AUTHENTICATED"))

    def test_noncanonical_status_rejected(self):
        self.rejected(make("match_only_no_auth"))

    def test_result_duplicated_rejected(self):
        msg = make().decode().splitlines()
        self.rejected(("\n".join([msg[0], msg[1], msg[1], msg[2]]) + "\n").encode())

    def test_trailing_space_rejected(self):
        self.rejected(make().replace(b"AUTHORIZATION=DENIED\n",
                                     b"AUTHORIZATION=DENIED \n"))

    def test_false_success_word_not_allowed(self):
        self.rejected(make("INSTALLATION_AUTHORIZED"))

    def test_binary_output_rejected(self):
        self.rejected(make()[:-1] + b"\x00\n")


if __name__ == "__main__":
    unittest.main()
