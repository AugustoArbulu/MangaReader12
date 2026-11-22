#!/usr/bin/env python3
"""Phase Y: signed preview is one-process QA, not installer rollback policy."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
SWIFT = (ROOT / "MangaReader12/Core/WebReaderSignedPreviewSequence.swift").read_text()
IPA = (ROOT / "MangaReader12/Core/WebReaderSignedIPAReview.swift").read_text()
PRODUCTION = (ROOT / "MangaReader12/Core/WebReaderProductionPublisherTrust.swift").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
CHECKER = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
XCODE = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
NATIVE = (ROOT / "ci/test_native_webreader_signed_preview_sequence.py").read_text()


class PreviewMonotonicSafety(unittest.TestCase):
    def test_compiled_in_ios12_target(self):
        name = "WebReaderSignedPreviewSequence.swift"
        self.assertEqual(XCODE.count(f"{name} in Sources"), 2)
        self.assertIn("A20000000000000000000039 /* " + name + " */,", XCODE)
        self.assertIn("A10000000000000000000039 /* " + name + " in Sources */,", XCODE)

    def test_real_signed_same_fd_review_performed_every_call(self):
        for token in (
            "WebReaderSignedIPAReview.inspectReadOnly(",
            "independentlyTrustedSPKISHA256: independentlyTrustedSPKISHA256",
            "installedBuild: highestReviewed",
            "highestReviewed = candidate.build",
            "candidate.build > highestReviewed",
            "lock.lock()", "defer { lock.unlock() }",
        ):
            self.assertIn(token, SWIFT)
        self.assertIn("WebReaderNativeIPAAuditor.inspect(", IPA)

    def test_review_state_is_explicitly_nonpersistent_and_nonauthorizing(self):
        for token in (
            "isPersistent: Bool = false",
            "installerLedgerVerified: Bool = false",
            "installationAuthorized: Bool = false",
            "installationPerformed: Bool = false",
            "invalidInstalledBuild",
            "oldOrRepeatedCandidate",
        ):
            self.assertIn(token, SWIFT)
        for forbidden in (
            "UserDefaults", "FileManager.default", "Data(contentsOf:",
            "Keychain", "SecItemAdd", "URLSession(", "appinst(", "posix_spawn(",
            "createDirectory(", "removeItem(", "install(",
        ):
            self.assertNotIn(forbidden, SWIFT)

    def test_native_test_has_race_and_reset_negative_cases(self):
        for token in (
            "DispatchQueue.concurrentPerform(iterations: 40)",
            "successes == 1", "duplicate candidate",
            "older candidate after 69", "wrong trusted pin",
            "corrupt archive", "fresh process has no signed-history persistence",
            "in-memory session is NOT a durable anti-rollback ledger",
            "NO INSTALL",
        ):
            self.assertIn(token, NATIVE)

    def test_prod_auth_and_ui_cannot_use_preview_to_install(self):
        self.assertIn("independentlyProvisionedSPKISHA256: String? = nil", PRODUCTION)
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHECKER)
        self.assertNotIn("WebReaderSignedPreviewSequence", UI)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)


if __name__ == "__main__":
    unittest.main()
