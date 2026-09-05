import Foundation

struct CoreDiagnosticItem {
    let name: String
    let passed: Bool
    let detail: String
}

enum CoreDiagnostics {
    static func run() -> [CoreDiagnosticItem] {
        var results: [CoreDiagnosticItem] = []
        results.append(runManifestDiagnostic())
        results.append(runDatabaseDiagnostic())
        results.append(runNetworkingPolicyDiagnostic())
        results.append(runJavaScriptCoreDiagnostic())
        return results
    }

    private static func runManifestDiagnostic() -> CoreDiagnosticItem {
        let fixture = """
        {
          "id": "diagnostic-source",
          "name": "Diagnostic Source",
          "version": "1.0.0",
          "lang": "en",
          "author": "MangaReader12",
          "script": "https://example.com/source.js",
          "icon": null,
          "apiVersion": 1,
          "minAppVersion": "0.1.0",
          "domains": ["example.com"],
          "nsfw": false,
          "sha256": null
        }
        """

        do {
            let data = Data(fixture.utf8)
            let manifest = try JSONDecoder().decode(SourceManifest.self, from: data)
            try manifest.validate()
            return CoreDiagnosticItem(name: "Manifest", passed: true, detail: "Decode + validation OK")
        } catch {
            return CoreDiagnosticItem(name: "Manifest", passed: false, detail: error.localizedDescription)
        }
    }

    private static func runDatabaseDiagnostic() -> CoreDiagnosticItem {
        do {
            let database = try SQLiteDatabase.defaultDatabase()
            try database.openAndMigrate()
            let version = try database.userVersion()
            database.close()

            guard version == 1 else {
                return CoreDiagnosticItem(name: "SQLite", passed: false, detail: "Unexpected schema version \(version)")
            }

            return CoreDiagnosticItem(name: "SQLite", passed: true, detail: "Schema v1 + WAL OK")
        } catch {
            return CoreDiagnosticItem(name: "SQLite", passed: false, detail: error.localizedDescription)
        }
    }

    private static func runNetworkingPolicyDiagnostic() -> CoreDiagnosticItem {
        let policy = HTTPPolicy(allowedDomains: ["example.com"])

        do {
            let accepted = try policy.validatedURL("https://sub.example.com/path")

            do {
                _ = try policy.validatedURL("http://example.com/path")
                return CoreDiagnosticItem(name: "Networking", passed: false, detail: "Insecure HTTP was not blocked")
            } catch HTTPClientError.blockedScheme {
                return CoreDiagnosticItem(name: "Networking", passed: true, detail: "HTTPS allowlist OK: \(accepted.host ?? "example.com")")
            } catch {
                return CoreDiagnosticItem(name: "Networking", passed: false, detail: error.localizedDescription)
            }
        } catch {
            return CoreDiagnosticItem(name: "Networking", passed: false, detail: error.localizedDescription)
        }
    }

    private static func runJavaScriptCoreDiagnostic() -> CoreDiagnosticItem {
        let manifest = SourceManifest(
            id: "diagnostic-source",
            name: "Diagnostic Source",
            version: "1.0.0",
            lang: "en",
            author: "MangaReader12",
            script: "https://example.com/source.js",
            icon: nil,
            apiVersion: 1,
            minAppVersion: "0.1.0",
            domains: ["example.com"],
            nsfw: false,
            sha256: nil
        )

        let runtime = JavaScriptSourceRuntime(manifest: manifest)
        switch runtime.diagnosticBridgeCheck() {
        case .success(let value):
            return CoreDiagnosticItem(name: "JavaScriptCore", passed: true, detail: "Native bridge OK: \(value)")
        case .failure(let error):
            return CoreDiagnosticItem(name: "JavaScriptCore", passed: false, detail: error.localizedDescription)
        }
    }
}
