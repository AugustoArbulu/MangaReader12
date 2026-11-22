#!/usr/bin/env python3
"""Build69 BW: require owner consent for reindex and clearing all offline images."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
UI = (ROOT / "MangaReader12/UI/DataStorageViewController.swift").read_text()


class MaintenancePrivacyAndRetention(unittest.TestCase):
    def test_reindex_never_runs_from_unconfirmed_table_tap(self):
        selected = UI.split("didSelectRowAt indexPath: IndexPath", 1)[1].split(
            "private func performMaintenance(", 1
        )[0]
        self.assertIn("case (2, 2):", selected)
        self.assertIn("confirmReindexDownloads()", selected)
        self.assertNotIn("manager.reindexDownloads()", selected)

    def test_reindex_confirmation_explains_stale_migration_path(self):
        confirm = UI.split("private func confirmReindexDownloads() {", 1)[1].split(
            "private func confirmClearDownloads()", 1
        )[0]
        for marker in (
            'title: "Reindexar e remover registros?"',
            "um caminho antigo pode causar uma ausência aparente.",
            "Não use esta opção para tentar consertar a migração.",
            "O .mr12backup não contém páginas offline.",
            'UIAlertAction(title: "Cancelar", style: .cancel)',
            'UIAlertAction(title: "Reindexar mesmo assim", style: .destructive)',
            "try manager.reindexDownloads()",
            "present(alert, animated: true)",
        ):
            self.assertIn(marker, confirm)
        self.assertLess(confirm.index("Reindexar mesmo assim"),
                        confirm.index("try manager.reindexDownloads()"))
        self.assertEqual(UI.count("manager.reindexDownloads()"), 1)

    def test_clear_all_is_explicit_and_discloses_backup_limitation(self):
        action = UI.split("private func confirmClearDownloads() {", 1)[1].split(
            "private func refreshSnapshot()", 1
        )[0]
        for marker in (
            'title: "Apagar todos os downloads?"',
            "Todos os capítulos offline e suas imagens serão removidos.",
            "O backup .mr12backup não contém essas páginas",
            'UIAlertAction(title: "Cancelar", style: .cancel)',
            "style: .destructive",
            "try manager.clearAllDownloads()",
            "present(alert, animated: true)",
        ):
            self.assertIn(marker, action)
        self.assertLess(action.index("style: .destructive"),
                        action.index("try manager.clearAllDownloads()"))
        self.assertEqual(UI.count("manager.clearAllDownloads()"), 1)


if __name__ == "__main__":
    unittest.main()
