#!/usr/bin/env python3
"""Build69 AZ: backup restore must obtain final destructive consent first.

Static source regression only: validates the actual iOS12 UIKit call path.
No backup opened, no live database, no downloads removed, no app installed.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
BACKUP_UI = (ROOT / "MangaReader12/UI/BackupViewController.swift").read_text()
BACKUP = (ROOT / "MangaReader12/Core/BackupManager.swift").read_text()
UPDATES = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
QA = (ROOT / "MangaReader12/Core/WebReaderPhysicalQAChecklist.swift").read_text()


class DestructiveRestoreRequiresConsent(unittest.TestCase):
    def test_confirm_before_any_portable_restore(self):
        self.assertEqual(BACKUP_UI.count("manager.restoreBackup(from: url)"), 1)
        selected = BACKUP_UI.split("didPickDocumentsAt urls: [URL]", 1)[1]
        confirmation = selected.split("private func performSelectedBackupRestore(from url: URL)", 1)[0]
        restore = selected.split("private func performSelectedBackupRestore(from url: URL)", 1)[1]
        for text in (
            "restoreConfirmationPending = true",
            'title: "Restaurar backup e remover downloads?"',
            "APAGA os capítulos",
            "baixados offline",
            "não restaure o backup",
            'title: "Cancelar", style: .cancel',
            'title: "Restaurar e apagar downloads", style: .destructive',
            "self.performSelectedBackupRestore(from: url)",
        ):
            self.assertIn(text, confirmation, text)
        self.assertNotIn("manager.restoreBackup(from: url)", confirmation)
        self.assertIn("manager.restoreBackup(from: url)", restore)
        self.assertLess(
            confirmation.index("warning.addAction(UIAlertAction("),
            confirmation.index("self.performSelectedBackupRestore(from: url)")
        )
        self.assertIn("guard !restoring, !restoreConfirmationPending else { return }", BACKUP_UI)
        self.assertIn("restoreConfirmationPending = false", confirmation)

    def test_current_portable_backup_does_not_serialize_download_pages(self):
        self.assertIn("static let formatVersion = 1", BACKUP)
        self.assertIn("DELETE FROM downloads;", BACKUP)
        self.assertIn("UPDATE chapters SET downloaded = 0;", BACKUP)
        self.assertIn("try clearExcludedDownloadFiles()", BACKUP)
        self.assertIn("try fileManager.removeItem(at: downloads)", BACKUP)
        self.assertIn("try sanitizePortableSnapshot(at: snapshotURL)", BACKUP)
        self.assertIn("Backup não inclui páginas offline", BACKUP_UI)
        self.assertIn("restaurar remove downloads existentes", BACKUP_UI)

    def test_manual_filza_guidance_preserves_installation_and_warns_of_restore(self):
        instructions = UPDATES.split("private func showFilzaInstructions() {", 1)[1].split(
            "private func shareStagedIPA(", 1
        )[0]
        self.assertIn("Não remova o WebReader instalado", instructions)
        self.assertIn("NÃO inclui", instructions)
        self.assertIn("Restaurar o backup apaga downloads", instructions)
        self.assertIn("instale por cima sem restaurar", instructions)
        self.assertNotIn("appinst(", instructions)
        self.assertNotIn("removeItem(", instructions)
        self.assertNotIn("WebReaderAppinstSocket.install(", instructions)

    def test_physical_qa_is_never_preapproved(self):
        self.assertIn("A instalação foi feita manualmente pelo Filza?", QA)
        self.assertIn("Instalou por cima, sem remover", QA)
        self.assertIn("Fechou/reabriu o app ainda offline", QA)
        self.assertIn("Amostra offline: arquivos sequenciais", QA)
        self.assertIn("carregam integralmente?", QA)
        self.assertIn(".mr12backup NÃO inclui páginas offline", QA)
        self.assertIn("RESTAURAR backup limpa downloads offline", QA)
        self.assertEqual(QA.count("[SIM/NÃO/NÃO TESTADO]"), 16)
        self.assertIn("não é diagnóstico automático", QA)
        self.assertNotIn("UserDefaults", QA)
        self.assertNotIn("FileManager.", QA)


if __name__ == "__main__":
    unittest.main()
