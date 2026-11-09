#!/usr/bin/env python3
"""Build69 BH: strict offline reading never invents missing page positions."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
CHAPTER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
INVENTORY = (ROOT / "MangaReader12/Downloads/WebReaderOfflinePageInventory.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()


class OfflineIntegrityRegression(unittest.TestCase):
    def test_native_inventory_build_wired_and_existing_reader_calls_it(self):
        self.assertEqual(PROJECT.count("WebReaderOfflinePageInventory.swift in Sources"), 2)
        self.assertIn(
            "A20000000000000000000044 /* WebReaderOfflinePageInventory.swift */,",
            PROJECT
        )
        self.assertIn(
            "A10000000000000000000044 /* WebReaderOfflinePageInventory.swift in Sources */,",
            PROJECT
        )
        pages = CHAPTER.split("func localPages(", 1)[1].split("func remove(", 1)[0]
        self.assertIn("WebReaderOfflinePageInventory.inspect(", pages)
        self.assertIn("throw ChapterDownloadError.missingCompletedFiles", pages)
        self.assertIn("try? repository.rebindCompletedPath(", pages)
        self.assertLess(
            pages.index("WebReaderOfflinePageInventory.inspect("),
            pages.index("repository.rebindCompletedPath(")
        )
        self.assertIn("return files.enumerated().map", pages)
        self.assertNotIn("contentsOfDirectory(", pages)
        self.assertNotIn("removeItem(", pages)
        self.assertNotIn("URLSession(", pages)

    def test_contiguous_regular_nonempty_page_filenames_required(self):
        self.assertIn('String(format: "page-%05d.bin", index)', INVENTORY)
        self.assertIn("file.lastPathComponent == expected", INVENTORY)
        self.assertIn(".isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey", INVENTORY)
        self.assertIn("meta.isSymbolicLink != true, meta.isRegularFile == true", INVENTORY)
        self.assertIn("byteCount > 0", INVENTORY)
        self.assertIn("folder.isSymbolicLink != true", INVENTORY)
        self.assertIn("files.count <= maximumPages", INVENTORY)
        self.assertIn("static let maximumPages = 99_999", INVENTORY)
        self.assertIn("throw AuditError.incompletePages", INVENTORY)
        for forbidden in ("removeItem(", "createDirectory(", "write(to:", "URLSession",
                          "sqlite3_", "Process(", "appinst(", "UserDefaults"):
            self.assertNotIn(forbidden, INVENTORY)

    def test_error_does_not_claim_image_decode(self):
        self.assertIn("image integrity still requires opening the reader offline", INVENTORY)
        self.assertNotIn("UIImage", INVENTORY)
        self.assertNotIn("CGImage", INVENTORY)


if __name__ == "__main__":
    unittest.main()
