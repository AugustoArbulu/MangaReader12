#!/usr/bin/env python3
"""Phase I fail-closed parser and classification tests; no trusted input."""
from dataclasses import replace
import unittest

from build66_queued_peer_report import (
    QueuedReportRejected, classify_queued_reports, parse_queued_report,
)

BASE = "READY NONROOT QUEUED_{} AUTHORIZATION=DENIED"
TAIL = "FINAL_INSTALL_AUTHORIZATION=DENIED"


def report(mode="SPLIT", first="MATCH_ONLY_NO_AUTH", second=None):
    if second is None:
        second = "NO_SECOND_SAMPLE" if mode == "BATCH" else "MISMATCH_REJECTED"
    return ("\n".join([
        BASE.format(mode),
        "RESULT STEP1=" + first + " AUTHORIZATION=DENIED",
        "RESULT STEP2=" + second + " AUTHORIZATION=DENIED",
        TAIL,
    ]) + "\n").encode("ascii")


class QueuedReportTests(unittest.TestCase):
    def test_valid_split(self):
        item = parse_queued_report(report())
        self.assertEqual(item.mode, "SPLIT")
        self.assertEqual(item.statuses, ("MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED"))
        self.assertFalse(item.installation_authorized)
        self.assertFalse(item.peer_authenticated)
        self.assertFalse(item.ios12_verified)

    def test_valid_batch(self):
        item = parse_queued_report(report("BATCH"))
        self.assertEqual(item.statuses[1], "NO_SECOND_SAMPLE")
        self.assertFalse(item.installation_performed)

    def test_all_accepted_diagnostic_states(self):
        for status in (
            "MATCH_ONLY_NO_AUTH", "MISMATCH_REJECTED", "TOKEN_UNAVAILABLE",
            "CSOPS_MISSING", "CDHASH_UNAVAILABLE", "TOKEN_MUTATION_UNSAFE",
            "CROSS_PID_UNSAFE", "PROTOCOL_REJECTED", "TRANSPORT_FAILED"
        ):
            with self.subTest(status=status):
                self.assertEqual(
                    parse_queued_report(report(first=status)).statuses[0], status
                )

    def test_wrong_input_types(self):
        for raw in (None, {}, [], "", 0, bytearray(report()), memoryview(report())):
            with self.subTest(raw=type(raw).__name__):
                with self.assertRaises(QueuedReportRejected):
                    parse_queued_report(raw)

    def test_empty_and_oversize(self):
        for raw in (b"", b"X" * 769):
            with self.assertRaises(QueuedReportRejected):
                parse_queued_report(raw)

    def test_unicode_rejected(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report() + b"\xff")

    def test_windows_endings_rejected(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report().replace(b"\n", b"\r\n"))

    def test_duplicate_newline_rejected(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report() + b"\n")

    def test_bad_header(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report().replace(b"NONROOT", b"ROOT"))

    def test_undocumented_mode(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report().replace(b"QUEUED_SPLIT", b"QUEUED_INSTALL"))

    def test_extra_line_and_auth_claim(self):
        for extra in (b"AUTHORIZATION=GRANTED\n", b"PID=123\n", b"CDHASH=faked\n"):
            with self.subTest(extra=extra):
                with self.assertRaises(QueuedReportRejected):
                    parse_queued_report(report() + extra)

    def test_missing_denial_footer(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report().replace(b"FINAL_INSTALL_AUTHORIZATION=DENIED", b"FINAL_INSTALL_AUTHORIZATION=ALLOWED"))

    def test_mutated_authority(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report().replace(b"AUTHORIZATION=DENIED", b"AUTHORIZATION=GRANTED", 1))

    def test_bad_status(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report(first="IDENTITY_APPROVED"))

    def test_wrong_order(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report().replace(b"STEP1", b"STEP2"))

    def test_batch_must_have_one_sample(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report("BATCH", second="MISMATCH_REJECTED"))

    def test_split_must_have_two_samples(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report("SPLIT", second="NO_SECOND_SAMPLE"))

    def test_non_second_not_sampled(self):
        with self.assertRaises(QueuedReportRejected):
            parse_queued_report(report("BATCH", first="NO_SECOND_SAMPLE"))

    def test_full_sequence_a_b_not_authenticated(self):
        a = parse_queued_report(report(first="MATCH_ONLY_NO_AUTH", second="MISMATCH_REJECTED"))
        b = parse_queued_report(report(first="MISMATCH_REJECTED", second="MATCH_ONLY_NO_AUTH"))
        finding = classify_queued_reports(a, b)
        self.assertEqual(finding.observations, ("A", "B"))
        self.assertEqual(finding.category, "A_B_SEQUENCE_OBSERVED_NOT_AUTHENTICATED")
        self.assertFalse(finding.stream_frames_authenticated)

    def test_last_writer_for_both_samples(self):
        a = parse_queued_report(report(first="MISMATCH_REJECTED", second="MISMATCH_REJECTED"))
        b = parse_queued_report(report(first="MATCH_ONLY_NO_AUTH", second="MATCH_ONLY_NO_AUTH"))
        finding = classify_queued_reports(a, b)
        self.assertEqual(finding.category, "B_OBSERVED_FOR_BOTH_QUEUED_FRAMES")
        self.assertFalse(finding.installation_authorized)

    def test_first_writer_for_both_samples(self):
        a = parse_queued_report(report(first="MATCH_ONLY_NO_AUTH", second="MATCH_ONLY_NO_AUTH"))
        b = parse_queued_report(report(first="MISMATCH_REJECTED", second="MISMATCH_REJECTED"))
        self.assertEqual(classify_queued_reports(a, b).category, "A_OBSERVED_FOR_BOTH_QUEUED_FRAMES")

    def test_reverse_observation(self):
        a = parse_queued_report(report(first="MISMATCH_REJECTED", second="MATCH_ONLY_NO_AUTH"))
        b = parse_queued_report(report(first="MATCH_ONLY_NO_AUTH", second="MISMATCH_REJECTED"))
        self.assertEqual(classify_queued_reports(a, b).category, "REVERSED_OBSERVATION_NOT_AUTHENTICATED")

    def test_api_error_is_inconclusive(self):
        a = parse_queued_report(report(first="TOKEN_UNAVAILABLE"))
        b = parse_queued_report(report(first="CSOPS_MISSING"))
        self.assertEqual(classify_queued_reports(a, b).category, "INCONCLUSIVE_QUEUED_STREAM_IDENTITY")

    def test_batch_is_never_per_frame_evidence(self):
        a = parse_queued_report(report("BATCH", first="MISMATCH_REJECTED"))
        b = parse_queued_report(report("BATCH", first="MATCH_ONLY_NO_AUTH"))
        item = classify_queued_reports(a, b)
        self.assertEqual(item.category, "BATCH_SINGLE_SAMPLE_CANNOT_ATTRIBUTE_FRAMES")
        self.assertEqual(item.observations, ("B", "NO_SECOND_SAMPLE"))
        self.assertFalse(item.installation_authorized)

    def test_reject_mismatched_modes(self):
        with self.assertRaises(QueuedReportRejected):
            classify_queued_reports(parse_queued_report(report()),
                                    parse_queued_report(report("BATCH")))

    def test_reject_claimed_evidence(self):
        item = parse_queued_report(report())
        for field in (
            "peer_authenticated", "publisher_authenticated", "ios12_verified",
            "installation_authorized", "installation_performed"
        ):
            with self.subTest(field=field):
                with self.assertRaises(QueuedReportRejected):
                    classify_queued_reports(replace(item, **{field: True}), item)

    def test_reject_untrusted_flag_removed(self):
        item = parse_queued_report(report())
        with self.assertRaises(QueuedReportRejected):
            classify_queued_reports(replace(item, untrusted_text_only=False), item)

    def test_reject_forged_result_object(self):
        with self.assertRaises(QueuedReportRejected):
            classify_queued_reports({}, parse_queued_report(report()))


if __name__ == "__main__":
    unittest.main()
