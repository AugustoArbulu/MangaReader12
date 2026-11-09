#!/usr/bin/env python3
"""Build69 BS: fail before filesystem operations on chapters >5000 pages."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
RESUME = (ROOT / "MangaReader12/Downloads/WebReaderOfflineResumePrefix.swift").read_text()


class MaxPagesAdmission(unittest.TestCase):
    def test_download_rejects_before_queue_or_folder_changes(self):
        body = MANAGER.split("    func download(\n", 1)[1].split(
            "    // Returns false for a job left over", 1
        )[0]
        guard = "guard pages.count <= WebReaderOfflineResumePrefix.maximumPlannedPages"
        self.assertIn(guard, body)
        self.assertIn("ChapterDownloadError.tooManyPages", body)
        self.assertLess(body.index(guard), body.index("worker.async {"))
        self.assertLess(body.index(guard), body.index("removeItem(at: directory)"))
        self.assertLess(body.index(guard), body.index("createDirectory("))
        self.assertIn("maximumPlannedPages = 5_000", RESUME)

    def test_defense_in_depth_before_encoding_plan(self):
        save = MANAGER.split("private func savePlan(for job:", 1)[1].split(
            "private func completedPagePrefix(", 1
        )[0]
        self.assertIn("guard job.pages.count > 0", save)
        self.assertIn("job.pages.count <= WebReaderOfflineResumePrefix.maximumPlannedPages", save)
        self.assertIn("throw ChapterDownloadError.tooManyPages", save)
        self.assertLess(save.index("throw ChapterDownloadError.tooManyPages"),
                        save.index("JSONEncoder().encode(plan)"))
        self.assertLess(save.index("JSONEncoder().encode(plan)"),
                        save.index("WebReaderOfflineRecoveryPlanWriter.write("))

    def test_operator_readable_error_no_data_deletion_instruction(self):
        self.assertIn("case tooManyPages", MANAGER)
        self.assertIn("case .tooManyPages:", MANAGER)
        self.assertIn("limite de 5.000 páginas", MANAGER)
        self.assertIn("Nenhum arquivo foi modificado", MANAGER)


if __name__ == "__main__":
    unittest.main()
