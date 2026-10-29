import Foundation

struct RepositoryRefreshResult {
    let catalog: RepositoryCatalog
    let plans: [RepositorySourcePlan]
}

enum SourceLifecycleError: Error, LocalizedError {
    case sourceNotInstalled
    case persistenceFailed(String)
    case rollbackFailed(String)

    var errorDescription: String? {
        switch self {
        case .sourceNotInstalled:
            return "Source is not installed."
        case .persistenceFailed(let message):
            return "Could not persist source state: \(message)"
        case .rollbackFailed(let message):
            return "Could not restore the previous source state: \(message)"
        }
    }
}

final class SourceLifecycleManager {
    static let demoRepositoryURL = "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/repository.json"

    private let database: SQLiteDatabase
    private let sourceRepository: SourceRepository
    private let repositoryRepository: RepositoryRepository
    private let installer: SourceScriptInstaller
    private let appVersion: String

    init(
        database: SQLiteDatabase,
        installer: SourceScriptInstaller,
        appVersion: String
    ) {
        self.database = database
        self.sourceRepository = SourceRepository(database: database)
        self.repositoryRepository = RepositoryRepository(database: database)
        self.installer = installer
        self.appVersion = appVersion
    }

    static func defaultManager() throws -> SourceLifecycleManager {
        let database = try SQLiteDatabase.defaultDatabase()
        try database.openAndMigrate()

        return SourceLifecycleManager(
            database: database,
            installer: try SourceScriptInstaller.defaultInstaller(),
            appVersion: Bundle.main.object(
                forInfoDictionaryKey: "CFBundleShortVersionString"
            ) as? String ?? "0.1.0"
        )
    }

    func repositories() throws -> [RepositoryRecord] {
        return try repositoryRepository.list()
    }

    func installedSources() throws -> [InstalledSourceRecord] {
        return try sourceRepository.list()
    }

    func refreshRepository(
        url: String,
        completion: @escaping (Result<RepositoryRefreshResult, Error>) -> Void
    ) {
        let client: RepositoryRemoteClient

        do {
            client = try RepositoryRemoteClient(repositoryURL: url)
        } catch {
            completion(.failure(error))
            return
        }

        _ = client.fetchCatalog { [
            sourceRepository = self.sourceRepository,
            repositoryRepository = self.repositoryRepository,
            appVersion = self.appVersion
        ] result in
            _ = client.repositoryURL

            switch result {
            case .success(let catalog):
                do {
                    let installed = try sourceRepository.list()
                    let installedMap = Dictionary(
                        uniqueKeysWithValues: installed.map {
                            ($0.manifest.id, $0.manifest)
                        }
                    )

                    let plans = try RepositoryCatalogPlanner.plan(
                        catalog: catalog,
                        installed: installedMap,
                        appVersion: appVersion
                    )

                    try repositoryRepository.save(
                        name: catalog.name,
                        url: url,
                        enabled: true,
                        lastRefresh: Date().timeIntervalSince1970
                    )

                    completion(.success(
                        RepositoryRefreshResult(
                            catalog: catalog,
                            plans: plans
                        )
                    ))
                } catch {
                    completion(.failure(error))
                }

            case .failure(let error):
                completion(.failure(error))
            }
        }
    }

    func installOrUpdate(
        manifest: SourceManifest,
        repositoryURL: String,
        completion: @escaping (Result<InstalledSourceRecord, Error>) -> Void
    ) {
        let client: RepositoryRemoteClient

        do {
            client = try RepositoryRemoteClient(repositoryURL: repositoryURL)
        } catch {
            completion(.failure(error))
            return
        }

        _ = client.fetchScript(for: manifest) { [weak self] result in
            _ = client.repositoryURL

            guard let self = self else { return }

            switch result {
            case .success(let payload):
                do {
                    let record = try self.installDownloaded(
                        manifest: manifest,
                        scriptData: payload.data
                    )
                    completion(.success(record))
                } catch {
                    completion(.failure(error))
                }

            case .failure(let error):
                completion(.failure(error))
            }
        }
    }

    @discardableResult
    func installDownloaded(
        manifest: SourceManifest,
        scriptData: Data
    ) throws -> InstalledSourceRecord {
        let previousRecord = try sourceRepository.fetch(sourceID: manifest.id)

        try installer.install(
            manifest: manifest,
            scriptData: scriptData
        )

        do {
            try sourceRepository.save(
                manifest: manifest,
                enabled: previousRecord?.enabled ?? true
            )
        } catch {
            if previousRecord != nil {
                do {
                    try installer.rollback(sourceID: manifest.id)
                } catch let rollbackError {
                    throw SourceLifecycleError.rollbackFailed(
                        "Database error: \(error.localizedDescription); rollback error: \(rollbackError.localizedDescription)"
                    )
                }
            } else {
                try? installer.remove(sourceID: manifest.id)
            }

            throw SourceLifecycleError.persistenceFailed(
                error.localizedDescription
            )
        }

        guard let stored = try sourceRepository.fetch(sourceID: manifest.id) else {
            throw SourceLifecycleError.persistenceFailed(
                "Installed record disappeared after save."
            )
        }

        return stored
    }

    func rollback(sourceID: String) throws -> InstalledSourceRecord {
        guard let current = try sourceRepository.fetch(sourceID: sourceID) else {
            throw SourceLifecycleError.sourceNotInstalled
        }

        guard let previous = try installer.previous(sourceID: sourceID) else {
            throw SourceScriptInstallerError.rollbackUnavailable
        }

        try installer.rollback(sourceID: sourceID)

        do {
            try sourceRepository.save(
                manifest: previous.manifest,
                enabled: current.enabled
            )
        } catch {
            try? installer.rollback(sourceID: sourceID)
            throw SourceLifecycleError.persistenceFailed(
                error.localizedDescription
            )
        }

        guard let stored = try sourceRepository.fetch(sourceID: sourceID) else {
            throw SourceLifecycleError.persistenceFailed(
                "Rolled-back record disappeared after save."
            )
        }

        return stored
    }

    func setSourceEnabled(_ enabled: Bool, sourceID: String) throws {
        try sourceRepository.setEnabled(enabled, sourceID: sourceID)
    }

    func removeSource(sourceID: String) throws {
        guard let current = try sourceRepository.fetch(sourceID: sourceID) else {
            try installer.remove(sourceID: sourceID)
            return
        }

        try sourceRepository.remove(sourceID: sourceID)

        do {
            try installer.remove(sourceID: sourceID)
        } catch {
            try? sourceRepository.save(
                manifest: current.manifest,
                enabled: current.enabled
            )
            throw error
        }
    }

    func removeRepository(url: String) throws {
        try repositoryRepository.remove(url: url)
    }
}
