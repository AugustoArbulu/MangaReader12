#!/usr/bin/env python3
"""Phase S native read-only signed-release policy; no production enrollment."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
GATE = (ROOT / "MangaReader12/Core/WebReaderSignedReleaseTrustGate.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
UPDATE = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
NATIVE = (ROOT / "ci/test_native_webreader_signed_release_trust_gate.py").read_text()


class NativeTrustGatePolicy(unittest.TestCase):
    def test_real_ios12_swift_source_added_to_target_once(self):
        for token in (
            "WebReaderSignedReleaseTrustGate.swift in Sources",
            "WebReaderSignedReleaseTrustGate.swift */ = {isa = PBXFileReference",
            "A20000000000000000000035 /* WebReaderSignedReleaseTrustGate.swift */,",
            "A10000000000000000000035 /* WebReaderSignedReleaseTrustGate.swift in Sources */,",
        ):
            self.assertIn(token, PROJECT)
        self.assertIn("enum WebReaderSignedReleaseTrustGate", GATE)

    def test_only_explicit_owner_trusted_fingerprint_allowed(self):
        for token in (
            "independentlyTrustedSPKISHA256: String?",
            "guard let pin = independentlyTrustedSPKISHA256",
            '"^[0-9a-f]{64}$"',
            "publicKeyX963.count == 65",
            "publicKeyX963.first == 0x04",
            "CC_SHA256(", "observed == pin",
            "trustAnchorMismatch", "missingIndependentTrustAnchor"
        ):
            with self.subTest(token=token):
                self.assertIn(token, GATE)

    def test_no_self_pinning_from_received_release(self):
        self.assertNotIn("productionPublicKeyX963 =", GATE)
        self.assertNotIn("UserDefaults", GATE)
        self.assertNotIn("URLSession", GATE)
        self.assertNotIn("UIPasteboard", GATE)
        self.assertNotIn("SecKeyCreateRandomKey", GATE)
        self.assertNotIn("privateKey", GATE)
        self.assertNotIn("/usr/bin/appinst", GATE)
        self.assertNotIn("posix_spawn(", GATE)

    def test_crypto_independent_of_legacy_v1(self):
        self.assertIn("version.intValue == 2", GATE)
        self.assertIn('version.stringValue == "2"', GATE)
        self.assertIn("WebReaderStrictJSON.accepts(envelopeData)", GATE)
        self.assertIn("WebReaderUpdateManifestVerifier.verify(", GATE)
        self.assertNotIn("publicGitHubRelease", GATE)

    def test_receipt_never_grants_install_and_identifies_unproven_checks(self):
        for token in (
            "signatureVerifiedAgainstSuppliedKey: Bool = true",
            "ownerIdentityEstablishedByDevice: Bool = false",
            "nativeIPACodeSignatureVerified: Bool = false",
            "peerAuthenticated: Bool = false",
            "userConsentVerified: Bool = false",
            "installationAuthorized: Bool = false",
            "installationPerformed: Bool = false",
        ):
            self.assertIn(token, GATE)

    def test_no_production_key_no_installer_and_no_runtime_wiring(self):
        self.assertIn("static let productionPublicKeyX963: Data? = nil", UPDATE)
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)
        self.assertNotIn("WebReaderSignedReleaseTrustGate", UI)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)

    def test_native_harness_has_positive_and_negative_cases(self):
        for marker in (
            "signed v2 accepted",
            "no trusted pin", "wrong pin", "mutated key",
            "v1 not allowed even when correctly signed",
            "invalid ECDSA signature",
            "not newer than installed",
            "bool schema version", "fractional schema",
            "read-only result never authorizes installation",
            "openssl", "swiftc"
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, NATIVE)


if __name__ == "__main__":
    unittest.main()
