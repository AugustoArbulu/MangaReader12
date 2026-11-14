#!/usr/bin/env python3
"""Build69 BV: every destructive offline UI path requires explicit consent.

Checks both UIKit swipe-to-delete and the custom Remover row action,
plus the path for retrying old partial downloads after an interrupted app.
No test invokes a delete, network request or a privileged installation.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
UI = (ROOT / "MangaReader12/UI/DownloadsViewController.swift").read_text()
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()


class DestructiveDownloadUIContract(unittest.TestCase):
    def test_both_swipe_and_action_use_same_confirmation(self):
        direct = UI.split("commit editingStyle:", 1)[1].split(
            "editActionsForRowAt", 1
        )[0]
        self.assertIn("confirmRemoveDownload(records[indexPath.row])", direct)
        self.assertNotIn("manager.remove(", direct)
        actions = UI.split("editActionsForRowAt", 1)[1].split(
            "private func pauseDownload(", 1
        )[0]
        self.assertIn("self?.confirmRemoveDownload(record)", actions)
        self.assertNotIn("self?.removeDownload(record)", actions)
        self.assertIn("private func confirmRemoveDownload(", UI)

    def test_confirmed_delete_discloses_nonbackup_of_page_images(self):
        confirm = UI.split("private func confirmRemoveDownload(", 1)[1].split(
            "private func removeDownload(", 1
        )[0]
        for marker in (
            'title: "Apagar páginas offline?"',
            "O arquivo .mr12backup não contém essas imagens.",
            'UIAlertAction(title: "Cancelar", style: .cancel)',
            'UIAlertAction(title: "Apagar download", style: .destructive)',
            "self?.removeDownload(record)",
            "present(alert, animated: true)",
        ):
            self.assertIn(marker, confirm)
        self.assertLess(confirm.index('title: "Apagar páginas offline?"'),
                        confirm.index("self?.removeDownload(record)"))
        self.assertNotIn("manager.remove(", confirm)
        self.assertIn('current?.state != "downloading"', UI.split(
            "private func removeDownload(", 1
        )[1].split("private func retryDownload(", 1)[0])

    def test_retry_of_partials_needs_new_owner_consent(self):
        prompt = UI.split("private func retryDownload(", 1)[1].split(
            "private func beginRetryDownload(", 1
        )[0]
        for marker in (
            'title: "Reiniciar este download?"',
            "Reiniciar substitui os arquivos locais dessa tentativa.",
            "As imagens não estão incluídas no .mr12backup.",
            'UIAlertAction(title: "Cancelar", style: .cancel)',
            'UIAlertAction(title: "Reiniciar download", style: .destructive)',
            "self?.beginRetryDownload(record)",
            "present(alert, animated: true)",
        ):
            self.assertIn(marker, prompt)
        self.assertNotIn("manager.download(", prompt)
        begin = UI.split("private func beginRetryDownload(", 1)[1].split(
            "private func resolveRetryDetails(", 1
        )[0]
        self.assertIn('$0.state == "failed" || $0.state == "paused"', begin)
        self.assertIn("retryInFlight.insert(key)", begin)
        self.assertIn("retryDownload(record)", UI.split(
            "private func resumeDownload(", 1
        )[1].split("private func prioritizeDownload(", 1)[0])
        self.assertIn("if let existing = try self.repository.record(", MANAGER)
        self.assertIn('existing.state == "completed"', MANAGER)


if __name__ == "__main__":
    unittest.main()
