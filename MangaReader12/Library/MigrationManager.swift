import Foundation

struct MigrationCandidate {
    let source: InstalledSourceRecord
    let summary: SourceMangaSummary
}

struct MigrationTransferReport {
    let targetTitle: String
    let matchedChapterStates: Int
    let categoriesTransferred: Int
}

enum MigrationError: Error, LocalizedError {
    case sourceNotAvailable
    case originalNotInLibrary
    case targetDetailsMissing
    case targetLibraryRecordMissing

    var errorDescription: String? {
        switch self {
        case .sourceNotAvailable:
            return "No enabled target source is available."
        case .originalNotInLibrary:
            return "Only Library entries can be migrated."
        case .targetDetailsMissing:
            return "The target source did not return valid manga details."
        case .targetLibraryRecordMissing:
            return "The migrated Library entry could not be found after saving."
        }
    }
}

final class MigrationManager {
    private let lifecycle: SourceLifecycleManager
    private let loader: InstalledSourceRuntimeLoader
    private let library: LibraryRepository
    private let categories: CategoryRepository
    private let reading: ReadingProgressRepository

    init(
        lifecycle: SourceLifecycleManager,
        loader: InstalledSourceRuntimeLoader,
        library: LibraryRepository,
        categories: CategoryRepository,
        reading: ReadingProgressRepository
    ) {
        self.lifecycle = lifecycle
        self.loader = loader
        self.library = library
        self.categories = categories
        self.reading = reading
    }

    static func defaultManager() throws -> MigrationManager {
        return MigrationManager(
            lifecycle: try SourceLifecycleManager.defaultManager(),
            loader: try InstalledSourceRuntimeLoader.defaultLoader(),
            library: try LibraryRepository.defaultRepository(),
            categories: try CategoryRepository.defaultRepository(),
            reading: try ReadingProgressRepository.defaultRepository()
        )
    }

    func search(
        title: String,
        excludingSourceID: String,
        progress: @escaping (_ completed: Int, _ total: Int) -> Void,
        completion: @escaping (Result<[MigrationCandidate], Error>) -> Void
    ) {
        let sources: [InstalledSourceRecord]

        do {
            sources = try lifecycle.installedSources().filter {
                $0.enabled && $0.manifest.id != excludingSourceID
            }
        } catch {
            completion(.failure(error))
            return
        }

        guard !sources.isEmpty else {
            completion(.failure(MigrationError.sourceNotAvailable))
            return
        }

        var candidates: [MigrationCandidate] = []

        func searchSource(index: Int) {
            if index >= sources.count {
                completion(.success(candidates))
                return
            }

            let source = sources[index]

            loader.load(sourceID: source.manifest.id) { runtimeResult in
                switch runtimeResult {
                case .failure:
                    DispatchQueue.main.async {
                        progress(index + 1, sources.count)
                    }
                    searchSource(index: index + 1)

                case .success(let runtime):
                    runtime.callDecoded(
                        "search",
                        arguments: [title, 1, [] as [Any]],
                        as: SourcePagedMangaResult.self
                    ) { searchResult in
                        if case .success(let page) = searchResult {
                            for summary in page.items.prefix(6) {
                                candidates.append(
                                    MigrationCandidate(
                                        source: source,
                                        summary: summary
                                    )
                                )
                            }
                        }

                        DispatchQueue.main.async {
                            progress(index + 1, sources.count)
                        }
                        searchSource(index: index + 1)
                    }
                }
            }
        }

        searchSource(index: 0)
    }

    func migrate(
        originalSourceID: String,
        originalManga: Manga,
        originalChapters: [Chapter],
        candidate: MigrationCandidate,
        completion: @escaping (Result<MigrationTransferReport, Error>) -> Void
    ) {
        let originalRecord: LibraryMangaRecord

        do {
            guard let record = try library.find(
                sourceID: originalSourceID,
                sourceMangaID: originalManga.id
            ) else {
                completion(.failure(MigrationError.originalNotInLibrary))
                return
            }
            originalRecord = record
        } catch {
            completion(.failure(error))
            return
        }

        loader.load(sourceID: candidate.source.manifest.id) { [weak self] runtimeResult in
            guard let self = self else { return }

            switch runtimeResult {
            case .failure(let error):
                completion(.failure(error))

            case .success(let runtime):
                runtime.callDecoded(
                    "details",
                    arguments: [candidate.summary.id],
                    as: Manga.self
                ) { detailsResult in
                    switch detailsResult {
                    case .failure(let error):
                        completion(.failure(error))

                    case .success(let targetManga):
                        runtime.callDecoded(
                            "chapters",
                            arguments: [candidate.summary.id],
                            as: [Chapter].self
                        ) { chapterResult in
                            switch chapterResult {
                            case .failure(let error):
                                completion(.failure(error))

                            case .success(let targetChapters):
                                do {
                                    let report = try self.transfer(
                                        originalRecord: originalRecord,
                                        originalSourceID: originalSourceID,
                                        originalManga: originalManga,
                                        originalChapters: originalChapters,
                                        targetSourceID: candidate.source.manifest.id,
                                        targetManga: targetManga,
                                        targetChapters: targetChapters
                                    )
                                    completion(.success(report))
                                } catch {
                                    completion(.failure(error))
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    private func transfer(
        originalRecord: LibraryMangaRecord,
        originalSourceID: String,
        originalManga: Manga,
        originalChapters: [Chapter],
        targetSourceID: String,
        targetManga: Manga,
        targetChapters: [Chapter]
    ) throws -> MigrationTransferReport {
        let oldCategoryIDs = try categories.categoryIDs(
            mangaID: originalRecord.internalID
        )
        let oldStates = try reading.chapterStates(
            sourceID: originalSourceID,
            sourceMangaID: originalManga.id
        )
        let oldHistory = try reading.history().first {
            $0.sourceID == originalSourceID &&
            $0.sourceMangaID == originalManga.id
        }

        try library.add(
            sourceID: targetSourceID,
            manga: targetManga,
            chapters: targetChapters
        )

        guard let targetRecord = try library.find(
            sourceID: targetSourceID,
            sourceMangaID: targetManga.id
        ) else {
            throw MigrationError.targetLibraryRecordMissing
        }

        try categories.setCategories(
            mangaID: targetRecord.internalID,
            categoryIDs: oldCategoryIDs
        )

        var oldByKey: [String: Chapter] = [:]
        for chapter in originalChapters {
            let key = migrationKey(chapter)
            if oldByKey[key] == nil {
                oldByKey[key] = chapter
            }
        }

        var matched = 0
        var migratedHistoryChapter: Chapter?

        for targetChapter in targetChapters {
            guard let oldChapter = oldByKey[migrationKey(targetChapter)],
                  let state = oldStates[oldChapter.id] else {
                continue
            }

            try reading.applyMigrationState(
                sourceID: targetSourceID,
                manga: targetManga,
                chapter: targetChapter,
                state: state
            )
            matched += 1

            if oldHistory?.sourceChapterID == oldChapter.id {
                migratedHistoryChapter = targetChapter
            }
        }

        if let history = oldHistory,
           let historyChapter = migratedHistoryChapter {
            try reading.recordHistory(
                sourceID: targetSourceID,
                manga: targetManga,
                chapter: historyChapter,
                date: history.lastReadAt
            )
        }

        try reading.removeHistory(
            sourceID: originalSourceID,
            sourceMangaID: originalManga.id
        )

        try library.remove(
            sourceID: originalSourceID,
            sourceMangaID: originalManga.id
        )

        return MigrationTransferReport(
            targetTitle: targetManga.title,
            matchedChapterStates: matched,
            categoriesTransferred: oldCategoryIDs.count
        )
    }

    private func migrationKey(_ chapter: Chapter) -> String {
        if let number = chapter.number {
            return "n:\(String(format: "%.4f", number))"
        }

        let normalized = chapter.name
            .lowercased()
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return "t:\(normalized)"
    }
}
