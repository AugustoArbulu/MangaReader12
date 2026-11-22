#!/usr/bin/env python3
"""Build69 BU: a stored image must remain eligible for resumed offline reads."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
RESUME = (ROOT / "MangaReader12/Downloads/WebReaderOfflineResumePrefix.swift").read_text()


class DownloadPageCeiling(unittest.TestCase):
    def test_page_body_checked_before_image_decode_and_atomic_file_write(self):
        body = MANAGER.split("private func performPageRequest(", 1)[1].split(
            "private func fail(", 1
        )[0]
        for marker in (
            "Int64(response.data.count) <=",
            "WebReaderOfflineResumePrefix.maximumPageBytes",
            "ChapterDownloadError.oversizedImagePayload",
            "ChapterDownloadImageValidator.canStore(",
            "try response.data.write(to: destination, options: .atomic)",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, body)
        self.assertLess(body.index("Int64(response.data.count) <="),
                        body.index("ChapterDownloadImageValidator.canStore("))
        self.assertLess(body.index("ChapterDownloadImageValidator.canStore("),
                        body.index("try response.data.write(to: destination"))
        self.assertIn("maximumPageBytes: Int64 = 20 * 1024 * 1024", RESUME)

    def test_rejected_page_is_not_reported_as_completed(self):
        self.assertIn("case oversizedImagePayload", MANAGER)
        self.assertIn("case .oversizedImagePayload:", MANAGER)
        self.assertIn("O capítulo não foi marcado como completo", MANAGER)
        self.assertIn("arquivos existentes foram preservados", MANAGER)
        self.assertIn("self.fail(job, error: ChapterDownloadError.oversizedImagePayload)", MANAGER)
        body = MANAGER.split("private func performPageRequest(", 1)[1].split(
            "private func fail(", 1
        )[0]
        self.assertNotIn('state: "completed"', body)
        self.assertNotIn("fileManager.removeItem", body)


if __name__ == "__main__":
    unittest.main()
