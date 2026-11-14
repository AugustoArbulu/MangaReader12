#!/usr/bin/env python3
"""Phase W: production trust is not injectable, remotely supplied or active."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION = (ROOT / "MangaReader12/Core/WebReaderProductionPublisherTrust.swift").read_text()
DEV = (ROOT / "MangaReader12/Core/WebReaderSignedReleaseTrustGate.swift").read_text()
CHECKER = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
XCODE = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
NATIVE = (ROOT / "ci/test_native_webreader_signed_release_trust_gate.py").read_text()


class ProductionPublisherPolicy(unittest.TestCase):
    def test_actual_production_code_is_in_ios12_target(self):
        name = "WebReaderProductionPublisherTrust.swift"
        self.assertEqual(XCODE.count(f"{name} in Sources"), 2)
        self.assertEqual(XCODE.count(f"{name} */ = {{isa = PBXFileReference"), 1)
        self.assertIn(
            "A20000000000000000000038 /* WebReaderProductionPublisherTrust.swift */,",
            XCODE
        )
        self.assertIn(
            "A10000000000000000000038 /* WebReaderProductionPublisherTrust.swift in Sources */,",
            XCODE
        )

    def test_no_production_trust_root_installed(self):
        self.assertIn(
            "static let independentlyProvisionedSPKISHA256: String? = nil",
            PRODUCTION
        )
        self.assertIn("static let productionTrustGeneration = 0", PRODUCTION)
        self.assertIn("static let revokedPublisherPins: Set<String> = []", PRODUCTION)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHECKER)
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)

    def test_production_path_does_not_accept_pin_or_key_from_caller(self):
        declaration = PRODUCTION.split(
            "static func inspectProductionManifestReadOnly(", 1
        )[1].split(") throws -> WebReaderSignedReleasePreview {", 1)[0]
        self.assertNotIn("publicKey", declaration)
        self.assertNotIn("trustedPin", declaration)
        self.assertNotIn("publisherFingerprint", declaration)
        self.assertIn("envelopeData: Data", declaration)
        self.assertIn("WebReaderUpdateChannel.productionPublicKeyX963", PRODUCTION)
        self.assertIn("independentlyProvisionedSPKISHA256", PRODUCTION)
        self.assertIn("productionTrustGeneration >= 1", PRODUCTION)
        self.assertIn("revokedPublisherPins.contains(pin)", PRODUCTION)
        self.assertIn("WebReaderSignedReleaseTrustGate.inspectReadOnlyV2(", PRODUCTION)

    def test_developer_injection_is_never_production_trust(self):
        self.assertIn("independentlyTrustedSPKISHA256: String?", DEV)
        self.assertIn("inspectProductionManifestReadOnly(", NATIVE)
        self.assertIn("developer fixture illegally configured production trust", NATIVE)
        self.assertIn("noProvisionedOwnerTrust", NATIVE)

    def test_no_automatic_install_or_key_persistence(self):
        for token in (
            "UserDefaults", "Keychain", "SecItemAdd", "URLSession",
            "Data(contentsOf:", "appinst(", "posix_spawn(",
            "FileManager.default", "privateKey",
        ):
            self.assertNotIn(token, PRODUCTION)
        self.assertNotIn("WebReaderProductionPublisherTrust.inspectProductionManifestReadOnly(", UI)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)

    def test_all_production_results_are_signed_manifest_preview_only(self):
        self.assertIn("WebReaderSignedReleasePreview", PRODUCTION)
        self.assertNotIn("installAuthorized = true", PRODUCTION)
        self.assertNotIn("installationAuthorized = true", PRODUCTION)
        self.assertNotIn("checkConnection(", PRODUCTION)


if __name__ == "__main__":
    unittest.main()
