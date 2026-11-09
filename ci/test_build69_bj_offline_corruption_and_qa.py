#!/usr/bin/env python3
"""Build69 BJ: preserve offline data on corrupted page inventories."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
DOWNLOADS_UI = (ROOT / "MangaReader12/UI/DownloadsViewController.swift").read_text()
CHECKLIST = (ROOT / "MangaReader12/Core/WebReaderPhysicalQAChecklist.swift").read_text()


class CompletedOfflineCorruptionRegression(unittest.TestCase):
    def test_missing_completed_folder_is_an_error_not_network_fallback(self):
        pages = MANAGER.split("func localPages(", 1)[1].split("func remove(", 1)[0]
        self.assertIn("record.state == \"completed\"", pages)
        self.assertIn("guard fileManager.fileExists(atPath: directory.path) else {", pages)
        self.assertIn("throw ChapterDownloadError.missingCompletedFiles", pages)
        self.assertIn("WebReaderOfflinePageInventory.inspect(", pages)
        self.assertNotIn("URLSession", pages)
        self.assertNotIn("removeItem(", pages)
        self.assertNotIn("createDirectory(", pages)
        self.assertNotIn("request(", pages)
        self.assertIn("Nenhum arquivo foi apagado", MANAGER)

    def test_downloads_reader_shows_non_destructive_incomplete_warning(self):
        self.assertIn("catch ChapterDownloadError.missingCompletedFiles {", DOWNLOADS_UI)
        self.assertIn("Capítulo offline incompleto", DOWNLOADS_UI)
        self.assertIn("Nenhum arquivo foi apagado", DOWNLOADS_UI)
        self.assertIn("Não restaure o backup", DOWNLOADS_UI)
        self.assertIn("Não carregar o JavaScript", DOWNLOADS_UI.replace(
            "Do not load the JavaScript", "Não carregar o JavaScript"
        ))
        offline = DOWNLOADS_UI.split(
            "A completed download is an independent local reading entry point.", 1
        )[1].split("private func stateText(", 1)[0]
        self.assertIn("manager.localPages(", offline)
        self.assertNotIn("WebReaderAppinstSocket.install(", offline)
        self.assertNotIn("removeItem(", offline)

    def test_16_unanswered_qa_checks_are_practical(self):
        self.assertEqual(CHECKLIST.count("[SIM/NÃO/NÃO TESTADO]"), 16)
        self.assertIn("Amostra offline: arquivos sequenciais", CHECKLIST)
        self.assertIn("Páginas dos capítulos offline pré-existentes carregam integralmente?", CHECKLIST)
        self.assertIn("Fechou/reabriu o app ainda offline", CHECKLIST)
        self.assertIn("Evitou restaurar backup por cima", CHECKLIST)
        self.assertNotIn("WebReaderAppinstSocket.install(", CHECKLIST)


if __name__ == "__main__":
    unittest.main()
