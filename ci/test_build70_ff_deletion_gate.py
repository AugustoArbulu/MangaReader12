#!/usr/bin/env python3
"""FF: pure/read-only bridge contract, synthetic Swift host tests.

No iPad, network, download or file removal; do not enable production flags.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
DATABASE = (ROOT / "MangaReader12/Database/SQLiteDatabase.swift").read_text()
START = "// BEGIN BUILD70_FF_INERT_READONLY_DELETION_BRIDGE"
END = "// END BUILD70_FF_INERT_READONLY_DELETION_BRIDGE"
GATE = MANAGER.split(START, 1)[1].split(END, 1)[0]

class FFGateTests(unittest.TestCase):
    def test_flag_disabled_and_no_dynamic_enable(self):
        self.assertIn("static let diagnosticCopyPreviewEnabled = false", GATE)
        self.assertNotIn("UserDefaults", GATE)
        for forbidden in ("removeItem(", "unlinkat(", "renameat(", "sqlite3_", "executeSQL",
                          "URLSession", "appinst", "startDownload(", "createDirectory("):
            self.assertNotIn(forbidden, GATE)

    def test_deletion_entrypoints_fail_closed_before_any_legacy_io(self):
        single = MANAGER.split("    func remove(\n", 1)[1].split("// BEGIN BUILD70_ET_BOUNDED_BULK_DELETE", 1)[0]
        bulk = MANAGER.split("func removeAllConfirmed() throws -> Int", 1)[1].split(
            "// END BUILD70_ET_BOUNDED_BULK_DELETE", 1
        )[0]
        reindex = DATABASE.split("func removeMissingFiles(fileManager:", 1)[1].split(
            "\n    func remove(\n", 1
        )[0]
        gate = "WebReaderOfflineDeletionV2ShadowGate.rejectLegacyDestructionWhenPreviewEnabled()"
        for body, first in (
            (single, "repository.listDownloads()"),
            (bulk, "repository.listDownloads()"),
            (reindex, "let records = try listDownloads()"),
        ):
            self.assertIn(gate, body)
            self.assertLess(body.index(gate), body.index(first))
        self.assertIn("throw ChapterDownloadError.unsafeOfflineDeletionContents", GATE)

    def test_preview_is_provisional_and_never_authorizes_destructive_action(self):
        self.assertIn("case provisionalCopyOnly", GATE)
        self.assertIn("record.state == \"completed\"", GATE)
        self.assertIn('!names.contains("_download-plan.json")', GATE)
        self.assertIn("WebReaderOfflineCanonicalOwnership.collides(", GATE)
        self.assertIn("WebReaderOfflineDeletionPreflight.inspect(", GATE)
        self.assertNotIn("try repository.remove", GATE)

    def test_swift_readonly_gate_with_synthetic_records(self):
        stubs = r"""
import Foundation
enum ChapterDownloadError: Error { case unsafeOfflineDeletionContents }
struct DownloadListRecord {
    let sourceID: String
    let sourceMangaID: String
    let sourceChapterID: String
    let state: String
}
enum WebReaderOfflineCanonicalOwnership {
    static func collides(sourceID: String, mangaID: String, chapterID: String,
                         recorded: [DownloadListRecord]) -> Bool {
        return recorded.filter {
            $0.sourceID == sourceID && $0.sourceMangaID == mangaID &&
            $0.sourceChapterID == chapterID
        }.count > 1
    }
}
enum WebReaderOfflineDeletionPreflight {
    enum Verdict { case allowed, absent, unsafe }
    static func inspect(directory: URL, sourceID: String, mangaID: String,
                        chapterID: String, fileManager: FileManager) -> Verdict {
        var isDir: ObjCBool = false
        return fileManager.fileExists(atPath: directory.path, isDirectory: &isDir) &&
            isDir.boolValue ? .allowed : .absent
    }
}
"""
        main = r"""
@main struct Runner {
    static func main() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FF-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: false)
        defer { try? FileManager.default.removeItem(at: root) }
        let row = DownloadListRecord(sourceID:"s",sourceMangaID:"m",sourceChapterID:"c",state:"completed")
        let paused = DownloadListRecord(sourceID:"s",sourceMangaID:"m",sourceChapterID:"c",state:"paused")
        func preview(_ item: DownloadListRecord, _ all: [DownloadListRecord]) -> WebReaderOfflineDeletionV2ShadowGate.Preview {
            WebReaderOfflineDeletionV2ShadowGate.previewForAudit(
                record: item, allRecords: all, directory: root)
        }
        precondition(!WebReaderOfflineDeletionV2ShadowGate.diagnosticCopyPreviewEnabled)
        try WebReaderOfflineDeletionV2ShadowGate.rejectLegacyDestructionWhenPreviewEnabled()
        precondition(preview(row,[row]) == .provisionalCopyOnly)
        precondition(preview(paused,[paused]) == .requiresReview)
        precondition(preview(row,[]) == .requiresReview)
        precondition(preview(row,[row,row]) == .requiresReview)
        try Data("sensitive".utf8).write(to: root.appendingPathComponent("_download-plan.json"))
        precondition(preview(row,[row]) == .requiresReview)
        try FileManager.default.removeItem(at: root.appendingPathComponent("_download-plan.json"))
        try FileManager.default.removeItem(at: root)
        precondition(preview(row,[row]) == .requiresReview)
        print("FF_PROVISIONAL_READONLY_PASS")
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "ff_gate.swift"
            binary = Path(tmp) / "ff_gate"
            source.write_text(stubs + GATE + main)
            subprocess.run(["swiftc", "-parse-as-library", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True, timeout=60)
            result = subprocess.run([str(binary)], check=True, capture_output=True,
                                    text=True, timeout=15)
            self.assertIn("FF_PROVISIONAL_READONLY_PASS", result.stdout)

if __name__ == "__main__":
    unittest.main()
