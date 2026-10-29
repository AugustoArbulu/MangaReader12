import Foundation

enum ChapterDownloadError: Error, LocalizedError {
    case applicationSupportUnavailable
    case emptyPages
    case httpStatus(Int)
    case missingCompletedFiles

    var errorDescription: String? {
        switch self {
        case .applicationSupportUnavailable:
            return "Application Support directory is unavailable."
        case .emptyPages:
            return "This chapter returned no pages to download."
        case .httpStatus(let status):
            return "Image server returned HTTP \(status) during download."
        case .missingCompletedFiles:
            return "The downloaded chapter files are missing."
        }
    }
}

final class ChapterDownloadManager {
    private let fileManager: FileManager
    private let repository: DownloadRepository

    init(
        fileManager: FileManager = .default,
        repository: DownloadRepository
    ) {
        self.fileManager = fileManager
        self.repository = repository
    }

    static func defaultManager() throws -> ChapterDownloadManager {
        return ChapterDownloadManager(
            repository: try DownloadRepository.defaultRepository()
        )
    }

    func download(
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        pages: [Page],
        manifest: SourceManifest,
        progress: @escaping (Double) -> Void,
        completion: @escaping (Result<[Page], Error>) -> Void
    ) {
        guard !pages.isEmpty else {
            completion(.failure(ChapterDownloadError.emptyPages))
            return
        }

        let directory: URL

        do {
            directory = try chapterDirectory(
                sourceID: sourceID,
                mangaID: manga.id,
                chapterID: chapter.id
            )

            if fileManager.fileExists(atPath: directory.path) {
                try fileManager.removeItem(at: directory)
            }

            try fileManager.createDirectory(
                at: directory,
                withIntermediateDirectories: true,
                attributes: nil
            )

            try repository.setState(
                sourceID: sourceID,
                manga: manga,
                chapter: chapter,
                state: "downloading",
                progress: 0,
                localPath: directory.path
            )
        } catch {
            completion(.failure(error))
            return
        }

        let client = HTTPClient(
            policy: HTTPPolicy(
                allowedDomains: manifest.domains,
                timeout: 30,
                maxRedirects: 5,
                maxResponseBytes: 20 * 1024 * 1024
            )
        )

        downloadPage(
            index: 0,
            sourceID: sourceID,
            manga: manga,
            chapter: chapter,
            pages: pages,
            directory: directory,
            client: client,
            progress: progress,
            completion: completion
        )
    }

    func localPages(
        sourceID: String,
        mangaID: String,
        chapterID: String
    ) throws -> [Page]? {
        guard let record = try repository.record(
            sourceID: sourceID,
            sourceMangaID: mangaID,
            sourceChapterID: chapterID
        ), record.state == "completed",
          let localPath = record.localPath else {
            return nil
        }

        let directory = URL(fileURLWithPath: localPath, isDirectory: true)
        guard fileManager.fileExists(atPath: directory.path) else {
            return nil
        }

        let files = try fileManager.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        )
        .filter { $0.lastPathComponent.hasPrefix("page-") && $0.pathExtension == "bin" }
        .sorted { $0.lastPathComponent < $1.lastPathComponent }

        guard !files.isEmpty else {
            throw ChapterDownloadError.missingCompletedFiles
        }

        return files.enumerated().map { index, url in
            Page(
                index: index,
                imageUrl: url.absoluteString,
                headers: [:]
            )
        }
    }

    func remove(
        sourceID: String,
        mangaID: String,
        chapterID: String
    ) throws {
        if let record = try repository.record(
            sourceID: sourceID,
            sourceMangaID: mangaID,
            sourceChapterID: chapterID
        ), let localPath = record.localPath,
           fileManager.fileExists(atPath: localPath) {
            try fileManager.removeItem(atPath: localPath)
        }

        try repository.remove(
            sourceID: sourceID,
            sourceMangaID: mangaID,
            sourceChapterID: chapterID
        )
    }

    private func downloadPage(
        index: Int,
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        pages: [Page],
        directory: URL,
        client: HTTPClient,
        progress: @escaping (Double) -> Void,
        completion: @escaping (Result<[Page], Error>) -> Void
    ) {
        if index >= pages.count {
            do {
                try repository.setState(
                    sourceID: sourceID,
                    manga: manga,
                    chapter: chapter,
                    state: "completed",
                    progress: 1,
                    localPath: directory.path
                )

                let local = try localPages(
                    sourceID: sourceID,
                    mangaID: manga.id,
                    chapterID: chapter.id
                ) ?? []

                progress(1)
                completion(.success(local))
            } catch {
                completion(.failure(error))
            }
            return
        }

        let page = pages[index]

        client.send(
            HTTPRequest(
                method: "GET",
                url: page.imageUrl,
                headers: page.headers
            )
        ) { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let response):
                guard (200..<300).contains(response.statusCode) else {
                    self.fail(
                        error: ChapterDownloadError.httpStatus(response.statusCode),
                        sourceID: sourceID,
                        manga: manga,
                        chapter: chapter,
                        directory: directory,
                        progress: Double(index) / Double(pages.count),
                        completion: completion
                    )
                    return
                }

                do {
                    let filename = String(format: "page-%05d.bin", index)
                    let destination = directory.appendingPathComponent(filename)
                    try response.data.write(to: destination, options: .atomic)

                    let completed = Double(index + 1) / Double(pages.count)
                    try self.repository.setState(
                        sourceID: sourceID,
                        manga: manga,
                        chapter: chapter,
                        state: "downloading",
                        progress: completed,
                        localPath: directory.path
                    )

                    DispatchQueue.main.async {
                        progress(completed)
                    }

                    self.downloadPage(
                        index: index + 1,
                        sourceID: sourceID,
                        manga: manga,
                        chapter: chapter,
                        pages: pages,
                        directory: directory,
                        client: client,
                        progress: progress,
                        completion: completion
                    )
                } catch {
                    self.fail(
                        error: error,
                        sourceID: sourceID,
                        manga: manga,
                        chapter: chapter,
                        directory: directory,
                        progress: Double(index) / Double(pages.count),
                        completion: completion
                    )
                }

            case .failure(let error):
                self.fail(
                    error: error,
                    sourceID: sourceID,
                    manga: manga,
                    chapter: chapter,
                    directory: directory,
                    progress: Double(index) / Double(pages.count),
                    completion: completion
                )
            }
        }
    }

    private func fail(
        error: Error,
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        directory: URL,
        progress: Double,
        completion: @escaping (Result<[Page], Error>) -> Void
    ) {
        try? repository.setState(
            sourceID: sourceID,
            manga: manga,
            chapter: chapter,
            state: "failed",
            progress: progress,
            localPath: directory.path
        )

        DispatchQueue.main.async {
            completion(.failure(error))
        }
    }

    private func chapterDirectory(
        sourceID: String,
        mangaID: String,
        chapterID: String
    ) throws -> URL {
        guard let base = fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first else {
            throw ChapterDownloadError.applicationSupportUnavailable
        }

        return base
            .appendingPathComponent("MangaReader12", isDirectory: true)
            .appendingPathComponent("Downloads", isDirectory: true)
            .appendingPathComponent(safeComponent(sourceID), isDirectory: true)
            .appendingPathComponent(safeComponent(mangaID), isDirectory: true)
            .appendingPathComponent(safeComponent(chapterID), isDirectory: true)
    }

    private func safeComponent(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(
            CharacterSet(charactersIn: "._-")
        )

        let scalars = value.unicodeScalars.map { scalar -> String in
            return allowed.contains(scalar) ? String(scalar) : "_"
        }

        let result = scalars.joined()
        return result.isEmpty ? "item" : result
    }
}
