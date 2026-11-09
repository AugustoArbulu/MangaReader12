#!/usr/bin/env python3
"""Build69 BI: offline presence audit is bounded, readonly and private."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
AUDIT = (ROOT / "MangaReader12/Core/WebReaderOfflinePreservationAudit.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()


class OfflinePresenceSafety(unittest.TestCase):
    def test_native_compilation_and_nonblocking_owner_ui(self):
        self.assertEqual(PROJECT.count("WebReaderOfflinePreservationAudit.swift in Sources"), 2)
        self.assertIn("A20000000000000000000045 /* WebReaderOfflinePreservationAudit.swift */,", PROJECT)
        self.assertIn("A10000000000000000000045 /* WebReaderOfflinePreservationAudit.swift in Sources */,", PROJECT)
        self.assertIn("if source == 3 { return 8 }", UI)
        self.assertIn("case (3, 7):", UI)
        self.assertIn("Conferir presença dos capítulos offline", UI)
        self.assertIn("if selectedSection == 3, indexPath.row == 7, !isIPCDiagnostic", UI)
        self.assertIn("private func copyOfflinePresenceAudit()", UI)
        self.assertIn("guard !isIPCDiagnostic, !offlinePresenceBusy else { return }", UI)
        body = UI.split("private func copyOfflinePresenceAudit() {", 1)[1].split(
            "private func copyUpgradeContinuitySnapshot()", 1
        )[0]
        self.assertLess(body.index("DispatchQueue.global(qos: .utility)"),
                        body.index("WebReaderOfflinePreservationAudit.diagnostic("))
        self.assertLess(body.index("WebReaderOfflinePreservationAudit.diagnostic("),
                        body.index("DispatchQueue.main.async"))
        self.assertLess(body.index("DispatchQueue.main.async"),
                        body.index("UIPasteboard.general.string = report"))
        self.assertIn("guard self.view.window != nil else { return }", body)
        self.assertIn("Lote de até 64 capítulos copiado", body)

    def test_readonly_bounded_db_and_paths(self):
        for literal in (
            "private static let sampleLimit = 64",
            "SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX",
            'sqlite3_db_readonly(conn, "main") == 1',
            "BEGIN DEFERRED;",
            "ROLLBACK;",
            "PRAGMA user_version;",
            "LIMIT ? OFFSET ?;",
            "sqlite3_bind_int64(prepared, 1, Int64(sampleLimit))",
            "sqlite3_bind_int64(prepared, 2, offset)",
            "sqlite3_busy_timeout(conn, 200)",
            "OfflineDownloadPath.chapterDirectory(",
            "WebReaderOfflinePageInventory.inspect(",
            "sqlite3_column_bytes(stmt, column)",
            "count <= 2048",
            "Capítulos fora da amostra:",
            "NÃO comprova imagem íntegra",
            "Sem títulos, IDs, caminhos, imagens ou consultas à rede.",
        ):
            self.assertIn(literal, AUDIT)
        for forbidden in (
            "removeItem(", "createDirectory(", "write(to:", "URLSession",
            "SQLITE_OPEN_READWRITE", "SQLITE_OPEN_CREATE",
            "UPDATE ", "INSERT ", "DELETE ", "DROP TABLE",
            "UserDefaults", "appinst(", "posix_spawn(", "shell(",
        ):
            self.assertNotIn(forbidden, AUDIT)
        self.assertNotIn("d.local_path", AUDIT)
        self.assertNotIn("SELECT *", AUDIT)

    def test_no_claim_of_full_image_integrity(self):
        self.assertIn("não faz download", AUDIT)
        self.assertIn("Teste a leitura REAL sem Wi-Fi", AUDIT)
        self.assertIn("nenhuma página foi modificada", AUDIT.lower())


if __name__ == "__main__":
    unittest.main()
