#!/usr/bin/env python3
"""Offline report matrix for descriptor handoff; never grants authority."""
from dataclasses import replace
import unittest

from build66_fd_handoff_findings import (
    HandoffFindingsRejected, classify_handoff_pair
)
from build66_independent_peer_report import (
    parse_independent_peer_transcript
)


def report(status):
    return parse_independent_peer_transcript(
        ("READY NONROOT SINGLE_CONNECTION AUTHORIZATION=DENIED\n"
         + f"RESULT {status} AUTHORIZATION=DENIED\n"
         + "FINAL_INSTALL_AUTHORIZATION=DENIED\n").encode("ascii")
    )


MATCH = report("MATCH_ONLY_NO_AUTH")
MISMATCH = report("MISMATCH_REJECTED")
UNAVAILABLE = report("TOKEN_UNAVAILABLE")
DENIED = report("CDHASH_UNAVAILABLE")


class DescriptorPassingFindingsTests(unittest.TestCase):
    def safe(self, a, b, expected):
        result = classify_handoff_pair(a, b)
        self.assertEqual(result.category, expected)
        self.assertFalse(result.origin_connector_is_current_message_writer)
        self.assertFalse(result.current_writer_authenticated)
        self.assertFalse(result.origin_code_authenticates_publisher)
        self.assertFalse(result.iOS12_runtime_verified)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.installation_performed)

    def test_origin_observed_sender_not_observed(self):
        self.safe(MATCH, MISMATCH, "ORIGIN_STICKY_AFTER_FD_TRANSFER")

    def test_sender_observed_origin_not_observed(self):
        self.safe(MISMATCH, MATCH, "SENDER_CODE_OBSERVED_AFTER_FD_TRANSFER")

    def test_both_match_is_ambiguous(self):
        self.safe(MATCH, MATCH, "AMBIGUOUS_BOTH_REFERENCES_MATCH")

    def test_neither_matches_is_inconclusive(self):
        self.safe(MISMATCH, MISMATCH, "NEITHER_REFERENCE_MATCHES")

    def test_origin_token_missing(self):
        self.safe(UNAVAILABLE, MISMATCH, "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_sender_token_missing(self):
        self.safe(MISMATCH, UNAVAILABLE, "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_both_token_missing(self):
        self.safe(UNAVAILABLE, UNAVAILABLE, "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_origin_cdhash_denied(self):
        self.safe(DENIED, MATCH, "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_sender_cdhash_denied(self):
        self.safe(MATCH, DENIED, "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_csops_missing(self):
        self.safe(report("CSOPS_MISSING"), MATCH, "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_cross_pid_unsafely_accepted(self):
        self.safe(report("CROSS_PID_UNSAFE"), MISMATCH,
                  "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_mutated_token_unsafely_accepted(self):
        self.safe(MATCH, report("TOKEN_MUTATION_UNSAFE"),
                  "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_transport_failure(self):
        self.safe(report("TRANSPORT_FAILED"), MISMATCH,
                  "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_bad_client_protocol(self):
        self.safe(report("PROTOCOL_REJECTED"), MISMATCH,
                  "INCONCLUSIVE_KERNEL_CAPABILITY")

    def test_refuse_nontranscript_string(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair("MATCH_ONLY_NO_AUTH", MISMATCH)

    def test_refuse_raw_json(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair(b"{}", MISMATCH)

    def test_refuse_none(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair(None, MISMATCH)

    def test_refuse_reinterpreted_report(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair(
                replace(MATCH, from_untrusted_text_only=False), MISMATCH
            )

    def test_refuse_install_authority_in_origin(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair(
                replace(MATCH, installation_authorized=True), MISMATCH
            )

    def test_refuse_install_authority_in_sender(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair(
                MATCH, replace(MISMATCH, installation_authorized=True)
            )

    def test_refuse_forged_publisher_origin(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair(
                replace(MATCH, publisher_authenticated=True), MISMATCH
            )

    def test_refuse_forged_publisher_sender(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair(
                MATCH, replace(MISMATCH, publisher_authenticated=True)
            )

    def test_refuse_forged_webreader_peer_origin(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair(
                replace(MATCH, authenticated_webreader_peer=True), MISMATCH
            )

    def test_refuse_forged_webreader_peer_sender(self):
        with self.assertRaises(HandoffFindingsRejected):
            classify_handoff_pair(
                MATCH, replace(MISMATCH, authenticated_webreader_peer=True)
            )

    def test_boolean_and_integer_untrusted(self):
        for value in (True, False, 1, 0):
            with self.subTest(value=value), self.assertRaises(HandoffFindingsRejected):
                classify_handoff_pair(MATCH, value)


if __name__ == "__main__":
    unittest.main()
