#!/usr/bin/env python3
"""Build69 BP: privacy-safe 64-chapter SQLite paging and responsive UIKit control."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
AUDIT = (ROOT / "MangaReader12/Core/WebReaderOfflinePreservationAudit.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()


class OfflineBatchPagingContract(unittest.TestCase):
    def test_bounded_parameterized_sqlite_pagination(self):
        for marker in (
            "private static let sampleLimit = 64",
            "requestedOffset >= 0, requestedOffset <= 1_000_000_000",
            "Int64(requestedOffset) < total ?",
            "LIMIT ? OFFSET ?;",
            "sqlite3_bind_int64(prepared, 1, Int64(sampleLimit))",
            "sqlite3_bind_int64(prepared, 2, offset)",
            "offset + Int64(sampleLimit) < total ?",
            "Índice inicial deste lote:",
            "Próximo índice da auditoria:",
            "static func diagnostic(",
            "static func report(",
            "SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX",
            "sqlite3_busy_timeout(conn, 200)",
        ):
            self.assertIn(marker, AUDIT, marker)
        self.assertNotIn("SQLITE_OPEN_READWRITE", AUDIT)
        self.assertNotIn("DELETE FROM", AUDIT)
        self.assertNotIn("UPDATE ", AUDIT)
        self.assertNotIn("appinst(", AUDIT)
        self.assertNotIn("URLSession(", AUDIT)

    def test_single_next_page_offset_maintained_only_on_main_after_report(self):
        self.assertIn("private var offlineSampleOffset = 0", UI)
        self.assertIn("let requestedOffset = offlineSampleOffset", UI)
        self.assertIn("sampleOffset: requestedOffset", UI)
        self.assertIn("offlineSampleOffset = audit.nextOffset", UI)
        self.assertIn("UIPasteboard.general.string = audit.report", UI)
        self.assertIn("Próximo lote: índice ", UI)
        body = UI.split("private func copyOfflinePresenceAudit() {", 1)[1].split(
            "private func copyUpgradeContinuitySnapshot()", 1
        )[0]
        self.assertIn("guard !isIPCDiagnostic, !offlinePresenceBusy else { return }", body)
        self.assertLess(body.index("DispatchQueue.global(qos: .utility)"),
                        body.index("WebReaderOfflinePreservationAudit.diagnostic("))
        self.assertLess(body.index("WebReaderOfflinePreservationAudit.diagnostic("),
                        body.index("DispatchQueue.main.async"))
        self.assertLess(body.index("DispatchQueue.main.async"),
                        body.index("offlineSampleOffset = audit.nextOffset"))
        self.assertLess(body.index("offlineSampleOffset = audit.nextOffset"),
                        body.index("UIPasteboard.general.string = audit.report"))
        self.assertIn("guard self.view.window != nil else { return }", body)
        self.assertNotIn("removeItem(", body)

    def test_legacy_single_batch_report_still_supported(self):
        self.assertIn("return diagnostic(", AUDIT)
        self.assertIn("applicationSupportOverride: applicationSupportOverride", AUDIT)
        self.assertIn(").report", AUDIT)


if __name__ == "__main__":
    unittest.main()
