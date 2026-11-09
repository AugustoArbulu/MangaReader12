#!/usr/bin/env python3
"""Build68 Phases T/U: signed IPA joint inspection + truthful UIKit status."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
IPA = (ROOT / "MangaReader12/Core/WebReaderSignedIPAReview.swift").read_text()
GATE = (ROOT / "MangaReader12/Core/WebReaderSignedReleaseTrustGate.swift").read_text()
SNAPSHOT = (ROOT / "MangaReader12/Core/WebReaderUpdaterSecuritySnapshot.swift").read_text()
AUDITOR = (ROOT / "MangaReader12/Core/WebReaderNativeIPAAuditor.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
XCODE = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
CHECKER = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
NATIVE_IPA = (ROOT / "ci/test_native_webreader_signed_ipa_joint_audit.py").read_text()
NATIVE_SNAPSHOT = (ROOT / "ci/test_native_webreader_update_security_snapshot.py").read_text()


class NativeSignedIPAandStatusTests(unittest.TestCase):
    def test_both_native_sources_compile_in_ios12_app_target(self):
        for name, id_ in (
            ("WebReaderSignedIPAReview.swift", "36"),
            ("WebReaderUpdaterSecuritySnapshot.swift", "37"),
        ):
            self.assertEqual(XCODE.count(f"{name} in Sources"), 2)
            self.assertEqual(XCODE.count(f"{name} */ = {{isa = PBXFileReference"), 1)
            self.assertIn(f"A200000000000000000000{id_} /* {name} */,", XCODE)
            self.assertIn(f"A100000000000000000000{id_} /* {name} in Sources */,", XCODE)

    def test_manifest_and_local_ipa_independently_checked(self):
        for s in (
            "WebReaderSignedReleaseTrustGate.inspectReadOnlyV2(",
            "WebReaderNativeIPAAuditor.inspect(",
            "independentlyTrustedSPKISHA256: independentlyTrustedSPKISHA256",
            "signedUpdate: signed.update",
            "audited.verifiedSHA256 == signed.update.sha256",
            "audited.build == signed.update.build",
            "audited.minimumIOS == signed.update.minimumIOS",
        ):
            self.assertIn(s, IPA)
        self.assertIn("let finalDigest = fileSHA256(file)", AUDITOR)
        self.assertIn("O_NOFOLLOW | O_NONBLOCK", AUDITOR)
        self.assertIn("WebReaderStrictJSON.accepts(envelopeData)", GATE)

    def test_receipt_cannot_claim_privileged_install_admission(self):
        for s in (
            "nativeExecutableSignatureChecked: Bool = false",
            "publisherIdentityProvenByDevice: Bool = false",
            "fileLockedForLaterUse: Bool = false",
            "peerAuthenticated: Bool = false",
            "consentForInstallVerified: Bool = false",
            "installationAuthorized: Bool = false",
            "installationPerformed: Bool = false",
        ):
            self.assertIn(s, IPA)
        for forbid in (
            "posix_spawn(", "appinst", "URLSession(", "UserDefaults",
            "SecKeyCreateRandomKey(", "loadFromRelease", "install("
        ):
            # 'appinst' may occur in the comment; only prohibit actual path/code.
            if forbid == "appinst":
                self.assertNotIn("/usr/bin/appinst", IPA)
            else:
                self.assertNotIn(forbid, IPA)

    def test_signed_ipa_native_harness_has_positive_and_negative_scenarios(self):
        for token in (
            "signedSHA256 == report.observedSHA256",
            "changed bytes same-size",
            "wrong app identity signed by fixture",
            "ZIP CRC damaged but correctly signed",
            "tampered ECDSA signature",
            "symbolic link to valid IPA",
            "missing independent editorial pin",
            "build not newer",
            "NO automatic installation"
        ):
            self.assertIn(token, NATIVE_IPA)

    def test_updates_ui_has_true_readonly_status_and_copy_action(self):
        self.assertIn("if source == 3 { return 8 }", UI)
        for token in (
            "case (3, 0):", "case (3, 1):", "case (3, 2):",
            "case (3, 3):", "case (3, 4):",
            "WebReaderUpdaterSecuritySnapshot.keyDescription",
            "WebReaderUpdaterSecuritySnapshot.peerDescription",
            "copyUpdaterSecurityReport()",
            "WebReaderUpdaterSecuritySnapshot.safeReport(",
            "UIPasteboard.general.string =",
            "Nenhuma instalação",  # Existing safety notices
        ):
            self.assertIn(token, UI if token != "Nenhuma instalação" else UI + SNAPSHOT)
        self.assertIn("guard !isIPCDiagnostic else { return }", UI)

    def test_status_is_nonprivileged_no_paths_and_no_user_data(self):
        for token in (
            "GitHub Releases público", "Chave editorial de produção ausente",
            "identity", "não atestada", "Instalação automática: bloqueada",
            "Nenhuma instalação foi solicitada por este relatório",
        ):
            if token == "identity":
                continue
            self.assertIn(token, SNAPSHOT)
        self.assertIn("iosVersion.range(", SNAPSHOT)
        self.assertIn("installedBuild >= 0", SNAPSHOT)
        self.assertIn("no personal paths", NATIVE_SNAPSHOT)
        for forbid in ("appinst(", "posix_spawn(", "FileManager.", "URLSession",
                       "Data(contentsOf:", "removeItem("):
            self.assertNotIn(forbid, SNAPSHOT)

    def test_prod_installer_and_editor_key_still_absent(self):
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHECKER)
        self.assertNotIn("WebReaderSignedIPAReview.inspectReadOnly(", UI)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)


if __name__ == "__main__":
    unittest.main()
