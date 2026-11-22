#!/usr/bin/env python3
"""Build70/DM: host-only real Swift schema-v1/offline reopen fixture.

A read-only *source extraction* of the actual WebReader Swift implementation
is compiled on the macOS runner against TEMPORARY synthetic SQLite and page
files. The fixture intentionally creates its own fake DB and files in the
runner's disposable directory; it NEVER accesses or mutates any iPad data.

No IPA, code signing, appinst, networking, real WebReader app launch, install,
private files or release. This does NOT prove physical app-container retention.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
DB = "MangaReader12/Database/SQLiteDatabase.swift"
DOWNLOADS = "MangaReader12/Downloads/ChapterDownloadManager.swift"
INVENTORY = "MangaReader12/Downloads/WebReaderOfflinePageInventory.swift"
RECEIPT = "MangaReader12/Downloads/WebReaderOfflineCompletionReceipt.swift"
BACKUP = "MangaReader12/Core/BackupManager.swift"
STORAGE = "MangaReader12/Core/StorageManager.swift"
BEGIN_RELOCATION = "// BEGIN OFFLINE_PATH_RELOCATION"
END_RELOCATION = "// END OFFLINE_PATH_RELOCATION"
END_DB = "// MARK: - Installed source persistence"


class DMRejected(ValueError):
    pass


def audited_swift_sources(base: Path = ROOT) -> tuple[str, str, str, str]:
    """Require stable real-source invariants; never approximate SQL fixtures."""
    files = {}
    for relative in (DB, DOWNLOADS, INVENTORY, RECEIPT, BACKUP, STORAGE):
        path = base / relative
        if path.is_symlink() or not path.is_file():
            raise DMRejected("required Swift source unavailable")
        files[relative] = path.read_text(encoding="utf-8")
    db, downloads = files[DB], files[DOWNLOADS]
    backup, storage = files[BACKUP], files[STORAGE]
    if db.count(END_DB) != 1 or db.count("final class SQLiteDatabase {") != 1:
        raise DMRejected("cannot isolate exact real Swift database class")
    top = db[:db.index(END_DB)]
    invariants = (
        "static let currentSchemaVersion = 1",
        "func openAndMigrate() throws",
        'try executeUnlocked("PRAGMA foreign_keys = ON;")',
        'try executeUnlocked("PRAGMA journal_mode = WAL;")',
        "try migrateUnlocked()",
        "guard foundVersion <= Self.currentSchemaVersion else {",
        "throw SQLiteDatabaseError.unsupportedSchemaVersion(foundVersion)",
        "guard version <= Self.currentSchemaVersion else {",
        "throw SQLiteDatabaseError.unsupportedSchemaVersion(version)",
        "guard version < Self.currentSchemaVersion else { return }",
        'try executeUnlocked("BEGIN IMMEDIATE TRANSACTION;")',
        "try executeUnlocked(Self.schemaV1)",
        "try executeUnlocked(\"COMMIT;\")",
        'try? executeUnlocked("ROLLBACK;")',
        "SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX",
    )
    for value in invariants:
        if value not in top:
            raise DMRejected("database migration invariant changed")
    for table in (
        "manga", "library", "chapters", "downloads", "history",
        "categories", "manga_categories",
    ):
        if f"CREATE TABLE IF NOT EXISTS {table} (" not in top:
            raise DMRejected("schema-v1 persistence table missing")
    if (downloads.count(BEGIN_RELOCATION) != 1 or
            downloads.count(END_RELOCATION) != 1):
        raise DMRejected("cannot isolate real current-container path resolver")
    path_fragment = downloads.split(BEGIN_RELOCATION, 1)[1].split(END_RELOCATION, 1)[0]
    for component in (
        "enum OfflineDownloadPath",
        "static func chapterDirectory(",
        'appendingPathComponent("MangaReader12", isDirectory: true)',
        'appendingPathComponent("Downloads", isDirectory: true)',
        "safeComponent(sourceID)", "safeComponent(mangaID)",
        "safeComponent(chapterID)",
    ):
        if component not in path_fragment:
            raise DMRejected("current-container offline path resolver changed")
    inventory = files[INVENTORY]
    receipt = files[RECEIPT]
    for token in (
        'file.lastPathComponent == expected',
        'meta.isSymbolicLink != true', 'meta.isRegularFile == true',
        'byteCount > 0', 'static let maximumPages = 99_999',
    ):
        if token not in inventory:
            raise DMRejected("offline page guard changed")
    for token in (
        'static let filename = ".webreader-completion-v1"',
        "static func verifyIfPresent(",
        "values.isSymbolicLink != true",
        'text == prefix + String(actualPages) + "\\n"',
    ):
        if token not in receipt:
            raise DMRejected("offline receipt guard changed")
    # Backup restore is explicitly destructive for offline images.
    if ('func restoreBackup(from url: URL)' not in backup or
            "try clearExcludedDownloadFiles()" not in backup or
            "try fileManager.removeItem(at: downloads)" not in backup):
        raise DMRejected("backup destructive behavior changed: re-review required")
    # Fase ET: "Apagar todos" can only delegate to the synchronized
    # chapter-scoped, preflighted bulk path. Never accept the obsolete
    # recursive Downloads-root erase or unconditional SQLite clearAll.
    marker = "func clearAllDownloads() throws {"
    if storage.count(marker) != 1 or "func reindexDownloads()" not in storage:
        raise DMRejected("download erasure API moved: re-review required")
    clear_body = storage.split(marker, 1)[1].split("func reindexDownloads()", 1)[0]
    if ("ChapterDownloadManager.defaultManager().removeAllConfirmed()" not in clear_body
            or "removeItem(" in clear_body
            or "downloadsRepository.clearAll()" in clear_body):
        raise DMRejected("unsafe bulk download erasure: re-review required")

    bulk_start = "// BEGIN BUILD70_ET_BOUNDED_BULK_DELETE"
    bulk_end = "// END BUILD70_ET_BOUNDED_BULK_DELETE"
    if downloads.count(bulk_start) != 1 or downloads.count(bulk_end) != 1:
        raise DMRejected("bounded bulk deletion source unavailable")
    bulk = downloads.split(bulk_start, 1)[1].split(bulk_end, 1)[0]
    for required in (
        "func removeAllConfirmed() throws -> Int",
        "guard runningKey == nil, pending.isEmpty else {",
        "WebReaderOfflineCanonicalOwnership.collides(",
        "WebReaderOfflineDeletionPreflight.inspect(",
        "guard actual == item.verdict else {",
        "try fileManager.removeItem(at: item.directory)",
        "try repository.remove(",
    ):
        if required not in bulk:
            raise DMRejected("unsafe bulk download guard changed")
    # The ET worker intentionally audits twice: all rows before any write,
    # then the selected folder again immediately before its actual removal.
    # A single remaining call must not satisfy the security contract.
    if bulk.count("WebReaderOfflineDeletionPreflight.inspect(") != 2:
        raise DMRejected("first-pass or final deletion preflight removed")
    if ("removeItem(at: downloadsDirectory()" in bulk
            or "downloadsRepository.clearAll()" in bulk
            or 'executeSQLite("DELETE FROM downloads;' in bulk):
        raise DMRejected("unbounded download erasure reintroduced")
    if not re.search(r"private static let schemaV1 = \"\"\"", top):
        raise DMRejected("cannot isolate schema-v1 SQL")
    return top, path_fragment, inventory, receipt


# Swift executable fixture, concatenated after actual isolated Swift classes.
# The code under test (DB open/migrate, current-container resolver, file
# inventory, receipt) is copied VERBATIM from current repository source.
# Only these synthetic test instructions are new.
SWIFT_TEST = r'''
enum DMFixtureError: Error { case assertion(String) }

func dmCheck(_ condition: Bool, _ message: String) throws {
    guard condition else { throw DMFixtureError.assertion(message) }
}

func dmExec(_ db: SQLiteDatabase, _ sql: String) throws {
    try db.withConnection { handle in
        var err: UnsafeMutablePointer<Int8>?
        let code = sqlite3_exec(handle, sql, nil, nil, &err)
        defer { if let value = err { sqlite3_free(value) } }
        guard code == SQLITE_OK else {
            throw DMFixtureError.assertion("synthetic fixture SQL failed")
        }
    }
}

func dmScalar(_ db: SQLiteDatabase, _ sql: String) throws -> String {
    return try db.withConnection { handle in
        var query: OpaquePointer?
        guard sqlite3_prepare_v2(handle, sql, -1, &query, nil) == SQLITE_OK,
              let stmt = query else {
            sqlite3_finalize(query)
            throw DMFixtureError.assertion("query prepare")
        }
        defer { sqlite3_finalize(stmt) }
        guard sqlite3_step(stmt) == SQLITE_ROW else {
            throw DMFixtureError.assertion("query row")
        }
        if let text = sqlite3_column_text(stmt, 0) {
            return String(cString: text)
        }
        throw DMFixtureError.assertion("non-text result")
    }
}

func dmSnapshot(_ db: SQLiteDatabase) throws -> [String] {
    let statements: [String] = [
        "PRAGMA user_version;",
        "SELECT COUNT(*) FROM manga;",
        "SELECT COUNT(*) FROM library;",
        "SELECT COUNT(*) FROM chapters;",
        "SELECT COUNT(*) FROM history;",
        "SELECT COUNT(*) FROM downloads WHERE state='completed';",
        "SELECT COUNT(*) FROM categories;",
        "SELECT COUNT(*) FROM manga_categories;",
        "SELECT title FROM manga WHERE internal_id=7;",
        "SELECT CAST(is_read AS TEXT) FROM chapters WHERE internal_id=3;",
        "SELECT CAST(last_page_read AS TEXT) FROM chapters WHERE internal_id=3;",
        "SELECT CAST(bookmarked AS TEXT) FROM chapters WHERE internal_id=3;",
        "SELECT state FROM downloads WHERE chapter_id=3;",
        "SELECT local_path FROM downloads WHERE chapter_id=3;",
        "SELECT name FROM categories WHERE internal_id=9;",
        "SELECT CAST(last_read_at AS TEXT) FROM history WHERE manga_id=7;",
    ]
    return try statements.map { try dmScalar(db, $0) }
}

func dmMain() throws {
    guard CommandLine.arguments.count == 2 else {
        throw DMFixtureError.assertion("requires temporary synthetic directory")
    }
    let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
    let support = root.appendingPathComponent("Application Support", isDirectory: true)
    let folder = support.appendingPathComponent("MangaReader12", isDirectory: true)
    try FileManager.default.createDirectory(
        at: folder, withIntermediateDirectories: true
    )
    let sqlite = folder.appendingPathComponent("library.sqlite")
    // This path deliberately refers to a stale iOS container. Actual offline
    // chapter pages must resolve under the CURRENT temp Application Support.
    let stale = "/var/mobile/Containers/Data/Application/OLD/Library/Application Support/Downloads"
    let directory = OfflineDownloadPath.chapterDirectory(
        applicationSupport: support,
        sourceID: "fixture.source",
        mangaID: "fake/example",
        chapterID: "chapter-1"
    )
    try dmCheck(!directory.path.contains("OLD"), "stale path reused")
    try dmCheck(directory.path.hasPrefix(support.path + "/MangaReader12/Downloads/"),
                "current-container path changed")
    try FileManager.default.createDirectory(
        at: directory, withIntermediateDirectories: true
    )
    let pageA = directory.appendingPathComponent("page-00000.bin")
    let pageB = directory.appendingPathComponent("page-00001.bin")
    let first = Data([0x01, 0x02, 0xC3, 0x55, 0x00, 0xAA])
    let second = Data([0x91, 0x00, 0x45, 0xFF, 0x0A])
    try first.write(to: pageA)
    try second.write(to: pageB)
    try WebReaderOfflineCompletionReceipt.write(
        directory: directory, expectedPages: 2
    )
    let initial = try WebReaderOfflinePageInventory.inspect(directory: directory)
    try dmCheck(initial.count == 2, "initial page inventory")
    try dmCheck(try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: directory, actualPages: initial.count), "initial receipt")

    let old = SQLiteDatabase(path: sqlite.path)
    try old.openAndMigrate()
    try dmExec(old, """
    INSERT INTO manga (internal_id,source_id,source_manga_id,title,status,date_added)
        VALUES (7,'fixture.source','fake/example','Fictional title','ongoing',1.0);
    INSERT INTO library (manga_id,date_added) VALUES (7,1.0);
    INSERT INTO chapters
        (internal_id,manga_id,source_chapter_id,name,is_read,last_page_read,bookmarked,downloaded)
        VALUES (3,7,'chapter-1','Synthetic chapter',1,4,1,1);
    INSERT INTO downloads (internal_id,chapter_id,state,progress,local_path,updated_at)
        VALUES (10,3,'completed',1.0,
        '/var/mobile/Containers/Data/Application/OLD/Library/Application Support/Downloads',1.0);
    INSERT INTO history (manga_id,chapter_id,last_read_at) VALUES (7,3,12.5);
    INSERT INTO categories (internal_id,name) VALUES (9,'Fixture favorites');
    INSERT INTO manga_categories (manga_id,category_id) VALUES (7,9);
    """)
    let before = try dmSnapshot(old)
    try dmCheck(before[0] == "1", "not schema v1")
    try dmCheck(before[1...7].allSatisfy { $0 == "1" }, "fixture rows")
    try dmCheck(before[8] == "Fictional title", "title changed")
    try dmCheck(before[9] == "1" && before[10] == "4" &&
        before[11] == "1", "reader progress or bookmark")
    try dmCheck(before[12] == "completed" && before[13] == stale,
                "download record changed")
    old.close()

    // Simulates reopening existing schema-v1 data using *unchanged*
    // production SQLiteDatabase.openAndMigrate() Swift code. This does
    // not simulate iOS installation nor AppDelegate startup.
    let reopened = SQLiteDatabase(path: sqlite.path)
    try reopened.openAndMigrate()
    let after = try dmSnapshot(reopened)
    try dmCheck(after == before, "existing chapter/bookmark/library data changed")
    reopened.close()

    // A database with a FUTURE schema must fail closed and preserve all
    // fictional contents: this is never a physical user's database.
    let preparation = SQLiteDatabase(path: sqlite.path)
    try dmExec(preparation, "PRAGMA user_version = 2;")
    preparation.close()
    let incompatible = SQLiteDatabase(path: sqlite.path)
    do {
        try incompatible.openAndMigrate()
        throw DMFixtureError.assertion("future SQLite schema 2 accepted by v1 reader")
    } catch SQLiteDatabaseError.unsupportedSchemaVersion(let version) {
        try dmCheck(version == 2, "wrong rejected future schema version")
    }
    incompatible.close()
    let afterRejected = SQLiteDatabase(path: sqlite.path)
    let preserved = try dmSnapshot(afterRejected)
    try dmCheck(preserved[0] == "2", "future version marker was overwritten")
    try dmCheck(Array(preserved.dropFirst()) == Array(before.dropFirst()),
                "future schema rejection changed library/favorites/progress")
    try dmExec(afterRejected, "PRAGMA user_version = 1;")
    afterRejected.close()

    try dmCheck(try Data(contentsOf: pageA) == first &&
                Data(contentsOf: pageB) == second,
                "offline page bytes changed after DB reopen")
    let final = try WebReaderOfflinePageInventory.inspect(directory: directory)
    try dmCheck(final.count == 2, "reopened inventory missing page")
    try dmCheck(try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: directory, actualPages: 2), "reopened completion receipt")

    // Negative safety check on ONLY the disposable fixture: a missing
    // *final* page still leaves a valid sequential prefix; the original
    // two-page count receipt must reject the shortened directory.
    try FileManager.default.removeItem(at: pageB)
    let shortened = try WebReaderOfflinePageInventory.inspect(directory: directory)
    try dmCheck(shortened.count == 1, "fixture shortened to one page")
    do {
        _ = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
            directory: directory, actualPages: shortened.count
        )
        throw DMFixtureError.assertion("truncated last page falsely accepted")
    } catch WebReaderOfflineCompletionReceipt.ReceiptError.invalidReceipt {
        // Expected: the receipt sealed two pages, now only one remains.
    }
    try second.write(to: pageB)
    try dmCheck(try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: directory, actualPages: 2), "restored synthetic fixture")
    print("PASS DM: production Swift SQLite v1 reopen preserved fictional records, read-state, bookmarks, historical path and 2 offline files; future v2 schema rejected without data loss; missing final page detected")
}

do {
    try dmMain()
} catch {
    fputs("DM_REJECTED: synthetic Swift fixture failed\n", stderr)
    exit(1)
}
'''


def inspect_source_only() -> dict:
    parts = audited_swift_sources()
    return {
        "status": "DM_SOURCE_SCHEMA_V1_AND_OFFLINE_INVARIANTS_ONLY",
        "sourceSectionCount": len(parts),
        "databaseSchema": 1,
        "realSQLiteDataContentsVerifiedOnPhysicalIPad": False,
        "appContainerAfterUpgradeRetainedProven": False,
        "offlineImageDecodingVerified": False,
        "realBuild71InstallationTested": False,
        "ownerApprovalForQARecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstall": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def run_native_swift_fixture() -> dict:
    if sys.platform != "darwin":
        raise DMRejected("actual Swift integration fixture needs macOS")
    if not shutil.which("xcrun"):
        raise DMRejected("missing Apple SDK compiler")
    parts = audited_swift_sources()
    # Production exact slices, not Python reimplementations.
    whole = "\n".join(parts) + "\n" + SWIFT_TEST
    with tempfile.TemporaryDirectory(prefix="wr-dm-ios12-data-host-fixture-") as tmp:
        t = Path(tmp)
        swift = t / "dm-real-compiled.swift"
        exe = t / "dm-real-compiled"
        user_files = t / "disposable-library"
        user_files.mkdir()
        swift.write_text(whole, encoding="utf-8")
        try:
            compile = subprocess.run([
                "xcrun", "--sdk", "macosx", "swiftc",
                str(swift), "-o", str(exe),
            ], capture_output=True, text=True, timeout=180)
            if compile.returncode != 0:
                raise DMRejected(
                    "Swift production-extract compilation failed:\n" +
                    compile.stderr[-5000:]
                )
            execute = subprocess.run(
                [str(exe), str(user_files)],
                capture_output=True, text=True, timeout=60,
            )
            if execute.returncode != 0 or not execute.stdout.startswith("PASS DM:"):
                raise DMRejected(
                    "Swift real-source fixture failed:\n" +
                    execute.stderr[-5000:]
                )
            message = execute.stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise DMRejected("native Swift fixture unavailable") from exc
    return {
        "status": "DM_REAL_SWIFT_SQLITE_AND_OFFLINE_HOST_FIXTURE_PASS",
        "nativeFixtureResult": message,
        "schemaV1ExistingDataReopenedOnMac": True,
        "fictionalReaderProgressAndFavoritesPreservedOnMac": True,
        "fictionalOfflineFileBytesPreservedOnMac": True,
        "syntheticMissingLastPageDetected": True,
        "syntheticFutureSchemaRejectedWithoutRowLoss": True,
        "realDeviceIOS12ExecutionProven": False,
        "realAppUpgradePreservationProven": False,
        "actualUserLibraryVerified": False,
        "realOfflineImageDecodingProven": False,
        "publisherAuthenticated": False,
        "ownerDistributionApprovalRecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstall": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--native-swift-test", action="store_true")
    args = cli.parse_args()
    try:
        receipt = (
            run_native_swift_fixture()
            if args.native_swift_test else inspect_source_only()
        )
    except DMRejected as exc:
        cli.error("BLOCKED: " + str(exc))
    print(json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
