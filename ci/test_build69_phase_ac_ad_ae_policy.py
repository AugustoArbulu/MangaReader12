#!/usr/bin/env python3
"""Build69 AC/AD/AE: harden checksums, whole-CDN response and owner QA UX."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
STAGER = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
REPORT = (ROOT / "MangaReader12/Core/WebReaderPhysicalQAChecklist.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
LOCAL = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
NATIVE = (ROOT / "ci/test_native_webreader_ipa_stager.py").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
CHANNEL = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()


class Build69SecurityRegression(unittest.TestCase):
    def test_copying_local_sha_is_never_a_stale_snapshot(self):
        body = UI.split("private func copyLocalIPAHash() {", 1)[1].split(
            "private func discardLocalIPA()", 1
        )[0]
        for marker in (
            "manualReviewInProgress = true",
            "WebReaderLocalIPAReviewer.recheck(",
            "receipt, installedBuild: currentBuild",
            "guard verified else {",
            "WebReaderLocalIPAReviewer.discard(receipt)",
            "self.manualIPAReview = nil",
            "SHA-256 não copiado",
            "guard self.view.window != nil",
            "UIPasteboard.general.string = receipt.expectedSHA256",
        ):
            self.assertIn(marker, body)
        self.assertLess(
            body.index("WebReaderLocalIPAReviewer.recheck("),
            body.index("UIPasteboard.general.string = receipt.expectedSHA256"),
        )
        self.assertLess(
            body.index("guard verified else {"),
            body.index("UIPasteboard.general.string = receipt.expectedSHA256"),
        )

    def test_receipts_and_shares_use_same_fd_auditor(self):
        for name in ("copyStagedIPAReceipt()", "shareStagedIPA("):
            self.assertIn(name, UI)
        self.assertIn("WebReaderNativeIPAAuditor.inspect(", UI)
        self.assertIn("WebReaderLocalIPAReviewer.recheck(", LOCAL + UI)
        self.assertIn("O_NOFOLLOW | O_NONBLOCK", LOCAL)

    def test_cdn_redirects_require_get_and_no_credentials(self):
        segment = STAGER.split("willPerformHTTPRedirection response:", 1)[1].split(
            "didReceive response: URLResponse", 1
        )[0]
        for marker in (
            "components.scheme == \"https\"",
            "components.port == nil, components.fragment == nil",
            "request.httpMethod == \"GET\", request.httpBody == nil",
            "request.value(forHTTPHeaderField: \"Authorization\") == nil",
            "request.value(forHTTPHeaderField: \"Cookie\") == nil",
            "release-assets.githubusercontent.com",
            "objects.githubusercontent.com",
            "redirectCount <= 2",
        ):
            self.assertIn(marker, segment)

    def test_cdn_body_must_be_untransformed_full_archive(self):
        segment = STAGER.split("didReceive response: URLResponse", 1)[1].split(
            "didReceive data: Data", 1
        )[0]
        for marker in (
            "http.statusCode == 200",
            "Content-Encoding", "Content-Range",
            'encoding == nil || encoding == "identity"',
            "finish(.failed(.unexpectedContentType))",
            "response.expectedContentLength <= update.ipaSize",
        ):
            self.assertIn(marker, segment)
        self.assertIn("response.allHeaderFields", STAGER)
        self.assertNotIn("http.value(forHTTPHeaderField:", STAGER)
        for marker in (
            'IPAStubProtocol.contentEncoding = "gzip"',
            'IPAStubProtocol.contentRange = "bytes 0-10/100"',
            "normal full untransformed IPA should still work",
        ):
            self.assertIn(marker, NATIVE)

    def test_forward_only_staging_rechecks_current_build(self):
        stage = STAGER.split("func stage(completion", 1)[1].split(
            "func cancel()", 1
        )[0]
        for marker in (
            "testProtocolClasses == nil ? nil : testInstalledBuild",
            "let currentBuild = testInstalledBuild ?? bundleBuild",
            "update.build > currentBuild",
            "callback(.failed(.notNewerThanInstalled))",
        ):
            self.assertIn(marker, STAGER)
        self.assertLess(stage.index("update.build > currentBuild"),
                        stage.index("let staging = destinationDirectory"))
        self.assertIn(
            "Build anterior ou igual à instalada • download bloqueado", UI
        )
        self.assertIn(
            "replayed/downgrade candidates zero GET", NATIVE
        )

    def test_refresh_cannot_discard_active_download_reference(self):
        self.assertIn("!isIPCDiagnostic, !checking, !signedChannelBusy,", UI)
        self.assertIn("!stagingIPA, !verifyingExport", UI)

    def test_qa_checklist_is_compiled_and_only_manual(self):
        name = "WebReaderPhysicalQAChecklist.swift"
        self.assertEqual(PROJECT.count(f"{name} in Sources"), 2)
        self.assertIn(f"A20000000000000000000041 /* {name} */,", PROJECT)
        self.assertIn(f"A10000000000000000000041 /* {name} in Sources */,", PROJECT)
        self.assertIn("if source == 3 { return 8 }", UI)
        self.assertIn("case (3, 5):", UI)
        self.assertIn("Copiar roteiro de testes físicos", UI)
        self.assertIn("WebReaderPhysicalQAChecklist.report(", UI)
        self.assertIn("guard !isIPCDiagnostic", UI)
        self.assertIn("[SIM/NÃO/NÃO TESTADO]", REPORT)
        self.assertIn("não é diagnóstico automático", REPORT)
        self.assertIn("Este roteiro não executa downloads", REPORT)
        for forbidden in ("FileManager.", "URLSession", "UserDefaults",
                          "Documents/", "removeItem(", "appinst(", "posix_spawn("):
            self.assertNotIn(forbidden, REPORT)

    def test_production_installer_still_default_deny_and_stable_identity(self):
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHANNEL)
        self.assertEqual(PROJECT.count("CURRENT_PROJECT_VERSION = 56;"), 2)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)


if __name__ == "__main__":
    unittest.main()
