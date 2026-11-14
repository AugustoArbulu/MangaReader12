#!/usr/bin/env python3
"""Static fail-closed AS/AT policy: no test key auto-enrolled into production."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"

class OwnerPublicTrustPolicy(unittest.TestCase):
    def test_production_key_and_install_remain_disabled(self):
        production = (CORE / "WebReaderProductionPublisherTrust.swift").read_text()
        channel = (CORE / "WebReaderUpdateChecker.swift").read_text()
        install = (CORE / "WebReaderAppinstSocket.swift").read_text()
        self.assertIn("static let independentlyProvisionedSPKISHA256: String? = nil", production)
        self.assertIn("static let productionTrustGeneration = 0", production)
        self.assertIn("static let revokedPublisherPins: Set<String> = []", production)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", channel)
        self.assertIn("static let liveInstallationEnabled = false", install)

    def test_pre_network_configuration_checks_real_public_point_and_pin(self):
        source = (CORE / "WebReaderProductionPublisherTrust.swift").read_text()
        checker = (CORE / "WebReaderProductionSignedReleaseChecker.swift").read_text()
        gate = (CORE / "WebReaderSignedReleaseTrustGate.swift").read_text()
        self.assertIn("static func isCandidateReadyForReview(", source)
        self.assertIn("static var isProvisioned: Bool", source)
        self.assertIn("return isCandidateReadyForReview(", source)
        self.assertIn("ownerPin: independentlyProvisionedSPKISHA256", source)
        self.assertIn("generation: productionTrustGeneration", source)
        self.assertIn("publicKeyX963: WebReaderUpdateChannel.productionPublicKeyX963", source)
        self.assertIn("revokedPins: revokedPublisherPins", source)
        self.assertIn("WebReaderSignedReleaseTrustGate.observedP256SPKISHA256(", source)
        self.assertIn("SecKeyCreateWithData(", gate)
        self.assertIn("CC_SHA256(", gate)
        pos = checker.index("guard WebReaderProductionPublisherTrust.isProvisioned else {")
        session = checker.index("let connection = URLSession(", pos)
        self.assertLess(pos, session)
        self.assertIn("callback(.disabled)", checker[pos:session])
        self.assertIn('expectedChannel: "production"', source)
        self.assertNotIn('UserDefaults', source)
        self.assertNotIn("URLSession(", source)  # comments may name API, but no call

    def test_public_review_tool_never_enrolls_keys_or_runs_an_installer(self):
        tool = (ROOT / "ci/build69_publisher_bootstrap_review.py").read_text()
        self.assertIn("ownerIndependenceVerifiedByScript", tool)
        self.assertIn('"ownerExplicitApprovalRecorded": False', tool)
        self.assertIn('"productionKeyProvisionedInApp": False', tool)
        self.assertIn('"publicationAuthorized": False', tool)
        self.assertIn('"chimeraInstallationAuthorized": False', tool)
        self.assertIn('"installationPerformed": False', tool)
        for forbidden in ("subprocess", "URLSession", "requests.get(",
                          "posix_spawn(", "appinst(", "private_key",
                          ".write_text(", ".write_bytes(", "main/updates/"):
            self.assertNotIn(forbidden, tool)

if __name__ == "__main__":
    unittest.main()
