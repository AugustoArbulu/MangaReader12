import Foundation
import SQLite3

final class SQLiteDatabase {
    private let queue = DispatchQueue(label: "com.mangareader12.database")
    private let path: String
    private var handle: OpaquePointer?

    init(path: String) {
        self.path = path
    }

    deinit {
        close()
    }

    static func defaultDatabase() throws -> SQLiteDatabase {
        let fileManager = FileManager.default
        guard let base = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            throw SQLiteDatabaseError.applicationSupportUnavailable
        }

        let directory = base.appendingPathComponent("MangaReader12", isDirectory: true)
        try fileManager.createDirectory(at: directory, withIntermediateDirectories: true, attributes: nil)
        let databaseURL = directory.appendingPathComponent("library.sqlite", isDirectory: false)
        return SQLiteDatabase(path: databaseURL.path)
    }

    func openAndMigrate() throws {
        try queue.sync {
            try openIfNeeded()
            try executeUnlocked("PRAGMA foreign_keys = ON;")
            try executeUnlocked("PRAGMA journal_mode = WAL;")
            try migrateUnlocked()
        }
    }

    func userVersion() throws -> Int {
        return try queue.sync {
            try openIfNeeded()

            var statement: OpaquePointer?
            defer { sqlite3_finalize(statement) }

            guard sqlite3_prepare_v2(handle, "PRAGMA user_version;", -1, &statement, nil) == SQLITE_OK else {
                throw lastError()
            }

            guard sqlite3_step(statement) == SQLITE_ROW else {
                throw lastError()
            }

            return Int(sqlite3_column_int(statement, 0))
        }
    }

    func close() {
        queue.sync {
            if let handle = handle {
                sqlite3_close(handle)
                self.handle = nil
            }
        }
    }

    private func openIfNeeded() throws {
        guard handle == nil else { return }

        var database: OpaquePointer?
        let flags = SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX
        let result = sqlite3_open_v2(path, &database, flags, nil)

        guard result == SQLITE_OK, let opened = database else {
            if let database = database {
                sqlite3_close(database)
            }
            throw SQLiteDatabaseError.openFailed(code: result)
        }

        handle = opened
    }

    private func migrateUnlocked() throws {
        let version = try userVersionUnlocked()
        guard version < 1 else { return }

        try executeUnlocked("BEGIN IMMEDIATE TRANSACTION;")
        do {
            try executeUnlocked(Self.schemaV1)
            try executeUnlocked("PRAGMA user_version = 1;")
            try executeUnlocked("COMMIT;")
        } catch {
            try? executeUnlocked("ROLLBACK;")
            throw error
        }
    }

    private func userVersionUnlocked() throws -> Int {
        var statement: OpaquePointer?
        defer { sqlite3_finalize(statement) }

        guard sqlite3_prepare_v2(handle, "PRAGMA user_version;", -1, &statement, nil) == SQLITE_OK else {
            throw lastError()
        }

        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw lastError()
        }

        return Int(sqlite3_column_int(statement, 0))
    }

    private func executeUnlocked(_ sql: String) throws {
        var errorMessage: UnsafeMutablePointer<Int8>?
        let result = sqlite3_exec(handle, sql, nil, nil, &errorMessage)

        guard result == SQLITE_OK else {
            let message = errorMessage.map { String(cString: $0) } ?? "Unknown SQLite error"
            if let errorMessage = errorMessage {
                sqlite3_free(errorMessage)
            }
            throw SQLiteDatabaseError.executionFailed(code: result, message: message)
        }

        if let errorMessage = errorMessage {
            sqlite3_free(errorMessage)
        }
    }

    private func lastError() -> SQLiteDatabaseError {
        let code = sqlite3_errcode(handle)
        let message: String
        if let cString = sqlite3_errmsg(handle) {
            message = String(cString: cString)
        } else {
            message = "Unknown SQLite error"
        }
        return .executionFailed(code: code, message: message)
    }

    private static let schemaV1 = """
    CREATE TABLE IF NOT EXISTS manga (
        internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL,
        source_manga_id TEXT NOT NULL,
        title TEXT NOT NULL,
        cover TEXT,
        description TEXT,
        status TEXT NOT NULL DEFAULT 'unknown',
        url TEXT,
        last_update REAL,
        date_added REAL NOT NULL,
        UNIQUE(source_id, source_manga_id)
    );

    CREATE TABLE IF NOT EXISTS library (
        manga_id INTEGER PRIMARY KEY,
        date_added REAL NOT NULL,
        last_checked REAL,
        FOREIGN KEY(manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS chapters (
        internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        manga_id INTEGER NOT NULL,
        source_chapter_id TEXT NOT NULL,
        name TEXT NOT NULL,
        number REAL,
        volume REAL,
        url TEXT,
        is_read INTEGER NOT NULL DEFAULT 0,
        last_page_read INTEGER NOT NULL DEFAULT 0,
        bookmarked INTEGER NOT NULL DEFAULT 0,
        downloaded INTEGER NOT NULL DEFAULT 0,
        UNIQUE(manga_id, source_chapter_id),
        FOREIGN KEY(manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS categories (
        internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        sort_order INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS manga_categories (
        manga_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        PRIMARY KEY(manga_id, category_id),
        FOREIGN KEY(manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE,
        FOREIGN KEY(category_id) REFERENCES categories(internal_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS history (
        manga_id INTEGER PRIMARY KEY,
        chapter_id INTEGER,
        last_read_at REAL NOT NULL,
        FOREIGN KEY(manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE,
        FOREIGN KEY(chapter_id) REFERENCES chapters(internal_id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS downloads (
        internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chapter_id INTEGER NOT NULL UNIQUE,
        state TEXT NOT NULL,
        progress REAL NOT NULL DEFAULT 0,
        local_path TEXT,
        updated_at REAL NOT NULL,
        FOREIGN KEY(chapter_id) REFERENCES chapters(internal_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS sources (
        source_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        version TEXT NOT NULL,
        lang TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        manifest_json TEXT NOT NULL,
        installed_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS repositories (
        internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE,
        enabled INTEGER NOT NULL DEFAULT 1,
        last_refresh REAL
    );

    CREATE TABLE IF NOT EXISTS source_settings (
        source_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT,
        PRIMARY KEY(source_id, key),
        FOREIGN KEY(source_id) REFERENCES sources(source_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS migration_map (
        internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_manga_id INTEGER NOT NULL,
        destination_manga_id INTEGER NOT NULL,
        migrated_at REAL NOT NULL,
        FOREIGN KEY(source_manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE,
        FOREIGN KEY(destination_manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_manga_source ON manga(source_id, source_manga_id);
    CREATE INDEX IF NOT EXISTS idx_chapters_manga ON chapters(manga_id, number, volume);
    CREATE INDEX IF NOT EXISTS idx_downloads_state ON downloads(state);
    """
}

enum SQLiteDatabaseError: Error, LocalizedError {
    case applicationSupportUnavailable
    case openFailed(code: Int32)
    case executionFailed(code: Int32, message: String)

    var errorDescription: String? {
        switch self {
        case .applicationSupportUnavailable:
            return "Application Support directory is unavailable."
        case .openFailed(let code):
            return "Could not open SQLite database (code \(code))."
        case .executionFailed(let code, let message):
            return "SQLite error \(code): \(message)"
        }
    }
}
