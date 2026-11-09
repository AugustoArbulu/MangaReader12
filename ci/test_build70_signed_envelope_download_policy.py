#!/usr/bin/env python3
"""Phase CH — signed envelope continuity from discover to manual export.

Read-only static checks; executed in Linux CI. Real cryptographic semantics are
covered separately by the macOS Security.framework native fixture.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
UI = ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift"


class SignedEnvelopeContinuityPolicy(unittest.TestCase):
    def test_signed_checker_only_exposes_actual_verified_bytes(self):
        s = (CORE / "WebReaderProductionSignedReleaseChecker.swift").read_text()
        self.assertIn("private var verifiedEnvelopeData: Data?", s)
        self.assertIn("func verifiedEnvelopeCopy() -> Data?", s)
        self.assertIn("verifiedEnvelopeData = nil", s)
        self.assertIn("verifiedEnvelopeData = bytes", s)
        self.assertLess(
            s.index("WebReaderProductionPublisherTrust.inspectProductionManifestReadOnly("),
            s.index("verifiedEnvelopeData = bytes")
        )
        self.assertLess(
            s.index("verifiedEnvelopeData = bytes"),
            s.index("finish(.updateAvailable(preview.update))")
        )
        self.assertIn("guard WebReaderProductionPublisherTrust.isProvisioned", s)

    def test_stager_requires_real_envelope_before_network_and_files(self):
        s = (CORE / "WebReaderIPAStager.swift").read_text()
        section = s.split(
            "    func stage(completion callback:", 1
        )[1].split("\n    func cancel()", 1)[0]
        guard = "WebReaderSignedProductionEnvelopeBinding.matchesCompiledOwnerRootReadOnly("
        self.assertIn("private let signedManifestEnvelopeData: Data?", s)
        self.assertIn("signedManifestEnvelopeData: Data? = nil", s)
        self.assertIn("update.provenance == .signedManifest && testProtocolClasses == nil", section)
        self.assertIn("guard let signedBytes = signedManifestEnvelopeData", section)
        self.assertIn(guard, section)
        self.assertIn("callback(.failed(.disabled))", section)
        self.assertLess(section.index(guard), section.index(
            "FileManager.default.createDirectory("
        ))
        self.assertLess(section.index(guard), section.index(
            "URLSessionConfiguration.ephemeral"
        ))
        self.assertIn("WebReaderNativeIPAAuditor.inspect(", s)
        self.assertIn("guard hex == update.sha256", s)
        self.assertNotIn("appinst(", s)

    def test_ui_never_promotes_unverified_marker_to_signed_download(self):
        s = UI.read_text()
        self.assertIn("private var authenticatedSignedEnvelopeData: Data?", s)
        self.assertIn("authenticatedSignedEnvelopeData = nil", s)
        self.assertIn("if let envelope = signed.verifiedEnvelopeCopy()", s)
        self.assertIn(
            "WebReaderSignedProductionEnvelopeBinding.matchesCompiledOwnerRootReadOnly(",
            s
        )
        self.assertIn("self.authenticatedSignedEnvelopeData = envelope", s)
        self.assertIn("selectedSignedUpdateIsBound(update)", s)
        self.assertIn(
            "signedManifestEnvelopeData: update.provenance == .signedManifest ?",
            s
        )
        self.assertIn("let signedEnvelope = authenticatedSignedEnvelopeData", s)
        self.assertGreaterEqual(s.count(
            "WebReaderSignedProductionEnvelopeBinding.matchesCompiledOwnerRootReadOnly("), 4)
        self.assertNotIn("WebReaderAppinstSocket.install(", s)

    def test_cryptographic_reference_compares_all_signed_metadata(self):
        s = (CORE / "WebReaderSignedProductionEnvelopeBinding.swift").read_text()
        for attr in ("build", "minimumIOS", "ipaURL", "ipaSize", "sha256",
                     "publishedAt", "releaseNotes"):
            with self.subTest(attr=attr):
                self.assertIn(f"verified.{attr} == update.{attr}", s)
        self.assertIn("expectedChannel: \"production\"", s)
        self.assertIn("update.provenance == .signedManifest", s)
        self.assertIn("WebReaderProductionPublisherTrust.isProvisioned", s)
        self.assertIn("WebReaderUpdateChannel.productionPublicKeyX963", s)
        self.assertIn(
            "WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256", s
        )
        self.assertIn("installedBuild: installedBuild", s)
        self.assertNotIn("install(", s)

    def test_actual_production_and_chimera_remain_disabled(self):
        self.assertIn(
            "static let liveInstallationEnabled = false",
            (CORE / "WebReaderAppinstSocket.swift").read_text()
        )
        self.assertIn(
            "static let productionPublicKeyX963: Data? = nil",
            (CORE / "WebReaderUpdateChecker.swift").read_text()
        )
        self.assertIn(
            "static let independentlyProvisionedSPKISHA256: String? = nil",
            (CORE / "WebReaderProductionPublisherTrust.swift").read_text()
        )


if __name__ == "__main__":
    unittest.main()
