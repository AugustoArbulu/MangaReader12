import Foundation

enum ChapterDownloadError: Error, LocalizedError {
    case applicationSupportUnavailable
    case emptyPages
    case httpStatus(Int)
    case missingCompletedFiles
    case alreadyScheduled
    case downloadInProgress

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
        case .alreadyScheduled:
            return "Este capítulo já está na fila de downloads."
        case .downloadInProgress:
            return "Pause o download antes de removê-lo."
        }
    }
}

// A job keeps the HTTP client alive while the queue is active. An interrupted
// page is cancelled at the URLSessionTask level and retried on resume;
// previously atomically written pages remain untouched.
private final class ChapterDownloadJob {
    let key: String
    let sourceID: String
    let manga: Manga
    let chapter: Chapter
    let pages: [Page]
    let directory: URL
    let client: HTTPClient
    let progress: (Double) -> Void
    let completion: (Result<[Page], Error>) -> Void
    var nextIndex = 0
    var state = "queued"
    var task: URLSessionDataTask?

    init(
        key: String,
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        pages: [Page],
        directory: URL,
        manifest: SourceManifest,
        progress: @escaping (Double) -> Void,
        completion: @escaping (Result<[Page], Error>) -> Void
    ) {
        self.key = key
        self.sourceID = sourceID
        self.manga = manga
        self.chapter = chapter
        self.pages = pages
        self.directory = directory
        self.client = HTTPClient(policy: HTTPPolicy(
            allowedDomains: manifest.domains,
            timeout: 30,
            maxRedirects: 5,
            maxResponseBytes: 20 * 1024 * 1024
        ))
        self.progress = progress
        self.completion = completion
    }

    var fraction: Double {
        return Double(nextIndex) / Double(max(1, pages.count))
    }
}

final class ChapterDownloadManager {
    private static let sharedLock = NSLock()
    private static var sharedManager: ChapterDownloadManager?

    private let fileManager: FileManager
    private let repository: DownloadRepository
    private let worker = DispatchQueue(label: "com.mangareader12.downloads.queue")
    private var jobs: [String: ChapterDownloadJob] = [:]
    private var pending: [String] = []
    private var runningKey: String?

    init(
        fileManager: FileManager = .default,
        repository: DownloadRepository
    ) {
        self.fileManager = fileManager
        self.repository = repository
    }

    static func defaultManager() throws -> ChapterDownloadManager {
        sharedLock.lock()
        defer { sharedLock.unlock() }

        if let instance = sharedManager { return instance }
        let repository = try DownloadRepository.defaultRepository()
        // A prior process cannot own a live URLSession task anymore. Mark
        // interrupted queued/running jobs as retryable, never as "Offline".
        try repository.markInterruptedDownloads()
        let instance = ChapterDownloadManager(repository: repository)
        sharedManager = instance
        return instance
    }

    private func jobKey(sourceID: String, mangaID: String, chapterID: String) -> String {
        return [sourceID, mangaID, chapterID].joined(separator: "\u{1F}")
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
            DispatchQueue.main.async {
                completion(.failure(ChapterDownloadError.emptyPages))
            }
            return
        }

        worker.async {
            let key = self.jobKey(
                sourceID: sourceID, mangaID: manga.id, chapterID: chapter.id
            )
            guard self.jobs[key] == nil else {
                DispatchQueue.main.async {
                    completion(.failure(ChapterDownloadError.alreadyScheduled))
                }
                return
            }

            do {
                let directory = try self.chapterDirectory(
                    sourceID: sourceID, mangaID: manga.id, chapterID: chapter.id
                )
                // Retrying a failed download starts from zero; normal
                // in-session pause/resume preserves the original directory.
                if self.fileManager.fileExists(atPath: directory.path) {
                    try self.fileManager.removeItem(at: directory)
                }
                try self.fileManager.createDirectory(
                    at: directory, withIntermediateDirectories: true, attributes: nil
                )
                try self.repository.setState(
                    sourceID: sourceID, manga: manga, chapter: chapter,
                    state: "queued", progress: 0, localPath: directory.path
                )
                let job = ChapterDownloadJob(
                    key: key, sourceID: sourceID, manga: manga,
                    chapter: chapter, pages: pages, directory: directory,
                    manifest: manifest, progress: progress, completion: completion
                )
                self.jobs[key] = job
                self.pending.append(key)
                DispatchQueue.main.async { progress(0) }
                self.startNextIfNeeded()
            } catch {
                DispatchQueue.main.async { completion(.failure(error)) }
            }
        }
    }

    // Returns false for a job left over from another app process; the UI can
    // re-resolve pages from its installed source to restart it.
    func pause(
        sourceID: String, mangaID: String, chapterID: String
    ) throws -> Bool {
        return try worker.sync {
            let key = jobKey(sourceID: sourceID, mangaID: mangaID, chapterID: chapterID)
            guard let job = jobs[key],
                  job.state == "queued" || job.state == "downloading" else {
                return false
            }

            try repository.setState(
                sourceID: job.sourceID, manga: job.manga, chapter: job.chapter,
                state: "paused", progress: job.fraction, localPath: job.directory.path
            )
            job.state = "paused"
            pending.removeAll { $0 == key }
            if runningKey == key {
                runningKey = nil
                job.task?.cancel()
                job.task = nil
            }
            startNextIfNeeded()
            return true
        }
    }

    func resume(
        sourceID: String, mangaID: String, chapterID: String
    ) throws -> Bool {
        return try worker.sync {
            let key = jobKey(sourceID: sourceID, mangaID: mangaID, chapterID: chapterID)
            guard let job = jobs[key], job.state == "paused" else {
                return false
            }
            try repository.setState(
                sourceID: job.sourceID, manga: job.manga, chapter: job.chapter,
                state: "queued", progress: job.fraction, localPath: job.directory.path
            )
            job.state = "queued"
            pending.append(key)
            startNextIfNeeded()
            return true
        }
    }

    func prioritize(
        sourceID: String, mangaID: String, chapterID: String
    ) -> Bool {
        return worker.sync {
            let key = jobKey(sourceID: sourceID, mangaID: mangaID, chapterID: chapterID)
            guard let job = jobs[key], job.state == "queued",
                  let position = pending.firstIndex(of: key),
                  position > 0 else { return false }
            pending.remove(at: position)
            pending.insert(key, at: 0)
            return true
        }
    }

    private func startNextIfNeeded() {
        guard runningKey == nil else { return }
        while !pending.isEmpty {
            let key = pending.removeFirst()
            guard let job = jobs[key], job.state == "queued" else { continue }
            do {
                try repository.setState(
                    sourceID: job.sourceID, manga: job.manga, chapter: job.chapter,
                    state: "downloading", progress: job.fraction,
                    localPath: job.directory.path
                )
                job.state = "downloading"
                runningKey = key
                downloadNextPage(of: job)
                return
            } catch {
                fail(job, error: error)
            }
        }
    }

    private func downloadNextPage(of job: ChapterDownloadJob) {
        guard runningKey == job.key, job.state == "downloading" else { return }
        if job.nextIndex >= job.pages.count {
            do {
                try repository.setState(
                    sourceID: job.sourceID, manga: job.manga, chapter: job.chapter,
                    state: "completed", progress: 1,
                    localPath: job.directory.path
                )
                let local = try localPages(
                    sourceID: job.sourceID,
                    mangaID: job.manga.id,
                    chapterID: job.chapter.id
                ) ?? []
                finish(job, result: .success(local))
            } catch {
                fail(job, error: error)
            }
            return
        }

        let index = job.nextIndex
        let page = job.pages[index]
        job.task = job.client.send(
            HTTPRequest(method: "GET", url: page.imageUrl, headers: page.headers)
        ) { [weak self, weak job] result in
            guard let self = self, let job = job else { return }
            self.worker.async {
                // A cancelled request from an earlier pause is never allowed
                // to mutate the file system or transition the chapter to failed.
                guard self.jobs[job.key] === job,
                      self.runningKey == job.key,
                      job.state == "downloading",
                      job.nextIndex == index else { return }
                job.task = nil

                switch result {
                case .failure(let error):
                    self.fail(job, error: error)
                case .success(let response):
                    guard (200..<300).contains(response.statusCode) else {
                        self.fail(job, error: ChapterDownloadError.httpStatus(response.statusCode))
                        return
                    }

                    do {
                        let filename = String(format: "page-%05d.bin", index)
                        let destination = job.directory.appendingPathComponent(filename)
                        try response.data.write(to: destination, options: .atomic)
                        job.nextIndex = index + 1
                        try self.repository.setState(
                            sourceID: job.sourceID, manga: job.manga, chapter: job.chapter,
                            state: "downloading", progress: job.fraction,
                            localPath: job.directory.path
                        )
                        let fraction = job.fraction
                        DispatchQueue.main.async { job.progress(fraction) }
                        self.downloadNextPage(of: job)
                    } catch {
                        self.fail(job, error: error)
                    }
                }
            }
        }
    }

    private func fail(_ job: ChapterDownloadJob, error: Error) {
        try? repository.setState(
            sourceID: job.sourceID, manga: job.manga, chapter: job.chapter,
            state: "failed", progress: job.fraction,
            localPath: job.directory.path
        )
        finish(job, result: .failure(error))
    }

    private func finish(
        _ job: ChapterDownloadJob,
        result: Result<[Page], Error>
    ) {
        job.task = nil
        jobs.removeValue(forKey: job.key)
        pending.removeAll { $0 == job.key }
        if runningKey == job.key { runningKey = nil }
        DispatchQueue.main.async {
            if case .success = result { job.progress(1) }
            job.completion(result)
        }
        startNextIfNeeded()
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
        guard fileManager.fileExists(atPath: directory.path) else { return nil }

        let files = try fileManager.contentsOfDirectory(
            at: directory, includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        )
        .filter { $0.lastPathComponent.hasPrefix("page-") && $0.pathExtension == "bin" }
        .sorted { $0.lastPathComponent < $1.lastPathComponent }

        guard !files.isEmpty else {
            throw ChapterDownloadError.missingCompletedFiles
        }

        return files.enumerated().map { index, url in
            Page(index: index, imageUrl: url.absoluteString, headers: [:])
        }
    }

    func remove(
        sourceID: String,
        mangaID: String,
        chapterID: String
    ) throws {
        try worker.sync {
            let key = jobKey(sourceID: sourceID, mangaID: mangaID, chapterID: chapterID)
            if runningKey == key {
                throw ChapterDownloadError.downloadInProgress
            }
            let removedJob = jobs.removeValue(forKey: key)
            pending.removeAll { $0 == key }
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
            // If a queued/paused job is explicitly removed, release its
            // retained caller closure instead of leaving it waiting forever.
            if let job = removedJob {
                DispatchQueue.main.async {
                    job.completion(.failure(HTTPClientError.cancelled))
                }
            }
            startNextIfNeeded()
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
