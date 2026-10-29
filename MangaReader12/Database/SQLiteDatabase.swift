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



    func list() throws -> [InstalledSourceRecord] {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT manifest_json, enabled, installed_at, updated_at
                FROM sources
                ORDER BY name COLLATE NOCASE ASC;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            var records: [InstalledSourceRecord] = []

            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE {
                    break
                }

                guard result == SQLITE_ROW,
                      let manifestJSON = columnText(statement, index: 0),
                      let data = manifestJSON.data(using: .utf8) else {
                    throw sqliteError(handle)
                }

                records.append(
                    InstalledSourceRecord(
                        manifest: try JSONDecoder().decode(SourceManifest.self, from: data),
                        enabled: sqlite3_column_int(statement, 1) != 0,
                        installedAt: sqlite3_column_double(statement, 2),
                        updatedAt: sqlite3_column_double(statement, 3)
                    )
                )
            }

            return records
        }
    }

    func setEnabled(_ enabled: Bool, sourceID: String) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let statement = try prepareStatement(
                "UPDATE sources SET enabled = ?, updated_at = ? WHERE source_id = ?;",
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            guard sqlite3_bind_int(statement, 1, enabled ? 1 : 0) == SQLITE_OK,
                  sqlite3_bind_double(statement, 2, Date().timeIntervalSince1970) == SQLITE_OK else {
                throw sqliteError(handle)
            }

            try bindText(sourceID, index: 3, statement: statement)

            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
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



    func list() throws -> [RepositoryRecord] {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT internal_id, name, url, enabled, last_refresh
                FROM repositories
                ORDER BY name COLLATE NOCASE ASC;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            var records: [RepositoryRecord] = []

            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE {
                    break
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

                records.append(
                    RepositoryRecord(
                        internalID: sqlite3_column_int64(statement, 0),
                        name: name,
                        url: storedURL,
                        enabled: sqlite3_column_int(statement, 3) != 0,
                        lastRefresh: lastRefresh
                    )
                )
            }

            return records
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



// MARK: - Library persistence

struct LibraryMangaRecord: Equatable {
    let internalID: Int64
    let sourceID: String
    let sourceMangaID: String
    let title: String
    let cover: String?
    let description: String?
    let status: MangaStatus
    let url: String?
    let dateAdded: TimeInterval
}

final class LibraryRepository {
    private let database: SQLiteDatabase

    init(database: SQLiteDatabase) {
        self.database = database
    }

    static func defaultRepository() throws -> LibraryRepository {
        let database = try SQLiteDatabase.defaultDatabase()
        try database.openAndMigrate()
        return LibraryRepository(database: database)
    }

    func find(sourceID: String, sourceMangaID: String) throws -> LibraryMangaRecord? {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT
                    m.internal_id,
                    m.source_id,
                    m.source_manga_id,
                    m.title,
                    m.cover,
                    m.description,
                    m.status,
                    m.url,
                    l.date_added
                FROM library l
                JOIN manga m ON m.internal_id = l.manga_id
                WHERE m.source_id = ? AND m.source_manga_id = ?
                LIMIT 1;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            try bindText(sourceID, index: 1, statement: statement)
            try bindText(sourceMangaID, index: 2, statement: statement)

            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return nil }

            guard result == SQLITE_ROW,
                  let storedSourceID = columnText(statement, index: 1),
                  let storedMangaID = columnText(statement, index: 2),
                  let title = columnText(statement, index: 3),
                  let statusRaw = columnText(statement, index: 6) else {
                throw sqliteError(handle)
            }

            return LibraryMangaRecord(
                internalID: sqlite3_column_int64(statement, 0),
                sourceID: storedSourceID,
                sourceMangaID: storedMangaID,
                title: title,
                cover: columnText(statement, index: 4),
                description: columnText(statement, index: 5),
                status: MangaStatus(rawValue: statusRaw) ?? .unknown,
                url: columnText(statement, index: 7),
                dateAdded: sqlite3_column_double(statement, 8)
            )
        }
    }

    func isInLibrary(sourceID: String, sourceMangaID: String) throws -> Bool {
        try database.openAndMigrate()
        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT 1
                FROM library l
                JOIN manga m ON m.internal_id = l.manga_id
                WHERE m.source_id = ? AND m.source_manga_id = ?
                LIMIT 1;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }
            try bindText(sourceID, index: 1, statement: statement)
            try bindText(sourceMangaID, index: 2, statement: statement)
            return sqlite3_step(statement) == SQLITE_ROW
        }
    }

    func add(sourceID: String, manga: Manga, chapters: [Chapter]) throws {
        try database.openAndMigrate()
        let now = Date().timeIntervalSince1970

        try database.withConnection { handle in
            try executeSQLite("BEGIN IMMEDIATE TRANSACTION;", handle: handle)
            do {
                let updateManga = try prepareStatement(
                    """
                    UPDATE manga
                    SET title = ?, cover = ?, description = ?, status = ?, url = ?, last_update = ?
                    WHERE source_id = ? AND source_manga_id = ?;
                    """,
                    handle: handle
                )
                defer { sqlite3_finalize(updateManga) }

                try bindText(manga.title, index: 1, statement: updateManga)
                try bindOptionalText(manga.cover, index: 2, statement: updateManga)
                try bindOptionalText(manga.description, index: 3, statement: updateManga)
                try bindText(manga.status.rawValue, index: 4, statement: updateManga)
                try bindOptionalText(manga.url, index: 5, statement: updateManga)
                guard sqlite3_bind_double(updateManga, 6, now) == SQLITE_OK else {
                    throw sqliteError(handle)
                }
                try bindText(sourceID, index: 7, statement: updateManga)
                try bindText(manga.id, index: 8, statement: updateManga)
                guard sqlite3_step(updateManga) == SQLITE_DONE else {
                    throw sqliteError(handle)
                }

                if sqlite3_changes(handle) == 0 {
                    let insertManga = try prepareStatement(
                        """
                        INSERT INTO manga
                        (source_id, source_manga_id, title, cover, description, status, url, last_update, date_added)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        handle: handle
                    )
                    defer { sqlite3_finalize(insertManga) }

                    try bindText(sourceID, index: 1, statement: insertManga)
                    try bindText(manga.id, index: 2, statement: insertManga)
                    try bindText(manga.title, index: 3, statement: insertManga)
                    try bindOptionalText(manga.cover, index: 4, statement: insertManga)
                    try bindOptionalText(manga.description, index: 5, statement: insertManga)
                    try bindText(manga.status.rawValue, index: 6, statement: insertManga)
                    try bindOptionalText(manga.url, index: 7, statement: insertManga)
                    guard sqlite3_bind_double(insertManga, 8, now) == SQLITE_OK,
                          sqlite3_bind_double(insertManga, 9, now) == SQLITE_OK else {
                        throw sqliteError(handle)
                    }
                    guard sqlite3_step(insertManga) == SQLITE_DONE else {
                        throw sqliteError(handle)
                    }
                }

                let findManga = try prepareStatement(
                    """
                    SELECT internal_id
                    FROM manga
                    WHERE source_id = ? AND source_manga_id = ?
                    LIMIT 1;
                    """,
                    handle: handle
                )
                defer { sqlite3_finalize(findManga) }
                try bindText(sourceID, index: 1, statement: findManga)
                try bindText(manga.id, index: 2, statement: findManga)
                guard sqlite3_step(findManga) == SQLITE_ROW else {
                    throw sqliteError(handle)
                }
                let mangaID = sqlite3_column_int64(findManga, 0)

                let addLibrary = try prepareStatement(
                    """
                    INSERT OR IGNORE INTO library
                    (manga_id, date_added, last_checked)
                    VALUES (?, ?, ?);
                    """,
                    handle: handle
                )
                defer { sqlite3_finalize(addLibrary) }
                guard sqlite3_bind_int64(addLibrary, 1, mangaID) == SQLITE_OK,
                      sqlite3_bind_double(addLibrary, 2, now) == SQLITE_OK,
                      sqlite3_bind_double(addLibrary, 3, now) == SQLITE_OK else {
                    throw sqliteError(handle)
                }
                guard sqlite3_step(addLibrary) == SQLITE_DONE else {
                    throw sqliteError(handle)
                }

                for chapter in chapters {
                    let updateChapter = try prepareStatement(
                        """
                        UPDATE chapters
                        SET name = ?, number = ?, volume = ?, url = ?
                        WHERE manga_id = ? AND source_chapter_id = ?;
                        """,
                        handle: handle
                    )

                    try bindText(chapter.name, index: 1, statement: updateChapter)
                    try bindOptionalDouble(chapter.number, index: 2, statement: updateChapter)
                    try bindOptionalDouble(chapter.volume, index: 3, statement: updateChapter)
                    try bindOptionalText(chapter.url, index: 4, statement: updateChapter)
                    guard sqlite3_bind_int64(updateChapter, 5, mangaID) == SQLITE_OK else {
                        sqlite3_finalize(updateChapter)
                        throw sqliteError(handle)
                    }
                    try bindText(chapter.id, index: 6, statement: updateChapter)
                    guard sqlite3_step(updateChapter) == SQLITE_DONE else {
                        sqlite3_finalize(updateChapter)
                        throw sqliteError(handle)
                    }
                    let changed = sqlite3_changes(handle)
                    sqlite3_finalize(updateChapter)

                    if changed == 0 {
                        let insertChapter = try prepareStatement(
                            """
                            INSERT INTO chapters
                            (manga_id, source_chapter_id, name, number, volume, url)
                            VALUES (?, ?, ?, ?, ?, ?);
                            """,
                            handle: handle
                        )
                        guard sqlite3_bind_int64(insertChapter, 1, mangaID) == SQLITE_OK else {
                            sqlite3_finalize(insertChapter)
                            throw sqliteError(handle)
                        }
                        try bindText(chapter.id, index: 2, statement: insertChapter)
                        try bindText(chapter.name, index: 3, statement: insertChapter)
                        try bindOptionalDouble(chapter.number, index: 4, statement: insertChapter)
                        try bindOptionalDouble(chapter.volume, index: 5, statement: insertChapter)
                        try bindOptionalText(chapter.url, index: 6, statement: insertChapter)
                        guard sqlite3_step(insertChapter) == SQLITE_DONE else {
                            sqlite3_finalize(insertChapter)
                            throw sqliteError(handle)
                        }
                        sqlite3_finalize(insertChapter)
                    }
                }

                try executeSQLite("COMMIT;", handle: handle)
            } catch {
                try? executeSQLite("ROLLBACK;", handle: handle)
                throw error
            }
        }
    }

    func remove(sourceID: String, sourceMangaID: String) throws {
        try database.openAndMigrate()
        try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                DELETE FROM library
                WHERE manga_id = (
                    SELECT internal_id FROM manga
                    WHERE source_id = ? AND source_manga_id = ?
                    LIMIT 1
                );
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }
            try bindText(sourceID, index: 1, statement: statement)
            try bindText(sourceMangaID, index: 2, statement: statement)
            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }

    func list() throws -> [LibraryMangaRecord] {
        try database.openAndMigrate()
        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT
                    m.internal_id,
                    m.source_id,
                    m.source_manga_id,
                    m.title,
                    m.cover,
                    m.description,
                    m.status,
                    m.url,
                    l.date_added
                FROM library l
                JOIN manga m ON m.internal_id = l.manga_id
                ORDER BY l.date_added DESC, m.title COLLATE NOCASE ASC;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            var records: [LibraryMangaRecord] = []
            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }
                guard result == SQLITE_ROW,
                      let sourceID = columnText(statement, index: 1),
                      let sourceMangaID = columnText(statement, index: 2),
                      let title = columnText(statement, index: 3),
                      let statusRaw = columnText(statement, index: 6) else {
                    throw sqliteError(handle)
                }

                records.append(
                    LibraryMangaRecord(
                        internalID: sqlite3_column_int64(statement, 0),
                        sourceID: sourceID,
                        sourceMangaID: sourceMangaID,
                        title: title,
                        cover: columnText(statement, index: 4),
                        description: columnText(statement, index: 5),
                        status: MangaStatus(rawValue: statusRaw) ?? .unknown,
                        url: columnText(statement, index: 7),
                        dateAdded: sqlite3_column_double(statement, 8)
                    )
                )
            }
            return records
        }
    }

    func list(categoryID: Int64) throws -> [LibraryMangaRecord] {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT
                    m.internal_id,
                    m.source_id,
                    m.source_manga_id,
                    m.title,
                    m.cover,
                    m.description,
                    m.status,
                    m.url,
                    l.date_added
                FROM library l
                JOIN manga m ON m.internal_id = l.manga_id
                JOIN manga_categories mc ON mc.manga_id = m.internal_id
                WHERE mc.category_id = ?
                ORDER BY l.date_added DESC, m.title COLLATE NOCASE ASC;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            guard sqlite3_bind_int64(statement, 1, categoryID) == SQLITE_OK else {
                throw sqliteError(handle)
            }

            var records: [LibraryMangaRecord] = []

            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }

                guard result == SQLITE_ROW,
                      let sourceID = columnText(statement, index: 1),
                      let sourceMangaID = columnText(statement, index: 2),
                      let title = columnText(statement, index: 3),
                      let statusRaw = columnText(statement, index: 6) else {
                    throw sqliteError(handle)
                }

                records.append(
                    LibraryMangaRecord(
                        internalID: sqlite3_column_int64(statement, 0),
                        sourceID: sourceID,
                        sourceMangaID: sourceMangaID,
                        title: title,
                        cover: columnText(statement, index: 4),
                        description: columnText(statement, index: 5),
                        status: MangaStatus(rawValue: statusRaw) ?? .unknown,
                        url: columnText(statement, index: 7),
                        dateAdded: sqlite3_column_double(statement, 8)
                    )
                )
            }

            return records
        }
    }

    func knownChapterIDs(
        sourceID: String,
        sourceMangaID: String
    ) throws -> Set<String> {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT c.source_chapter_id
                FROM chapters c
                JOIN manga m ON m.internal_id = c.manga_id
                WHERE m.source_id = ? AND m.source_manga_id = ?;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            try bindText(sourceID, index: 1, statement: statement)
            try bindText(sourceMangaID, index: 2, statement: statement)

            var ids = Set<String>()

            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }

                guard result == SQLITE_ROW,
                      let chapterID = columnText(statement, index: 0) else {
                    throw sqliteError(handle)
                }

                ids.insert(chapterID)
            }

            return ids
        }
    }

    func touchLastChecked(
        sourceID: String,
        sourceMangaID: String,
        date: Date = Date()
    ) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                UPDATE library
                SET last_checked = ?
                WHERE manga_id = (
                    SELECT internal_id
                    FROM manga
                    WHERE source_id = ? AND source_manga_id = ?
                    LIMIT 1
                );
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            guard sqlite3_bind_double(statement, 1, date.timeIntervalSince1970) == SQLITE_OK else {
                throw sqliteError(handle)
            }
            try bindText(sourceID, index: 2, statement: statement)
            try bindText(sourceMangaID, index: 3, statement: statement)

            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }

}

// MARK: - Categories


struct CategoryRecord: Equatable {
    let internalID: Int64
    let name: String
    let sortOrder: Int
}

final class CategoryRepository {
    private let database: SQLiteDatabase

    init(database: SQLiteDatabase) {
        self.database = database
    }

    static func defaultRepository() throws -> CategoryRepository {
        let database = try SQLiteDatabase.defaultDatabase()
        try database.openAndMigrate()
        return CategoryRepository(database: database)
    }

    func list() throws -> [CategoryRecord] {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT internal_id, name, sort_order
                FROM categories
                ORDER BY sort_order ASC, name COLLATE NOCASE ASC;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            var records: [CategoryRecord] = []

            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }

                guard result == SQLITE_ROW,
                      let name = columnText(statement, index: 1) else {
                    throw sqliteError(handle)
                }

                records.append(
                    CategoryRecord(
                        internalID: sqlite3_column_int64(statement, 0),
                        name: name,
                        sortOrder: Int(sqlite3_column_int(statement, 2))
                    )
                )
            }

            return records
        }
    }

    @discardableResult
    func create(name: String) throws -> CategoryRecord {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw CategoryRepositoryError.emptyName
        }

        try database.openAndMigrate()

        return try database.withConnection { handle in
            let nextOrderStatement = try prepareStatement(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM categories;",
                handle: handle
            )
            defer { sqlite3_finalize(nextOrderStatement) }

            guard sqlite3_step(nextOrderStatement) == SQLITE_ROW else {
                throw sqliteError(handle)
            }

            let nextOrder = sqlite3_column_int(nextOrderStatement, 0)
            let insert = try prepareStatement(
                """
                INSERT INTO categories (name, sort_order)
                VALUES (?, ?);
                """,
                handle: handle
            )
            defer { sqlite3_finalize(insert) }

            try bindText(trimmed, index: 1, statement: insert)
            guard sqlite3_bind_int(insert, 2, nextOrder) == SQLITE_OK,
                  sqlite3_step(insert) == SQLITE_DONE else {
                throw sqliteError(handle)
            }

            return CategoryRecord(
                internalID: sqlite3_last_insert_rowid(handle),
                name: trimmed,
                sortOrder: Int(nextOrder)
            )
        }
    }

    func remove(categoryID: Int64) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let statement = try prepareStatement(
                "DELETE FROM categories WHERE internal_id = ?;",
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            guard sqlite3_bind_int64(statement, 1, categoryID) == SQLITE_OK,
                  sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }

    func categoryIDs(mangaID: Int64) throws -> Set<Int64> {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT category_id
                FROM manga_categories
                WHERE manga_id = ?;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            guard sqlite3_bind_int64(statement, 1, mangaID) == SQLITE_OK else {
                throw sqliteError(handle)
            }

            var result = Set<Int64>()

            while true {
                let step = sqlite3_step(statement)
                if step == SQLITE_DONE { break }
                guard step == SQLITE_ROW else {
                    throw sqliteError(handle)
                }
                result.insert(sqlite3_column_int64(statement, 0))
            }

            return result
        }
    }

    func names(mangaID: Int64) throws -> [String] {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT c.name
                FROM manga_categories mc
                JOIN categories c ON c.internal_id = mc.category_id
                WHERE mc.manga_id = ?
                ORDER BY c.sort_order ASC, c.name COLLATE NOCASE ASC;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            guard sqlite3_bind_int64(statement, 1, mangaID) == SQLITE_OK else {
                throw sqliteError(handle)
            }

            var names: [String] = []

            while true {
                let step = sqlite3_step(statement)
                if step == SQLITE_DONE { break }

                guard step == SQLITE_ROW,
                      let name = columnText(statement, index: 0) else {
                    throw sqliteError(handle)
                }

                names.append(name)
            }

            return names
        }
    }

    func setCategories(
        mangaID: Int64,
        categoryIDs: Set<Int64>
    ) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            try executeSQLite("BEGIN IMMEDIATE TRANSACTION;", handle: handle)

            do {
                let delete = try prepareStatement(
                    "DELETE FROM manga_categories WHERE manga_id = ?;",
                    handle: handle
                )
                defer { sqlite3_finalize(delete) }

                guard sqlite3_bind_int64(delete, 1, mangaID) == SQLITE_OK,
                      sqlite3_step(delete) == SQLITE_DONE else {
                    throw sqliteError(handle)
                }

                for categoryID in categoryIDs {
                    let insert = try prepareStatement(
                        """
                        INSERT INTO manga_categories (manga_id, category_id)
                        VALUES (?, ?);
                        """,
                        handle: handle
                    )

                    guard sqlite3_bind_int64(insert, 1, mangaID) == SQLITE_OK,
                          sqlite3_bind_int64(insert, 2, categoryID) == SQLITE_OK,
                          sqlite3_step(insert) == SQLITE_DONE else {
                        sqlite3_finalize(insert)
                        throw sqliteError(handle)
                    }

                    sqlite3_finalize(insert)
                }

                try executeSQLite("COMMIT;", handle: handle)
            } catch {
                try? executeSQLite("ROLLBACK;", handle: handle)
                throw error
            }
        }
    }
}

enum CategoryRepositoryError: Error, LocalizedError {
    case emptyName

    var errorDescription: String? {
        switch self {
        case .emptyName:
            return "Category name cannot be empty."
        }
    }
}


// MARK: - Reading progress, history and downloads

struct ChapterReadingState: Equatable {
    let sourceChapterID: String
    let isRead: Bool
    let lastPageRead: Int
    let downloaded: Bool
}

struct HistoryRecord: Equatable {
    let sourceID: String
    let sourceMangaID: String
    let mangaTitle: String
    let cover: String?
    let mangaURL: String?
    let sourceChapterID: String?
    let chapterName: String?
    let lastReadAt: TimeInterval
}

struct ChapterDownloadRecord: Equatable {
    let sourceID: String
    let sourceMangaID: String
    let sourceChapterID: String
    let state: String
    let progress: Double
    let localPath: String?
    let updatedAt: TimeInterval
}

struct DownloadListRecord: Equatable {
    let sourceID: String
    let sourceMangaID: String
    let mangaTitle: String
    let cover: String?
    let sourceChapterID: String
    let chapterName: String
    let state: String
    let progress: Double
    let localPath: String?
    let updatedAt: TimeInterval
}

final class ReadingProgressRepository {
    private let database: SQLiteDatabase

    init(database: SQLiteDatabase) {
        self.database = database
    }

    static func defaultRepository() throws -> ReadingProgressRepository {
        let database = try SQLiteDatabase.defaultDatabase()
        try database.openAndMigrate()
        return ReadingProgressRepository(database: database)
    }

    func recordProgress(
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        pageIndex: Int,
        totalPages: Int
    ) throws {
        try database.openAndMigrate()
        let safePage = max(0, pageIndex)
        let completed = totalPages > 0 && safePage >= totalPages - 1
        let now = Date().timeIntervalSince1970

        try database.withConnection { handle in
            try executeSQLite("BEGIN IMMEDIATE TRANSACTION;", handle: handle)
            do {
                let ids = try ensureReadingRows(
                    sourceID: sourceID,
                    manga: manga,
                    chapter: chapter,
                    handle: handle
                )

                let updateChapter = try prepareStatement(
                    """
                    UPDATE chapters
                    SET last_page_read = ?,
                        is_read = CASE WHEN ? = 1 THEN 1 ELSE is_read END
                    WHERE internal_id = ?;
                    """,
                    handle: handle
                )
                defer { sqlite3_finalize(updateChapter) }

                guard sqlite3_bind_int(updateChapter, 1, Int32(safePage)) == SQLITE_OK,
                      sqlite3_bind_int(updateChapter, 2, completed ? 1 : 0) == SQLITE_OK,
                      sqlite3_bind_int64(updateChapter, 3, ids.chapterID) == SQLITE_OK,
                      sqlite3_step(updateChapter) == SQLITE_DONE else {
                    throw sqliteError(handle)
                }

                let updateHistory = try prepareStatement(
                    """
                    UPDATE history
                    SET chapter_id = ?, last_read_at = ?
                    WHERE manga_id = ?;
                    """,
                    handle: handle
                )
                defer { sqlite3_finalize(updateHistory) }

                guard sqlite3_bind_int64(updateHistory, 1, ids.chapterID) == SQLITE_OK,
                      sqlite3_bind_double(updateHistory, 2, now) == SQLITE_OK,
                      sqlite3_bind_int64(updateHistory, 3, ids.mangaID) == SQLITE_OK,
                      sqlite3_step(updateHistory) == SQLITE_DONE else {
                    throw sqliteError(handle)
                }

                if sqlite3_changes(handle) == 0 {
                    let insertHistory = try prepareStatement(
                        """
                        INSERT INTO history (manga_id, chapter_id, last_read_at)
                        VALUES (?, ?, ?);
                        """,
                        handle: handle
                    )
                    defer { sqlite3_finalize(insertHistory) }

                    guard sqlite3_bind_int64(insertHistory, 1, ids.mangaID) == SQLITE_OK,
                          sqlite3_bind_int64(insertHistory, 2, ids.chapterID) == SQLITE_OK,
                          sqlite3_bind_double(insertHistory, 3, now) == SQLITE_OK,
                          sqlite3_step(insertHistory) == SQLITE_DONE else {
                        throw sqliteError(handle)
                    }
                }

                try executeSQLite("COMMIT;", handle: handle)
            } catch {
                try? executeSQLite("ROLLBACK;", handle: handle)
                throw error
            }
        }
    }

    func markRead(
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        isRead: Bool
    ) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let ids = try ensureReadingRows(
                sourceID: sourceID,
                manga: manga,
                chapter: chapter,
                handle: handle
            )

            let statement = try prepareStatement(
                """
                UPDATE chapters
                SET is_read = ?,
                    last_page_read = CASE WHEN ? = 0 THEN 0 ELSE last_page_read END
                WHERE internal_id = ?;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            guard sqlite3_bind_int(statement, 1, isRead ? 1 : 0) == SQLITE_OK,
                  sqlite3_bind_int(statement, 2, isRead ? 1 : 0) == SQLITE_OK,
                  sqlite3_bind_int64(statement, 3, ids.chapterID) == SQLITE_OK,
                  sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }

    func chapterStates(
        sourceID: String,
        sourceMangaID: String
    ) throws -> [String: ChapterReadingState] {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT c.source_chapter_id, c.is_read, c.last_page_read, c.downloaded
                FROM chapters c
                JOIN manga m ON m.internal_id = c.manga_id
                WHERE m.source_id = ? AND m.source_manga_id = ?;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            try bindText(sourceID, index: 1, statement: statement)
            try bindText(sourceMangaID, index: 2, statement: statement)

            var states: [String: ChapterReadingState] = [:]

            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }

                guard result == SQLITE_ROW,
                      let sourceChapterID = columnText(statement, index: 0) else {
                    throw sqliteError(handle)
                }

                states[sourceChapterID] = ChapterReadingState(
                    sourceChapterID: sourceChapterID,
                    isRead: sqlite3_column_int(statement, 1) != 0,
                    lastPageRead: Int(sqlite3_column_int(statement, 2)),
                    downloaded: sqlite3_column_int(statement, 3) != 0
                )
            }

            return states
        }
    }

    func applyMigrationState(
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        state: ChapterReadingState
    ) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let ids = try ensureReadingRows(
                sourceID: sourceID,
                manga: manga,
                chapter: chapter,
                handle: handle
            )

            let statement = try prepareStatement(
                """
                UPDATE chapters
                SET is_read = ?, last_page_read = ?
                WHERE internal_id = ?;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            guard sqlite3_bind_int(statement, 1, state.isRead ? 1 : 0) == SQLITE_OK,
                  sqlite3_bind_int(statement, 2, Int32(max(0, state.lastPageRead))) == SQLITE_OK,
                  sqlite3_bind_int64(statement, 3, ids.chapterID) == SQLITE_OK,
                  sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }

    func recordHistory(
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        date: TimeInterval = Date().timeIntervalSince1970
    ) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let ids = try ensureReadingRows(
                sourceID: sourceID,
                manga: manga,
                chapter: chapter,
                handle: handle
            )

            let update = try prepareStatement(
                """
                UPDATE history
                SET chapter_id = ?, last_read_at = ?
                WHERE manga_id = ?;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(update) }

            guard sqlite3_bind_int64(update, 1, ids.chapterID) == SQLITE_OK,
                  sqlite3_bind_double(update, 2, date) == SQLITE_OK,
                  sqlite3_bind_int64(update, 3, ids.mangaID) == SQLITE_OK,
                  sqlite3_step(update) == SQLITE_DONE else {
                throw sqliteError(handle)
            }

            if sqlite3_changes(handle) == 0 {
                let insert = try prepareStatement(
                    """
                    INSERT INTO history (manga_id, chapter_id, last_read_at)
                    VALUES (?, ?, ?);
                    """,
                    handle: handle
                )
                defer { sqlite3_finalize(insert) }

                guard sqlite3_bind_int64(insert, 1, ids.mangaID) == SQLITE_OK,
                      sqlite3_bind_int64(insert, 2, ids.chapterID) == SQLITE_OK,
                      sqlite3_bind_double(insert, 3, date) == SQLITE_OK,
                      sqlite3_step(insert) == SQLITE_DONE else {
                    throw sqliteError(handle)
                }
            }
        }
    }

    func chapterState(
        sourceID: String,
        sourceMangaID: String,
        sourceChapterID: String
    ) throws -> ChapterReadingState? {
        return try chapterStates(
            sourceID: sourceID,
            sourceMangaID: sourceMangaID
        )[sourceChapterID]
    }

    func history() throws -> [HistoryRecord] {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT
                    m.source_id,
                    m.source_manga_id,
                    m.title,
                    m.cover,
                    m.url,
                    c.source_chapter_id,
                    c.name,
                    h.last_read_at
                FROM history h
                JOIN manga m ON m.internal_id = h.manga_id
                LEFT JOIN chapters c ON c.internal_id = h.chapter_id
                ORDER BY h.last_read_at DESC;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            var records: [HistoryRecord] = []

            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }

                guard result == SQLITE_ROW,
                      let sourceID = columnText(statement, index: 0),
                      let sourceMangaID = columnText(statement, index: 1),
                      let mangaTitle = columnText(statement, index: 2) else {
                    throw sqliteError(handle)
                }

                records.append(
                    HistoryRecord(
                        sourceID: sourceID,
                        sourceMangaID: sourceMangaID,
                        mangaTitle: mangaTitle,
                        cover: columnText(statement, index: 3),
                        mangaURL: columnText(statement, index: 4),
                        sourceChapterID: columnText(statement, index: 5),
                        chapterName: columnText(statement, index: 6),
                        lastReadAt: sqlite3_column_double(statement, 7)
                    )
                )
            }

            return records
        }
    }

    func removeHistory(
        sourceID: String,
        sourceMangaID: String
    ) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                DELETE FROM history
                WHERE manga_id = (
                    SELECT internal_id FROM manga
                    WHERE source_id = ? AND source_manga_id = ?
                    LIMIT 1
                );
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            try bindText(sourceID, index: 1, statement: statement)
            try bindText(sourceMangaID, index: 2, statement: statement)

            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }
}

final class DownloadRepository {
    private let database: SQLiteDatabase

    init(database: SQLiteDatabase) {
        self.database = database
    }

    static func defaultRepository() throws -> DownloadRepository {
        let database = try SQLiteDatabase.defaultDatabase()
        try database.openAndMigrate()
        return DownloadRepository(database: database)
    }

    func setState(
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        state: String,
        progress: Double,
        localPath: String?
    ) throws {
        try database.openAndMigrate()
        let now = Date().timeIntervalSince1970
        let clampedProgress = max(0, min(progress, 1))

        try database.withConnection { handle in
            let ids = try ensureReadingRows(
                sourceID: sourceID,
                manga: manga,
                chapter: chapter,
                handle: handle
            )

            let update = try prepareStatement(
                """
                UPDATE downloads
                SET state = ?, progress = ?, local_path = ?, updated_at = ?
                WHERE chapter_id = ?;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(update) }

            try bindText(state, index: 1, statement: update)
            guard sqlite3_bind_double(update, 2, clampedProgress) == SQLITE_OK else {
                throw sqliteError(handle)
            }
            try bindOptionalText(localPath, index: 3, statement: update)
            guard sqlite3_bind_double(update, 4, now) == SQLITE_OK,
                  sqlite3_bind_int64(update, 5, ids.chapterID) == SQLITE_OK,
                  sqlite3_step(update) == SQLITE_DONE else {
                throw sqliteError(handle)
            }

            if sqlite3_changes(handle) == 0 {
                let insert = try prepareStatement(
                    """
                    INSERT INTO downloads
                    (chapter_id, state, progress, local_path, updated_at)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    handle: handle
                )
                defer { sqlite3_finalize(insert) }

                guard sqlite3_bind_int64(insert, 1, ids.chapterID) == SQLITE_OK else {
                    throw sqliteError(handle)
                }
                try bindText(state, index: 2, statement: insert)
                guard sqlite3_bind_double(insert, 3, clampedProgress) == SQLITE_OK else {
                    throw sqliteError(handle)
                }
                try bindOptionalText(localPath, index: 4, statement: insert)
                guard sqlite3_bind_double(insert, 5, now) == SQLITE_OK,
                      sqlite3_step(insert) == SQLITE_DONE else {
                    throw sqliteError(handle)
                }
            }

            let downloaded = state == "completed"
            let markChapter = try prepareStatement(
                "UPDATE chapters SET downloaded = ? WHERE internal_id = ?;",
                handle: handle
            )
            defer { sqlite3_finalize(markChapter) }

            guard sqlite3_bind_int(markChapter, 1, downloaded ? 1 : 0) == SQLITE_OK,
                  sqlite3_bind_int64(markChapter, 2, ids.chapterID) == SQLITE_OK,
                  sqlite3_step(markChapter) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }

    func record(
        sourceID: String,
        sourceMangaID: String,
        sourceChapterID: String
    ) throws -> ChapterDownloadRecord? {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT d.state, d.progress, d.local_path, d.updated_at
                FROM downloads d
                JOIN chapters c ON c.internal_id = d.chapter_id
                JOIN manga m ON m.internal_id = c.manga_id
                WHERE m.source_id = ?
                  AND m.source_manga_id = ?
                  AND c.source_chapter_id = ?
                LIMIT 1;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            try bindText(sourceID, index: 1, statement: statement)
            try bindText(sourceMangaID, index: 2, statement: statement)
            try bindText(sourceChapterID, index: 3, statement: statement)

            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return nil }

            guard result == SQLITE_ROW,
                  let state = columnText(statement, index: 0) else {
                throw sqliteError(handle)
            }

            return ChapterDownloadRecord(
                sourceID: sourceID,
                sourceMangaID: sourceMangaID,
                sourceChapterID: sourceChapterID,
                state: state,
                progress: sqlite3_column_double(statement, 1),
                localPath: columnText(statement, index: 2),
                updatedAt: sqlite3_column_double(statement, 3)
            )
        }
    }

    func listDownloads() throws -> [DownloadListRecord] {
        try database.openAndMigrate()

        return try database.withConnection { handle in
            let statement = try prepareStatement(
                """
                SELECT
                    m.source_id,
                    m.source_manga_id,
                    m.title,
                    m.cover,
                    c.source_chapter_id,
                    c.name,
                    d.state,
                    d.progress,
                    d.local_path,
                    d.updated_at
                FROM downloads d
                JOIN chapters c ON c.internal_id = d.chapter_id
                JOIN manga m ON m.internal_id = c.manga_id
                ORDER BY d.updated_at DESC, m.title COLLATE NOCASE ASC;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(statement) }

            var records: [DownloadListRecord] = []

            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }

                guard result == SQLITE_ROW,
                      let sourceID = columnText(statement, index: 0),
                      let sourceMangaID = columnText(statement, index: 1),
                      let mangaTitle = columnText(statement, index: 2),
                      let sourceChapterID = columnText(statement, index: 4),
                      let chapterName = columnText(statement, index: 5),
                      let state = columnText(statement, index: 6) else {
                    throw sqliteError(handle)
                }

                records.append(
                    DownloadListRecord(
                        sourceID: sourceID,
                        sourceMangaID: sourceMangaID,
                        mangaTitle: mangaTitle,
                        cover: columnText(statement, index: 3),
                        sourceChapterID: sourceChapterID,
                        chapterName: chapterName,
                        state: state,
                        progress: sqlite3_column_double(statement, 7),
                        localPath: columnText(statement, index: 8),
                        updatedAt: sqlite3_column_double(statement, 9)
                    )
                )
            }

            return records
        }
    }

    func clearAll() throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            try executeSQLite("BEGIN IMMEDIATE TRANSACTION;", handle: handle)
            do {
                try executeSQLite("DELETE FROM downloads;", handle: handle)
                try executeSQLite("UPDATE chapters SET downloaded = 0;", handle: handle)
                try executeSQLite("COMMIT;", handle: handle)
            } catch {
                try? executeSQLite("ROLLBACK;", handle: handle)
                throw error
            }
        }
    }

    func removeMissingFiles(fileManager: FileManager = .default) throws -> Int {
        let records = try listDownloads()
        var removed = 0

        for record in records {
            guard let path = record.localPath,
                  !fileManager.fileExists(atPath: path) else {
                continue
            }

            try remove(
                sourceID: record.sourceID,
                sourceMangaID: record.sourceMangaID,
                sourceChapterID: record.sourceChapterID
            )
            removed += 1
        }

        return removed
    }

    func remove(
        sourceID: String,
        sourceMangaID: String,
        sourceChapterID: String
    ) throws {
        try database.openAndMigrate()

        try database.withConnection { handle in
            let find = try prepareStatement(
                """
                SELECT c.internal_id
                FROM chapters c
                JOIN manga m ON m.internal_id = c.manga_id
                WHERE m.source_id = ?
                  AND m.source_manga_id = ?
                  AND c.source_chapter_id = ?
                LIMIT 1;
                """,
                handle: handle
            )
            defer { sqlite3_finalize(find) }

            try bindText(sourceID, index: 1, statement: find)
            try bindText(sourceMangaID, index: 2, statement: find)
            try bindText(sourceChapterID, index: 3, statement: find)

            guard sqlite3_step(find) == SQLITE_ROW else { return }
            let chapterID = sqlite3_column_int64(find, 0)

            let delete = try prepareStatement(
                "DELETE FROM downloads WHERE chapter_id = ?;",
                handle: handle
            )
            defer { sqlite3_finalize(delete) }

            guard sqlite3_bind_int64(delete, 1, chapterID) == SQLITE_OK,
                  sqlite3_step(delete) == SQLITE_DONE else {
                throw sqliteError(handle)
            }

            let mark = try prepareStatement(
                "UPDATE chapters SET downloaded = 0 WHERE internal_id = ?;",
                handle: handle
            )
            defer { sqlite3_finalize(mark) }

            guard sqlite3_bind_int64(mark, 1, chapterID) == SQLITE_OK,
                  sqlite3_step(mark) == SQLITE_DONE else {
                throw sqliteError(handle)
            }
        }
    }
}

private func ensureReadingRows(
    sourceID: String,
    manga: Manga,
    chapter: Chapter,
    handle: OpaquePointer
) throws -> (mangaID: Int64, chapterID: Int64) {
    let now = Date().timeIntervalSince1970

    let updateManga = try prepareStatement(
        """
        UPDATE manga
        SET title = ?, cover = ?, description = ?, status = ?, url = ?, last_update = ?
        WHERE source_id = ? AND source_manga_id = ?;
        """,
        handle: handle
    )
    defer { sqlite3_finalize(updateManga) }

    try bindText(manga.title, index: 1, statement: updateManga)
    try bindOptionalText(manga.cover, index: 2, statement: updateManga)
    try bindOptionalText(manga.description, index: 3, statement: updateManga)
    try bindText(manga.status.rawValue, index: 4, statement: updateManga)
    try bindOptionalText(manga.url, index: 5, statement: updateManga)
    guard sqlite3_bind_double(updateManga, 6, now) == SQLITE_OK else {
        throw sqliteError(handle)
    }
    try bindText(sourceID, index: 7, statement: updateManga)
    try bindText(manga.id, index: 8, statement: updateManga)

    guard sqlite3_step(updateManga) == SQLITE_DONE else {
        throw sqliteError(handle)
    }

    if sqlite3_changes(handle) == 0 {
        let insertManga = try prepareStatement(
            """
            INSERT INTO manga
            (source_id, source_manga_id, title, cover, description, status, url, last_update, date_added)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            handle: handle
        )
        defer { sqlite3_finalize(insertManga) }

        try bindText(sourceID, index: 1, statement: insertManga)
        try bindText(manga.id, index: 2, statement: insertManga)
        try bindText(manga.title, index: 3, statement: insertManga)
        try bindOptionalText(manga.cover, index: 4, statement: insertManga)
        try bindOptionalText(manga.description, index: 5, statement: insertManga)
        try bindText(manga.status.rawValue, index: 6, statement: insertManga)
        try bindOptionalText(manga.url, index: 7, statement: insertManga)
        guard sqlite3_bind_double(insertManga, 8, now) == SQLITE_OK,
              sqlite3_bind_double(insertManga, 9, now) == SQLITE_OK,
              sqlite3_step(insertManga) == SQLITE_DONE else {
            throw sqliteError(handle)
        }
    }

    let findManga = try prepareStatement(
        """
        SELECT internal_id
        FROM manga
        WHERE source_id = ? AND source_manga_id = ?
        LIMIT 1;
        """,
        handle: handle
    )
    defer { sqlite3_finalize(findManga) }

    try bindText(sourceID, index: 1, statement: findManga)
    try bindText(manga.id, index: 2, statement: findManga)

    guard sqlite3_step(findManga) == SQLITE_ROW else {
        throw sqliteError(handle)
    }
    let mangaID = sqlite3_column_int64(findManga, 0)

    let updateChapter = try prepareStatement(
        """
        UPDATE chapters
        SET name = ?, number = ?, volume = ?, url = ?
        WHERE manga_id = ? AND source_chapter_id = ?;
        """,
        handle: handle
    )

    try bindText(chapter.name, index: 1, statement: updateChapter)
    try bindOptionalDouble(chapter.number, index: 2, statement: updateChapter)
    try bindOptionalDouble(chapter.volume, index: 3, statement: updateChapter)
    try bindOptionalText(chapter.url, index: 4, statement: updateChapter)
    guard sqlite3_bind_int64(updateChapter, 5, mangaID) == SQLITE_OK else {
        sqlite3_finalize(updateChapter)
        throw sqliteError(handle)
    }
    try bindText(chapter.id, index: 6, statement: updateChapter)

    guard sqlite3_step(updateChapter) == SQLITE_DONE else {
        sqlite3_finalize(updateChapter)
        throw sqliteError(handle)
    }
    let chapterChanged = sqlite3_changes(handle)
    sqlite3_finalize(updateChapter)

    if chapterChanged == 0 {
        let insertChapter = try prepareStatement(
            """
            INSERT INTO chapters
            (manga_id, source_chapter_id, name, number, volume, url)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            handle: handle
        )

        guard sqlite3_bind_int64(insertChapter, 1, mangaID) == SQLITE_OK else {
            sqlite3_finalize(insertChapter)
            throw sqliteError(handle)
        }
        try bindText(chapter.id, index: 2, statement: insertChapter)
        try bindText(chapter.name, index: 3, statement: insertChapter)
        try bindOptionalDouble(chapter.number, index: 4, statement: insertChapter)
        try bindOptionalDouble(chapter.volume, index: 5, statement: insertChapter)
        try bindOptionalText(chapter.url, index: 6, statement: insertChapter)

        guard sqlite3_step(insertChapter) == SQLITE_DONE else {
            sqlite3_finalize(insertChapter)
            throw sqliteError(handle)
        }
        sqlite3_finalize(insertChapter)
    }

    let findChapter = try prepareStatement(
        """
        SELECT internal_id
        FROM chapters
        WHERE manga_id = ? AND source_chapter_id = ?
        LIMIT 1;
        """,
        handle: handle
    )
    defer { sqlite3_finalize(findChapter) }

    guard sqlite3_bind_int64(findChapter, 1, mangaID) == SQLITE_OK else {
        throw sqliteError(handle)
    }
    try bindText(chapter.id, index: 2, statement: findChapter)

    guard sqlite3_step(findChapter) == SQLITE_ROW else {
        throw sqliteError(handle)
    }

    return (
        mangaID: mangaID,
        chapterID: sqlite3_column_int64(findChapter, 0)
    )
}

private func executeSQLite(_ sql: String, handle: OpaquePointer) throws {
    var errorMessage: UnsafeMutablePointer<Int8>?
    let result = sqlite3_exec(handle, sql, nil, nil, &errorMessage)
    guard result == SQLITE_OK else {
        let message = errorMessage.map { String(cString: $0) } ?? "Unknown SQLite error"
        if let errorMessage = errorMessage { sqlite3_free(errorMessage) }
        throw SQLiteDatabaseError.executionFailed(code: result, message: message)
    }
    if let errorMessage = errorMessage { sqlite3_free(errorMessage) }
}

private func bindOptionalText(
    _ value: String?,
    index: Int32,
    statement: OpaquePointer
) throws {
    if let value = value {
        try bindText(value, index: index, statement: statement)
    } else {
        let result = sqlite3_bind_null(statement, index)
        guard result == SQLITE_OK else {
            if let handle = sqlite3_db_handle(statement) {
                throw sqliteError(handle)
            }
            throw SQLiteDatabaseError.connectionUnavailable
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
