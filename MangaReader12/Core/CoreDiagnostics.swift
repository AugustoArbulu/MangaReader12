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
        results.append(runResponseLimitDiagnostic())
        results.append(runJavaScriptCoreDiagnostic())
        results.append(runSourceContractDiagnostic())
        results.append(runRepositoryCatalogDiagnostic())
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

            guard SourceContractFunction.requiredNames == [
                "metadata",
                "popular",
                "search",
                "details",
                "chapters",
                "pages"
            ] else {
                return CoreDiagnosticItem(
                    name: "Manifest",
                    passed: false,
                    detail: "Source API v1 function list drifted"
                )
            }

            return CoreDiagnosticItem(
                name: "Manifest",
                passed: true,
                detail: "Decode + API v1 validation OK"
            )
        } catch {
            return CoreDiagnosticItem(
                name: "Manifest",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }

    private static func runDatabaseDiagnostic() -> CoreDiagnosticItem {
        do {
            let database = try SQLiteDatabase.defaultDatabase()
            defer { database.close() }

            try database.openAndMigrate()
            let version = try database.userVersion()

            guard version == 1 else {
                return CoreDiagnosticItem(
                    name: "SQLite",
                    passed: false,
                    detail: "Unexpected schema version \(version)"
                )
            }

            let sourceID = "diagnostic-persistence"
            let repository = SourceRepository(database: database)
            defer { try? repository.remove(sourceID: sourceID) }

            let manifest = SourceManifest(
                id: sourceID,
                name: "Diagnostic Persistence Source",
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

            try repository.save(manifest: manifest, enabled: true)

            guard let stored = try repository.fetch(sourceID: sourceID),
                  stored.manifest == manifest,
                  stored.enabled else {
                return CoreDiagnosticItem(
                    name: "SQLite",
                    passed: false,
                    detail: "Source repository round-trip mismatch"
                )
            }

            return CoreDiagnosticItem(
                name: "SQLite",
                passed: true,
                detail: "Schema v1 + source persistence OK"
            )
        } catch {
            return CoreDiagnosticItem(
                name: "SQLite",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }

    private static func runNetworkingPolicyDiagnostic() -> CoreDiagnosticItem {
        let policy = HTTPPolicy(allowedDomains: ["example.com"])

        do {
            let accepted = try policy.validatedURL("https://sub.example.com/path")

            do {
                _ = try policy.validatedURL("http://example.com/path")
                return CoreDiagnosticItem(
                    name: "Networking",
                    passed: false,
                    detail: "Insecure HTTP was not blocked"
                )
            } catch HTTPClientError.blockedScheme {
                let timeoutError = HTTPClient.classifyTransportError(URLError(.timedOut))
                guard case HTTPClientError.timedOut = timeoutError else {
                    return CoreDiagnosticItem(
                        name: "Networking",
                        passed: false,
                        detail: "Timeout classification failed"
                    )
                }

                return CoreDiagnosticItem(
                    name: "Networking",
                    passed: true,
                    detail: "HTTPS allowlist + timeout classification OK: \(accepted.host ?? "example.com")"
                )
            } catch {
                return CoreDiagnosticItem(
                    name: "Networking",
                    passed: false,
                    detail: error.localizedDescription
                )
            }
        } catch {
            return CoreDiagnosticItem(
                name: "Networking",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }

    private static func runResponseLimitDiagnostic() -> CoreDiagnosticItem {
        do {
            var buffer = HTTPResponseBuffer(maxBytes: 8)
            try buffer.validateExpectedContentLength(8)
            try buffer.append(Data(repeating: 0x41, count: 4))
            try buffer.append(Data(repeating: 0x42, count: 4))

            guard buffer.data.count == 8 else {
                return CoreDiagnosticItem(
                    name: "Response limit",
                    passed: false,
                    detail: "Streaming buffer did not retain expected bytes"
                )
            }

            do {
                try buffer.append(Data([0x43]))
                return CoreDiagnosticItem(
                    name: "Response limit",
                    passed: false,
                    detail: "Oversized chunk was not rejected"
                )
            } catch HTTPClientError.responseTooLarge {
                return CoreDiagnosticItem(
                    name: "Response limit",
                    passed: true,
                    detail: "Streaming response cap cancels before overrun"
                )
            } catch {
                return CoreDiagnosticItem(
                    name: "Response limit",
                    passed: false,
                    detail: error.localizedDescription
                )
            }
        } catch {
            return CoreDiagnosticItem(
                name: "Response limit",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }

    private static func diagnosticManifest() -> SourceManifest {
        return SourceManifest(
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
    }

    private static func runJavaScriptCoreDiagnostic() -> CoreDiagnosticItem {
        let runtime = JavaScriptSourceRuntime(manifest: diagnosticManifest())

        switch runtime.diagnosticBridgeCheck() {
        case .success(let value):
            return CoreDiagnosticItem(
                name: "JavaScriptCore",
                passed: true,
                detail: "Native bridge OK: \(value)"
            )
        case .failure(let error):
            return CoreDiagnosticItem(
                name: "JavaScriptCore",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }

    private static func runSourceContractDiagnostic() -> CoreDiagnosticItem {
        let runtime = JavaScriptSourceRuntime(manifest: diagnosticManifest())

        switch runtime.diagnosticSourceContractCheck() {
        case .success(let detail):
            return CoreDiagnosticItem(
                name: "Source contract",
                passed: true,
                detail: detail
            )
        case .failure(let error):
            return CoreDiagnosticItem(
                name: "Source contract",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }

    private static func runRepositoryCatalogDiagnostic() -> CoreDiagnosticItem {
        let fixture = """
        {
          "name": "Diagnostic Repository",
          "apiVersion": 1,
          "sources": [
            {
              "id": "fixture.alpha",
              "name": "Fixture Alpha",
              "version": "2.0.0",
              "lang": "en",
              "author": "MangaReader12",
              "script": "https://example.com/alpha.js",
              "icon": null,
              "apiVersion": 1,
              "minAppVersion": "0.1.0",
              "domains": ["example.com"],
              "nsfw": false,
              "sha256": null
            },
            {
              "id": "fixture.beta",
              "name": "Fixture Beta",
              "version": "1.0.0",
              "lang": "en",
              "author": "MangaReader12",
              "script": "https://example.com/beta.js",
              "icon": null,
              "apiVersion": 1,
              "minAppVersion": "0.1.0",
              "domains": ["example.com"],
              "nsfw": false,
              "sha256": null
            }
          ]
        }
        """

        do {
            let catalog = try JSONDecoder().decode(
                RepositoryCatalog.self,
                from: Data(fixture.utf8)
            )

            try catalog.validate()

            let installedAlpha = SourceManifest(
                id: "fixture.alpha",
                name: "Fixture Alpha",
                version: "1.0.0",
                lang: "en",
                author: "MangaReader12",
                script: "https://example.com/alpha.js",
                icon: nil,
                apiVersion: 1,
                minAppVersion: "0.1.0",
                domains: ["example.com"],
                nsfw: false,
                sha256: nil
            )

            let plan = try RepositoryCatalogPlanner.plan(
                catalog: catalog,
                installed: ["fixture.alpha": installedAlpha],
                appVersion: "0.1.0"
            )

            guard plan.count == 2,
                  plan[0].sourceID == "fixture.alpha",
                  plan[0].action == .update,
                  plan[1].sourceID == "fixture.beta",
                  plan[1].action == .install else {
                return CoreDiagnosticItem(
                    name: "Repository catalog",
                    passed: false,
                    detail: "Install/update planning mismatch"
                )
            }

            let duplicateCatalog = RepositoryCatalog(
                name: "Duplicate Check",
                apiVersion: 1,
                sources: [catalog.sources[0], catalog.sources[0]]
            )

            do {
                try duplicateCatalog.validate()
                return CoreDiagnosticItem(
                    name: "Repository catalog",
                    passed: false,
                    detail: "Duplicate source IDs were not rejected"
                )
            } catch RepositoryCatalogError.duplicateSourceID {
                return CoreDiagnosticItem(
                    name: "Repository catalog",
                    passed: true,
                    detail: "Catalog validation + install/update planning OK"
                )
            } catch {
                return CoreDiagnosticItem(
                    name: "Repository catalog",
                    passed: false,
                    detail: error.localizedDescription
                )
            }
        } catch {
            return CoreDiagnosticItem(
                name: "Repository catalog",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }
}
