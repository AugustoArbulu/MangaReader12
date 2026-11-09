#!/usr/bin/env python3
"""Build69 BD native-app read-only library continuity wiring safety policy."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
SNAP = (ROOT / "MangaReader12/Core/WebReaderUpgradeContinuitySnapshot.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()


class UpgradeContinuityContract(unittest.TestCase):
    def test_compiled_and_integrated_only_for_full_webreader_screen(self):
        self.assertEqual(PROJECT.count("WebReaderUpgradeContinuitySnapshot.swift in Sources"), 2)
        self.assertIn(
            "A20000000000000000000043 /* WebReaderUpgradeContinuitySnapshot.swift */,",
            PROJECT
        )
        self.assertIn(
            "A10000000000000000000043 /* WebReaderUpgradeContinuitySnapshot.swift in Sources */,",
            PROJECT
        )
        self.assertIn("if source == 3 { return 8 }", UI)
        self.assertIn("case (3, 6):", UI)
        self.assertIn('Copiar contagens da biblioteca para comparar', UI)
        self.assertIn("if selectedSection == 3, indexPath.row == 6, !isIPCDiagnostic {", UI)
        self.assertIn("private func copyUpgradeContinuitySnapshot()", UI)
        self.assertIn("guard !isIPCDiagnostic else { return }", UI)
        self.assertIn("WebReaderUpgradeContinuitySnapshot.report(", UI)
        self.assertIn("UIPasteboard.general.string = report", UI)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)

    def test_actual_query_open_is_readonly_and_no_migration(self):
        self.assertIn("SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX", SNAP)
        self.assertIn('sqlite3_db_readonly(opened, "main") == 1', SNAP)
        self.assertIn("PRAGMA user_version;", SNAP)
        self.assertIn("version == Int64(expectedSchema)", SNAP)
        self.assertIn("static let expectedSchema = 1", SNAP)
        self.assertIn("Banco: INDISPONÍVEL", SNAP)
        self.assertIn("NÃO páginas verificadas", SNAP)
        self.assertIn("Wi-Fi DESLIGADO", SNAP)
        self.assertIn("O backup .mr12backup NÃO inclui imagens", SNAP)
        for forbidden in (
            "UserDefaults", "URLSession", "Process(", "appinst(", "posix_spawn(",
            "sqlite3_exec(", "SQLITE_OPEN_CREATE", "SQLITE_OPEN_READWRITE",
            "openAndMigrate(", "createDirectory(", "removeItem(",
            "UPDATE ", "INSERT ", "DELETE ", "DROP TABLE", "ALTER TABLE",
            "SELECT *", "local_path", "title FROM", "source_manga_id"
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, SNAP)

    def test_bounded_queries_never_contain_private_strings(self):
        self.assertEqual(SNAP.count("SELECT COUNT(*)"), 9)
        self.assertIn("Downloads marcados completos no banco", SNAP)
        self.assertIn("Categorias", SNAP)
        self.assertIn("Obras na biblioteca", SNAP)
        self.assertIn("last_page_read > 0", SNAP)
        self.assertIn("is_read = 1", SNAP)
        self.assertIn("bookmarked = 1", SNAP)


if __name__ == "__main__":
    unittest.main()
