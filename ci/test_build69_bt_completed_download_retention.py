#!/usr/bin/env python3
"""Build69 BT: no automatic deletion of downloaded/complete old chapters."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()


class CompletedChapterRetention(unittest.TestCase):
    def test_completed_download_guard_before_any_folder_creation_or_page_replacement(self):
        body = MANAGER.split("    func download(\n", 1)[1].split(
            "    // Returns false for a job left over", 1
        )[0]
        for token in (
            "if let existing = try self.repository.record(",
            "sourceMangaID: manga.id",
            "sourceChapterID: chapter.id",
            'existing.state == "completed"',
            "throw ChapterDownloadError.alreadyCompleted",
            "existingDataPolicy == .replaceAfterExplicitUserConfirmation",
            "WebReaderPartialRetryFolderAudit.canReplace(",
        ):
            self.assertIn(token, body)
        # Folder removal is not a prerequisite for any new download.
        self.assertNotIn("removeItem(at: directory)", body)
        self.assertLess(body.index('existing.state == "completed"'),
                        body.index("WebReaderPartialRetryFolderAudit.canReplace("))
        self.assertLess(body.index("throw ChapterDownloadError.alreadyCompleted"),
                        body.index("createDirectory("))
        self.assertIn("job.state == \"completed\"", MANAGER.replace(
            "record.state == \"completed\"", "job.state == \"completed\""
        ))

    def test_error_tells_owner_to_explicitly_remove_first(self):
        self.assertIn("case alreadyCompleted", MANAGER)
        self.assertIn("case .alreadyCompleted:", MANAGER)
        self.assertIn("remova manualmente o download na área Downloads", MANAGER)
        self.assertIn("Nenhum arquivo foi apagado.", MANAGER)

    def test_explicit_legacy_remove_path_not_accidentally_disabled(self):
        self.assertIn("func remove(", MANAGER)
        self.assertIn("ChapterDownloadError.downloadInProgress", MANAGER)
        self.assertIn("func localPages(", MANAGER)


if __name__ == "__main__":
    unittest.main()
