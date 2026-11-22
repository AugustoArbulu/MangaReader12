#!/usr/bin/env python3
"""Host-only parser tests. No authority is granted by a probe text report."""
import unittest
from build66_peer_capability_report import (
    PeerProbeReportRejected, parse_build63_peer_probe
)

HEADER = "WEBREADER_BUILD63_PEER_CAPABILITY: non-root, no install"
FOOTER = "FINAL_INSTALL_AUTHORIZATION=DENIED"


def report(tcp="PEER_PID=MATCH", unix="PEER_PID=MATCH", footer=FOOTER):
    return ("\n".join([
        HEADER,
        f"PROBE TCP_LOOPBACK {tcp} AUTHORIZATION=DENIED",
        f"PROBE UNIX_LOCAL {unix} AUTHORIZATION=DENIED",
        footer,
    ]) + "\n").encode("ascii")


class PeerProbeReportTests(unittest.TestCase):
    def accepted_only_as_observation(self, raw):
        parsed = parse_build63_peer_probe(raw)
        self.assertTrue(parsed.observed_metadata_only)
        self.assertFalse(parsed.ios12_capability_confirmed)
        self.assertFalse(parsed.peer_authentication_confirmed)
        self.assertFalse(parsed.installation_authorized)
        self.assertFalse(parsed.installation_performed)
        return parsed

    def test_matching_pid_both_transports_denies(self):
        p = self.accepted_only_as_observation(report())
        self.assertEqual((p.tcp_status, p.unix_status), ("MATCH", "MATCH"))

    def test_unavailable_both_transports_denies(self):
        self.accepted_only_as_observation(report(
            "PEER_PID=UNAVAILABLE", "PEER_PID=UNAVAILABLE"
        ))

    def test_mismatch_report_does_not_authorize(self):
        self.accepted_only_as_observation(report(
            "PEER_PID=MISMATCH", "PEER_PID=MISMATCH"
        ))

    def test_mixed_kernel_pid_status(self):
        self.accepted_only_as_observation(report(
            "PEER_PID=MATCH", "PEER_PID=UNAVAILABLE"
        ))

    def test_failed_transports_are_diagnostic_only(self):
        self.accepted_only_as_observation(report(
            "TRANSPORT=FAILED_16", "TRANSPORT=FAILED_20"
        ))

    def test_no_trailing_newline_is_allowed(self):
        self.accepted_only_as_observation(report().rstrip(b"\n"))

    def test_empty_report_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(b"")

    def test_extra_line_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(report() + b"extra\n")

    def test_missing_footer_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(report(footer=""))

    def test_authorized_footer_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(report(footer="FINAL_INSTALL_AUTHORIZATION=ALLOWED"))

    def test_authorized_transport_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(
                report().replace(b"AUTHORIZATION=DENIED", b"AUTHORIZATION=ALLOWED", 1)
            )

    def test_unexpected_transport_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(
                report().replace(b"UNIX_LOCAL", b"LOCAL_SOCKET")
            )

    def test_duplicate_transport_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(
                report().replace(b"UNIX_LOCAL", b"TCP_LOOPBACK")
            )

    def test_pid_integer_instead_of_status_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(
                report().replace(b"PEER_PID=MATCH", b"PEER_PID=1234", 1)
            )

    def test_non_ascii_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(report() + b"\xff")

    def test_oversized_report_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(b"a" * 1025)

    def test_nonbytes_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe("not bytes")

    def test_malicious_extra_install_field_rejected(self):
        with self.assertRaises(PeerProbeReportRejected):
            parse_build63_peer_probe(
                report().replace(
                    b"PEER_PID=MATCH", b"PEER_PID=MATCH INSTALL=/bin/appinst", 1
                )
            )

    def test_pid_match_in_forged_report_still_no_authentication(self):
        # The parser has no way to distinguish captured from forged text.
        p = self.accepted_only_as_observation(report())
        self.assertFalse(p.peer_authentication_confirmed)


if __name__ == "__main__":
    unittest.main()
