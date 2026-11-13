import Foundation
import ImageIO
import Darwin

// BEGIN OFFLINE_PATH_RELOCATION
// Absolute paths persisted in SQLite can outlive their iOS app container UUID.
// Derive the only trusted path from the current Application Support directory.
enum OfflineDownloadPath {
    static func safeComponent(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(
            CharacterSet(charactersIn: "._-")
        )
        let result = value.unicodeScalars.map { scalar -> String in
            return allowed.contains(scalar) ? String(scalar) : "_"
        }.joined()
        return result.isEmpty || result == "." || result == ".." ? "item" : result
    }

    static func chapterDirectory(
        applicationSupport: URL,
        sourceID: String,
        mangaID: String,
        chapterID: String
    ) -> URL {
        return applicationSupport
            .appendingPathComponent("MangaReader12", isDirectory: true)
            .appendingPathComponent("Downloads", isDirectory: true)
            .appendingPathComponent(safeComponent(sourceID), isDirectory: true)
            .appendingPathComponent(safeComponent(mangaID), isDirectory: true)
            .appendingPathComponent(safeComponent(chapterID), isDirectory: true)
    }
}
// END OFFLINE_PATH_RELOCATION

// BEGIN BUILD70_EL_SAFE_PARTIAL_RETRY
// Normal chapter/batch downloads must preserve any preexisting local data.
// The Downloads retry flow supplies the explicit user-confirmed override.
enum ChapterDownloadExistingDataPolicy: Equatable {
    case preserve
    case replaceAfterExplicitUserConfirmation
}

/// Admission audit only. Does not decode or modify stored page data.
/// Unexpected leaves, symlinks, special files and completed receipts
/// must never be erased by a retry, even after user confirmation.
enum WebReaderPartialRetryFolderAudit {
    private static func sameIdentity(_ a: stat, _ b: stat) -> Bool {
        return a.st_dev == b.st_dev && a.st_ino == b.st_ino &&
            a.st_mode == b.st_mode && a.st_nlink == b.st_nlink &&
            a.st_size == b.st_size &&
            a.st_mtimespec.tv_sec == b.st_mtimespec.tv_sec &&
            a.st_mtimespec.tv_nsec == b.st_mtimespec.tv_nsec &&
            a.st_ctimespec.tv_sec == b.st_ctimespec.tv_sec &&
            a.st_ctimespec.tv_nsec == b.st_ctimespec.tv_nsec
    }

    static func canReplace(
        directory: URL,
        plannedPages: Int,
        fileManager: FileManager = .default
    ) -> Bool {
        guard plannedPages > 0, plannedPages <= 5_000 else { return false }
        var before = stat()
        guard Darwin.lstat(directory.path, &before) == 0,
              (before.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR) else {
            return false
        }
        let fd = Darwin.open(
            directory.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC
        )
        guard fd >= 0 else { return false }
        defer { _ = Darwin.close(fd) }

        var opened = stat()
        guard Darwin.fstat(fd, &opened) == 0,
              sameIdentity(before, opened) else { return false }
        guard let names = try? fileManager.contentsOfDirectory(
            atPath: directory.path
        ), names.count <= plannedPages + 1 else { return false }

        for name in names {
            let isPlan = name == "_download-plan.json"
            if !isPlan {
                guard name.range(
                    of: "^page-[0-9]{5}\\.bin$",
                    options: .regularExpression
                ) != nil,
                let index = Int(name.dropFirst(5).prefix(5)),
                index < plannedPages else { return false }
            }
            var item = stat()
            guard Darwin.fstatat(
                fd, name, &item, AT_SYMLINK_NOFOLLOW
            ) == 0,
            (item.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
            item.st_nlink == 1, item.st_size > 0,
            item.st_size <= (isPlan ? 16 * 1024 * 1024 : 20 * 1024 * 1024)
            else { return false }
        }

        var afterFD = stat()
        var afterPath = stat()
        guard Darwin.fstat(fd, &afterFD) == 0,
              Darwin.lstat(directory.path, &afterPath) == 0,
              sameIdentity(before, afterFD),
              sameIdentity(before, afterPath) else { return false }
        return true
    }
}
// END BUILD70_EL_SAFE_PARTIAL_RETRY

enum ChapterDownloadError: Error, LocalizedError {
    case applicationSupportUnavailable
    case emptyPages
    case tooManyPages
    case httpStatus(Int)
    case missingCompletedFiles
    case invalidImagePayload
    case oversizedImagePayload
    case alreadyScheduled
    case alreadyCompleted
    case existingLocalDataRequiresReview
    case unsafeExistingLocalData
    case downloadInProgress

    var errorDescription: String? {
        switch self {
        case .applicationSupportUnavailable:
            return "Application Support directory is unavailable."
        case .emptyPages:
            return "This chapter returned no pages to download."
        case .tooManyPages:
            return "O capítulo excede o limite de 5.000 páginas por download recuperável. Nenhum arquivo foi modificado."
        case .httpStatus(let status):
            return "Image server returned HTTP \(status) during download."
        case .missingCompletedFiles:
            return "O capítulo offline está incompleto: uma ou mais páginas estão ausentes, vazias ou inválidas. Nenhum arquivo foi apagado."
        case .invalidImagePayload:
            return "O servidor retornou uma página inválida ou um documento HTML em vez de uma imagem. O capítulo não foi marcado como completo."
        case .oversizedImagePayload:
            return "A página excede o limite de 20 MiB por imagem offline. O capítulo não foi marcado como completo e os arquivos existentes foram preservados."
        case .alreadyScheduled:
            return "Este capítulo já está na fila de downloads."
        case .alreadyCompleted:
            return "O capítulo já está marcado como baixado. Para refazer, remova manualmente o download na área Downloads. Nenhum arquivo foi apagado."
        case .existingLocalDataRequiresReview:
            return "Já existem páginas ou metadados offline. Abra Downloads e confirme a reinicialização. Preserve uma cópia externa antes de substituir. Nenhum arquivo foi apagado."
        case .unsafeExistingLocalData:
            return "A pasta offline contém arquivos inesperados ou inseguros. Nenhum arquivo foi apagado. Preserve a pasta para revisão."
        case .downloadInProgress:
            return "Pause o download antes de removê-lo."
        }
    }
}

// BEGIN IMAGE_PAYLOAD_VALIDATOR
// Validates page bytes before committing them to offline storage. A challenge
// page may return HTTP 200 with HTML; never mark such files as downloaded.
// ImageIO creates an image *source* without decoding full pixel buffers.
enum ChapterDownloadImageValidator {
    static func canStore(data: Data, headers: [String: String]) -> Bool {
        guard !data.isEmpty else { return false }

        for (name, value) in headers {
            guard name.caseInsensitiveCompare("Content-Type") == .orderedSame else {
                continue
            }
            let contentType = value.split(separator: ";", maxSplits: 1)
                .first.map { String($0).trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }
                ?? ""
            if contentType.hasPrefix("text/") ||
                ["application/json", "application/javascript",
                 "application/xml", "application/xhtml+xml"].contains(contentType) {
                return false
            }
        }

        // WebP is not supported by ImageIO on iOS 12. A successful, bounded
        // libwebp decode verifies the complete payload, not merely its header,
        // before the bytes are atomically stored for offline reading.
        if WebPImageDecoder.isWebP(data) {
            return WebPImageDecoder.image(from: data) != nil
        }

        // ImageIO may identify a truncated file from its header alone.
        // PNG requires its final IEND chunk; JPEG needs its EOI marker
        // near the end (some valid JPEGs contain a short trailing payload).
        if data.starts(with: [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) {
            let iend: [UInt8] = [
                0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
                0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
            ]
            guard data.count >= 20 && data.suffix(12).elementsEqual(iend) else {
                return false
            }
        } else if data.starts(with: [0xFF, 0xD8, 0xFF]) {
            let tail = Array(data.suffix(64))
            guard tail.count >= 2,
                  (1..<tail.count).contains(where: {
                      tail[$0 - 1] == 0xFF && tail[$0] == 0xD9
                  }) else {
                return false
            }
        }

        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              CGImageSourceGetCount(source) > 0 else {
            return false
        }
        return CGImageSourceGetStatusAtIndex(source, 0) == .statusComplete
    }
}
// END IMAGE_PAYLOAD_VALIDATOR

// Private metadata saved next to each chapter's page files. The entire
// operation stays within the app's Application Support sandbox.
private struct DownloadRecoveryPlan: Codable {
    let schemaVersion: Int
    let sourceID: String
    let manga: Manga
    let chapter: Chapter
    let pages: [Page]
    let manifest: SourceManifest
    let queueOrder: Int
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
    let manifest: SourceManifest
    var queueOrder: Int
    let progress: (Double) -> Void
    let completion: (Result<[Page], Error>) -> Void
    var nextIndex = 0
    var state = "queued"
    var task: URLSessionDataTask?
    var requestSerial = 0

    init(
        key: String,
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        pages: [Page],
        directory: URL,
        manifest: SourceManifest,
        queueOrder: Int,
        progress: @escaping (Double) -> Void,
        completion: @escaping (Result<[Page], Error>) -> Void
    ) {
        self.key = key
        self.sourceID = sourceID
        self.manga = manga
        self.chapter = chapter
        self.pages = pages
        self.directory = directory
        self.manifest = manifest
        self.queueOrder = queueOrder
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
    // QA-only throttle for the bundled Demo sources. Disabled by default.
    // Never slows real sources or modifies their HTTP/network behavior.
    static let demoSlowModeKey = "diagnostics.slowDemoDownloads"
    static let demoSlowDelay: TimeInterval = 8

    private static let sharedLock = NSLock()
    private static var sharedManager: ChapterDownloadManager?

    private let fileManager: FileManager
    private let repository: DownloadRepository
    private let worker = DispatchQueue(label: "com.mangareader12.downloads.queue")
    private var jobs: [String: ChapterDownloadJob] = [:]
    private var pending: [String] = []
    private var runningKey: String?
    private var nextQueueOrder = 0

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
        let instance = ChapterDownloadManager(repository: repository)
        try instance.restorePreviousSession()
        sharedManager = instance
        return instance
    }

    private func planURL(for directory: URL) -> URL {
        return directory.appendingPathComponent("_download-plan.json")
    }

    private func savePlan(for job: ChapterDownloadJob) throws {
        guard job.pages.count > 0,
              job.pages.count <= WebReaderOfflineResumePrefix.maximumPlannedPages else {
            throw ChapterDownloadError.tooManyPages
        }
        let plan = DownloadRecoveryPlan(
            schemaVersion: 1, sourceID: job.sourceID,
            manga: job.manga, chapter: job.chapter, pages: job.pages,
            manifest: job.manifest, queueOrder: job.queueOrder
        )
        let data = try JSONEncoder().encode(plan)
        // Match the BQ reader's maximum before touching any existing plan.
        // The writer publishes a complete private 0600 temporary file via
        // atomic rename, including when Prioritize changes queue order.
        try WebReaderOfflineRecoveryPlanWriter.write(
            data: data, to: planURL(for: job.directory)
        )
    }

    private func completedPagePrefix(in directory: URL, count: Int) -> Int {
        // A resumable download may contain only an initial subset. Never
        // reuse a symlink, directory, zero-byte file or oversized file as an
        // already validated page after an interrupted transfer.
        return WebReaderOfflineResumePrefix.count(
            directory: directory, plannedPages: count, fileManager: fileManager
        )
    }

    private func restorePreviousSession() throws {
        let records = try repository.listDownloads()
        // No URLSessionDataTask survives a process restart. Rebuild only
        // validated plans, leaving missing/corrupted plans retryable.
        try repository.markInterruptedDownloads()
        var restoredQueue: [ChapterDownloadJob] = []
        for record in records where
            record.state == "queued" ||
            record.state == "downloading" ||
            record.state == "paused" {
            do {
                let expected = try chapterDirectory(
                    sourceID: record.sourceID,
                    mangaID: record.sourceMangaID,
                    chapterID: record.sourceChapterID
                )
                guard record.localPath == expected.path else { continue }
                // Recovery metadata is untrusted after an interrupted
                // transfer. Reject symlink/FIFO/oversized plans without
                // removing the offline page files already on disk.
                let data = try WebReaderOfflineRecoveryPlanReader.read(
                    from: planURL(for: expected)
                )
                let plan = try JSONDecoder().decode(DownloadRecoveryPlan.self, from: data)
                guard plan.schemaVersion == 1,
                      plan.sourceID == record.sourceID,
                      plan.manifest.id == record.sourceID,
                      plan.manga.id == record.sourceMangaID,
                      plan.chapter.id == record.sourceChapterID,
                      !plan.pages.isEmpty,
                      plan.pages.count <= 5000 else { continue }
                let key = jobKey(
                    sourceID: record.sourceID,
                    mangaID: record.sourceMangaID,
                    chapterID: record.sourceChapterID
                )
                guard jobs[key] == nil else { continue }
                let job = ChapterDownloadJob(
                    key: key, sourceID: plan.sourceID,
                    manga: plan.manga, chapter: plan.chapter,
                    pages: plan.pages, directory: expected,
                    manifest: plan.manifest, queueOrder: plan.queueOrder,
                    progress: { _ in }, completion: { _ in }
                )
                job.nextIndex = completedPagePrefix(
                    in: expected, count: plan.pages.count
                )
                job.state = record.state == "paused" ? "paused" : "queued"
                try repository.setState(
                    sourceID: job.sourceID, manga: job.manga,
                    chapter: job.chapter, state: job.state,
                    progress: job.fraction, localPath: job.directory.path
                )
                jobs[key] = job
                nextQueueOrder = max(nextQueueOrder, plan.queueOrder + 1)
                if job.state == "queued" { restoredQueue.append(job) }
            } catch {
                // Keep any already downloaded page files for inspection;
                // the database row can be retried via source resolution.
                continue
            }
        }
        restoredQueue.sort {
            if $0.queueOrder == $1.queueOrder {
                return $0.key < $1.key
            }
            return $0.queueOrder < $1.queueOrder
        }
        pending = restoredQueue.map { $0.key }
        startNextIfNeeded()
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
        existingDataPolicy: ChapterDownloadExistingDataPolicy = .preserve,
        progress: @escaping (Double) -> Void,
        completion: @escaping (Result<[Page], Error>) -> Void
    ) {
        guard !pages.isEmpty else {
            DispatchQueue.main.async {
                completion(.failure(ChapterDownloadError.emptyPages))
            }
            return
        }
        guard pages.count <= WebReaderOfflineResumePrefix.maximumPlannedPages else {
            DispatchQueue.main.async {
                completion(.failure(ChapterDownloadError.tooManyPages))
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
                // A second download tap must not silently erase a completed
                // chapter, including old Build68 pages without a receipt.
                // The operator can explicitly remove it from Downloads first.
                if let existing = try self.repository.record(
                    sourceID: sourceID,
                    sourceMangaID: manga.id,
                    sourceChapterID: chapter.id
                ), existing.state == "completed" {
                    throw ChapterDownloadError.alreadyCompleted
                }
                let directory = try self.chapterDirectory(
                    sourceID: sourceID, mangaID: manga.id, chapterID: chapter.id
                )
                // No implicit overwrite on chapter taps or batch queues.
                // A destructive user prompt in Downloads is required, and
                // unknown/unsafe contents block replacement even then.
                if self.fileManager.fileExists(atPath: directory.path) {
                    guard existingDataPolicy == .replaceAfterExplicitUserConfirmation,
                          let previous = try self.repository.record(
                              sourceID: sourceID,
                              sourceMangaID: manga.id,
                              sourceChapterID: chapter.id
                          ),
                          previous.state == "failed" || previous.state == "paused" else {
                        throw ChapterDownloadError.existingLocalDataRequiresReview
                    }
                    guard WebReaderPartialRetryFolderAudit.canReplace(
                        directory: directory, plannedPages: pages.count,
                        fileManager: self.fileManager
                    ) else {
                        throw ChapterDownloadError.unsafeExistingLocalData
                    }
                    try self.fileManager.removeItem(at: directory)
                }
                try self.fileManager.createDirectory(
                    at: directory, withIntermediateDirectories: true, attributes: nil
                )
                let job = ChapterDownloadJob(
                    key: key, sourceID: sourceID, manga: manga,
                    chapter: chapter, pages: pages, directory: directory,
                    manifest: manifest, queueOrder: self.nextQueueOrder,
                    progress: progress, completion: completion
                )
                try self.savePlan(for: job)
                try self.repository.setState(
                    sourceID: sourceID, manga: manga, chapter: chapter,
                    state: "queued", progress: 0, localPath: directory.path
                )
                self.nextQueueOrder += 1
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
                job.requestSerial += 1
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
            let previousOrder = job.queueOrder
            let firstOrder = pending.compactMap { jobs[$0]?.queueOrder }.min() ?? 0
            job.queueOrder = firstOrder - 1
            do {
                try savePlan(for: job)
            } catch {
                job.queueOrder = previousOrder
                return false
            }
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
                // A successful HTTP queue is not proof that all page files
                // still exist. Check the exact sequence before recording a
                // completed chapter in SQLite; preserve all files on failure.
                let committed = try WebReaderOfflinePageInventory.inspect(
                    directory: job.directory, fileManager: fileManager
                )
                guard committed.count == job.pages.count else {
                    throw ChapterDownloadError.missingCompletedFiles
                }
                // New Build69 downloads carry an optional count-only
                // receipt. Old Build68 chapters never require one.
                try WebReaderOfflineCompletionReceipt.write(
                    directory: job.directory, expectedPages: job.pages.count
                )
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
        job.requestSerial += 1
        let serial = job.requestSerial

        // Demo chapters can finish in 0.1s, making it impossible to test
        // Pause/Resume/Prioritize by hand. Only a consciously enabled test
        // switch inserts an asynchronous delay before each Demo page.
        // It never sleeps on the UI thread, alters real sources, or writes
        // fake downloaded pages.
        let isBundledDemo = job.sourceID == "fixture.localdemo" ||
            job.sourceID == "fixture.altdemo"
        if isBundledDemo &&
           UserDefaults.standard.bool(forKey: ChapterDownloadManager.demoSlowModeKey) {
            worker.asyncAfter(
                deadline: .now() + ChapterDownloadManager.demoSlowDelay
            ) { [weak self, weak job] in
                guard let self = self, let job = job else { return }
                self.performPageRequest(of: job, index: index, serial: serial)
            }
        } else {
            performPageRequest(of: job, index: index, serial: serial)
        }
    }

    private func performPageRequest(
        of job: ChapterDownloadJob, index: Int, serial: Int
    ) {
        // If pause/resume happened during the artificial delay, the old
        // scheduled request must never start or complete in the new session.
        guard jobs[job.key] === job,
              runningKey == job.key,
              job.state == "downloading",
              job.nextIndex == index,
              job.requestSerial == serial else { return }

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
                      job.nextIndex == index,
                      job.requestSerial == serial else { return }
                job.task = nil

                switch result {
                case .failure(let error):
                    self.fail(job, error: error)
                case .success(let response):
                    guard (200..<300).contains(response.statusCode) else {
                        self.fail(job, error: ChapterDownloadError.httpStatus(response.statusCode))
                        return
                    }

                    // The resume prefix accepts pages up to 20 MiB. Keep
                    // the same ceiling at download time, or a page saved
                    // successfully could become unrecoverable after restart.
                    guard !response.data.isEmpty,
                          Int64(response.data.count) <=
                            WebReaderOfflineResumePrefix.maximumPageBytes else {
                        self.fail(job, error: ChapterDownloadError.oversizedImagePayload)
                        return
                    }
                    guard ChapterDownloadImageValidator.canStore(
                        data: response.data, headers: response.headers
                    ) else {
                        self.fail(job, error: ChapterDownloadError.invalidImagePayload)
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
        // Retire stale URLs/headers from the resumable plan on completion
        // or failure. Never remove the actual offline page files here.
        try? fileManager.removeItem(at: planURL(for: job.directory))
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
        ), record.state == "completed" else { return nil }

        // Do not follow the obsolete stored absolute local_path from Build56.
        let directory = try chapterDirectory(
            sourceID: sourceID, mangaID: mangaID, chapterID: chapterID
        )
        // A completed record with a missing directory is not an uncached
        // chapter. Report missing local data instead of falling back to web.
        guard fileManager.fileExists(atPath: directory.path) else {
            throw ChapterDownloadError.missingCompletedFiles
        }

        // A completed SQLite row does not prove every local page survived.
        // Reject gaps, empty files and symbolic links instead of renumbering
        // a sparse list and accidentally showing an incomplete chapter.
        let files: [URL]
        do {
            files = try WebReaderOfflinePageInventory.inspect(
                directory: directory, fileManager: fileManager
            )
        } catch {
            throw ChapterDownloadError.missingCompletedFiles
        }

        // Verify the expected total page count when this is a newly
        // completed Build69 chapter. A legacy Build68 folder has no receipt
        // and is still readable. Failure never changes the local files.
        do {
            try WebReaderOfflineCompletionReceipt.verifyIfPresent(
                directory: directory, actualPages: files.count,
                fileManager: fileManager
            )
        } catch {
            throw ChapterDownloadError.missingCompletedFiles
        }

        // Repair only the DB location for real downloaded pages, without
        // moving/deleting files or starting a network request. Reading must
        // still succeed when this opportunistic metadata update fails.
        if record.localPath != directory.path {
            try? repository.rebindCompletedPath(
                sourceID: sourceID,
                sourceMangaID: mangaID,
                sourceChapterID: chapterID,
                currentPath: directory.path
            )
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
            // An explicit user deletion may remove only this app's own
            // current chapter directory; never an obsolete SQLite path.
            let current = try chapterDirectory(
                sourceID: sourceID, mangaID: mangaID, chapterID: chapterID
            )
            if fileManager.fileExists(atPath: current.path) {
                try fileManager.removeItem(at: current)
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
        guard let support = fileManager.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first else {
            throw ChapterDownloadError.applicationSupportUnavailable
        }
        return OfflineDownloadPath.chapterDirectory(
            applicationSupport: support,
            sourceID: sourceID, mangaID: mangaID, chapterID: chapterID
        )
    }
}
