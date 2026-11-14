#!/usr/bin/env python3
"""Build69 BO: resumed downloads reuse only safe, real, bounded page files."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
RESUME = (ROOT / "MangaReader12/Downloads/WebReaderOfflineResumePrefix.swift").read_text()
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()


class ResumePrefixContract(unittest.TestCase):
    def test_ios12_app_target_compiles_the_checker(self):
        self.assertEqual(PROJECT.count("WebReaderOfflineResumePrefix.swift in Sources"), 2)
        self.assertIn(
            "A20000000000000000000047 /* WebReaderOfflineResumePrefix.swift */,",
            PROJECT
        )
        self.assertIn(
            "A10000000000000000000047 /* WebReaderOfflineResumePrefix.swift in Sources */,",
            PROJECT
        )

    def test_resumable_pages_require_regular_nonsymlink_nonempty_files(self):
        for expected in (
            "maximumPlannedPages = 5_000",
            "maximumPageBytes: Int64 = 20 * 1024 * 1024",
            "plannedPages > 0 && plannedPages <= maximumPlannedPages",
            ".isDirectoryKey, .isSymbolicLinkKey",
            "folder.isDirectory == true, folder.isSymbolicLink != true",
            'String(format: "page-%05d.bin", valid)',
            ".isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey",
            "attributes.isRegularFile == true",
            "attributes.isSymbolicLink != true",
            "bytes > 0, Int64(bytes) <= maximumPageBytes",
            "return valid",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, RESUME)
        for forbidden in (
            "removeItem(", "createDirectory(", "URLSession", "write(to:",
            "sqlite3_", "appinst(", "posix_spawn("
        ):
            self.assertNotIn(forbidden, RESUME)

    def test_manager_continues_to_use_existing_resume_flow(self):
        body = MANAGER.split("private func completedPagePrefix(", 1)[1].split(
            "private func restorePreviousSession()", 1
        )[0]
        self.assertIn("WebReaderOfflineResumePrefix.count(", body)
        self.assertIn("directory: directory, plannedPages: count, fileManager: fileManager", body)
        self.assertNotIn("attributesOfItem(atPath:", body)
        self.assertIn("completedPagePrefix(", MANAGER.split(
            "private func restorePreviousSession()", 1
        )[1])
        self.assertNotIn("removeItem(", body)


if __name__ == "__main__":
    unittest.main()
