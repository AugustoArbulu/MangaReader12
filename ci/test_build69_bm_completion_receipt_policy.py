#!/usr/bin/env python3
"""Build69 BM: new-download receipt is optional on old read, required on new completion."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
RECEIPT = (ROOT / "MangaReader12/Downloads/WebReaderOfflineCompletionReceipt.swift").read_text()
AUDIT = (ROOT / "MangaReader12/Core/WebReaderOfflinePreservationAudit.swift").read_text()
PBX = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()


class CompletionReceiptSafety(unittest.TestCase):
    def test_new_receipt_compiled_in_ios12_target(self):
        self.assertEqual(PBX.count("WebReaderOfflineCompletionReceipt.swift in Sources"), 2)
        self.assertIn("A20000000000000000000046 /* WebReaderOfflineCompletionReceipt.swift */,", PBX)
        self.assertIn("A10000000000000000000046 /* WebReaderOfflineCompletionReceipt.swift in Sources */,", PBX)

    def test_download_completion_checks_files_and_receipt_before_marking_complete(self):
        finish = MANAGER.split("if job.nextIndex >= job.pages.count {", 1)[1].split(
            "let index = job.nextIndex", 1
        )[0]
        for marker in (
            "WebReaderOfflinePageInventory.inspect(",
            "guard committed.count == job.pages.count else {",
            "WebReaderOfflineCompletionReceipt.write(",
            'state: "completed", progress: 1,',
        ):
            self.assertIn(marker, finish)
        self.assertLess(finish.index("WebReaderOfflinePageInventory.inspect("),
                        finish.index("WebReaderOfflineCompletionReceipt.write("))
        self.assertLess(finish.index("WebReaderOfflineCompletionReceipt.write("),
                        finish.index('state: "completed", progress: 1,'))
        self.assertNotIn("removeItem(", finish)
        self.assertNotIn("URLSession(", finish)

    def test_existing_legacy_works_and_new_receipt_checked_before_rebind(self):
        pages = MANAGER.split("func localPages(", 1)[1].split("func remove(", 1)[0]
        self.assertIn("WebReaderOfflineCompletionReceipt.verifyIfPresent(", pages)
        self.assertLess(pages.index("WebReaderOfflinePageInventory.inspect("),
                        pages.index("WebReaderOfflineCompletionReceipt.verifyIfPresent("))
        self.assertLess(pages.index("WebReaderOfflineCompletionReceipt.verifyIfPresent("),
                        pages.index("repository.rebindCompletedPath("))
        self.assertIn("throw ChapterDownloadError.missingCompletedFiles", pages)
        self.assertIn("return false // Build68 legacy", RECEIPT)
        self.assertIn("WR-OFFLINE-COMPLETE-V1:", RECEIPT)
        self.assertIn("byteCount > 0, byteCount <= 64", RECEIPT)
        self.assertIn("values.isSymbolicLink != true", RECEIPT)
        self.assertIn("actualPages", RECEIPT)
        self.assertIn("expectedPages", RECEIPT)
        self.assertIn("options: .atomic", RECEIPT)
        self.assertNotIn("URLSession", RECEIPT)
        self.assertNotIn("sqlite3_", RECEIPT)
        self.assertNotIn("removeItem(", RECEIPT)

    def test_bounded_offline_audit_does_not_misclassify_corrupted_receipts(self):
        self.assertIn("WebReaderOfflineCompletionReceipt.verifyIfPresent(", AUDIT)
        self.assertIn("var sealed = 0", AUDIT)
        self.assertIn("if hasReceipt { sealed += 1 }", AUDIT)
        self.assertIn("Com recibo de quantidade de páginas:", AUDIT)
        self.assertIn("Legados sem recibo entre os válidos:", AUDIT)
        self.assertIn("NÃO comprova imagem íntegra", AUDIT)
        self.assertIn("try? WebReaderOfflinePageInventory.inspect(", AUDIT)
        self.assertNotIn("removeItem(", AUDIT)


if __name__ == "__main__":
    unittest.main()
