#!/usr/bin/env python3
"""Build69 BQ: recovery plan read is bounded and never follows filesystem links."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
READER = (ROOT / "MangaReader12/Downloads/WebReaderOfflineRecoveryPlanReader.swift").read_text()
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()


class RecoveryPlanContract(unittest.TestCase):
    def test_ios12_target_includes_new_file(self):
        self.assertEqual(PROJECT.count("WebReaderOfflineRecoveryPlanReader.swift in Sources"), 2)
        self.assertIn(
            "A20000000000000000000048 /* WebReaderOfflineRecoveryPlanReader.swift */,",
            PROJECT
        )
        self.assertIn(
            "A10000000000000000000048 /* WebReaderOfflineRecoveryPlanReader.swift in Sources */,",
            PROJECT
        )

    def test_no_follow_regular_size_and_stability(self):
        for marker in (
            "import Darwin",
            "static let maxBytes = 16 * 1024 * 1024",
            "Darwin.open(url.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)",
            "Darwin.fstat(fd, &before)",
            "mode_t(S_IFREG)",
            "before.st_size > 0",
            "before.st_size <= off_t(maxBytes)",
            "Darwin.read(fd, bytes.baseAddress, wanted)",
            "Darwin.fstat(fd, &after)",
            "after.st_dev == before.st_dev",
            "after.st_ino == before.st_ino",
            "after.st_size == before.st_size",
            "after.st_mtimespec.tv_nsec == before.st_mtimespec.tv_nsec",
            "after.st_ctimespec.tv_nsec == before.st_ctimespec.tv_nsec",
            "defer { _ = Darwin.close(fd) }",
        ):
            self.assertIn(marker, READER, marker)
        for forbidden in (
            "Data(contentsOf:", "createDirectory(", "removeItem(",
            "URLSession(", "appinst(", "posix_spawn(", "write(to:",
        ):
            self.assertNotIn(forbidden, READER)

    def test_restore_uses_bounded_reader_without_deleting_pages(self):
        restore = MANAGER.split("private func restorePreviousSession()", 1)[1].split(
            "func enqueue(", 1
        )[0]
        self.assertIn("WebReaderOfflineRecoveryPlanReader.read(", restore)
        self.assertIn("from: planURL(for: expected)", restore)
        self.assertNotIn("Data(contentsOf: planURL(for: expected))", restore)
        self.assertNotIn("removeItem(", restore)
        self.assertIn("DownloadRecoveryPlan.self", restore)


if __name__ == "__main__":
    unittest.main()
