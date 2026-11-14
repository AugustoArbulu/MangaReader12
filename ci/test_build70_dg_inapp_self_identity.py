#!/usr/bin/env python3
"""Phase DG: WebReader in-app SELF UID/GID report wiring, host-only.

Ensures a user-triggered read-only row in the existing Security section.
No helper, IPC peer, sandbox entitlement or root identity is established,
and the production installer / publisher switches stay disabled.
The tests do not execute iOS UIKit; the macOS CI builds the full app.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
UI_FILE = ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift"


def segment_between(text, start, end):
    if text.count(start) != 1 or text.count(end) != 1:
        raise AssertionError("could not isolate one diagnostic method")
    return text.split(start, 1)[1].split(end, 1)[0]


class DGSelfProcessIdentityUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.screen = UI_FILE.read_text(encoding="utf-8")
        cls.method = segment_between(
            cls.screen,
            "private func copyOwnProcessIdentityReport() {",
            "// MARK: - Release download cache",
        )

    def test_darwin_apis_available_in_ios_12_source(self):
        self.assertIn("import UIKit\nimport Darwin\n", self.screen)
        for expr in ("Darwin.getuid()", "Darwin.geteuid()",
                     "Darwin.getgid()", "Darwin.getegid()"):
            with self.subTest(expr=expr):
                self.assertEqual(self.method.count(expr), 1)

    def test_security_section_has_ninth_row_without_changing_other_tabs(self):
        self.assertIn("return isIPCDiagnostic ? 2 : 7", self.screen)
        self.assertIn("if source == 3 { return 9 }", self.screen)
        self.assertIn("if source == 6 { return 8 }", self.screen)
        self.assertIn("if source == 5 { return build60DisposableAvailable ? 6 :", self.screen)
        self.assertIn("if source == 2 { return availableUpdate != nil ? 6 : 1 }", self.screen)

    def test_security_row_is_descriptive_and_copy_only(self):
        self.assertEqual(self.screen.count("case (3, 8):"), 1)
        self.assertIn('"Copiar identidade do processo WebReader"', self.screen)
        self.assertIn("UID e GID do próprio app", self.screen)
        self.assertIn("cell.accessoryType = .disclosureIndicator", self.screen)

    def test_tap_dispatch_is_guarded_and_only_calls_self_report(self):
        self.assertIn(
            "if selectedSection == 3, indexPath.row == 8, !isIPCDiagnostic {",
            self.screen,
        )
        self.assertEqual(self.screen.count("            copyOwnProcessIdentityReport()\n"), 1)
        self.assertIn("guard !isIPCDiagnostic else { return }", self.method)

    def test_report_captures_actual_current_process_without_user_inputs(self):
        for field in ("APP_SELF_UID=", "APP_SELF_EUID=",
                      "APP_SELF_GID=", "APP_SELF_EGID="):
            self.assertIn('"' + field + '"', self.method)
        self.assertIn('String(installedBuild)', self.method)
        self.assertIn("ProcessInfo.processInfo.operatingSystemVersion", self.method)
        self.assertIn('"APP_SELF_IDENTITY_SCOPE=SELF_ONLY"', self.method)

    def test_report_is_copied_to_clipboard_only_after_user_tap(self):
        self.assertIn('UIPasteboard.general.string = lines.joined(separator: "\\n")', self.method)
        self.assertIn("let alert = UIAlertController(", self.method)
        self.assertIn("title: \"Identidade do app copiada\"", self.method)
        self.assertIn("present(alert, animated: true)", self.method)
        self.assertNotIn("viewDidLoad(", self.method)
        self.assertNotIn("viewDidAppear(", self.method)

    def test_no_claim_that_helper_or_sandbox_was_verified(self):
        for exact in (
            '"HELPER_PROCESS_IDENTITY=NOT_TESTED"',
            '"IPC_PEER_AUTHENTICATED=NO"',
            '"IOS12_SANDBOX_SEPARATION_PROVEN=NO"',
            '"APP_WRITE_DENIAL_TO_HELPER_VAULT_PROVEN=NO"',
            '"PUBLISHER_TRUST_CONFIGURED=NO"',
            '"INSTALLATION_AUTHORIZED=NO"',
            '"INSTALLATION_ATTEMPTED=NO"',
        ):
            with self.subTest(line=exact):
                self.assertIn(exact, self.method)
        self.assertNotIn("=YES", self.method)

    def test_no_private_data_file_paths_or_in_app_network(self):
        prohibited = (
            "URLSession", "URLRequest(", "Data(contentsOf:",
            "FileManager", "UserDefaults", "Process(", "posix_spawn(",
            "socket(", "connect(", "appinst(", "installApplication:",
            "Library", "Documents", "Containers/Data", "stat(", "lstat(",
            "getpeereid(", "sysctl(", "setuid(", "setgid(", "kill(",
            "getpid(", "getppid(", "dlopen(", "chmod(", "chown(",
        )
        for token in prohibited:
            with self.subTest(token=token):
                self.assertNotIn(token, self.method)

    def test_production_install_hard_stop_preserved(self):
        socket = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
        channel = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
        editorial = (ROOT / "MangaReader12/Core/WebReaderProductionPublisherTrust.swift").read_text()
        self.assertIn("static let liveInstallationEnabled = false", socket)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", channel)
        self.assertIn("static let independentlyProvisionedSPKISHA256: String? = nil", editorial)
        self.assertNotIn("WebReaderAppinstSocket.install(", self.screen)

    def test_no_new_xcode_project_file_or_extra_entitlement(self):
        pbxproj = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
        self.assertEqual(pbxproj.count("WebReaderAppUpdatesViewController.swift in Sources"), 2)
        self.assertIn("WebReaderAppUpdatesViewController.swift", pbxproj)
        self.assertNotIn("WebReaderProcessIdentity.entitlements", pbxproj)

    def test_offline_preservation_and_legacy_updater_rows_remain(self):
        self.assertIn("copyUpgradeContinuitySnapshot()", self.screen)
        self.assertIn("copyOfflinePresenceAudit()", self.screen)
        self.assertIn("Instalação pelo Chimera bloqueada", self.screen)
        self.assertIn('"Copiar diagnóstico de segurança"', self.screen)
        self.assertIn('"Copiar roteiro de testes físicos"', self.screen)
        self.assertIn('"Copiar contagens da biblioteca para comparar"', self.screen)
        self.assertIn('"Conferir presença dos capítulos offline"', self.screen)


if __name__ == "__main__":
    unittest.main()
