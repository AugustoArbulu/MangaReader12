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

    func withConnection<T>(_ block: (OpaquePointer) throws -> T) throws -> T {
        return try queue.sync {
            try openIfNeeded()
            guard let handle = handle else {
                throw SQLiteDatabaseError.connectionUnavailable
            }
            return try block(handle)
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
    case connectionUnavailable
    case openFailed(code: Int32)
    case executionFailed(code: Int32, message: String)

    var errorDescription: String? {
        switch self {
        case .applicationSupportUnavailable:
            return "Application Support directory is unavailable."
        case .connectionUnavailable:
            return "SQLite connection is unavailable."
        case .openFailed(let code):
            return "Could not open SQLite database (code \(code))."
        case .executionFailed(let code, let message):
            return "SQLite error \(code): \(message)"
        }
    }
}

// MARK: - Installed source persistence

struct InstalledSourceRecord: Equatable {
    let manifest: SourceManifest
    let enabled: Bool
    let installedAt: TimeInterval
    let updatedAt: TimeInterval
}

final class SourceRepository {
    private let database: SQLiteDatabase

    init(database: SQLiteDatabase) {
        self.database = database
    }

    func save(manifest: SourceManifest, enabled: Bool = true) throws {
        try manifest.validate()
        try database.openAndMigrate()

        let manifestData = try JSONEncoder().encode(manifest)
        guard let manifestJSON = String(data: manifestData, encoding: .utf8) else {
            throw SourceRepositoryError.manifestEncodingFailed
        }

        let now = Date().timeIntervalSince1970

        try database.withConnection { handle in
            let updateSQL = """
            UPDATE sources
            SET name = ?, version = ?, lang = ?, enabled = ?, manifest_json = ?, updated_at = ?
            WHERE source_id = ?;
            """

            let update = try prepareStatement(updateSQL, handle: handle)
            defer { sqlite3_finalize(update) }

            try bindText(manifest.name, index: 1, statement: update)
            try bindText(manifest.version, index: 2, statement: update)
            try bindText(manifest.lang, index: 3, statement: update)
            guard sqlite3_bind_int(update, 4, enabled ? 1 : 0) == SQLITE_OK else {
                throw sqliteError(handle)
            }
            try bindText(manifestJSON, index: 5, statement: update)
            guard sqlite3_bind_double(update, 6, now) == SQLITE_OK else {
                throw sqliteError(handle)
            }
            try bindText(manifest.id, index: 7, statement: update)

            guard sqlite3_step(update) == SQLITE_DONE else {
                throw sqliteError(handle)
            }

            if sqlite3_changes(handle) == 0 {
                let insertSQL = """
                INSERT INTO sources
                (source_id, name, version, lang, enabled, manifest_json, installed_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """

                let insert = try prepareStatement(insertSQL, handle: handle)
                defer { sqlite3_finalize(insert) }

                try bindText(manifest.id, index: 1, statement: insert)
                try bindText(manifest.name, index: 2, statement: insert)
                try bindText(manifest.version, index: 3, statement: insert)
                try bindText(manifest.lang, index: 4, statement: insert)
                guard sqlite3_bind_int(insert, 5, enabled ? 1 : 0) == SQLITE_OK else {
                    throw sqliteError(handle)
                }
                try bindText(manifestJSON, index: 6, statement: insert)
                guard sqlite3_bind_double(insert, 7, now) == SQLITE_OK,
                      sqlite3_bind_double(insert, 8, now) == SQLITE_OK else {
                    throw sqliteError(handle)
                }

                guard sqlite3_step(insert) == SQLITE_DONE else {
                    throw sqliteError(handle)
                }
            }
        }
    }

    func fetch(sourceID: String) throws -> InstalledSourceRecord? {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let sql = """
            SELECT manifest_json, enabled, installed_at, updated_at
            FROM sources
            WHERE source_id = ?
            LIMIT 1;
            """

            let statement = try prepareStatement(sql, handle: handle)
            defer { sqlite3_finalize(statement) }

            try bindText(sourceID, index: 1, statement: statement)

            let result = sqlite3_step(statement)
            if result == SQLITE_DONE {
                return nil
            }

            guard result == SQLITE_ROW,
                  let manifestJSON = columnText(statement, index: 0),
                  let data = manifestJSON.data(using: .utf8) else {
                throw sqliteError(handle)
            }

            let manifest = try JSONDecoder().decode(SourceManifest.self, from: data)
            let enabled = sqlite3_column_int(statement, 1) != 0
            let installedAt = sqlite3_column_double(statement, 2)
            let updatedAt = sqlite3_column_double(statement, 3)

            return InstalledSourceRecord(
                manifest: manifest,
                enabled: enabled,
                installedAt: installedAt,
                updatedAt: updatedAt
            )
        }
    }

    func remove(sourceID: String) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let statement = try prepareStatement(
                "DELETE FROM sources WHERE source_id = ?;",
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            try bindText(sourceID, index: 1, statement: statement)
            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }
}

enum SourceRepositoryError: Error, LocalizedError {
    case manifestEncodingFailed

    var errorDescription: String? {
        switch self {
        case .manifestEncodingFailed:
            return "Could not encode source manifest for persistence."
        }
    }
}

// MARK: - Repository persistence

struct RepositoryRecord: Equatable {
    let internalID: Int64
    let name: String
    let url: String
    let enabled: Bool
    let lastRefresh: TimeInterval?
}

final class RepositoryRepository {
    private let database: SQLiteDatabase

    init(database: SQLiteDatabase) {
        self.database = database
    }

    func save(
        name: String,
        url: String,
        enabled: Bool = true,
        lastRefresh: TimeInterval? = nil
    ) throws {
        guard !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              let parsedURL = URL(string: url),
              parsedURL.scheme?.lowercased() == "https",
              parsedURL.host != nil else {
            throw RepositoryRepositoryError.invalidRecord
        }

        try database.openAndMigrate()

        try database.withConnection { handle in
            let update = try prepareStatement(
                """
                UPDATE repositories
                SET name = ?, enabled = ?, last_refresh = ?
                WHERE url = ?;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(update) }

            try bindText(name, index: 1, statement: update)
            guard sqlite3_bind_int(update, 2, enabled ? 1 : 0) == SQLITE_OK else {
                throw sqliteError(handle)
            }
            try bindOptionalDouble(lastRefresh, index: 3, statement: update)
            try bindText(url, index: 4, statement: update)

            guard sqlite3_step(update) == SQLITE_DONE else {
                throw sqliteError(handle)
            }

            if sqlite3_changes(handle) == 0 {
                let insert = try prepareStatement(
                    """
                    INSERT INTO repositories
                    (name, url, enabled, last_refresh)
                    VALUES (?, ?, ?, ?);
                    """,
                    handle: handle
                )
                defer { sqlite3_finalize(insert) }

                try bindText(name, index: 1, statement: insert)
                try bindText(url, index: 2, statement: insert)
                guard sqlite3_bind_int(insert, 3, enabled ? 1 : 0) == SQLITE_OK else {
                    throw sqliteError(handle)
                }
                try bindOptionalDouble(lastRefresh, index: 4, statement: insert)

                guard sqlite3_step(insert) == SQLITE_DONE else {
                    throw sqliteError(handle)
                }
            }
        }
    }

    func fetch(url: String) throws -> RepositoryRecord? {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT internal_id, name, url, enabled, last_refresh
                FROM repositories
                WHERE url = ?
                LIMIT 1;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            try bindText(url, index: 1, statement: statement)

            let result = sqlite3_step(statement)
            if result == SQLITE_DONE {
                return nil
            }

            guard result == SQLITE_ROW,
                  let name = columnText(statement, index: 1),
                  let storedURL = columnText(statement, index: 2) else {
                throw sqliteError(handle)
            }

            let lastRefresh: TimeInterval?
            if sqlite3_column_type(statement, 4) == SQLITE_NULL {
                lastRefresh = nil
            } else {
                lastRefresh = sqlite3_column_double(statement, 4)
            }

            return RepositoryRecord(
                internalID: sqlite3_column_int64(statement, 0),
                name: name,
                url: storedURL,
                enabled: sqlite3_column_int(statement, 3) != 0,
                lastRefresh: lastRefresh
            )
        }
    }

    func markRefreshed(
        url: String,
        at timestamp: TimeInterval = Date().timeIntervalSince1970
    ) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let statement = try prepareStatement(
                "UPDATE repositories SET last_refresh = ? WHERE url = ?;",
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            guard sqlite3_bind_double(statement, 1, timestamp) == SQLITE_OK else {
                throw sqliteError(handle)
            }
            try bindText(url, index: 2, statement: statement)

            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }

    func remove(url: String) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let statement = try prepareStatement(
                "DELETE FROM repositories WHERE url = ?;",
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            try bindText(url, index: 1, statement: statement)

            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }
}

enum RepositoryRepositoryError: Error, LocalizedError {
    case invalidRecord

    var errorDescription: String? {
        switch self {
        case .invalidRecord:
            return "Repository record must have a name and HTTPS URL."
        }
    }
}

private let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

private func prepareStatement(_ sql: String, handle: OpaquePointer) throws -> OpaquePointer {
    var statement: OpaquePointer?
    let result = sql.withCString {
        sqlite3_prepare_v2(handle, $0, -1, &statement, nil)
    }

    guard result == SQLITE_OK, let prepared = statement else {
        throw sqliteError(handle)
    }

    return prepared
}

private func bindText(_ value: String, index: Int32, statement: OpaquePointer) throws {
    let result = value.withCString {
        sqlite3_bind_text(statement, index, $0, -1, sqliteTransient)
    }

    guard result == SQLITE_OK else {
        if let handle = sqlite3_db_handle(statement) {
            throw sqliteError(handle)
        }
        throw SQLiteDatabaseError.connectionUnavailable
    }
}

private func bindOptionalDouble(
    _ value: Double?,
    index: Int32,
    statement: OpaquePointer
) throws {
    let result: Int32
    if let value = value {
        result = sqlite3_bind_double(statement, index, value)
    } else {
        result = sqlite3_bind_null(statement, index)
    }

    guard result == SQLITE_OK else {
        if let handle = sqlite3_db_handle(statement) {
            throw sqliteError(handle)
        }
        throw SQLiteDatabaseError.connectionUnavailable
    }
}

private func columnText(_ statement: OpaquePointer, index: Int32) -> String? {
    guard let bytes = sqlite3_column_text(statement, index) else {
        return nil
    }

    let length = Int(sqlite3_column_bytes(statement, index))
    let data = Data(bytes: bytes, count: length)
    return String(data: data, encoding: .utf8)
}

private func sqliteError(_ handle: OpaquePointer) -> SQLiteDatabaseError {
    let code = sqlite3_errcode(handle)
    let message: String

    if let cString = sqlite3_errmsg(handle) {
        message = String(cString: cString)
    } else {
        message = "Unknown SQLite error"
    }

    return .executionFailed(code: code, message: message)
}
