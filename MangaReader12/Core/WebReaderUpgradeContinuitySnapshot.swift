import Foundation
import SQLite3

/// Build69 BD. A conservative, read-only before/after upgrade snapshot.
///
/// This uses a separate SQLite READONLY connection to the *existing* database.
/// It does not create directories, migrate tables, or alter preferences,
/// enumerate image files, or inspect private title/source/path strings.
///
/// This is a count of database RECORDS, not proof that the corresponding
/// downloaded image bytes still exist. Physical offline reading is mandatory.
enum WebReaderUpgradeContinuitySnapshot {
    private static let expectedSchema = 1
    private static let countStatements: [(String, String)] = [
        ("Obras na biblioteca", "SELECT COUNT(*) FROM library;"),
        ("Capítulos registrados", "SELECT COUNT(*) FROM chapters;"),
        ("Capítulos lidos", "SELECT COUNT(*) FROM chapters WHERE is_read = 1;"),
        ("Capítulos com página registrada", "SELECT COUNT(*) FROM chapters WHERE last_page_read > 0;"),
        ("Capítulos favoritos", "SELECT COUNT(*) FROM chapters WHERE bookmarked = 1;"),
        ("Downloads marcados completos no banco", "SELECT COUNT(*) FROM downloads WHERE state = 'completed';"),
        ("Registros de histórico", "SELECT COUNT(*) FROM history;"),
        ("Categorias", "SELECT COUNT(*) FROM categories;"),
        ("Vínculos obra/categoria", "SELECT COUNT(*) FROM manga_categories;")
    ]

    private static func exactCount(_ db: OpaquePointer, sql: String) -> Int64? {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK,
              let prepared = stmt else {
            sqlite3_finalize(stmt)
            return nil
        }
        defer { sqlite3_finalize(prepared) }
        guard sqlite3_step(prepared) == SQLITE_ROW,
              sqlite3_column_type(prepared, 0) == SQLITE_INTEGER else { return nil }
        let count = sqlite3_column_int64(prepared, 0)
        // Count queries should return exactly one nonnegative integer.
        guard count >= 0, sqlite3_step(prepared) == SQLITE_DONE else { return nil }
        return count
    }

    private static func runReadTransactionStatement(
        _ db: OpaquePointer, sql: String
    ) -> Bool {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK,
              let prepared = stmt else {
            sqlite3_finalize(stmt)
            return false
        }
        defer { sqlite3_finalize(prepared) }
        return sqlite3_step(prepared) == SQLITE_DONE
    }

    private static func readCounts(databaseURL: URL) -> [String]? {
        // Absence is NOT an empty library: it means there was no readable DB.
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return nil }
        var db: OpaquePointer?
        let status = sqlite3_open_v2(
            databaseURL.path, &db,
            SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX, nil
        )
        guard status == SQLITE_OK, let opened = db else {
            if let db = db { sqlite3_close(db) }
            return nil
        }
        defer { sqlite3_close(opened) }
        guard sqlite3_db_readonly(opened, "main") == 1 else { return nil }
        sqlite3_busy_timeout(opened, 200)
        // Pin the counters to ONE consistent SQLite read snapshot even if
        // normal library operations add chapters during this QA diagnostic.
        guard runReadTransactionStatement(opened, sql: "BEGIN DEFERRED;") else {
            return nil
        }
        defer { _ = runReadTransactionStatement(opened, sql: "ROLLBACK;") }
        guard let version = exactCount(opened, sql: "PRAGMA user_version;"),
              version == Int64(expectedSchema) else { return nil }
        var lines: [String] = []
        for (title, query) in countStatements {
            guard let count = exactCount(opened, sql: query) else { return nil }
            lines.append(title + ": " + String(count))
        }
        return lines
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
            "WebReader • CONTINUIDADE DE DADOS — leitura local apenas",
            "Build observada: " + build + " • iOS: " + version,
            "Números do SQLite, sem títulos, IDs, caminhos ou páginas de obras."
        ]
        guard let support = applicationSupportOverride ??
            FileManager.default.urls(
                for: .applicationSupportDirectory, in: .userDomainMask
            ).first else {
            return (header + [
                "Banco: INDISPONÍVEL (não significa biblioteca vazia)",
                "Nenhum dado foi modificado.",
                "Este diagnóstico não abre imagens, não altera arquivos nem usa rede."
            ]).joined(separator: "\n")
        }
        let databaseURL = support
            .appendingPathComponent("MangaReader12", isDirectory: true)
            .appendingPathComponent("library.sqlite", isDirectory: false)
        guard let values = readCounts(databaseURL: databaseURL) else {
            return (header + [
                "Banco: INDISPONÍVEL (ausente, bloqueado ou schema incompatível)",
                "Nenhum dado foi modificado.",
                "Não reinstale nem restaure automaticamente se houver falha.",
                "Este diagnóstico não abre imagens, não altera arquivos nem usa rede."
            ]).joined(separator: "\n")
        }
        return (header + [
            "Banco SQLite: legível • schema v1",
        ] + values + [
            "Downloads completos = registros no banco, NÃO páginas verificadas.",
            "Compare este texto ANTES e DEPOIS do upgrade manual.",
            "Faça o teste real de capítulos offline com Wi-Fi DESLIGADO.",
            "O backup .mr12backup NÃO inclui imagens; restaurar apaga Downloads.",
            "Este diagnóstico não abre imagens, não altera arquivos nem usa rede."
        ]).joined(separator: "\n")
    }
}
