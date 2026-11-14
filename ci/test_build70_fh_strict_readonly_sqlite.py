#!/usr/bin/env python3
"""FH: compile extracted real SQLite v1 read-only audit on synthetic fixtures."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
DB = (ROOT / "MangaReader12/Database/SQLiteDatabase.swift").read_text()
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()

def between(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]

class FHStrictReadOnlyTests(unittest.TestCase):
    def test_db_rejects_migration_and_enforces_readonly(self):
        method = between(DB, "// BEGIN BUILD70_FH_STRICT_READONLY_SQLITE",
                            "// END BUILD70_FH_STRICT_READONLY_SQLITE")
        for required in ("SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX",
                         "sqlite3_db_readonly", "PRAGMA query_only = ON",
                         "BEGIN TRANSACTION;", "PRAGMA user_version;",
                         "auditRequiresSchemaV1", "ROLLBACK;", "COMMIT;"):
            self.assertIn(required, method)
        for forbidden in ("SQLITE_OPEN_CREATE", "openAndMigrate(", "migrateUnlocked(",
                          "PRAGMA journal_mode", "CREATE TABLE", "DELETE FROM downloads"):
            # Only code (not comments) is searched; comments explain exclusions.
            code = "\n".join(x for x in method.splitlines() if not x.lstrip().startswith("//"))
            self.assertNotIn(forbidden, code)

    def test_list_is_bounded_and_inconsistent_rows_require_review(self):
        method = between(DB, "// BEGIN BUILD70_FH_READONLY_DOWNLOAD_ROWS",
                            "// END BUILD70_FH_READONLY_DOWNLOAD_ROWS")
        for required in ("withStrictReadOnlyConnection", "LIMIT 5001;",
                         "records.count < 5_000", "auditRecordLimitExceeded",
                         "c.downloaded <> 1", "inconsistent-completed"):
            self.assertIn(required, method)
        self.assertNotIn("openAndMigrate(", "\n".join(
            x for x in method.splitlines() if not x.lstrip().startswith("//")))

    def test_manager_is_provisional_and_does_not_call_normal_list(self):
        method = between(MANAGER, "// BEGIN BUILD70_FH_READONLY_SQLITE_TO_PREVIEW",
                             "// END BUILD70_FH_READONLY_SQLITE_TO_PREVIEW")
        self.assertIn("repository.listDownloadsForAuditReadOnly()", method)
        self.assertIn("previewOfflineDeletionCandidates(from: rows)", method)
        for forbidden in ("removeItem(", "renameat(", "sqlite3_exec(",
                          "repository.listDownloads()", "try repository.remove("):
            self.assertNotIn(forbidden, method)
        self.assertEqual(MANAGER.count("func previewOfflineDeletionCandidatesFromSQLiteReadOnly()"), 1)

    def test_compiles_real_sqlite_class_and_checks_db_without_writes(self):
        if not shutil.which("swiftc"):
            self.skipTest("Swift unavailable")
        dbClass = "final class SQLiteDatabase {" + between(
            DB, "final class SQLiteDatabase {", "\nenum SQLiteDatabaseError")
        errors = "enum SQLiteDatabaseError" + between(
            DB, "enum SQLiteDatabaseError", "\n// MARK: - Installed source persistence")
        downloadRecord = "struct DownloadListRecord" + between(
            DB, "struct DownloadListRecord", "\nfinal class ReadingProgressRepository")
        method = between(DB, "// BEGIN BUILD70_FH_READONLY_DOWNLOAD_ROWS",
                         "// END BUILD70_FH_READONLY_DOWNLOAD_ROWS")
        helpers = "private func executeSQLite(" + DB.split("private func executeSQLite(", 1)[1]
        source = r'''
import Foundation
import SQLite3
''' + dbClass + "\n" + errors + "\n" + downloadRecord + r'''
final class DownloadAuditSandbox {
    let database: SQLiteDatabase
    init(_ database: SQLiteDatabase) { self.database = database }
''' + method + "\n}\n" + helpers + r'''
@main struct FHRunner {
    static func exec(_ db: OpaquePointer, _ sql: String) {
        precondition(sqlite3_exec(db, sql, nil, nil, nil) == SQLITE_OK, sql)
    }
    static func main() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FH-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: false)
        defer { try? FileManager.default.removeItem(at: root) }
        let path = root.appendingPathComponent("library.sqlite").path
        let database = SQLiteDatabase(path: path)
        try database.openAndMigrate()
        try database.withConnection { h in
            exec(h, "INSERT INTO manga(source_id,source_manga_id,title,date_added) VALUES ('s','m','Fixture',1);")
            exec(h, "INSERT INTO chapters(manga_id,source_chapter_id,name,downloaded) VALUES (1,'c1','First',1),(1,'c2','Second',0);")
            exec(h, "INSERT INTO downloads(chapter_id,state,updated_at) VALUES (1,'completed',10),(2,'completed',9);")
        }
        let sandbox = DownloadAuditSandbox(database)
        let first = try sandbox.listDownloadsForAuditReadOnly()
        precondition(first.count == 2)
        precondition(first[0].state == "completed")
        precondition(first[1].state == "inconsistent-completed")
        try database.withStrictReadOnlyConnection { h in
            precondition(sqlite3_db_readonly(h, "main") == 1)
            let mutation = sqlite3_exec(h, "DELETE FROM downloads;", nil, nil, nil)
            precondition(mutation != SQLITE_OK)
        }
        let after = try sandbox.listDownloadsForAuditReadOnly()
        precondition(after.count == 2)
        try database.withConnection { h in exec(h, "PRAGMA user_version = 2;") }
        do {
            _ = try sandbox.listDownloadsForAuditReadOnly()
            fatalError("unexpected schema accepted")
        } catch SQLiteDatabaseError.auditRequiresSchemaV1(let v) {
            precondition(v == 2)
        }
        try database.withConnection { h in exec(h, "PRAGMA user_version = 1;") }
        // Add >5000 synthetic download rows to exercise allocation bounds.
        try database.withConnection { h in
            exec(h, """
            WITH RECURSIVE n(x) AS (
                SELECT 3 UNION ALL SELECT x+1 FROM n WHERE x < 5002
            )
            INSERT INTO chapters(manga_id, source_chapter_id, name, downloaded)
            SELECT 1, printf('chapter-%d',x), 'Synthetic', 1 FROM n;
            """)
            exec(h, """
            INSERT INTO downloads(chapter_id, state, updated_at)
            SELECT internal_id, 'completed', 5 FROM chapters
            WHERE internal_id > 2;
            """)
        }
        do {
            _ = try sandbox.listDownloadsForAuditReadOnly()
            fatalError("unbounded result accepted")
        } catch SQLiteDatabaseError.auditRecordLimitExceeded {
            // Expected.
        }
        let absent = root.appendingPathComponent("absent.sqlite").path
        do {
            _ = try SQLiteDatabase(path: absent).withStrictReadOnlyConnection { _ in true }
            fatalError("nonexistent DB created")
        } catch {
            precondition(!FileManager.default.fileExists(atPath: absent))
        }
        print("FH_SQLITE_READONLY_INTEGRATION_PASS")
    }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            swift = tmp / "fh.swift"
            exe = tmp / "fh"
            swift.write_text(source)
            command = ["swiftc", "-parse-as-library"]
            if sys.platform != "darwin":
                mod = tmp / "SQLite3"
                mod.mkdir()
                (mod / "module.modulemap").write_text(
                    'module SQLite3 [system] { header "/usr/include/sqlite3.h" link "sqlite3" export * }\n')
                command += ["-I", str(tmp)]
            command += [str(swift), "-lsqlite3", "-o", str(exe)]
            compilation = subprocess.run(command, text=True, capture_output=True, timeout=90)
            self.assertEqual(compilation.returncode, 0, compilation.stderr)
            execution = subprocess.run([str(exe)], text=True, capture_output=True, timeout=50)
            self.assertEqual(execution.returncode, 0, execution.stderr)
            self.assertIn("FH_SQLITE_READONLY_INTEGRATION_PASS", execution.stdout)

if __name__ == "__main__":
    unittest.main()
