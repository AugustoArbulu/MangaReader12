#!/usr/bin/env python3
"""EQ: refuse ambiguous normalized offline paths (host-only synthetic QA).

No real device, network request, IPA, installer, SQLite mutation or deletion.
Native tests compile the exact Swift Foundation helper with fake DB records.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
DATABASE = (ROOT / "MangaReader12/Database/SQLiteDatabase.swift").read_text()


class OfflineCanonicalOwnershipContract(unittest.TestCase):
    def test_collision_normalization_is_conservative_and_scope_bounded(self):
        body = MANAGER.split("// BEGIN BUILD70_EQ_CANONICAL_OWNERSHIP", 1)[1].split(
            "// END BUILD70_EQ_CANONICAL_OWNERSHIP", 1)[0]
        for marker in (
            "enum WebReaderOfflineCanonicalOwnership",
            "OfflineDownloadPath.safeComponent(raw)",
            ".precomposedStringWithCanonicalMapping",
            ".caseInsensitive", ".diacriticInsensitive", ".widthInsensitive",
            "if identity == requestedIdentity { return false }",
            "recorded.contains",
        ):
            self.assertIn(marker, body)
        for forbidden in ("removeItem(", "write(", "createDirectory(", "URLSession(",
                          "sqlite3_", "appinst(", "posix_spawn("):
            self.assertNotIn(forbidden, body)

    def test_admission_rejects_collision_before_creating_folders(self):
        body = MANAGER.split("    func download(\n", 1)[1].split(
            "    // Returns false for a job left over", 1)[0]
        checker = "WebReaderOfflineCanonicalOwnership.collides("
        self.assertIn(checker, body)
        self.assertLess(body.index(checker), body.index("createDirectory("))
        self.assertLess(body.index(checker), body.index("self.savePlan(for: job)"))
        self.assertIn("throw ChapterDownloadError.ambiguousOfflineChapterPath", body)

    def test_restore_skips_ambiguous_record_before_reading_plan(self):
        body = MANAGER.split("private func restorePreviousSession()", 1)[1].split(
            "private func jobKey(", 1)[0]
        self.assertIn("!WebReaderOfflineCanonicalOwnership.collides(", body)
        self.assertLess(
            body.index("WebReaderOfflineCanonicalOwnership.collides("),
            body.index("WebReaderOfflineRecoveryPlanReader.read(")
        )
        self.assertIn("recorded: records", body)
        self.assertNotIn("removeItem(", body)

    def test_completed_chapter_read_refuses_wrong_owner(self):
        body = MANAGER.split("    func localPages(", 1)[1].split(
            "    func remove(", 1)[0]
        checker = "WebReaderOfflineCanonicalOwnership.collides("
        self.assertIn(checker, body)
        self.assertLess(body.index(checker),
                        body.index("WebReaderOfflinePageInventory.inspect("))
        self.assertLess(body.index(checker), body.index("rebindCompletedPath("))
        self.assertIn("throw ChapterDownloadError.ambiguousOfflineChapterPath", body)

    def test_explicit_delete_never_removes_another_chapter_or_orphan_folder(self):
        body = MANAGER.split("    func remove(", 1)[1].split(
            "    private func chapterDirectory(", 1)[0]
        self.assertIn("let rows = try repository.listDownloads()", body)
        self.assertIn("guard rows.contains(where: {", body)
        self.assertIn("WebReaderOfflineCanonicalOwnership.collides(", body)
        self.assertIn("throw ChapterDownloadError.ambiguousOfflineChapterPath", body)
        for unsafe in ("jobs.removeValue(forKey: key)", "pending.removeAll",
                       "fileManager.removeItem(at: current)", "repository.remove("):
            self.assertLess(body.index("throw ChapterDownloadError.ambiguousOfflineChapterPath"),
                            body.index(unsafe))
        self.assertIn("ChapterDownloadError.downloadInProgress", body)

    def test_database_cleanup_never_rebinds_ambiguous_paths(self):
        body = DATABASE.split("    func removeMissingFiles(", 1)[1].split(
            "    func remove(", 1)[0]
        self.assertIn("WebReaderOfflineCanonicalOwnership.collides(", body)
        self.assertIn("recorded: records", body)
        self.assertLess(body.index("WebReaderOfflineCanonicalOwnership.collides("),
                        body.index("rebindCompletedPath("))
        self.assertLess(body.index("WebReaderOfflineCanonicalOwnership.collides("),
                        body.index("try remove("))

    def test_path_relocation_fixture_stays_independent_of_db_type(self):
        block = MANAGER.split("// BEGIN OFFLINE_PATH_RELOCATION", 1)[1].split(
            "// END OFFLINE_PATH_RELOCATION", 1)[0]
        self.assertNotIn("DownloadListRecord", block)
        self.assertIn("enum OfflineDownloadPath", block)
        self.assertIn("safeComponent(_ value: String)", block)

    @unittest.skipUnless(sys.platform == "darwin", "requires macOS Swift Foundation")
    def test_native_swift_rejects_actual_colliding_identifiers(self):
        path = MANAGER.split("// BEGIN OFFLINE_PATH_RELOCATION\n", 1)[1].split(
            "// END OFFLINE_PATH_RELOCATION", 1)[0]
        owner = MANAGER.split("// BEGIN BUILD70_EQ_CANONICAL_OWNERSHIP\n", 1)[1].split(
            "// END BUILD70_EQ_CANONICAL_OWNERSHIP", 1)[0]
        swift = shutil.which("swiftc")
        self.assertIsNotNone(swift)
        fixture = """
import Foundation
struct DownloadListRecord {
    let sourceID: String
    let sourceMangaID: String
    let sourceChapterID: String
}

func row(_ source: String, _ manga: String, _ chapter: String) -> DownloadListRecord {
    return DownloadListRecord(
        sourceID: source, sourceMangaID: manga, sourceChapterID: chapter
    )
}
func collision(_ source: String, _ manga: String, _ chapter: String,
               _ rows: [DownloadListRecord]) -> Bool {
    return WebReaderOfflineCanonicalOwnership.collides(
        sourceID: source, mangaID: manga, chapterID: chapter, recorded: rows
    )
}
precondition(
    OfflineDownloadPath.safeComponent("part/01")
        == OfflineDownloadPath.safeComponent("part?01"),
    "fixture must truly alias on disk"
)
precondition(collision("asura", "series", "part?01",
                       [row("asura", "series", "part/01")]), "punctuation collision")
precondition(collision("asura", "series", "..",
                       [row("asura", "series", ".")]), "dot basename collision")
precondition(collision("asura", "series", "CHAPTER-ONE",
                       [row("asura", "series", "chapter-one")]), "case collision")
precondition(collision("asura", "Résumé", "first",
                       [row("asura", "Resume", "first")]), "Unicode conservative")
precondition(collision("ASURA", "series", "first",
                       [row("asura", "series", "first")]), "source case collision")
precondition(!collision("asura", "series", "part/01",
                        [row("asura", "series", "part/01")]), "same identity is fine")
precondition(!collision("asura", "series", "part?01",
                        [row("asura", "another-series", "part/01")]),
             "different parents stay separate")
precondition(!collision("asura", "series", "part?01", []), "empty DB list")
print("PASS EQ Swift: collisions denied; independent chapters remain usable")
"""
        with tempfile.TemporaryDirectory(prefix="wr-eq-canonical-") as temp:
            root = Path(temp)
            extra = root / "OfflineCanonicalOwnership.swift"
            main = root / "main.swift"
            binary = root / "eq-synthetic-test"
            extra.write_text(
                "import Foundation\n" + path + "\n" + owner, encoding="utf-8"
            )
            main.write_text(fixture, encoding="utf-8")
            compiled = subprocess.run(
                [swift, "-swift-version", "5", str(extra), str(main),
                 "-o", str(binary)], text=True, capture_output=True, timeout=120
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr[-5000:])
            executed = subprocess.run(
                [str(binary)], text=True, capture_output=True, timeout=30
            )
            self.assertEqual(executed.returncode, 0,
                             executed.stdout + executed.stderr[-5000:])
            self.assertIn("PASS EQ Swift:", executed.stdout)


if __name__ == "__main__":
    unittest.main()
