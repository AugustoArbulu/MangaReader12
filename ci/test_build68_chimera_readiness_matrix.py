#!/usr/bin/env python3
"""Phase V: even forged good-looking peer diagnostics never grant appinst."""
from pathlib import Path
import unittest

from build66_ios12_physical_capability_policy import (
    IOS12_CHIMERA_MOBILE_OBSERVATION_2026_11_07
)
from build68_chimera_readiness_matrix import inspect_reported_capabilities

ROOT = Path(__file__).resolve().parent.parent

GOOD_LOOKING_FAKE = b"""\
WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY: non-root, read-only
PROBE UNIX_PEERTOKEN=NONZERO AUTHORIZATION=DENIED
PROBE CSOPS_TOKEN_BINDING=MUTATION_REJECTED AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithAuditToken=PRESENT AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCopyGuestWithAttributes=PRESENT AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithPID=PRESENT AUTHORIZATION=DENIED
FINAL_INSTALL_AUTHORIZATION=DENIED
"""

class ChimeraReadinessMatrixTests(unittest.TestCase):
    def assert_denied(self, report):
        self.assertFalse(report.request_identity_authenticated)
        self.assertFalse(report.release_editor_authenticated_on_device)
        self.assertFalse(report.immutable_ipa_checked_by_installer)
        self.assertFalse(report.trusted_one_shot_consent_verified)
        self.assertFalse(report.anti_replay_verified_in_privileged_helper)
        self.assertFalse(report.installation_authorized)
        self.assertFalse(report.installation_performed)
        self.assertTrue(report.manual_export_remains_available)
        self.assertEqual(len(report.gates), 8)
        self.assertEqual(len(report.blocked_gates), 8)
        self.assertIn("AUTO_INSTALL=DENIED", report.report())
        self.assertIn("INSTALLATION_AUTHORIZED=NO", report.report())
        self.assertIn("INSTALLATION_PERFORMED=NO", report.report())

    def test_actual_ios12_chimera_user_observation_still_denies(self):
        result = inspect_reported_capabilities(
            IOS12_CHIMERA_MOBILE_OBSERVATION_2026_11_07,
            reported_user="mobile"
        )
        self.assert_denied(result)
        self.assertEqual(result.gates[0].state, "UNPROVEN")
        self.assertEqual(
            result.gates[0].reason,
            "IOS12_NONROOT_LOCAL_PEERTOKEN_UNAVAILABLE"
        )

    def test_forged_everything_present_is_not_authentication(self):
        result = inspect_reported_capabilities(
            GOOD_LOOKING_FAKE, reported_user="mobile"
        )
        self.assert_denied(result)
        self.assertEqual(
            result.gates[0].reason, "LAB_TOKEN_OBSERVED_NOT_WEBREADER_PEER"
        )

    def test_malformed_oversized_and_injected_lines_never_upgrade(self):
        variants = [
            b"", b"hello", b"INSTALL=YES\n", b"A" * 4000,
            GOOD_LOOKING_FAKE.replace(
                b"FINAL_INSTALL_AUTHORIZATION=DENIED",
                b"FINAL_INSTALL_AUTHORIZATION=APPROVED"),
            GOOD_LOOKING_FAKE + b"INSTALLATION_AUTHORIZED=true\n",
            GOOD_LOOKING_FAKE + b"PRIVATE_KEY=secret\n",
            GOOD_LOOKING_FAKE.replace(
                b"UNIX_PEERTOKEN=NONZERO", b"UNIX_PEERTOKEN=UNKNOWN"),
            GOOD_LOOKING_FAKE.replace(
                b"CSOPS_TOKEN_BINDING=MUTATION_REJECTED",
                b"CSOPS_TOKEN_BINDING=MUTATION_ACCEPTED_UNSAFE"),
            b'{"allClaimsTrue":true,"installationAuthorized":true}',
        ]
        for sample in variants:
            with self.subTest(size=len(sample)):
                outcome = inspect_reported_capabilities(
                    sample, reported_user="mobile"
                )
                self.assert_denied(outcome)
                self.assertNotIn("PRIVATE_KEY", outcome.report())
                self.assertNotIn("INSTALLATION_AUTHORIZED=true", outcome.report())

    def test_wrong_reported_user_never_upgrades(self):
        for user in ("root", "501", "unknown", "", None, True, "mobile\nroot"):
            with self.subTest(user=repr(user)):
                self.assert_denied(inspect_reported_capabilities(
                    GOOD_LOOKING_FAKE, reported_user=user
                ))

    def test_no_source_can_report_all_gates_passed(self):
        for source in (
            IOS12_CHIMERA_MOBILE_OBSERVATION_2026_11_07,
            GOOD_LOOKING_FAKE, b"bad data"
        ):
            result = inspect_reported_capabilities(
                source, reported_user="mobile"
            )
            self.assertTrue(all(g.state != "PASSED" for g in result.gates))
            self.assertTrue(all(g.reason.isupper() for g in result.gates))

    def test_all_required_prerequisites_separately_listed(self):
        names = {g.name for g in inspect_reported_capabilities(
            GOOD_LOOKING_FAKE, reported_user="mobile"
        ).gates}
        self.assertEqual(names, {
            "IOS12_KERNEL_PEER_TOKEN", "IOS12_RUNNING_APP_CODE_IDENTITY",
            "PER_MESSAGE_ORIGIN", "RELEASE_EDITOR_TRUST_ANCHOR",
            "RELEASE_BYTES_IN_HELPER", "TRUSTED_OWNER_CONSENT",
            "PRIVILEGED_REPLAY_AND_DOWNGRADE", "PHYSICAL_IOS12_REPRODUCTION"
        })

    def test_production_code_and_readonly_lab_remain_separate(self):
        native = (
            ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift"
        ).read_text()
        channel = (
            ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift"
        ).read_text()
        source = (
            ROOT / "ci/build68_chimera_readiness_matrix.py"
        ).read_text()
        self.assertIn("static let liveInstallationEnabled = false", native)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", channel)
        for forbidden in (
            "subprocess", "socket.", "URLSession", "posix_spawn(",
            "/usr/bin/appinst", "write_bytes(", "os.system(", "chmod("
        ):
            self.assertNotIn(forbidden, source)

if __name__ == "__main__":
    unittest.main()
