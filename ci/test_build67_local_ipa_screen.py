#!/usr/bin/env python3
"""Build67 local Files/Filza QA screen policy: no silent installation."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
STAGING = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
MANIFEST = (ROOT / "MangaReader12/Core/WebReaderUpdateManifestVerifier.swift").read_text()


class LocalIPAScreenContractTests(unittest.TestCase):
    def test_document_picker_only_after_user_action(self):
        for expected in (
            "UIDocumentPickerDelegate",
            "UIDocumentPickerViewController(",
            'documentTypes: ["public.data"], in: .import',
            "func documentPicker(",
            "didPickDocumentsAt urls: [URL]",
            "promptLocalIPAImport()",
            "Selecionar IPA",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, UI)

    def test_not_available_to_ipc_probe(self):
        self.assertIn("return isIPCDiagnostic ? 2 : 7", UI)
        self.assertIn("guard !isIPCDiagnostic", UI)
        self.assertIn("case 6: return", UI)

    def test_hash_and_build_user_consent(self):
        self.assertIn('of: "^[1-9][0-9]{0,8}$"', UI)
        self.assertIn('of: "^[0-9a-f]{64}$"', UI)
        self.assertIn("build > self.installedBuild", UI)
        self.assertIn("manualExpectedSHA256 = rawSHA", UI)
        self.assertIn("expectedBuild: expectedBuild", UI)
        self.assertIn("expectedSHA256: expectedSHA", UI)

    def test_private_release_metadata_not_reclassified(self):
        self.assertIn("case manualLocalFile", MANIFEST)
        self.assertIn("expected.provenance = .manualLocalFile", STAGING)
        self.assertIn("update.provenance == .publicGitHubRelease", UI)

    def test_not_publisher_authentication(self):
        self.assertIn("publisherAuthenticated: Bool = false", STAGING)
        self.assertIn("installationAuthorized: Bool = false", STAGING)
        self.assertIn("installationPerformed: Bool = false", STAGING)
        self.assertIn("NÃO autentica o editor nem instala", UI)
        self.assertIn("NÃO autentica o publicador", UI)

    def test_app_support_isolated_from_library(self):
        self.assertIn('appendingPathComponent("WebReaderLocalQAImports"', STAGING)
        self.assertNotIn("LibraryBackup", STAGING)
        self.assertNotIn("removeItem(at: sourceURL)", STAGING)
        self.assertIn("Darwin.openat(", STAGING)
        self.assertIn("Darwin.read(sourceFD", STAGING)
        self.assertIn("Darwin.write(", STAGING)
        self.assertIn("directory.standardizedFileURL", STAGING)

    def test_native_verifier_and_recheck(self):
        self.assertIn("WebReaderNativeIPAAuditor.inspect(", STAGING)
        self.assertIn("WebReaderLocalIPAReviewer.recheck(", UI)
        self.assertIn("WebReaderLocalIPAReviewer.importForReview(", UI)
        self.assertIn("WebReaderLocalIPAReviewer.discard(", UI)
        self.assertIn("manualReviewInProgress", UI)
        self.assertIn("manualImportInProgress", UI)

    def test_file_size_limit_and_atomic_cleanup(self):
        self.assertIn("512 * 1024 * 1024", STAGING)
        self.assertIn("if ownsTemporary && !keep", STAGING)
        self.assertIn("Darwin.unlinkat(dirFD, fileName, 0)", STAGING)
        self.assertIn("Darwin.fstat(sourceFD, &original)", STAGING)
        self.assertIn("Darwin.fstat(outputFD, &destinationAfter)", STAGING)

    def test_storage_budget_and_safe_copy_permissions(self):
        for text in (
            "requiredFreeBytes(ipaBytes:",
            "hasEnoughSpace(freeBytes:",
            "free.int64Value",
            "case insufficientSpace",
            "Darwin.openat(",
            "Darwin.fstat(dirFD, &dirInfo)",
            "mode_t(S_IFDIR)",
            "O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW",
            "fm.copyItem(at: sourceURL, to: saved)",
            "Darwin.fchmod(outputFD, mode_t(0o600))",
            "if !keep { try? fm.removeItem(at: saved) }",
        ):
            with self.subTest(text=text):
                self.assertIn(text, STAGING)

    def test_distinct_low_storage_user_feedback(self):
        self.assertIn("catch WebReaderLocalIPAReviewError.insufficientSpace", UI)
        self.assertIn("Espaço insuficiente para copiar a IPA", UI)
        self.assertIn("IPA excede o limite de 512 MB", UI)
        self.assertIn("Não foi possível criar a cópia local de QA", UI)
        self.assertIn("self.manualImportStatus = failureReason", UI)
        self.assertIn("let old = self.manualIPAReview", UI)

    def test_no_privileged_install_or_external_network(self):
        for forbidden in (
            "appinst(", "/usr/bin/appinst", "posix_spawn(", "Process(",
            "system(", "launchctl", "curl ", "URLSession.shared.downloadTask",
            "setuid(", "setgid(", "rm -rf", "UserDefaults.standard.set",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, STAGING)
                self.assertNotIn(forbidden, UI)

    def test_manual_sharing_only(self):
        self.assertIn("UIActivityViewController(", UI)
        self.assertIn("activityItems: [receipt.copiedIPAURL]", UI)
        self.assertIn("if source == 6 { return 4 }", UI)
        self.assertIn("copyLocalIPAHash()", UI)
        self.assertIn("UIPasteboard.general.string = receipt.expectedSHA256", UI)
        self.assertIn("Cópia de QA descartada; a biblioteca permanece intacta", UI)
        self.assertIn("section: 6", UI)

    def test_no_credentials_required_or_saved(self):
        self.assertNotIn("GitHub Token", UI)
        self.assertNotIn("personal access token", UI)
        self.assertNotIn("Authorization: Bearer", UI)

    def test_online_installer_deny_still_present(self):
        self.assertIn("Instalação pelo Chimera bloqueada", UI)
        self.assertIn("static let", (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text())
        self.assertIn("static let liveInstallationEnabled = false",
                      (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text())


if __name__ == "__main__":
    unittest.main()
