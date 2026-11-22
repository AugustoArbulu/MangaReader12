#!/usr/bin/env python3
"""Adversarial tests for iOS12 CL->CM sanitized peer reason reporting."""
from dataclasses import FrozenInstanceError
import unittest

from package_chimera_signed_peer_cm import reason_shell, KERNEL_CODES, package, OUT, CHECKSUM
from build71_cm_peer_reason_report import (
    inspect_untrusted_cm_report, CMPeerReasonRejected, EXPECTED
)

HEADER = (
    "WEBREADER_CM_IOS12_PEER_REASON: NONROOT READ_ONLY\n"
    "REFERENCE=ADHOC_HOST_BUILT_NOT_EDITORIAL\n"
    "APP_PEER_AUTHENTICATED=NO\n"
    "TRANSPORT_TEST=UNIX_LOCAL_TWO_SIGNED_EXECUTABLES\n"
)
FOOTER = (
    "IOS12_RUNTIME_CODE_IDENTITY_SUPPORT=UNPROVEN_BY_THIS_REPORT\n"
    "BUNDLE_AND_PUBLISHER_IDENTITY=NOT_TESTED\n"
    "FINAL_INSTALL_AUTHORIZATION=DENIED\n"
)


def report(a="MATCH_ONLY_NO_AUTH", b="MISMATCH_REJECTED", c="MATCH_ONLY_NO_AUTH"):
    return (HEADER
            + "OBSERVATION_a=" + a + " AUTHORIZATION=DENIED\n"
            + "OBSERVATION_b=" + b + " AUTHORIZATION=DENIED\n"
            + "OBSERVATION_c=" + c + " AUTHORIZATION=DENIED\n"
            + FOOTER).encode("ascii")


class CMPeerReasonTests(unittest.TestCase):
    def test_exact_expected_laboratory_observation_still_denies_install(self):
        result = inspect_untrusted_cm_report(report())
        self.assertEqual(result.observations, EXPECTED)
        self.assertTrue(result.all_expected_controlled_comparisons)
        self.assertEqual(result.evidence_category, "EXPECTED_CDHASH_LAB_PATTERN_UNTRUSTED")
        for field in (
            "ios12_runtime_verified_by_this_parser", "webreader_process_authenticated",
            "publisher_authenticated", "installation_authorized",
            "installation_performed"
        ):
            self.assertFalse(getattr(result, field))
        with self.assertRaises(FrozenInstanceError):
            result.installation_authorized = True

    def test_uniform_token_denials_become_specific_without_authority(self):
        for code in ("TOKEN_UNAVAILABLE", "CSOPS_MISSING", "CDHASH_UNAVAILABLE"):
            with self.subTest(code=code):
                result = inspect_untrusted_cm_report(report(code, code, code))
                self.assertEqual(result.evidence_category, "SAME_KERNEL_CAPABILITY_FAILURE_ALL_THREE")
                self.assertEqual(result.observations, (code,) * 3)
                self.assertFalse(result.installation_authorized)
                self.assertFalse(result.webreader_process_authenticated)

    def test_dangerous_token_validation_fails_closed(self):
        for code in ("TOKEN_MUTATION_UNSAFE", "CROSS_PID_UNSAFE"):
            result = inspect_untrusted_cm_report(report(code, code, code))
            self.assertEqual(result.evidence_category, "KERNEL_TOKEN_VALIDATION_FAILED_UNSAFE")
            self.assertFalse(result.installation_authorized)

    def test_transport_and_mixed_failures_cannot_authorize(self):
        for code in ("SOCKET_UNAVAILABLE", "CLIENT_FAILED", "TRANSPORT_FAILED"):
            result = inspect_untrusted_cm_report(report(code, code, code))
            self.assertEqual(result.evidence_category, "LOCAL_TRANSPORT_FAILURE")
            self.assertFalse(result.installation_authorized)
        self.assertFalse(inspect_untrusted_cm_report(
            report("MISMATCH_REJECTED", "INCONCLUSIVE", "CSOPS_MISSING")
        ).all_expected_controlled_comparisons)

    def test_spoofed_status_and_mconclusive_are_rejected(self):
        original = report()
        cases = [
            original.replace(b"OBSERVATION_c=MATCH_ONLY_NO_AUTH", b"OBSERVATION_c=MINCONCLUSIVE"),
            original.replace(b"AUTHORIZATION=DENIED", b"AUTHORIZATION=ALLOWED"),
            original.replace(b"APP_PEER_AUTHENTICATED=NO", b"APP_PEER_AUTHENTICATED=YES"),
            original.replace(b"FINAL_INSTALL_AUTHORIZATION=DENIED",
                             b"FINAL_INSTALL_AUTHORIZATION=GRANTED"),
            original.replace(b"OBSERVATION_a=", b"OBSERVATION_b="),
            original + b"INSTALLATION_AUTHORIZED=TRUE\n",
            original + b"\n",
            original.replace(b"\n", b"\r\n"),
            original + b"\x00",
            original * 5,
            b"{}", b"", "not bytes",
        ]
        for item in cases:
            with self.subTest(case=repr(item)[:70]), self.assertRaises(CMPeerReasonRejected):
                inspect_untrusted_cm_report(item)

    def test_runner_preserves_exact_safe_reason_codes_and_rejects_untrusted_logs(self):
        script = reason_shell("a"*40, "b"*40)
        self.assertIn(b"WEBREADER_CM_IOS12_PEER_REASON", script)
        for code in KERNEL_CODES:
            self.assertIn(("OBSERVATION_$label=" + code).encode(), script)
        self.assertIn(b"result_count", script)
        self.assertIn(b"footer_count", script)
        self.assertIn(b'if [ "$result_count" != 1 ] || [ "$footer_count" != 1 ]; then', script)
        self.assertIn(b"OBSERVATION_$label=INCONCLUSIVE AUTHORIZATION=DENIED", script)
        for forbidden in (b"/usr/bin/appinst", b"WRINST1", b"launchctl",
                          b"curl ", b"wget ", b"sudo ", b"/var/mobile/"):
            self.assertNotIn(forbidden, script)

    def test_new_package_upgrades_cl_without_creating_second_package_identity(self):
        from package_chimera_signed_peer_cm import PKG, VERSION, CONTROL
        self.assertEqual(PKG, "com.example.webreader.peercl")
        self.assertEqual(VERSION, "0.2.0")
        self.assertIn("Package: com.example.webreader.peercl\n", CONTROL)
        self.assertIn("Version: 0.2.0\n", CONTROL)
        self.assertEqual(CHECKSUM.name, OUT.name + ".sha256")


if __name__ == "__main__":
    unittest.main()
