#!/usr/bin/env python3
"""Build69 BR: safe writer matches BQ reader and does not mutate offline images."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
WRITER = (ROOT / "MangaReader12/Downloads/WebReaderOfflineRecoveryPlanWriter.swift").read_text()
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()


class AtomicRecoveryPlanWriterContract(unittest.TestCase):
    def test_ios12_target_includes_writer(self):
        self.assertEqual(PROJECT.count("WebReaderOfflineRecoveryPlanWriter.swift in Sources"), 2)
        self.assertIn(
            "A20000000000000000000049 /* WebReaderOfflineRecoveryPlanWriter.swift */,",
            PROJECT
        )
        self.assertIn(
            "A10000000000000000000049 /* WebReaderOfflineRecoveryPlanWriter.swift in Sources */,",
            PROJECT
        )

    def test_bounded_private_atomic_write(self):
        for marker in (
            "static let maxBytes = WebReaderOfflineRecoveryPlanReader.maxBytes",
            "url.lastPathComponent == destinationName",
            "O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC",
            "Darwin.fstat(dirFD, &folderStat)",
            "Darwin.fstatat(",
            "AT_SYMLINK_NOFOLLOW",
            "Darwin.openat(",
            "O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC",
            "mode_t(0o600)",
            "Darwin.write(",
            "Darwin.fsync(fd) == 0",
            "FileProtectionType.completeUntilFirstUserAuthentication",
            "guard safeExistingDestination()",
            "Darwin.renameat(",
            "Darwin.unlinkat(",
            "defer { _ = Darwin.close(dirFD) }",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, WRITER)
        self.assertEqual(WRITER.count("guard safeExistingDestination()"), 2)
        self.assertLess(WRITER.index("Darwin.fsync(fd) == 0"),
                        WRITER.index("Darwin.renameat("))
        self.assertNotIn("Data.write(to:", WRITER)
        for forbidden in (
            "URLSession(", "appinst(", "posix_spawn(",
            "sqlite3_", "removeItem(", "rm -rf", "upload-artifact",
        ):
            self.assertNotIn(forbidden, WRITER)

    def test_both_initial_queue_and_prioritize_call_bounded_writer(self):
        save = MANAGER.split("private func savePlan(", 1)[1].split(
            "private func completedPagePrefix(", 1
        )[0]
        self.assertIn("let data = try JSONEncoder().encode(plan)", save)
        self.assertIn("WebReaderOfflineRecoveryPlanWriter.write(", save)
        self.assertIn("data: data, to: planURL(for: job.directory)", save)
        self.assertNotIn("data.write(to: url, options: .atomic)", save)
        self.assertIn("try self.savePlan(for: job)", MANAGER)
        self.assertIn("try savePlan(for: job)", MANAGER)
        self.assertIn("job.queueOrder = previousOrder", MANAGER)
        self.assertIn("WebReaderOfflineRecoveryPlanReader.read(", MANAGER)


if __name__ == "__main__":
    unittest.main()
