#!/usr/bin/env python3
"""ET: bounded bulk-download deletion tests; synthetic host-only fixtures.

No iPad, network, appinst, real SQLite, real user pages or Build71.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
STORAGE = (ROOT / "MangaReader12/Core/StorageManager.swift").read_text()
UI = (ROOT / "MangaReader12/UI/DataStorageViewController.swift").read_text()


class BulkDeletionSafetyTests(unittest.TestCase):
    @staticmethod
    def body():
        return MANAGER.split(
            "// BEGIN BUILD70_ET_BOUNDED_BULK_DELETE\n", 1
        )[1].split("// END BUILD70_ET_BOUNDED_BULK_DELETE", 1)[0]

    def test_storage_delegates_to_serialized_per_chapter_safe_worker(self):
        body = STORAGE.split("    func clearAllDownloads() throws {", 1)[1].split(
            "    func reindexDownloads()", 1)[0]
        self.assertIn("ChapterDownloadManager.defaultManager().removeAllConfirmed()", body)
        for forbidden in (
            "fileManager.removeItem(", "downloadsRepository.clearAll()",
            "createDirectory(", "removeItem(atPath:"
        ):
            self.assertNotIn(forbidden, body)
        self.assertIn("try worker.sync {", self.body())

    def test_bulk_preflights_entire_batch_before_first_mutation(self):
        body = self.body()
        for text in (
            'record.state == "completed"',
            'record.state == "failed"',
            'record.state == "paused"',
            "runningKey == nil, pending.isEmpty",
            "repository.listDownloads()",
            "seenKeys.insert(key).inserted",
            "WebReaderOfflineCanonicalOwnership.collides(",
            "WebReaderOfflineDeletionPreflight.inspect(",
            "actual == item.verdict",
            "Set(jobs.keys).isSubset(of: seenKeys)",
            "throw ChapterDownloadError.unsafeOfflineDeletionContents",
        ):
            self.assertIn(text, body)
        for mutation in ("try fileManager.removeItem(at: item.directory)",
                         "try repository.remove(", "jobs.removeValue(forKey: key)"):
            self.assertLess(body.index("for record in rows {"), body.index(mutation))
            self.assertLess(body.index("guard Set(jobs.keys).isSubset(of: seenKeys)"),
                            body.index(mutation))
            self.assertLess(body.index("for item in planned {"),
                            body.index(mutation))
        self.assertLess(body.index("try fileManager.removeItem(at: item.directory)"),
                        body.index("try repository.remove("))

    def test_unsafe_or_unknown_files_never_trigger_root_deletion(self):
        body = self.body()
        self.assertIn("if actual == .allowed {", body)
        self.assertIn("guard actual == item.verdict else {", body)
        self.assertNotIn("removeItem(at: downloadsDirectory()", body)
        self.assertNotIn("removeItem(at: root)", body)
        self.assertNotIn("downloadsRepository.clearAll()", body)
        self.assertNotIn("DELETE FROM downloads", body.split("// No file-system root erase")[0])

    def test_bulk_stops_when_jobs_are_running_or_unreferenced(self):
        body = self.body()
        self.assertIn("runningKey == nil, pending.isEmpty", body)
        self.assertIn("Set(jobs.keys).isSubset(of: seenKeys)", body)
        self.assertIn("throw ChapterDownloadError.downloadInProgress", body)

    def test_ui_keeps_owner_consent_and_discloses_orphan_preservation(self):
        block = UI.split("private func confirmClearDownloads() {", 1)[1].split(
            "private func refreshSnapshot()", 1)[0]
        for text in (
            'title: "Apagar todos os downloads?"',
            "O backup .mr12backup não contém",
            "pastas desconhecidas ou órfãs serão preservadas.",
            "alguns capítulos podem",
            'UIAlertAction(title: "Cancelar", style: .cancel)',
            "style: .destructive",
            "try manager.clearAllDownloads()",
        ):
            self.assertIn(text, block)
        self.assertIn("Capítulos registrados removidos", block)
        self.assertNotIn("try manager.clearAllDownloads()", UI.split(
            "didSelectRowAt indexPath: IndexPath", 1)[1].split(
            "private func performMaintenance(", 1)[0])

    @unittest.skipUnless(sys.platform == "darwin", "real Swift execution macOS only")
    def test_real_swift_bulk_deletion_orchestration_with_disposable_data(self):
        swiftc = shutil.which("swiftc")
        self.assertIsNotNone(swiftc)
        actual = self.body()
        path = MANAGER.split("// BEGIN OFFLINE_PATH_RELOCATION\n", 1)[1].split(
            "// END OFFLINE_PATH_RELOCATION", 1)[0]
        owner = MANAGER.split("// BEGIN BUILD70_EQ_CANONICAL_OWNERSHIP\n", 1)[1].split(
            "// END BUILD70_EQ_CANONICAL_OWNERSHIP", 1)[0]
        models = r'''
import Foundation
import Darwin

struct DownloadListRecord {
    let sourceID: String
    let sourceMangaID: String
    let sourceChapterID: String
    let state: String
}
enum ChapterDownloadError: Error {
    case downloadInProgress
    case ambiguousOfflineChapterPath
    case unsafeOfflineDeletionContents
}
enum HTTPClientError: Error { case cancelled }
final class FakeJob {
    let completion: (Result<[String], Error>) -> Void
    init(_ callback: @escaping (Result<[String], Error>) -> Void = { _ in }) {
        completion = callback
    }
}
final class DownloadRepository {
    var rows: [DownloadListRecord]
    var deleted: [String] = []
    init(_ rows: [DownloadListRecord]) { self.rows = rows }
    func listDownloads() throws -> [DownloadListRecord] { rows }
    func remove(sourceID: String, sourceMangaID: String,
                sourceChapterID: String) throws {
        deleted.append(sourceChapterID)
        rows.removeAll {
            $0.sourceID == sourceID && $0.sourceMangaID == sourceMangaID &&
                $0.sourceChapterID == sourceChapterID
        }
    }
}
// This stand-in only simulates the per-folder verdict. The separate native
// ER/ES tests compile and execute the full production metadata preflight.
enum WebReaderOfflineDeletionPreflight {
    enum Verdict: Equatable { case absent, allowed, unsafe }
    static func inspect(directory: URL, sourceID: String, mangaID: String,
                        chapterID: String,
                        fileManager: FileManager = .default) -> Verdict {
        guard fileManager.fileExists(atPath: directory.path) else { return .absent }
        let names = (try? fileManager.contentsOfDirectory(atPath: directory.path)) ?? []
        if names.contains("private-note.txt") { return .unsafe }
        return .allowed
    }
}
'''
        holder = r'''
final class ChapterDownloadManager {
    let fileManager = FileManager.default
    let repository: DownloadRepository
    let root: URL
    let worker = DispatchQueue(label: "qa-bulk-delete")
    var runningKey: String?
    var pending: [String] = []
    var jobs: [String: FakeJob] = [:]
    init(_ root: URL, _ repo: DownloadRepository) {
        self.root = root
        repository = repo
    }
    func jobKey(sourceID: String, mangaID: String, chapterID: String) -> String {
        return [sourceID, mangaID, chapterID].joined(separator: "\u{1F}")
    }
    func chapterDirectory(sourceID: String, mangaID: String,
                          chapterID: String) throws -> URL {
        return OfflineDownloadPath.chapterDirectory(
            applicationSupport: root, sourceID: sourceID,
            mangaID: mangaID, chapterID: chapterID
        )
    }
''' + actual + '\n}\n'
        fixture = r'''
import Foundation
let fm = FileManager.default
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
func row(_ chapter: String, _ state: String = "completed") -> DownloadListRecord {
    return DownloadListRecord(sourceID: "asura", sourceMangaID: "series",
                              sourceChapterID: chapter, state: state)
}
func chapter(_ id: String) -> URL {
    return OfflineDownloadPath.chapterDirectory(
        applicationSupport: root, sourceID: "asura",
        mangaID: "series", chapterID: id
    )
}
func put(_ id: String, filename: String = "page-00000.bin") throws {
    let target = chapter(id)
    try fm.createDirectory(at: target, withIntermediateDirectories: true)
    try Data([1, 2, 3]).write(to: target.appendingPathComponent(filename))
}
let orphan = root.appendingPathComponent("MangaReader12/Downloads/unknown-owner")
try fm.createDirectory(at: orphan, withIntermediateDirectories: true)
try Data("PRESERVE".utf8).write(to: orphan.appendingPathComponent("orphan-data.bin"))

try put("first")
try put("second", filename: "private-note.txt")
let db = DownloadRepository([row("first"), row("second")])
let manager = ChapterDownloadManager(root, db)
do {
    _ = try manager.removeAllConfirmed()
    fatalError("bulk accepted an unsafe second chapter")
} catch ChapterDownloadError.unsafeOfflineDeletionContents {}
precondition(fm.fileExists(atPath: chapter("first").path),
             "first chapter cannot be removed until entire batch is vetted")
precondition(db.deleted.isEmpty, "the preflight must have zero DB mutations")
precondition(fm.fileExists(atPath: chapter("second").path))
try fm.removeItem(at: chapter("second").appendingPathComponent("private-note.txt"))
try Data([4, 5, 6]).write(to: chapter("second").appendingPathComponent("page-00000.bin"))
let removedCount = try manager.removeAllConfirmed()
precondition(removedCount == 2, "two known safe rows removed")
precondition(db.rows.isEmpty, "known DB rows removed only on confirmed success")
precondition(!fm.fileExists(atPath: chapter("first").path))
precondition(!fm.fileExists(atPath: chapter("second").path))
precondition(fm.fileExists(atPath: orphan.appendingPathComponent("orphan-data.bin").path),
             "unknown orphan must never be recursively removed")

try put("active")
let active = DownloadRepository([row("active", "downloading")])
let stopped = ChapterDownloadManager(root, active)
do {
    _ = try stopped.removeAllConfirmed()
    fatalError("active download erroneously accepted")
} catch ChapterDownloadError.downloadInProgress {}
precondition(fm.fileExists(atPath: chapter("active").path), "active pages lost")
precondition(active.deleted.isEmpty, "active DB state mutated")

let paused = DownloadRepository([row("active", "paused")])
let queued = ChapterDownloadManager(root, paused)
queued.pending = ["user-job"]
do {
    _ = try queued.removeAllConfirmed()
    fatalError("pending queue erroneously accepted")
} catch ChapterDownloadError.downloadInProgress {}
precondition(paused.deleted.isEmpty, "pending job changed the DB")
queued.pending = []

try put("part/01")
let aliased = DownloadRepository([row("part/01"), row("part?01")])
let overlap = ChapterDownloadManager(root, aliased)
do {
    _ = try overlap.removeAllConfirmed()
    fatalError("aliased folders were accepted")
} catch ChapterDownloadError.ambiguousOfflineChapterPath {}
precondition(fm.fileExists(atPath: chapter("part/01").path),
             "ambiguous chapter must remain")
precondition(aliased.deleted.isEmpty, "collision caused database removal")

let nothing = DownloadRepository([])
let noRows = ChapterDownloadManager(root, nothing)
let emptyResult = try noRows.removeAllConfirmed()
precondition(emptyResult == 0, "empty inventory")
precondition(fm.fileExists(atPath: orphan.appendingPathComponent("orphan-data.bin").path),
             "empty database must not trigger root erase")
print("PASS ET native Swift: atomic preflight; safe registered rows only; orphans kept")
'''
        with tempfile.TemporaryDirectory(prefix="wr-et-bulk-safety-") as temp:
            folder = Path(temp)
            models_file = folder / "OfflineBulkFixtures.swift"
            main = folder / "main.swift"
            binary = folder / "et-disposable"
            models_file.write_text(models + path + owner + holder, encoding="utf-8")
            main.write_text(fixture, encoding="utf-8")
            compiled = subprocess.run(
                [swiftc, "-swift-version", "5", str(models_file), str(main),
                 "-o", str(binary)], capture_output=True, text=True, timeout=120
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr[-8000:])
            executed = subprocess.run(
                [str(binary), str(folder)], capture_output=True,
                text=True, timeout=30
            )
            self.assertEqual(executed.returncode, 0,
                             executed.stdout + executed.stderr[-8000:])
            self.assertIn("PASS ET native Swift:", executed.stdout)


if __name__ == "__main__":
    unittest.main()
