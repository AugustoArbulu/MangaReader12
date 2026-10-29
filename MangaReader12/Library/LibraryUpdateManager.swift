import Foundation

struct LibraryUpdateEvent: Codable, Equatable {
    let sourceID: String
    let sourceMangaID: String
    let mangaTitle: String
    let mangaCover: String?
    let mangaURL: String?
    let sourceChapterID: String
    let chapterName: String
    let discoveredAt: TimeInterval
}

struct LibraryUpdateResult {
    let checkedManga: Int
    let newChapters: [LibraryUpdateEvent]
    let failures: [String]
}

final class UpdateFeedStore {
    private let defaults: UserDefaults
    private let key = "updates.feed.v1"
    private let maxEvents = 200

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func events() -> [LibraryUpdateEvent] {
        guard let data = defaults.data(forKey: key),
              let decoded = try? JSONDecoder().decode(
                [LibraryUpdateEvent].self,
                from: data
              ) else {
            return []
        }

        return decoded.sorted { $0.discoveredAt > $1.discoveredAt }
    }

    func append(_ events: [LibraryUpdateEvent]) {
        guard !events.isEmpty else { return }

        var combined = self.events()
        let existingKeys = Set(combined.map {
            "\($0.sourceID)|\($0.sourceMangaID)|\($0.sourceChapterID)"
        })

        var mutableKeys = existingKeys

        for event in events {
            let key = "\(event.sourceID)|\(event.sourceMangaID)|\(event.sourceChapterID)"
            guard !mutableKeys.contains(key) else { continue }
            mutableKeys.insert(key)
            combined.append(event)
        }

        combined.sort { $0.discoveredAt > $1.discoveredAt }

        if combined.count > maxEvents {
            combined = Array(combined.prefix(maxEvents))
        }

        if let data = try? JSONEncoder().encode(combined) {
            defaults.set(data, forKey: key)
        }
    }

    func clear() {
        defaults.removeObject(forKey: key)
    }
}

final class LibraryUpdateManager {
    private let libraryRepository: LibraryRepository
    private let lifecycleManager: SourceLifecycleManager
    private let runtimeLoader: InstalledSourceRuntimeLoader
    private let feedStore: UpdateFeedStore

    init(
        libraryRepository: LibraryRepository,
        lifecycleManager: SourceLifecycleManager,
        runtimeLoader: InstalledSourceRuntimeLoader,
        feedStore: UpdateFeedStore = UpdateFeedStore()
    ) {
        self.libraryRepository = libraryRepository
        self.lifecycleManager = lifecycleManager
        self.runtimeLoader = runtimeLoader
        self.feedStore = feedStore
    }

    static func defaultManager() throws -> LibraryUpdateManager {
        return LibraryUpdateManager(
            libraryRepository: try LibraryRepository.defaultRepository(),
            lifecycleManager: try SourceLifecycleManager.defaultManager(),
            runtimeLoader: try InstalledSourceRuntimeLoader.defaultLoader()
        )
    }

    func checkAll(
        progress: @escaping (_ completed: Int, _ total: Int) -> Void,
        completion: @escaping (Result<LibraryUpdateResult, Error>) -> Void
    ) {
        let records: [LibraryMangaRecord]
        let installedSources: [InstalledSourceRecord]

        do {
            records = try libraryRepository.list()
            installedSources = try lifecycleManager.installedSources()
        } catch {
            completion(.failure(error))
            return
        }

        guard !records.isEmpty else {
            completion(.success(
                LibraryUpdateResult(
                    checkedManga: 0,
                    newChapters: [],
                    failures: []
                )
            ))
            return
        }

        let sourceMap = Dictionary(
            uniqueKeysWithValues: installedSources.map {
                ($0.manifest.id, $0)
            }
        )

        var events: [LibraryUpdateEvent] = []
        var failures: [String] = []

        func check(index: Int) {
            if index >= records.count {
                self.feedStore.append(events)
                completion(.success(
                    LibraryUpdateResult(
                        checkedManga: records.count,
                        newChapters: events,
                        failures: failures
                    )
                ))
                return
            }

            let record = records[index]
            let next: () -> Void = {
                DispatchQueue.main.async {
                    progress(index + 1, records.count)
                }
                check(index: index + 1)
            }

            guard let source = sourceMap[record.sourceID] else {
                failures.append("\(record.title): source ausente")
                next()
                return
            }

            guard source.enabled else {
                failures.append("\(record.title): source desativada")
                next()
                return
            }

            let known: Set<String>

            do {
                known = try self.libraryRepository.knownChapterIDs(
                    sourceID: record.sourceID,
                    sourceMangaID: record.sourceMangaID
                )
            } catch {
                failures.append("\(record.title): \(error.localizedDescription)")
                next()
                return
            }

            self.runtimeLoader.load(sourceID: record.sourceID) { runtimeResult in
                switch runtimeResult {
                case .failure(let error):
                    failures.append("\(record.title): \(error.localizedDescription)")
                    next()

                case .success(let runtime):
                    runtime.callDecoded(
                        "chapters",
                        arguments: [record.sourceMangaID],
                        as: [Chapter].self
                    ) { chapterResult in
                        switch chapterResult {
                        case .failure(let error):
                            failures.append("\(record.title): \(error.localizedDescription)")

                        case .success(let chapters):
                            let manga = Manga(
                                id: record.sourceMangaID,
                                title: record.title,
                                altTitles: [],
                                cover: record.cover,
                                author: nil,
                                artist: nil,
                                description: record.description,
                                status: record.status,
                                genres: [],
                                url: record.url
                            )

                            do {
                                try self.libraryRepository.add(
                                    sourceID: record.sourceID,
                                    manga: manga,
                                    chapters: chapters
                                )

                                try self.libraryRepository.touchLastChecked(
                                    sourceID: record.sourceID,
                                    sourceMangaID: record.sourceMangaID
                                )

                                let timestamp = Date().timeIntervalSince1970

                                for chapter in chapters where !known.contains(chapter.id) {
                                    events.append(
                                        LibraryUpdateEvent(
                                            sourceID: record.sourceID,
                                            sourceMangaID: record.sourceMangaID,
                                            mangaTitle: record.title,
                                            mangaCover: record.cover,
                                            mangaURL: record.url,
                                            sourceChapterID: chapter.id,
                                            chapterName: chapter.name,
                                            discoveredAt: timestamp
                                        )
                                    )
                                }
                            } catch {
                                failures.append("\(record.title): \(error.localizedDescription)")
                            }
                        }

                        next()
                    }
                }
            }
        }

        check(index: 0)
    }
}
