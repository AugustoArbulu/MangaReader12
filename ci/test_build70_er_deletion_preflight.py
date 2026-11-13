#!/usr/bin/env python3
"""ER: refuse deletion of unfamiliar offline chapter contents (synthetic host QA).

Read Swift source + compile exact preflight helper on macOS with disposable
files; no real iPad, network, appinst, IPA or database modifications.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
UI = (ROOT / "MangaReader12/UI/DownloadsViewController.swift").read_text()
DATABASE = (ROOT / "MangaReader12/Database/SQLiteDatabase.swift").read_text()
READER = (ROOT / "MangaReader12/Downloads/WebReaderOfflineRecoveryPlanReader.swift").read_text()
INVENTORY = (ROOT / "MangaReader12/Downloads/WebReaderOfflinePageInventory.swift").read_text()
RECEIPT = (ROOT / "MangaReader12/Downloads/WebReaderOfflineCompletionReceipt.swift").read_text()


class DeletionPreflightTests(unittest.TestCase):
    @staticmethod
    def helper():
        return MANAGER.split("// BEGIN BUILD70_ER_DELETION_PREFLIGHT", 1)[1].split(
            "// END BUILD70_ER_DELETION_PREFLIGHT", 1
        )[0]

    @staticmethod
    def remove():
        return MANAGER.split("    func remove(\n", 1)[1].split(
            "    private func chapterDirectory(", 1
        )[0]

    def test_only_recognized_regular_files_may_be_recursively_removed(self):
        source = self.helper()
        for required in (
            'name == "_download-plan.json"',
            "WebReaderOfflineCompletionReceipt.filename",
            'of: "^page-[0-9]{5}\\\\.bin$"',
            "WebReaderOfflinePageInventory.maximumPages",
            "maximumBytes = 20 * 1024 * 1024",
            "maximumBytes = 64",
            "names.count <= 100_001",
            "Darwin.fstatat(fd, name, &item, AT_SYMLINK_NOFOLLOW)",
            "item.st_nlink == 1",
            "item.st_size > 0",
            "O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC",
            "Darwin.lstat(directory.path, &before)",
            "stable(before, afterFD)",
            "stable(before, afterPath)",
            "for (path, original) in ancestors",
            "stable(original, current)",
        ):
            self.assertIn(required, source, required)
        for forbidden in (
            "removeItem(", "unlinkat(", "rmdir(", "write(", "createDirectory(",
            "sqlite3_", "URLSession(", "appinst(", "posix_spawn("
        ):
            self.assertNotIn(forbidden, source, forbidden)

    def test_deletion_refuses_uncertain_folder_before_queue_and_sqlite_changes(self):
        body = self.remove()
        checkpoint = "WebReaderOfflineDeletionPreflight.inspect("
        self.assertIn(checkpoint, body)
        self.assertIn("guard verdict != .unsafe else {", body)
        self.assertIn("throw ChapterDownloadError.unsafeOfflineDeletionContents", body)
        self.assertIn("if verdict == .allowed {", body)
        self.assertIn("try fileManager.removeItem(at: current)", body)
        self.assertIn("let rows = try repository.listDownloads()", body)
        self.assertIn("WebReaderOfflineCanonicalOwnership.collides(", body)
        self.assertIn("sourceID: sourceID, mangaID: mangaID, chapterID: chapterID,", body)
        for mutation in (
            "try fileManager.removeItem(at: current)",
            "jobs.removeValue(forKey: key)",
            "pending.removeAll",
            "try repository.remove(",
        ):
            self.assertLess(body.index("throw ChapterDownloadError.unsafeOfflineDeletionContents"),
                            body.index(mutation), mutation)
        self.assertLess(body.index("try fileManager.removeItem(at: current)"),
                        body.index("jobs.removeValue(forKey: key)"))
        self.assertIn("ChapterDownloadError.downloadInProgress", body)

    def test_absent_chapter_requires_safe_and_stable_parent_chain(self):
        helper = self.helper()
        self.assertIn("private static func absentWithSafeAncestors(", helper)
        self.assertIn("return absentWithSafeAncestors(directory: directory)", helper)
        self.assertIn("existingAncestors.append((parent.path, info))", helper)
        self.assertIn("absentAncestors.append(parent.path)", helper)
        self.assertIn("stable(original, current)", helper)
        self.assertIn("Darwin.lstat(directory.path, &leaf) != 0", helper)
        self.assertNotIn("return errno == ENOENT ? .absent : .unsafe", helper)
        self.assertLess(
            helper.index("absentWithSafeAncestors(directory: directory)"),
            helper.index("let fd = Darwin.open(")
        )

    def test_provenance_rejects_foreign_or_corrupt_plan_and_receipt(self):
        helper = self.helper()
        for token in (
            "WebReaderOfflineRecoveryPlanReader.read(",
            "JSONDecoder().decode(",
            "DownloadRecoveryPlan.self, from: data",
            "plan.schemaVersion == 1",
            "plan.sourceID == sourceID",
            "plan.manifest.id == sourceID",
            "plan.manga.id == mangaID",
            "plan.chapter.id == chapterID",
            "!plan.pages.isEmpty",
            "plan.pages.count <= WebReaderOfflineResumePrefix.maximumPlannedPages",
            "WebReaderOfflinePageInventory.inspect(",
            "WebReaderOfflineCompletionReceipt.verifyIfPresent(",
            "else { return .unsafe }",
        ):
            self.assertIn(token, helper, token)
        self.assertLess(
            helper.index("WebReaderOfflineRecoveryPlanReader.read("),
            helper.index("return .allowed")
        )
        self.assertLess(
            helper.index("WebReaderOfflineCompletionReceipt.verifyIfPresent("),
            helper.index("return .allowed")
        )
        self.assertIn("O_NOFOLLOW", READER)
        self.assertIn("readData(ofLength: 65)", RECEIPT)
        self.assertNotIn("removeItem(", helper)

    def test_missing_folder_deletes_only_unambiguous_metadata(self):
        body = self.remove()
        self.assertIn("if verdict == .allowed {", body)
        self.assertIn("try repository.remove(", body)
        self.assertIn("guard rows.contains(where: {", body)
        self.assertIn("verdict != .unsafe", body)
        self.assertIn("return absentWithSafeAncestors(directory: directory)", self.helper())

    def test_ui_requires_destructive_confirmation_unchanged(self):
        block = UI.split("private func confirmRemoveDownload(", 1)[1].split(
            "private func removeDownload(", 1)[0]
        for marker in (
            'title: "Apagar páginas offline?"',
            "O arquivo .mr12backup não contém essas imagens.",
            'UIAlertAction(title: "Cancelar", style: .cancel)',
            'UIAlertAction(title: "Apagar download", style: .destructive)',
            "self?.removeDownload(record)",
        ):
            self.assertIn(marker, block)
        self.assertNotIn("manager.remove(", block)
        self.assertIn("case .unsafeOfflineDeletionContents:", MANAGER)

    def test_persisted_collision_guard_and_database_rebind_still_enforced(self):
        body = self.remove()
        self.assertLess(body.index("WebReaderOfflineCanonicalOwnership.collides("),
                        body.index("WebReaderOfflineDeletionPreflight.inspect("))
        maintenance = DATABASE.split("    func removeMissingFiles(", 1)[1].split(
            "    func remove(", 1)[0]
        self.assertIn("WebReaderOfflineCanonicalOwnership.collides(", maintenance)

    @unittest.skipUnless(sys.platform == "darwin", "macOS native Swift only")
    def test_real_swift_preflight_adversarial_chapter_fixtures(self):
        helper = self.helper()
        swiftc = shutil.which("swiftc")
        self.assertIsNotNone(swiftc)
        fixture = r'''
import Foundation
import Darwin

let fm = FileManager.default
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
func mk(_ name: String) throws -> URL {
    let url = root.appendingPathComponent(name, isDirectory: true)
    try fm.createDirectory(at: url, withIntermediateDirectories: true)
    return url
}
func put(_ url: URL, _ name: String, _ data: [UInt8] = [1, 2, 3]) throws {
    try Data(data).write(to: url.appendingPathComponent(name))
}
func verdict(_ url: URL) -> WebReaderOfflineDeletionPreflight.Verdict {
    return WebReaderOfflineDeletionPreflight.inspect(
        directory: url, sourceID: "source", mangaID: "manga", chapterID: "chapter"
    )
}
func verify(_ actual: WebReaderOfflineDeletionPreflight.Verdict,
            _ expected: WebReaderOfflineDeletionPreflight.Verdict, _ note: String) {
    precondition(actual == expected, note)
}
let absent = root.appendingPathComponent("absent")
verify(verdict(absent), .absent, "missing directory only metadata")

let safeMissingParent = try mk("safe-ancestors/MangaReader12/Downloads/source/manga")
verify(verdict(safeMissingParent.appendingPathComponent("missing")),
       .absent, "missing leaf under real ancestors stays metadata-only")
let safeMissingTree = root.appendingPathComponent(
    "not-created/MangaReader12/Downloads/source/manga/chapter")
verify(verdict(safeMissingTree), .absent, "fully missing internal tree")

let linkedAncestorTarget = try mk("linked-ancestor-target/MangaReader12/Downloads")
let aliasedMissing = root.appendingPathComponent("aliased-missing")
try fm.createSymbolicLink(at: aliasedMissing,
                          withDestinationURL: linkedAncestorTarget)
verify(verdict(aliasedMissing.appendingPathComponent("source/manga/missing")),
       .unsafe, "missing leaf cannot bypass symlink ancestor check")

let fileParent = root.appendingPathComponent("parent-is-file")
try Data([7, 7, 7]).write(to: fileParent)
verify(verdict(fileParent.appendingPathComponent("source/manga/missing")),
       .unsafe, "file ancestor cannot be treated as missing chapter")
let chapter = try mk("app/MangaReader12/Downloads/source/manga/chapter")
try put(chapter, "page-00000.bin")
let plan: [String: Any] = [
    "schemaVersion": 1, "sourceID": "source",
    "manga": ["id": "manga"], "chapter": ["id": "chapter"],
    "pages": [["index": 0]], "manifest": ["id": "source"],
    "queueOrder": 1
]
func savePlan(_ data: [String: Any], _ directory: URL) throws {
    let bytes = try JSONSerialization.data(withJSONObject: data)
    try bytes.write(to: directory.appendingPathComponent("_download-plan.json"))
}
try savePlan(plan, chapter)
let validReceipt = Array("WR-OFFLINE-COMPLETE-V1:1\n".utf8)
try put(chapter, ".webreader-completion-v1", validReceipt)
verify(verdict(chapter), .allowed, "correct recovery identity and receipt")

let foreignPlan = try mk("foreign-plan/a/b/c/d")
try put(foreignPlan, "page-00000.bin")
var otherChapter = plan
otherChapter["chapter"] = ["id": "another-chapter"]
try savePlan(otherChapter, foreignPlan)
verify(verdict(foreignPlan), .unsafe, "foreign chapter plan identity")

let malformedPlan = try mk("malformed-plan/a/b/c/d")
try put(malformedPlan, "page-00000.bin")
try put(malformedPlan, "_download-plan.json", [0x7b, 0x22])
verify(verdict(malformedPlan), .unsafe, "incomplete JSON must not be erased")

let foreignSource = try mk("foreign-source/a/b/c/d")
try put(foreignSource, "page-00000.bin")
var wrongSource = plan
wrongSource["manifest"] = ["id": "other-source"]
try savePlan(wrongSource, foreignSource)
verify(verdict(foreignSource), .unsafe, "foreign manifest identity")

let brokenReceipt = try mk("broken-receipt/a/b/c/d")
try put(brokenReceipt, "page-00000.bin")
try put(brokenReceipt, ".webreader-completion-v1", [1, 2, 3])
verify(verdict(brokenReceipt), .unsafe, "unexpected receipt text")

let validReceiptOnly = try mk("receipt-only/a/b/c/d")
try put(validReceiptOnly, "page-00000.bin")
try put(validReceiptOnly, ".webreader-completion-v1", validReceipt)
verify(verdict(validReceiptOnly), .allowed, "completed download with valid receipt")

verify(try Data(contentsOf: chapter.appendingPathComponent("page-00000.bin"))
    == Data([1, 2, 3]), .allowed == .allowed, "audit does not mutate bytes")
let empty = try mk("empty/a/b/c/d")
verify(verdict(empty), .allowed, "empty legitimate chapter")
let unknown = try mk("unknown/a/b/c/d")
try put(unknown, ".wr69-plan-crashed.tmp")
verify(verdict(unknown), .unsafe, "unknown crash metadata")
let foreign = try mk("foreign/a/b/c/d")
try put(foreign, "user-notes.txt")
verify(verdict(foreign), .unsafe, "foreign content")
let nested = try mk("nested/a/b/c/d")
try fm.createDirectory(at: nested.appendingPathComponent("private-subdir"),
                       withIntermediateDirectories: false)
verify(verdict(nested), .unsafe, "subdirectory must not be deleted")
let zero = try mk("zero/a/b/c/d")
try Data().write(to: zero.appendingPathComponent("page-00000.bin"))
verify(verdict(zero), .unsafe, "zero page")
let outside = root.appendingPathComponent("outside-sentinel.bin")
try Data([9, 8, 7]).write(to: outside)
let linked = try mk("linked/a/b/c/d")
try fm.createSymbolicLink(at: linked.appendingPathComponent("page-00000.bin"),
                          withDestinationURL: outside)
verify(verdict(linked), .unsafe, "symbolic file")
let hardlinked = try mk("hardlinked/a/b/c/d")
try fm.linkItem(at: outside,
                to: hardlinked.appendingPathComponent("page-00000.bin"))
verify(verdict(hardlinked), .unsafe, "shared inode file")
let parentReal = try mk("parent-real/source/manga/chapter")
try put(parentReal, "page-00000.bin")
try fm.createSymbolicLink(
    at: root.appendingPathComponent("aliased-parent"),
    withDestinationURL: root.appendingPathComponent("parent-real")
)
verify(verdict(root.appendingPathComponent("aliased-parent/source/manga/chapter")),
       .unsafe, "symlinked source ancestor")
try fm.createSymbolicLink(
    at: root.appendingPathComponent("aliased-chapter"), withDestinationURL: chapter
)
verify(verdict(root.appendingPathComponent("aliased-chapter")),
       .unsafe, "symlinked chapter folder")
let extra = try mk("extra/a/b/c/d")
try put(extra, "page-100000.bin")
verify(verdict(extra), .unsafe, "out-of-range page name")
let oversized = try mk("oversized/a/b/c/d")
let huge = oversized.appendingPathComponent("page-00000.bin")
fm.createFile(atPath: huge.path, contents: Data([1]))
let handle = try FileHandle(forWritingTo: huge)
handle.truncateFile(atOffset: UInt64(20 * 1024 * 1024 + 1))
handle.closeFile()
verify(verdict(oversized), .unsafe, "oversized page")
verify(try Data(contentsOf: outside) == Data([9, 8, 7]),
       .allowed == .allowed, "outside bytes remain unchanged")
print("PASS ER native Swift: admissible deletion scoped; suspicious files retained")
'''
        # Swift's verify() takes a Verdict; use boolean precondition for
        # byte-conservation assertions to avoid conflating two result types.
        fixture = fixture.replace(
            'verify(try Data(contentsOf: chapter.appendingPathComponent("page-00000.bin"))\n    == Data([1, 2, 3]), .allowed == .allowed, "audit does not mutate bytes")',
            'let originalPageBytes = try Data(contentsOf: chapter.appendingPathComponent("page-00000.bin"))\nprecondition(originalPageBytes == Data([1, 2, 3]), "audit does not mutate bytes")'
        ).replace(
            'verify(try Data(contentsOf: outside) == Data([9, 8, 7]),\n       .allowed == .allowed, "outside bytes remain unchanged")',
            'let originalOutsideBytes = try Data(contentsOf: outside)\nprecondition(originalOutsideBytes == Data([9, 8, 7]), "outside bytes remain unchanged")'
        )
        with tempfile.TemporaryDirectory(prefix="wr-er-safe-delete-") as tmp:
            folder = Path(tmp)
            extra = folder / "Preflight.swift"
            main = folder / "main.swift"
            exe = folder / "check"
            # Compile exact production reader/receipt/inventory helpers
            # with the same plan fields and synthetic stub model identities.
            codable = MANAGER.split(
                "private struct DownloadRecoveryPlan: Codable {", 1
            )[1].split("\n}\n\n// A job keeps", 1)[0]
            models = (
                "struct Manga: Codable { let id: String }\n"
                "struct Chapter: Codable { let id: String }\n"
                "struct Page: Codable { let index: Int }\n"
                "struct SourceManifest: Codable { let id: String }\n"
                "enum WebReaderOfflineResumePrefix { "
                "static let maximumPlannedPages = 5_000 }\n"
                "private struct DownloadRecoveryPlan: Codable {\n"
                + codable + "\n}\n"
            )
            extra.write_text(
                "import Foundation\nimport Darwin\n" + models
                + helper + "\n" + READER + "\n" + INVENTORY
                + "\n" + RECEIPT
            )
            main.write_text(fixture)
            compiled = subprocess.run(
                [swiftc, "-swift-version", "5", str(extra), str(main), "-o", str(exe)],
                text=True, capture_output=True, timeout=120
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr[-8000:])
            result = subprocess.run(
                [str(exe), str(folder)], text=True, capture_output=True, timeout=30
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-8000:])
            self.assertIn("PASS ER native Swift:", result.stdout)


if __name__ == "__main__":
    unittest.main()
