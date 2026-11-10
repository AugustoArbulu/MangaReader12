#!/usr/bin/env python3
"""Adversarial tests for Phase CL untrusted physical signed-peer observations."""
from dataclasses import FrozenInstanceError, replace
import unittest

from build71_cl_signed_peer_report import (
    CLPeerReportRejected, inspect_untrusted_cl_report
)

BASE = (
    "WEBREADER_CL_IOS12_SIGNED_PEER: NONROOT READ_ONLY\n"
    "REFERENCE=ADHOC_HOST_BUILT_NOT_EDITORIAL\n"
    "APP_PEER_AUTHENTICATED=NO\n"
    "TRANSPORT_TEST=UNIX_LOCAL_TWO_SIGNED_EXECUTABLES\n"
    "OBSERVATION_a=MATCH_ONLY_NO_AUTH AUTHORIZATION=DENIED\n"
    "OBSERVATION_b=MISMATCH_REJECTED AUTHORIZATION=DENIED\n"
    "OBSERVATION_c=MATCH_ONLY_NO_AUTH AUTHORIZATION=DENIED\n"
    "IOS12_RUNTIME_CODE_IDENTITY_SUPPORT=UNPROVEN_BY_THIS_REPORT\n"
    "BUNDLE_AND_PUBLISHER_IDENTITY=NOT_TESTED\n"
    "FINAL_INSTALL_AUTHORIZATION=DENIED\n"
)


class CLPhysicalReportTests(unittest.TestCase):
    def test_controlled_expected_pattern_never_authorizes(self):
        report = inspect_untrusted_cl_report(BASE.encode("ascii"))
        self.assertTrue(report.controlled_codehash_comparison_observed)
        self.assertEqual(
            report.interpretation,
            "EXPECTED_CONTROLLED_CDHASH_PATTERN_UNTRUSTED_TEXT_ONLY"
        )
        for item in ("webreader_process_authenticated",
                     "ios12_kernel_authority_established",
                     "publisher_authenticated", "install_authorized",
                     "installation_performed"):
            self.assertFalse(getattr(report, item))
        with self.assertRaises(FrozenInstanceError):
            report.install_authorized = True
        altered = replace(report, install_authorized=True)
        # Any tampering with a local Python object is NOT OS-backed evidence.
        self.assertTrue(altered.install_authorized)
        self.assertFalse(report.install_authorized)

    def test_socket_transport_failure_remains_inconclusive(self):
        for status in ("SOCKET_UNAVAILABLE", "CLIENT_FAILED", "INCONCLUSIVE"):
            with self.subTest(status=status):
                raw = BASE.replace(
                    "OBSERVATION_b=MISMATCH_REJECTED",
                    "OBSERVATION_b=" + status
                ).encode()
                report = inspect_untrusted_cl_report(raw)
                self.assertFalse(report.controlled_codehash_comparison_observed)
                self.assertFalse(report.webreader_process_authenticated)
                self.assertFalse(report.install_authorized)

    def test_unknown_and_spoofed_authorization_rejected(self):
        bad = [
            b"", b"{}", b"\xff", BASE.encode() + b"INSTALL_AUTHORIZED=YES\n",
            BASE.replace("APP_PEER_AUTHENTICATED=NO",
                         "APP_PEER_AUTHENTICATED=YES").encode(),
            BASE.replace("FINAL_INSTALL_AUTHORIZATION=DENIED",
                         "FINAL_INSTALL_AUTHORIZATION=ALLOWED").encode(),
            BASE.replace("OBSERVATION_b=MISMATCH_REJECTED",
                         "OBSERVATION_b=TRUSTED").encode(),
            BASE.replace("OBSERVATION_a=", "OBSERVATION_b=").encode(),
            BASE.replace("OBSERVATION_b=", "OBSERVATION_a=").encode(),
            BASE.replace("AUTHORIZATION=DENIED",
                         "AUTHORIZATION=ALLOWED").encode(),
            BASE.replace("\n", "\r\n").encode(),
            BASE.encode() + b"\n",
            BASE.encode() + b"\x00",
            BASE.encode() * 20,
            BASE
        ]
        for item in bad:
            with self.subTest(kind=str(type(item)), length=len(item)):
                with self.assertRaises(CLPeerReportRejected):
                    inspect_untrusted_cl_report(item)

    def test_no_trailing_newline_accepted(self):
        self.assertFalse(
            inspect_untrusted_cl_report(BASE[:-1].encode()).install_authorized
        )

if __name__ == "__main__":
    unittest.main()
