import Foundation
import SQLite3

/// Build69 BI: a bounded, metadata-only audit of completed offline chapters.
///
/// Never trusts historical stored local_path values (old container UUIDs).
/// Uses the SAME current-container resolver as the reader and the strict BH
/// page inventory. Only counts are disclosed; source/title/chapter IDs and
/// filesystem paths never appear in the report. No image payloads are read.
/// SQLite remains readonly and user page files are never changed.
enum WebReaderOfflinePreservationAudit {
    private static let sampleLimit = 64

    private static func countCompleted(_ db: OpaquePointer) -> Int64? {
        var stmt: OpaquePointer?
        let query = "SELECT COUNT(*) FROM downloads WHERE state = 'completed';"
        guard sqlite3_prepare_v2(db, query, -1, &stmt, nil) == SQLITE_OK,
              let prepared = stmt else {
            sqlite3_finalize(stmt)
            return nil
        }
        defer { sqlite3_finalize(prepared) }
        guard sqlite3_step(prepared) == SQLITE_ROW,
              sqlite3_column_type(prepared, 0) == SQLITE_INTEGER else { return nil }
        let count = sqlite3_column_int64(prepared, 0)
        guard count >= 0 && sqlite3_step(prepared) == SQLITE_DONE else { return nil }
        return count
    }

    private static func boundedID(_ stmt: OpaquePointer, _ column: Int32) -> String? {
        guard sqlite3_column_type(stmt, column) == SQLITE_TEXT,
              let pointer = sqlite3_column_text(stmt, column) else { return nil }
        let count = Int(sqlite3_column_bytes(stmt, column))
        guard count > 0 && count <= 2048 else { return nil }
        let raw = UnsafeBufferPointer(start: pointer, count: count)
        guard let text = String(bytes: raw, encoding: .utf8),
              !text.contains("\0") else { return nil }
        return text
    }

    private static func readSample(
        databaseURL: URL, support: URL
    ) -> (all: Int64, scanned: Int, valid: Int, sealed: Int, pages: Int)? {
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return nil }
        var db: OpaquePointer?
        let openedOK = sqlite3_open_v2(
            databaseURL.path, &db,
            SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX, nil
        )
        guard openedOK == SQLITE_OK, let conn = db else {
            if let db = db { sqlite3_close(db) }
            return nil
        }
        defer { sqlite3_close(conn) }
        guard sqlite3_db_readonly(conn, "main") == 1 else { return nil }
        sqlite3_busy_timeout(conn, 200)
        guard sqlite3_exec(conn, "BEGIN DEFERRED;", nil, nil, nil) == SQLITE_OK else {
            return nil
        }
        defer { _ = sqlite3_exec(conn, "ROLLBACK;", nil, nil, nil) }
        var schema: OpaquePointer?
        guard sqlite3_prepare_v2(conn, "PRAGMA user_version;", -1, &schema, nil)
                == SQLITE_OK,
              let versionQuery = schema else {
            sqlite3_finalize(schema)
            return nil
        }
        let schemaValid = sqlite3_step(versionQuery) == SQLITE_ROW &&
            sqlite3_column_int64(versionQuery, 0) == 1 &&
            sqlite3_step(versionQuery) == SQLITE_DONE
        sqlite3_finalize(versionQuery)
        guard schemaValid, let total = countCompleted(conn) else { return nil }

        let query = """
            SELECT m.source_id, m.source_manga_id, c.source_chapter_id
            FROM downloads AS d
            JOIN chapters AS c ON c.internal_id = d.chapter_id
            JOIN manga AS m ON m.internal_id = c.manga_id
            WHERE d.state = 'completed'
            ORDER BY d.internal_id ASC LIMIT 64;
            """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(conn, query, -1, &stmt, nil) == SQLITE_OK,
              let prepared = stmt else {
            sqlite3_finalize(stmt)
            return nil
        }
        defer { sqlite3_finalize(prepared) }
        var scanned = 0
        var valid = 0
        var sealed = 0
        var pages = 0
        while true {
            let next = sqlite3_step(prepared)
            if next == SQLITE_DONE { break }
            guard next == SQLITE_ROW, scanned < sampleLimit else { return nil }
            scanned += 1
            guard let sourceID = boundedID(prepared, 0),
                  let mangaID = boundedID(prepared, 1),
                  let chapterID = boundedID(prepared, 2) else { continue }
            let directory = OfflineDownloadPath.chapterDirectory(
                applicationSupport: support,
                sourceID: sourceID, mangaID: mangaID, chapterID: chapterID
            )
            // May fail on missing/empty/sparse/symlink files. That is a
            // counted failure, NEVER a reason to repair, move or delete.
            if let files = try? WebReaderOfflinePageInventory.inspect(
                directory: directory
            ), let hasReceipt = try? WebReaderOfflineCompletionReceipt.verifyIfPresent(
                directory: directory, actualPages: files.count
            ) {
                valid += 1
                if hasReceipt { sealed += 1 }
                pages += files.count
            }
        }
        guard Int64(scanned) <= total else { return nil }
        return (total, scanned, valid, sealed, pages)
    }

    static func report(
        installedBuild: Int, ios: OperatingSystemVersion,
        applicationSupportOverride: URL? = nil
    ) -> String {
        let build = installedBuild >= 1 && installedBuild <= 2_147_483_647
            ? String(installedBuild) : "desconhecida"
        let version = ios.majorVersion >= 0 && ios.majorVersion <= 99 &&
            ios.minorVersion >= 0 && ios.minorVersion <= 99 &&
            ios.patchVersion >= 0 && ios.patchVersion <= 99
            ? String(ios.majorVersion) + "." + String(ios.minorVersion) +
                "." + String(ios.patchVersion) : "desconhecido"
        let header = [
            "WebReader • PRESENÇA OFFLINE — diagnóstico local parcial",
            "Build observada: " + build + " • iOS: " + version,
            "Amostra máxima: 64 capítulos marcados completos.",
            "Sem títulos, IDs, caminhos, imagens ou consultas à rede."
        ]
        guard let support = applicationSupportOverride ?? FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first else {
            return (header + ["Banco: INDISPONÍVEL; nenhuma página foi modificada."])
                .joined(separator: "\n")
        }
        let database = support
            .appendingPathComponent("MangaReader12", isDirectory: true)
            .appendingPathComponent("library.sqlite", isDirectory: false)
        guard let sample = readSample(databaseURL: database, support: support) else {
            return (header + [
                "Banco: INDISPONÍVEL ou leitura interrompida.",
                "Não significa que não existam capítulos offline.",
                "Nenhuma página foi modificada."
            ]).joined(separator: "\n")
        }
        let bad = sample.scanned - sample.valid
        let remaining = sample.all - Int64(sample.scanned)
        return (header + [
            "Capítulos completos no banco: " + String(sample.all),
            "Capítulos da amostra inspecionados: " + String(sample.scanned),
            "Capítulos com arquivos sequenciais e não vazios: " + String(sample.valid),
            "Com recibo de quantidade de páginas: " + String(sample.sealed),
            "Legados sem recibo entre os válidos: " + String(sample.valid - sample.sealed),
            "Capítulos faltantes, incompletos ou inseguros: " + String(bad),
            "Capítulos fora da amostra: " + String(remaining),
            "Arquivos de páginas presentes na amostra: " + String(sample.pages),
            "Presença de arquivo ou recibo NÃO comprova imagem íntegra ou capítulo completo na origem.",
            "Se houver falhas, não desinstale nem restaure backup automaticamente.",
            "Teste a leitura REAL sem Wi-Fi, inclusive após fechar e reabrir o app.",
            "Nenhuma página foi modificada; este diagnóstico não faz download."
        ]).joined(separator: "\n")
    }
}
