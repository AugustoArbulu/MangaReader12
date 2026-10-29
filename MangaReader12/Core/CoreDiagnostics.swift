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
        results.append(runRepositoryTransportDiagnostic())
        results.append(runSourceInstallerDiagnostic())
        results.append(runSourceLifecycleDiagnostic())
        results.append(runInstalledRuntimeDiagnostic())
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

    private static func runRepositoryTransportDiagnostic() -> CoreDiagnosticItem {
        let repositoryURL = "https://example.com/mangareader12-diagnostic-repository.json"

        do {
            let knownHash = SHA256Digest.hex(Data("abc".utf8))
            guard knownHash == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" else {
                return CoreDiagnosticItem(
                    name: "Repository transport",
                    passed: false,
                    detail: "SHA-256 known-vector mismatch"
                )
            }

            let policy = try RepositoryTransportPolicy.httpPolicy(
                for: repositoryURL,
                maxResponseBytes: 1024 * 1024
            )
            _ = try policy.validatedURL(repositoryURL)

            do {
                _ = try RepositoryTransportPolicy.httpPolicy(
                    for: "http://example.com/repository.json",
                    maxResponseBytes: 1024
                )
                return CoreDiagnosticItem(
                    name: "Repository transport",
                    passed: false,
                    detail: "Insecure repository URL was not rejected"
                )
            } catch RepositoryTransportError.invalidRepositoryURL {
                // Expected.
            }

            let scriptData = Data("var source = {};".utf8)
            let digest = SHA256Digest.hex(scriptData)
            let manifest = SourceManifest(
                id: "diagnostic-integrity",
                name: "Diagnostic Integrity",
                version: "1.0.0",
                lang: "en",
                author: "MangaReader12",
                script: "https://example.com/source.js",
                icon: nil,
                apiVersion: 1,
                minAppVersion: "0.1.0",
                domains: ["example.com"],
                nsfw: false,
                sha256: digest
            )

            guard try SourceScriptIntegrity.verify(
                data: scriptData,
                manifest: manifest
            ) == .verified else {
                return CoreDiagnosticItem(
                    name: "Repository transport",
                    passed: false,
                    detail: "Matching source hash was not verified"
                )
            }

            let catalogFixture = """
            {
              "name": "Transport Diagnostic",
              "apiVersion": 1,
              "sources": [
                {
                  "id": "diagnostic-integrity",
                  "name": "Diagnostic Integrity",
                  "version": "1.0.0",
                  "lang": "en",
                  "author": "MangaReader12",
                  "script": "https://example.com/source.js",
                  "icon": null,
                  "apiVersion": 1,
                  "minAppVersion": "0.1.0",
                  "domains": ["example.com"],
                  "nsfw": false,
                  "sha256": "\(digest)"
                }
              ]
            }
            """

            let decoded = try RepositoryRemoteClient.decodeCatalog(
                Data(catalogFixture.utf8)
            )

            guard decoded.sources.count == 1,
                  decoded.sources[0].sha256 == digest else {
                return CoreDiagnosticItem(
                    name: "Repository transport",
                    passed: false,
                    detail: "Repository transport catalog decode mismatch"
                )
            }

            let database = try SQLiteDatabase.defaultDatabase()
            defer { database.close() }

            let repositoryStore = RepositoryRepository(database: database)
            defer { try? repositoryStore.remove(url: repositoryURL) }

            try repositoryStore.save(
                name: "Diagnostic Repository",
                url: repositoryURL,
                enabled: true,
                lastRefresh: nil
            )

            guard let stored = try repositoryStore.fetch(url: repositoryURL),
                  stored.enabled,
                  stored.lastRefresh == nil else {
                return CoreDiagnosticItem(
                    name: "Repository transport",
                    passed: false,
                    detail: "Repository persistence round-trip mismatch"
                )
            }

            let refreshTimestamp: TimeInterval = 12345
            try repositoryStore.markRefreshed(
                url: repositoryURL,
                at: refreshTimestamp
            )

            guard let refreshed = try repositoryStore.fetch(url: repositoryURL),
                  refreshed.lastRefresh == refreshTimestamp else {
                return CoreDiagnosticItem(
                    name: "Repository transport",
                    passed: false,
                    detail: "Repository refresh timestamp mismatch"
                )
            }

            return CoreDiagnosticItem(
                name: "Repository transport",
                passed: true,
                detail: "HTTPS policy + SHA-256 + refresh persistence OK"
            )
        } catch {
            return CoreDiagnosticItem(
                name: "Repository transport",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }

    private static func runSourceInstallerDiagnostic() -> CoreDiagnosticItem {
        let fileManager = FileManager.default
        let root = fileManager.temporaryDirectory.appendingPathComponent(
            "MangaReader12-M2C-\(UUID().uuidString)",
            isDirectory: true
        )

        let installer = SourceScriptInstaller(
            baseDirectory: root,
            fileManager: fileManager
        )

        let sourceID = "diagnostic-atomic-install"
        defer {
            try? installer.remove(sourceID: sourceID)
            try? fileManager.removeItem(at: root)
        }

        do {
            let scriptV1 = Data("var diagnosticVersion = 1;".utf8)
            let scriptV2 = Data("var diagnosticVersion = 2;".utf8)

            let manifestV1 = SourceManifest(
                id: sourceID,
                name: "Diagnostic Atomic Source",
                version: "1.0.0",
                lang: "en",
                author: "MangaReader12",
                script: "https://example.com/source.js",
                icon: nil,
                apiVersion: 1,
                minAppVersion: "0.1.0",
                domains: ["example.com"],
                nsfw: false,
                sha256: SHA256Digest.hex(scriptV1)
            )

            let manifestV2 = SourceManifest(
                id: sourceID,
                name: "Diagnostic Atomic Source",
                version: "2.0.0",
                lang: "en",
                author: "MangaReader12",
                script: "https://example.com/source.js",
                icon: nil,
                apiVersion: 1,
                minAppVersion: "0.1.0",
                domains: ["example.com"],
                nsfw: false,
                sha256: SHA256Digest.hex(scriptV2)
            )

            try installer.install(
                manifest: manifestV1,
                scriptData: scriptV1
            )

            guard try installer.active(sourceID: sourceID).manifest.version == "1.0.0",
                  try installer.previous(sourceID: sourceID) == nil else {
                return CoreDiagnosticItem(
                    name: "Source installer",
                    passed: false,
                    detail: "Initial install layout mismatch"
                )
            }

            try installer.install(
                manifest: manifestV2,
                scriptData: scriptV2
            )

            guard try installer.active(sourceID: sourceID).manifest.version == "2.0.0",
                  try installer.previous(sourceID: sourceID)?.manifest.version == "1.0.0" else {
                return CoreDiagnosticItem(
                    name: "Source installer",
                    passed: false,
                    detail: "Update did not preserve previous version"
                )
            }

            try installer.rollback(sourceID: sourceID)

            guard try installer.active(sourceID: sourceID).manifest.version == "1.0.0",
                  try installer.previous(sourceID: sourceID)?.manifest.version == "2.0.0" else {
                return CoreDiagnosticItem(
                    name: "Source installer",
                    passed: false,
                    detail: "Rollback did not restore previous version"
                )
            }

            let badManifest = SourceManifest(
                id: sourceID,
                name: "Diagnostic Atomic Source",
                version: "3.0.0",
                lang: "en",
                author: "MangaReader12",
                script: "https://example.com/source.js",
                icon: nil,
                apiVersion: 1,
                minAppVersion: "0.1.0",
                domains: ["example.com"],
                nsfw: false,
                sha256: SHA256Digest.hex(Data("expected bytes".utf8))
            )

            do {
                try installer.install(
                    manifest: badManifest,
                    scriptData: Data("corrupt bytes".utf8)
                )

                return CoreDiagnosticItem(
                    name: "Source installer",
                    passed: false,
                    detail: "Integrity mismatch was not rejected"
                )
            } catch RepositoryTransportError.integrityMismatch {
                guard try installer.active(sourceID: sourceID).manifest.version == "1.0.0" else {
                    return CoreDiagnosticItem(
                        name: "Source installer",
                        passed: false,
                        detail: "Rejected update changed active version"
                    )
                }

                return CoreDiagnosticItem(
                    name: "Source installer",
                    passed: true,
                    detail: "Atomic install + update + rollback OK"
                )
            }
        } catch {
            return CoreDiagnosticItem(
                name: "Source installer",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }


    private static func runSourceLifecycleDiagnostic() -> CoreDiagnosticItem {
        let fileManager = FileManager.default
        let root = fileManager.temporaryDirectory.appendingPathComponent(
            "MangaReader12-Lifecycle-\(UUID().uuidString)",
            isDirectory: true
        )
        let databasePath = root.appendingPathComponent("diagnostic.sqlite").path
        let sourcesDirectory = root.appendingPathComponent("Sources", isDirectory: true)

        do {
            try fileManager.createDirectory(
                at: root,
                withIntermediateDirectories: true,
                attributes: nil
            )

            let database = SQLiteDatabase(path: databasePath)
            defer {
                database.close()
                try? fileManager.removeItem(at: root)
            }

            try database.openAndMigrate()

            let installer = SourceScriptInstaller(
                baseDirectory: sourcesDirectory,
                fileManager: fileManager
            )

            let manager = SourceLifecycleManager(
                database: database,
                installer: installer,
                appVersion: "0.1.0"
            )

            let scriptV1 = Data("var source = {};".utf8)
            let manifestV1 = SourceManifest(
                id: "diagnostic.lifecycle",
                name: "Lifecycle Diagnostic",
                version: "1.0.0",
                lang: "en",
                author: "MangaReader12",
                script: "https://example.com/source.js",
                icon: nil,
                apiVersion: 1,
                minAppVersion: "0.1.0",
                domains: ["example.com"],
                nsfw: false,
                sha256: SHA256Digest.hex(scriptV1)
            )

            let installed = try manager.installDownloaded(
                manifest: manifestV1,
                scriptData: scriptV1
            )

            guard installed.manifest.version == "1.0.0",
                  installed.enabled,
                  try manager.installedSources().count == 1 else {
                return CoreDiagnosticItem(
                    name: "Source lifecycle",
                    passed: false,
                    detail: "Install/persistence mismatch"
                )
            }

            try manager.setSourceEnabled(
                false,
                sourceID: manifestV1.id
            )

            guard try manager.installedSources().first?.enabled == false else {
                return CoreDiagnosticItem(
                    name: "Source lifecycle",
                    passed: false,
                    detail: "Enable/disable state mismatch"
                )
            }

            let scriptV2 = Data("var source = { version: 2 };".utf8)
            let manifestV2 = SourceManifest(
                id: manifestV1.id,
                name: manifestV1.name,
                version: "2.0.0",
                lang: manifestV1.lang,
                author: manifestV1.author,
                script: manifestV1.script,
                icon: nil,
                apiVersion: 1,
                minAppVersion: "0.1.0",
                domains: manifestV1.domains,
                nsfw: false,
                sha256: SHA256Digest.hex(scriptV2)
            )

            let updated = try manager.installDownloaded(
                manifest: manifestV2,
                scriptData: scriptV2
            )

            guard updated.manifest.version == "2.0.0",
                  updated.enabled == false,
                  try installer.previous(sourceID: manifestV1.id)?.manifest.version == "1.0.0" else {
                return CoreDiagnosticItem(
                    name: "Source lifecycle",
                    passed: false,
                    detail: "Update did not preserve state/version"
                )
            }

            let rolledBack = try manager.rollback(sourceID: manifestV1.id)

            guard rolledBack.manifest.version == "1.0.0",
                  rolledBack.enabled == false else {
                return CoreDiagnosticItem(
                    name: "Source lifecycle",
                    passed: false,
                    detail: "Rollback did not restore persisted manifest"
                )
            }

            try manager.removeSource(sourceID: manifestV1.id)

            guard try manager.installedSources().isEmpty else {
                return CoreDiagnosticItem(
                    name: "Source lifecycle",
                    passed: false,
                    detail: "Source removal left database state behind"
                )
            }

            return CoreDiagnosticItem(
                name: "Source lifecycle",
                passed: true,
                detail: "DB + disk install/update/toggle/rollback/remove OK"
            )
        } catch {
            try? fileManager.removeItem(at: root)
            return CoreDiagnosticItem(
                name: "Source lifecycle",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }

    private static func runInstalledRuntimeDiagnostic() -> CoreDiagnosticItem {
        let fileManager = FileManager.default
        let root = fileManager.temporaryDirectory.appendingPathComponent(
            "MangaReader12-Runtime-\(UUID().uuidString)",
            isDirectory: true
        )

        let sourceID = "diagnostic.installed-runtime"
        let script = """
        var source = {
          metadata: function() {
            return {
              id: "diagnostic.installed-runtime",
              name: "Installed Runtime Diagnostic",
              lang: "en",
              version: "1.0.0"
            };
          },
          popular: function(page) {
            return { items: [], hasNextPage: false };
          },
          search: function(query, page, filters) {
            return { items: [], hasNextPage: false };
          },
          details: function(mangaId) {
            return {
              id: mangaId,
              title: "Diagnostic",
              altTitles: [],
              cover: null,
              author: null,
              artist: null,
              description: null,
              status: "unknown",
              genres: [],
              url: null
            };
          },
          chapters: function(mangaId) { return []; },
          pages: function(chapterId) { return []; }
        };
        """

        do {
            let installer = SourceScriptInstaller(
                baseDirectory: root,
                fileManager: fileManager
            )
            defer {
                try? installer.remove(sourceID: sourceID)
                try? fileManager.removeItem(at: root)
            }

            let scriptData = Data(script.utf8)
            let manifest = SourceManifest(
                id: sourceID,
                name: "Installed Runtime Diagnostic",
                version: "1.0.0",
                lang: "en",
                author: "MangaReader12",
                script: "https://example.com/source.js",
                icon: nil,
                apiVersion: 1,
                minAppVersion: "0.1.0",
                domains: ["example.com"],
                nsfw: false,
                sha256: SHA256Digest.hex(scriptData)
            )

            try installer.install(
                manifest: manifest,
                scriptData: scriptData
            )

            let loader = InstalledSourceRuntimeLoader(installer: installer)
            let semaphore = DispatchSemaphore(value: 0)
            var diagnosticResult: Result<SourceMetadata, Error>?

            loader.load(sourceID: sourceID) { runtimeResult in
                switch runtimeResult {
                case .success(let runtime):
                    runtime.callDecoded(
                        "metadata",
                        as: SourceMetadata.self
                    ) { metadataResult in
                        diagnosticResult = metadataResult
                        semaphore.signal()
                    }

                case .failure(let error):
                    diagnosticResult = .failure(error)
                    semaphore.signal()
                }
            }

            let waitResult = semaphore.wait(timeout: .now() + 3)
            guard waitResult == .success else {
                return CoreDiagnosticItem(
                    name: "Installed runtime",
                    passed: false,
                    detail: "Runtime load timed out"
                )
            }

            switch diagnosticResult {
            case .success(let metadata)?:
                guard metadata.id == sourceID,
                      metadata.version == "1.0.0" else {
                    return CoreDiagnosticItem(
                        name: "Installed runtime",
                        passed: false,
                        detail: "Installed metadata mismatch"
                    )
                }

                return CoreDiagnosticItem(
                    name: "Installed runtime",
                    passed: true,
                    detail: "active/source.js → JavaScriptCore contract OK"
                )

            case .failure(let error)?:
                return CoreDiagnosticItem(
                    name: "Installed runtime",
                    passed: false,
                    detail: error.localizedDescription
                )

            case nil:
                return CoreDiagnosticItem(
                    name: "Installed runtime",
                    passed: false,
                    detail: "Runtime produced no diagnostic result"
                )
            }
        } catch {
            try? fileManager.removeItem(at: root)
            return CoreDiagnosticItem(
                name: "Installed runtime",
                passed: false,
                detail: error.localizedDescription
            )
        }
    }

}
