#!/usr/bin/env python3
"""Phase H temporal A-B-A report policy: purely offline negative tests."""
from dataclasses import replace
import unittest
from build66_temporal_peer_report import (
    TemporalReportRejected, parse_temporal_peer_report,
    classify_temporal_reports,
)

HEAD = "READY NONROOT THREE_MESSAGES AUTHORIZATION=DENIED"
FOOTER = "FINAL_INSTALL_AUTHORIZATION=DENIED"
M = "MATCH_ONLY_NO_AUTH"
N = "MISMATCH_REJECTED"
U = "TOKEN_UNAVAILABLE"


def text_report(a=M, b=N, c=M):
    return ("\n".join([
        HEAD,
        f"RESULT STEP1={a} AUTHORIZATION=DENIED",
        f"RESULT STEP2={b} AUTHORIZATION=DENIED",
        f"RESULT STEP3={c} AUTHORIZATION=DENIED",
        FOOTER,
    ]) + "\n").encode()


def parsed(a=M, b=N, c=M):
    return parse_temporal_peer_report(text_report(a,b,c))


class TemporalTokenReportTests(unittest.TestCase):
    def safe(self, result):
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.installation_performed)
        self.assertFalse(result.publisher_authenticated)

    def test_canonical_report(self):
        x = parsed()
        self.assertEqual(x.statuses, (M,N,M))
        self.assertTrue(x.source_untrusted_text_only)
        self.assertFalse(x.sender_identified_on_ios12)
        self.safe(x)

    def test_correct_A_B_A_sequence_remains_non_authoritative(self):
        x = classify_temporal_reports(parsed(M,N,M),parsed(N,M,N))
        self.assertEqual(x.category,"A_B_A_MESSAGE_SENDER_REBINDING_OBSERVED")
        self.assertEqual(x.observed_origin_sender_sequence,("A","B","A"))
        self.assertFalse(x.current_writer_authenticated)
        self.assertFalse(x.ios12_runtime_verified)
        self.safe(x)

    def test_transfer_sticky_after_B(self):
        x=classify_temporal_reports(parsed(M,N,N),parsed(N,M,M))
        self.assertEqual(x.category,"TRANSFER_STICKY_AFTER_B_OBSERVED")
        self.safe(x)

    def test_origin_sticky(self):
        x=classify_temporal_reports(parsed(M,M,M),parsed(N,N,N))
        self.assertEqual(x.category,"ORIGIN_STICKY_THROUGH_MESSAGES")
        self.safe(x)

    def test_missing_token_is_inconclusive(self):
        x=classify_temporal_reports(parsed(U,N,M),parsed(N,M,N))
        self.assertEqual(x.category,"INCONCLUSIVE_OR_AMBIGUOUS")
        self.safe(x)

    def test_both_references_match_is_ambiguous(self):
        x=classify_temporal_reports(parsed(M,M,M),parsed(M,M,M))
        self.assertEqual(x.category,"INCONCLUSIVE_OR_AMBIGUOUS")
        self.safe(x)

    def test_unexpected_sequence(self):
        x=classify_temporal_reports(parsed(N,M,N),parsed(M,N,M))
        self.assertEqual(x.category,"UNEXPECTED_CONNECTION_IDENTITY_SEQUENCE")
        self.safe(x)

    def test_statuses_dont_contain_pid(self):
        self.assertTrue(all("PID=" not in value for value in parsed().statuses))

    def test_no_trailing_newline(self):
        self.safe(parse_temporal_peer_report(text_report().rstrip(b"\n")))

    def test_empty_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(b"")

    def test_extra_newline_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(text_report()+b"\n")

    def test_extra_line_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(text_report()+b"INSTALL\n")

    def test_missing_step_rejected(self):
        lines=text_report().decode().splitlines()
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(("\n".join(lines[:2]+lines[3:])+"\n").encode())

    def test_duplicate_step_rejected(self):
        lines=text_report().decode().splitlines()
        lines[3]=lines[2]
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(("\n".join(lines)+"\n").encode())

    def test_wrong_step_order_rejected(self):
        lines=text_report().decode().splitlines()
        lines[1],lines[2]=lines[2],lines[1]
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(("\n".join(lines)+"\n").encode())

    def test_token_dump_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(text_report().replace(b"STEP2=",b"STEP2=TOKEN=1234"))

    def test_pid_dump_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(text_report().replace(b"STEP3=",b"STEP3=PID=123"))

    def test_authorized_claim_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(text_report().replace(b"AUTHORIZATION=DENIED",b"AUTHORIZATION=ALLOWED"))

    def test_wrong_footer_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(text_report().replace(b"FINAL_INSTALL_AUTHORIZATION=DENIED",b"FINAL_INSTALL_AUTHORIZATION=YES"))

    def test_crlf_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(text_report().replace(b"\n",b"\r\n"))

    def test_bad_utf8_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(text_report()+b"\xff")

    def test_oversized_report_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report(b"x"*1025)

    def test_wrong_type_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            parse_temporal_peer_report("not bytes")

    def test_injected_sender_authentication_rejected(self):
        a=replace(parsed(),publisher_authenticated=True)
        with self.assertRaises(TemporalReportRejected):
            classify_temporal_reports(a,parsed(N,M,N))

    def test_injected_install_authority_rejected(self):
        a=replace(parsed(),installation_authorized=True)
        with self.assertRaises(TemporalReportRejected):
            classify_temporal_reports(a,parsed(N,M,N))

    def test_injected_report_type_rejected(self):
        with self.assertRaises(TemporalReportRejected):
            classify_temporal_reports("A-B-A",parsed(N,M,N))

    def test_injected_untrusted_type_rejected(self):
        a=replace(parsed(),source_untrusted_text_only=False)
        with self.assertRaises(TemporalReportRejected):
            classify_temporal_reports(a,parsed(N,M,N))


if __name__ == "__main__":
    unittest.main()
