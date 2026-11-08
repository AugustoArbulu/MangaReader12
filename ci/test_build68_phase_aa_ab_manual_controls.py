#!/usr/bin/env python3
"""Build68 AA/AB: cancellation and integrity receipts cannot install IPAs."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
STAGER = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
AUDITOR = (ROOT / "MangaReader12/Core/WebReaderNativeIPAAuditor.swift").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
CHANNEL = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
HARNESS = (ROOT / "ci/test_native_webreader_ipa_stager.py").read_text()


class ManualUpdateControls(unittest.TestCase):
    def test_cancel_visible_and_result_distinct_from_network_failure(self):
        for token in (
            "case cancelled", "case .cancelled:",
            "Cancelar download em andamento",
            "Toque para interromper • arquivo parcial será removido",
            "stager?.cancel()", "Download cancelado • cópia parcial removida",
        ):
            with self.subTest(token=token):
                self.assertIn(token, STAGER + UI)

    def test_cancel_closes_stream_and_removes_only_its_partial_file(self):
        start = STAGER.split("    func cancel() {", 1)[1].split(
            "    // Real GitHub Releases", 1
        )[0]
        self.assertIn("active.cancel()", start)
        self.assertIn("finish(.failed(.cancelled))", start)
        finished = STAGER.split(
            "private func finish(_ result: WebReaderIPAStageResult)", 1
        )[1].split("// MARK: - iOS12 local QA", 1)[0]
        for token in (
            "let temp = partialURL", "partialURL = nil",
            "stream?.close()", "oldSession?.invalidateAndCancel()",
            "if let temp = temp { try? FileManager.default.removeItem(at: temp) }",
            "callback?(result)",
        ):
            self.assertIn(token, finished)
        self.assertNotIn("Library", finished)
        self.assertNotIn("Documents", finished)
        self.assertNotIn("appinst", finished)

    def test_native_stalled_transport_fixture_exercises_cancel(self):
        for token in (
            "keepOpenForCancel",
            "firstChunkDelivered",
            "cancelled.cancel()",
            "cancel immediately removes incomplete IPA from private staging",
            "explicit cancel misclassified as download failure",
            "cancel invokes completion even without HTTP didComplete",
        ):
            self.assertIn(token, HARNESS)

    def test_receipt_requires_reaudit_not_trust_remote_hash_blindly(self):
        for token in (
            "if source == 2 { return availableUpdate != nil ? 6 : 1 }",
            "case (2, 5):",
            "copyStagedIPAReceipt()",
            "WebReaderNativeIPAAuditor.inspect(",
            "report.verifiedSHA256 == update.sha256",
            "self.stagedIPAURL == url",
            "stagedSHA256 == update.sha256",
            "IPA local modificada; baixe novamente",
            "WebReader • recibo de integridade, NÃO de instalação",
            "Instalação automática: NÃO autorizada e NÃO realizada",
        ):
            self.assertIn(token, UI)
        self.assertIn("O_NOFOLLOW | O_NONBLOCK", AUDITOR)
        self.assertIn("let finalDigest = fileSHA256(file)", AUDITOR)

    def test_receipt_never_claims_editor_identity_or_leaks_private_paths(self):
        body = UI.split("private func copyStagedIPAReceipt() {", 1)[1].split(
            "private func runOneAppTest()", 1
        )[0]
        for token in (
            "GitHub Release público; editor NÃO autenticado",
            "arquivo pode mudar após a revisão",
            "Não substitui autenticação editorial, backup ou Filza",
            "UIPasteboard.general.string = lines.joined",
        ):
            self.assertIn(token, body)
        for prohibited in (
            'url.path', '/var/mobile/', 'WebReaderAppinstSocket.install(',
            'posix_spawn(', 'SecItemAdd(', 'productionPublicKeyX963 =',
        ):
            self.assertNotIn(prohibited, body)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHANNEL)
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)


if __name__ == "__main__":
    unittest.main()
