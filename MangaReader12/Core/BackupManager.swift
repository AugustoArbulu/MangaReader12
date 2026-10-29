import Foundation
import SQLite3

struct MangaReaderBackupEnvelope: Codable {
    let formatVersion: Int
    let createdAt: TimeInterval
    let databaseBase64: String
    let preferences: [String: BackupPreferenceValue]
}

struct BackupPreferenceValue: Codable {
    let kind: String
    let stringValue: String?
    let integerValue: Int?
    let doubleValue: Double?
    let boolValue: Bool?
    let dataBase64: String?

    static func encode(_ value: Any) -> BackupPreferenceValue? {
        if let value = value as? String {
            return BackupPreferenceValue(
                kind: "string",
                stringValue: value,
                integerValue: nil,
                doubleValue: nil,
                boolValue: nil,
                dataBase64: nil
            )
        }

        if let value = value as? Bool {
            return BackupPreferenceValue(
                kind: "bool",
                stringValue: nil,
                integerValue: nil,
                doubleValue: nil,
                boolValue: value,
                dataBase64: nil
            )
        }

        if let value = value as? Int {
            return BackupPreferenceValue(
                kind: "int",
                stringValue: nil,
                integerValue: value,
                doubleValue: nil,
                boolValue: nil,
                dataBase64: nil
            )
        }

        if let value = value as? Double {
            return BackupPreferenceValue(
                kind: "double",
                stringValue: nil,
                integerValue: nil,
                doubleValue: value,
                boolValue: nil,
                dataBase64: nil
            )
        }

        if let value = value as? Data {
            return BackupPreferenceValue(
                kind: "data",
                stringValue: nil,
                integerValue: nil,
                doubleValue: nil,
                boolValue: nil,
                dataBase64: value.base64EncodedString()
            )
        }

        return nil
    }

    func decodedValue() -> Any? {
        switch kind {
        case "string":
            return stringValue
        case "bool":
            return boolValue
        case "int":
            return integerValue
        case "double":
            return doubleValue
        case "data":
            guard let raw = dataBase64 else { return nil }
            return Data(base64Encoded: raw)
        default:
            return nil
        }
    }
}

struct BackupRestoreReport {
    let createdAt: TimeInterval
    let restoredPreferenceCount: Int
}

enum BackupManagerError: Error, LocalizedError {
    case applicationSupportUnavailable
    case invalidBackup
    case unsupportedVersion(Int)
    case databaseOpenFailed(Int)
    case databaseCopyFailed(Int, String)
    case databaseValidationFailed

    var errorDescription: String? {
        switch self {
        case .applicationSupportUnavailable:
            return "Application Support directory is unavailable."
        case .invalidBackup:
            return "The selected MangaReader12 backup is invalid."
        case .unsupportedVersion(let version):
            return "Unsupported backup format version: \(version)."
        case .databaseOpenFailed(let code):
            return "Could not open the backup database (SQLite \(code))."
        case .databaseCopyFailed(let code, let message):
            return "Could not copy the backup database (SQLite \(code)): \(message)"
        case .databaseValidationFailed:
            return "The backup database failed validation."
        }
    }
}

final class BackupManager {
    static let formatVersion = 1

    private let fileManager: FileManager
    private let defaults: UserDefaults

    private let preferenceKeys = [
        "app.theme",
        "reader.mode",
        "reader.pageDirection",
        "reader.background",
        "reader.showPageNumber",
        "reader.keepScreenOn",
        "reader.tapZones",
        "reader.webtoonGap",
        "reader.doubleTapZoom",
        "updates.feed.v1",
        "backgroundUpdates.enabled"
    ]

    init(
        fileManager: FileManager = .default,
        defaults: UserDefaults = .standard
    ) {
        self.fileManager = fileManager
        self.defaults = defaults
    }

    func createBackupFile() throws -> URL {
        let directory = fileManager.temporaryDirectory.appendingPathComponent(
            "MangaReader12-Backup-\(UUID().uuidString)",
            isDirectory: true
        )
        try fileManager.createDirectory(
            at: directory,
            withIntermediateDirectories: true,
            attributes: nil
        )

        let snapshotURL = directory.appendingPathComponent("library.sqlite")
        try copyDatabase(
            from: try liveDatabaseURL(),
            to: snapshotURL
        )
        try sanitizePortableSnapshot(at: snapshotURL)

        let databaseData = try Data(contentsOf: snapshotURL)

        var preferences: [String: BackupPreferenceValue] = [:]
        for key in preferenceKeys {
            if let object = defaults.object(forKey: key),
               let encoded = BackupPreferenceValue.encode(object) {
                preferences[key] = encoded
            }
        }

        let envelope = MangaReaderBackupEnvelope(
            formatVersion: Self.formatVersion,
            createdAt: Date().timeIntervalSince1970,
            databaseBase64: databaseData.base64EncodedString(),
            preferences: preferences
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(envelope)

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd_HH-mm-ss"
        let name = "MangaReader12_\(formatter.string(from: Date())).mr12backup"
        let output = directory.appendingPathComponent(name)
        try data.write(to: output, options: .atomic)
        return output
    }

    func restoreBackup(from url: URL) throws -> BackupRestoreReport {
        let data = try Data(contentsOf: url)
        let envelope: MangaReaderBackupEnvelope

        do {
            envelope = try JSONDecoder().decode(
                MangaReaderBackupEnvelope.self,
                from: data
            )
        } catch {
            throw BackupManagerError.invalidBackup
        }

        guard envelope.formatVersion == Self.formatVersion else {
            throw BackupManagerError.unsupportedVersion(envelope.formatVersion)
        }

        guard let databaseData = Data(base64Encoded: envelope.databaseBase64) else {
            throw BackupManagerError.invalidBackup
        }

        let temporaryDatabase = fileManager.temporaryDirectory
            .appendingPathComponent("MangaReader12-Restore-\(UUID().uuidString).sqlite")
        defer { try? fileManager.removeItem(at: temporaryDatabase) }

        try databaseData.write(to: temporaryDatabase, options: .atomic)
        try validateDatabase(at: temporaryDatabase)

        let preservedSources = try installedSourcesThatStillHaveScripts()
        let liveURL = try liveDatabaseURL()

        try copyDatabase(
            from: temporaryDatabase,
            to: liveURL
        )
        try restorePreservedSources(preservedSources)
        try clearExcludedDownloadFiles()

        var restoredCount = 0
        for (key, value) in envelope.preferences {
            guard preferenceKeys.contains(key),
                  let object = value.decodedValue() else {
                continue
            }

            defaults.set(object, forKey: key)
            restoredCount += 1
        }
        defaults.synchronize()

        return BackupRestoreReport(
            createdAt: envelope.createdAt,
            restoredPreferenceCount: restoredCount
        )
    }

    private func installedSourcesThatStillHaveScripts() throws -> [InstalledSourceRecord] {
        let database = try SQLiteDatabase.defaultDatabase()
        defer { database.close() }

        try database.openAndMigrate()
        let repository = SourceRepository(database: database)
        let records = try repository.list()
        let installer = try SourceScriptInstaller.defaultInstaller()

        return records.filter { record in
            return (try? installer.active(
                sourceID: record.manifest.id
            )) != nil
        }
    }

    private func restorePreservedSources(
        _ records: [InstalledSourceRecord]
    ) throws {
        guard !records.isEmpty else { return }

        let database = try SQLiteDatabase.defaultDatabase()
        defer { database.close() }

        try database.openAndMigrate()
        let repository = SourceRepository(database: database)

        for record in records {
            try repository.save(
                manifest: record.manifest,
                enabled: record.enabled
            )
        }
    }

    private func clearExcludedDownloadFiles() throws {
        guard let base = fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first else {
            throw BackupManagerError.applicationSupportUnavailable
        }

        let downloads = base
            .appendingPathComponent("MangaReader12", isDirectory: true)
            .appendingPathComponent("Downloads", isDirectory: true)

        if fileManager.fileExists(atPath: downloads.path) {
            try fileManager.removeItem(at: downloads)
        }

        try fileManager.createDirectory(
            at: downloads,
            withIntermediateDirectories: true,
            attributes: nil
        )
    }

    private func liveDatabaseURL() throws -> URL {
        guard let base = fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first else {
            throw BackupManagerError.applicationSupportUnavailable
        }

        let directory = base.appendingPathComponent(
            "MangaReader12",
            isDirectory: true
        )
        try fileManager.createDirectory(
            at: directory,
            withIntermediateDirectories: true,
            attributes: nil
        )
        return directory.appendingPathComponent("library.sqlite")
    }

    private func sanitizePortableSnapshot(at url: URL) throws {
        var handle: OpaquePointer?
        let result = sqlite3_open_v2(
            url.path,
            &handle,
            SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX,
            nil
        )

        guard result == SQLITE_OK, let opened = handle else {
            if let handle = handle { sqlite3_close(handle) }
            throw BackupManagerError.databaseOpenFailed(Int(result))
        }
        defer { sqlite3_close(opened) }

        let sql = """
        BEGIN IMMEDIATE TRANSACTION;
        DELETE FROM downloads;
        UPDATE chapters SET downloaded = 0;
        DELETE FROM sources;
        COMMIT;
        """

        var message: UnsafeMutablePointer<Int8>?
        let executeResult = sqlite3_exec(opened, sql, nil, nil, &message)

        guard executeResult == SQLITE_OK else {
            let text = message.map { String(cString: $0) } ?? "Unknown SQLite error"
            if let message = message { sqlite3_free(message) }
            throw BackupManagerError.databaseCopyFailed(Int(executeResult), text)
        }

        if let message = message { sqlite3_free(message) }
    }

    private func validateDatabase(at url: URL) throws {
        var handle: OpaquePointer?
        let result = sqlite3_open_v2(
            url.path,
            &handle,
            SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX,
            nil
        )
        guard result == SQLITE_OK, let opened = handle else {
            if let handle = handle { sqlite3_close(handle) }
            throw BackupManagerError.databaseOpenFailed(Int(result))
        }
        defer { sqlite3_close(opened) }

        var statement: OpaquePointer?
        defer { sqlite3_finalize(statement) }

        guard sqlite3_prepare_v2(
            opened,
            "PRAGMA user_version;",
            -1,
            &statement,
            nil
        ) == SQLITE_OK,
        sqlite3_step(statement) == SQLITE_ROW,
        sqlite3_column_int(statement, 0) == 1 else {
            throw BackupManagerError.databaseValidationFailed
        }
    }

    private func copyDatabase(from sourceURL: URL, to destinationURL: URL) throws {
        var source: OpaquePointer?
        var destination: OpaquePointer?

        let sourceResult = sqlite3_open_v2(
            sourceURL.path,
            &source,
            SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX,
            nil
        )
        guard sourceResult == SQLITE_OK, let sourceHandle = source else {
            if let source = source { sqlite3_close(source) }
            throw BackupManagerError.databaseOpenFailed(Int(sourceResult))
        }
        defer { sqlite3_close(sourceHandle) }

        let destinationResult = sqlite3_open_v2(
            destinationURL.path,
            &destination,
            SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX,
            nil
        )
        guard destinationResult == SQLITE_OK, let destinationHandle = destination else {
            if let destination = destination { sqlite3_close(destination) }
            throw BackupManagerError.databaseOpenFailed(Int(destinationResult))
        }
        defer { sqlite3_close(destinationHandle) }

        guard let backup = sqlite3_backup_init(
            destinationHandle,
            "main",
            sourceHandle,
            "main"
        ) else {
            let code = sqlite3_errcode(destinationHandle)
            let message = sqlite3_errmsg(destinationHandle).map {
                String(cString: $0)
            } ?? "Unknown SQLite error"
            throw BackupManagerError.databaseCopyFailed(Int(code), message)
        }

        let stepResult = sqlite3_backup_step(backup, -1)
        let finishResult = sqlite3_backup_finish(backup)

        guard (stepResult == SQLITE_DONE || stepResult == SQLITE_OK),
              finishResult == SQLITE_OK else {
            let code = sqlite3_errcode(destinationHandle)
            let message = sqlite3_errmsg(destinationHandle).map {
                String(cString: $0)
            } ?? "Unknown SQLite error"
            throw BackupManagerError.databaseCopyFailed(Int(code), message)
        }
    }
}
