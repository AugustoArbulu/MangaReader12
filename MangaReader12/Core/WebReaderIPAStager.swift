import Foundation
import CommonCrypto
import Darwin

/// Phase 4 download *staging only*. This class never calls appinst, unpacks an
/// archive or replaces an installed application.
///
/// The signed-manifest channel requires a trusted publisher key.
/// The public GitHub Releases channel may also supply metadata, but it does
/// NOT authenticate a WebReader publisher. SHA-256 and native ZIP structure
/// checks cannot authorize installation; exporting remains manual.
/// The production signed publisher key remains absent.
enum WebReaderIPAStageFailure: Error, Equatable {
    case disabled
    case busy
    case invalidRelease
    case notNewerThanInstalled
    case storage
    case insufficientSpace
    case cancelled
    case transport
    case redirectRejected
    case unexpectedHTTPStatus(Int)
    case unexpectedContentType
    case sizeMismatch
    case integrityMismatch
    case invalidIPA
}

enum WebReaderIPAStageResult {
    case staged(URL)
    case failed(WebReaderIPAStageFailure)
}

final class WebReaderIPAStager: NSObject, URLSessionDataDelegate, URLSessionTaskDelegate {
    private let update: WebReaderVerifiedUpdate
    private let destinationDirectory: URL
    private let testProtocolClasses: [AnyClass]?
    private let testAvailableSpace: Int64?
    private let testFreeBytesSampler: (() -> Int64?)?
    private let testInstalledBuild: Int?
    private let onProgress: ((Int) -> Void)?
    // Deterministic test-only race gates; cannot be enabled without an
    // injected URLProtocol. Production transfers never execute them.
    private let beforeFinalCommit: (() -> Void)?
    private let afterFinalCommit: (() -> Void)?
    private let stateLock = NSLock()
    private var session: URLSession?
    private var currentTask: URLSessionDataTask?
    private var cancelRequested = false
    private var completion: ((WebReaderIPAStageResult) -> Void)?
    private var stream: OutputStream?
    private var partialURL: URL?
    private var count: Int64 = 0
    private var lastProgressBucket = 0
    private var lastSpaceCheckAt: Int64 = 0
    private var digest = CC_SHA256_CTX()
    private var redirects = 0

    init(
        verifiedUpdate: WebReaderVerifiedUpdate,
        destinationDirectory: URL = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        )[0].appendingPathComponent("WebReaderUpdates", isDirectory: true),
        testProtocolClasses: [AnyClass]? = nil,
        testAvailableSpace: Int64? = nil,
        testFreeBytesSampler: (() -> Int64?)? = nil,
        testInstalledBuild: Int? = nil,
        onProgress: ((Int) -> Void)? = nil,
        beforeFinalCommit: (() -> Void)? = nil,
        afterFinalCommit: (() -> Void)? = nil
    ) {
        self.update = verifiedUpdate
        self.destinationDirectory = destinationDirectory
        self.testProtocolClasses = testProtocolClasses
        // Test-only override is ignored without an injected transport.
        self.testAvailableSpace = testProtocolClasses == nil ? nil : testAvailableSpace
        self.testFreeBytesSampler = testProtocolClasses == nil ?
            nil : testFreeBytesSampler
        self.testInstalledBuild = testProtocolClasses == nil ? nil : testInstalledBuild
        self.onProgress = onProgress
        self.beforeFinalCommit = testProtocolClasses == nil ? nil : beforeFinalCommit
        self.afterFinalCommit = testProtocolClasses == nil ? nil : afterFinalCommit
        super.init()
    }

    /// Explicit, manual staging. Even with a valid update object, this is
    /// fail-closed when no production key has been configured in the app.
    func stage(completion callback: @escaping (WebReaderIPAStageResult) -> Void) {
        guard WebReaderUpdateChannel.isConfigured ||
            update.provenance == .publicGitHubRelease ||
            testProtocolClasses != nil else {
            callback(.failed(.disabled))
            return
        }
        let releasePath = "/AugustoArbulu/MangaReader12/releases/download/" +
            "build" + String(update.build) + "/"
        let allowedPaths: Set<String> = [
            releasePath + "WebReader-iOS12-unsigned.ipa",
            releasePath + "WebReader-Build" + String(update.build) +
                "-iOS12-adhoc.ipa"
        ]
        guard let components = URLComponents(
            url: update.ipaURL, resolvingAgainstBaseURL: false
        ),
            components.scheme == "https",
            components.host == "github.com",
            components.user == nil, components.password == nil,
            components.port == nil, components.query == nil,
            components.fragment == nil,
            allowedPaths.contains(components.percentEncodedPath),
            update.build > 0,
            update.ipaSize > 0 && update.ipaSize <= 512 * 1024 * 1024,
            update.sha256.range(
                of: "^[0-9a-f]{64}$", options: .regularExpression
            ) != nil
        else {
            callback(.failed(.invalidRelease))
            return
        }
        // Recheck installed version immediately before staging; metadata
        // validated in a prior UI/session cannot downgrade the active app.
        // An injected version is permitted only with an injected test URLProtocol.
        let bundleBuild = Int(Bundle.main.object(
            forInfoDictionaryKey: "CFBundleVersion"
        ) as? String ?? "") ?? 0
        let currentBuild = testInstalledBuild ?? bundleBuild
        guard currentBuild >= 0, update.build > currentBuild else {
            callback(.failed(.notNewerThanInstalled))
            return
        }
        stateLock.lock()
        guard currentTask == nil && completion == nil else {
            stateLock.unlock()
            callback(.failed(.busy))
            return
        }
        do {
            try FileManager.default.createDirectory(
                at: destinationDirectory, withIntermediateDirectories: true,
                attributes: nil
            )
        } catch {
            stateLock.unlock()
            callback(.failed(.storage))
            return
        }
        // Do not start a transfer that could exhaust the user's manga,
        // backup or offline reading storage. Unknown filesystem capacity
        // fails closed. This is a preflight, not a disk-space reservation.
        let freeAtStart: Int64?
        if let sampler = testFreeBytesSampler {
            freeAtStart = sampler()
        } else {
            freeAtStart = testAvailableSpace ??
                WebReaderIPADownloadBudget.availableFreeBytes(in: destinationDirectory)
        }
        guard let free = freeAtStart else {
            stateLock.unlock()
            callback(.failed(.storage))
            return
        }
        guard WebReaderIPADownloadBudget.enoughSpace(
            freeBytes: free, ipaBytes: update.ipaSize
        ) else {
            stateLock.unlock()
            callback(.failed(.insufficientSpace))
            return
        }
        let staging = destinationDirectory.appendingPathComponent(
            ".webreader-" + UUID().uuidString + ".partial"
        )
        guard FileManager.default.createFile(atPath: staging.path, contents: Data()),
            let fileStream = OutputStream(url: staging, append: false)
        else {
            stateLock.unlock()
            callback(.failed(.storage))
            return
        }
        fileStream.open()
        guard fileStream.streamStatus == .open else {
            fileStream.close()
            try? FileManager.default.removeItem(at: staging)
            stateLock.unlock()
            callback(.failed(.storage))
            return
        }
        let config = URLSessionConfiguration.ephemeral
        config.urlCache = nil
        config.urlCredentialStorage = nil
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.timeoutIntervalForRequest = 20
        config.timeoutIntervalForResource = 300
        config.httpMaximumConnectionsPerHost = 1
        if let protocols = testProtocolClasses {
            config.protocolClasses = protocols
        }
        let newSession = URLSession(
            configuration: config, delegate: self, delegateQueue: nil
        )
        var request = URLRequest(url: update.ipaURL)
        request.httpMethod = "GET"
        request.setValue("application/octet-stream", forHTTPHeaderField: "Accept")
        let task = newSession.dataTask(with: request)
        self.session = newSession
        self.currentTask = task
        self.cancelRequested = false
        self.completion = callback
        self.stream = fileStream
        self.partialURL = staging
        self.count = 0
        self.lastProgressBucket = 0
        self.lastSpaceCheckAt = 0
        self.redirects = 0
        CC_SHA256_Init(&digest)
        stateLock.unlock()
        task.resume()
    }

    func cancel() {
        stateLock.lock()
        // Mark cancellation BEFORE stopping the URLSession. Completion and
        // promotion must observe the same lock-serialized decision.
        guard let active = currentTask, completion != nil,
              !cancelRequested else {
            stateLock.unlock()
            return
        }
        cancelRequested = true
        stateLock.unlock()
        active.cancel()
        // A stalled transport may never send a final callback. In that case
        // finish removes the private partial IPA immediately, exactly once.
        finish(.failed(.cancelled))
    }

    /// iOS 12 compatible response-header lookup. The convenience accessor
    /// HTTPURLResponse.value(forHTTPHeaderField:) is iOS 13+, unlike
    /// allHeaderFields, which has been available since early iOS.
    /// Header keys can arrive as NSString/AnyHashable; compare ignoring case.
    private func responseHeader(
        _ name: String, from response: HTTPURLResponse
    ) -> String? {
        for (key, value) in response.allHeaderFields {
            guard String(describing: key).caseInsensitiveCompare(name) ==
                .orderedSame else { continue }
            return String(describing: value)
        }
        return nil
    }

    // Real GitHub Releases may redirect once to the release-asset CDN.
    // Redirects never carry credentials. All bytes must match the signed SHA.
    func urlSession(
        _ session: URLSession, task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        stateLock.lock()
        let current = self.session === session && currentTask === task
        redirects += current ? 1 : 0
        let redirectCount = redirects
        stateLock.unlock()
        guard current, redirectCount <= 2,
            let url = request.url,
            let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
            components.scheme == "https",
            components.user == nil, components.password == nil,
            components.port == nil, components.fragment == nil,
            request.httpMethod == "GET", request.httpBody == nil,
            request.value(forHTTPHeaderField: "Authorization") == nil,
            request.value(forHTTPHeaderField: "Cookie") == nil,
            let host = components.host,
            host == "release-assets.githubusercontent.com" ||
                host == "objects.githubusercontent.com"
        else {
            completionHandler(nil)
            if current { finish(.failed(.redirectRejected)) }
            return
        }
        completionHandler(request)
    }

    func urlSession(
        _ session: URLSession, dataTask: URLSessionDataTask,
        didReceive response: URLResponse,
        completionHandler: @escaping (URLSession.ResponseDisposition) -> Void
    ) {
        stateLock.lock()
        let current = self.session === session && currentTask === dataTask
        stateLock.unlock()
        guard current else {
            completionHandler(.cancel)
            return
        }
        guard let http = response as? HTTPURLResponse else {
            completionHandler(.cancel)
            finish(.failed(.transport))
            return
        }
        guard http.statusCode == 200 else {
            completionHandler(.cancel)
            finish(.failed(.unexpectedHTTPStatus(http.statusCode)))
            return
        }
        // Only accept the exact, untransformed whole IPA. CDN range
        // responses, gzip transforms or intermediaries returning partial
        // content must not become a download candidate.
        let encoding = responseHeader("Content-Encoding", from: http)?
            .trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard encoding == nil || encoding == "identity",
              responseHeader("Content-Range", from: http) == nil
        else {
            completionHandler(.cancel)
            finish(.failed(.unexpectedContentType))
            return
        }
        let permitted = Set([
            "application/octet-stream", "application/zip",
            "application/x-zip-compressed"
        ])
        guard let mime = http.mimeType?.lowercased(), permitted.contains(mime) else {
            completionHandler(.cancel)
            finish(.failed(.unexpectedContentType))
            return
        }
        guard response.expectedContentLength <= update.ipaSize else {
            completionHandler(.cancel)
            finish(.failed(.sizeMismatch))
            return
        }
        completionHandler(.allow)
    }

    func urlSession(
        _ session: URLSession, dataTask: URLSessionDataTask,
        didReceive data: Data
    ) {
        stateLock.lock()
        guard self.session === session && currentTask === dataTask,
            let output = stream
        else {
            stateLock.unlock()
            return
        }
        guard !data.isEmpty,
            Int64(data.count) <= update.ipaSize - count
        else {
            stateLock.unlock()
            if !data.isEmpty { finish(.failed(.sizeMismatch)) }
            return
        }
        // Check capacity again before writing the first chunk and after
        // each additional 4 MiB. An unrelated process can consume storage
        // after the initial admission check. Repeated checks retain the
        // ORIGINAL IPA-size reserve, not a shrinking safety margin.
        if count == 0 || count - lastSpaceCheckAt >= 4 * 1024 * 1024 {
            let freeNow: Int64?
            if let sampler = testFreeBytesSampler {
                freeNow = sampler()
            } else {
                freeNow = testAvailableSpace ??
                    WebReaderIPADownloadBudget.availableFreeBytes(
                        in: destinationDirectory
                    )
            }
            guard let remainingFree = freeNow,
                  WebReaderIPADownloadBudget.enoughSpaceDuringTransfer(
                    freeBytes: remainingFree,
                    remainingBytes: update.ipaSize - count,
                    totalIPABytes: update.ipaSize
                  ) else {
                stateLock.unlock()
                finish(.failed(.insufficientSpace))
                return
            }
            lastSpaceCheckAt = count
        }
        let success = data.withUnsafeBytes { raw -> Bool in
            guard let start = raw.bindMemory(to: UInt8.self).baseAddress else {
                return false
            }
            var offset = 0
            while offset < data.count {
                let written = output.write(
                    start.advanced(by: offset), maxLength: data.count - offset
                )
                if written <= 0 { return false }
                offset += written
            }
            return true
        }
        var progressPercent: Int?
        if success {
            data.withUnsafeBytes { raw in
                _ = CC_SHA256_Update(&digest, raw.baseAddress, CC_LONG(data.count))
            }
            count += Int64(data.count)
            let percent = Int((count * 100) / update.ipaSize)
            let bucket = min(19, percent / 5)
            if bucket > lastProgressBucket {
                lastProgressBucket = bucket
                progressPercent = min(95, bucket * 5)
            }
        }
        stateLock.unlock()
        if !success {
            finish(.failed(.storage))
        } else if let percent = progressPercent {
            // Emitted at most every five percent and never claims the
            // final hash/ZIP check is complete while bytes are arriving.
            onProgress?(percent)
        }
    }

    func urlSession(
        _ session: URLSession, task: URLSessionTask,
        didCompleteWithError error: Error?
    ) {
        stateLock.lock()
        let current = self.session === session && currentTask === task
        let total = count
        stateLock.unlock()
        guard current else { return }
        guard error == nil else {
            finish(.failed(.transport))
            return
        }
        guard total == update.ipaSize else {
            finish(.failed(.sizeMismatch))
            return
        }
        stateLock.lock()
        var outputDigest = [UInt8](
            repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH)
        )
        CC_SHA256_Final(&outputDigest, &digest)
        let hex = outputDigest.map { String(format: "%02x", $0) }.joined()
        stream?.close()
        stream = nil
        let file = partialURL
        stateLock.unlock()
        guard hex == update.sha256, let fileURL = file else {
            finish(.failed(.integrityMismatch))
            return
        }
        guard let reader = InputStream(url: fileURL) else {
            finish(.failed(.storage))
            return
        }
        reader.open()
        var magic = [UInt8](repeating: 0, count: 4)
        let bytesRead = reader.read(&magic, maxLength: magic.count)
        reader.close()
        guard bytesRead == 4 && magic == [0x50, 0x4B, 0x03, 0x04] else {
            finish(.failed(.integrityMismatch))
            return
        }
        // The downloaded file is NOT eligible for staging until its
        // complete ZIP directory, local headers, executable and Info.plist
        // independently match the authenticated manifest. No extraction.
        do {
            let version = Bundle.main.object(
                forInfoDictionaryKey: "CFBundleVersion"
            ) as? String
            let installedBuild = Int(version ?? "") ?? 0
            _ = try WebReaderNativeIPAAuditor.inspect(
                ipaURL: fileURL, signedUpdate: update,
                installedBuild: installedBuild,
                installedIOS: ProcessInfo.processInfo.operatingSystemVersion
            )
        } catch {
            finish(.failed(.invalidIPA))
            return
        }
        let destination = destinationDirectory.appendingPathComponent(
            "WebReader-build" + String(update.build) + "-" +
            UUID().uuidString + ".ipa"
        )
        beforeFinalCommit?()
        defer { afterFinalCommit?() }
        // The promotion is atomic with respect to cancel(): a cancelled
        // review can never leave behind an orphan named .ipa. A successful
        // promotion clears currentTask *before* releasing the lock, so late
        // cancellation cannot turn successful staging into a false failure.
        stateLock.lock()
        guard currentTask === task, completion != nil,
              !cancelRequested, partialURL == fileURL else {
            stateLock.unlock()
            return
        }
        do {
            try FileManager.default.moveItem(at: fileURL, to: destination)
            partialURL = nil
            currentTask = nil
            stateLock.unlock()
            finish(.staged(destination))
        } catch {
            stateLock.unlock()
            finish(.failed(.storage))
        }
    }

    private func finish(_ result: WebReaderIPAStageResult) {
        stateLock.lock()
        let callback = completion
        // A concurrent transport failure can race with the owner's cancel.
        // The cancellation decision wins if committed first.
        let resolved: WebReaderIPAStageResult =
            cancelRequested ? .failed(.cancelled) : result
        completion = nil
        currentTask = nil
        stream?.close()
        stream = nil
        let temp = partialURL
        partialURL = nil
        let oldSession = session
        session = nil
        stateLock.unlock()
        if let temp = temp { try? FileManager.default.removeItem(at: temp) }
        oldSession?.invalidateAndCancel()
        callback?(resolved)
    }
}


// MARK: - iOS12 local QA IPA review (manual, no GitHub credential, no install)

/// A local file and a manually supplied checksum are NOT publisher identity.
/// The separately obtained digest only binds the expected bytes. An official
/// release signing key remains absent; neither this receipt nor its import
/// URL may ever be passed to appinst without an independent security design.
enum WebReaderLocalIPAReviewError: Error {
    case invalidReference
    case unreadableFile
    case tooLarge
    case insufficientSpace
    case failedToCopy
    case invalidIPA
}

struct WebReaderLocalIPAReview {
    let copiedIPAURL: URL
    let build: Int
    let expectedSHA256: String
    let ipaBytes: Int64
    let zipEntries: Int
    // Capture the exact verified copy, not just its mutable pathname.
    let stagingDevice: UInt64
    let stagingInode: UInt64
    let manualSourceOnly: Bool = true
    let publisherAuthenticated: Bool = false
    let installationAuthorized: Bool = false
    let installationPerformed: Bool = false
}

/// Restricted to a dedicated staging directory, separate from Library,
/// downloaded chapters, backups, and the network update cache. A new import
/// is always audited AFTER copying it inside the app's own sandbox.
enum WebReaderLocalIPAReviewer {
    static let maximumSize: Int64 = 512 * 1024 * 1024

    /// Reserve room for both the IPA copy and a small filesystem margin.
    /// The source is not consumed, moved or deleted.
    static func requiredFreeBytes(ipaBytes: Int64) -> Int64 {
        let reserve = max(Int64(16 * 1024 * 1024),
            min(Int64(64 * 1024 * 1024), ipaBytes / 8))
        return ipaBytes + reserve
    }

    static func hasEnoughSpace(freeBytes: Int64, ipaBytes: Int64) -> Bool {
        return ipaBytes > 0 && ipaBytes <= maximumSize &&
            freeBytes >= requiredFreeBytes(ipaBytes: ipaBytes)
    }

    static var defaultDirectory: URL {
        return FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        )[0].appendingPathComponent("WebReaderLocalQAImports", isDirectory: true)
    }

    static func importForReview(
        sourceURL: URL, expectedBuild: Int, expectedSHA256: String,
        installedBuild: Int, installedIOS: OperatingSystemVersion,
        directory: URL = defaultDirectory
    ) throws -> WebReaderLocalIPAReview {
        guard sourceURL.isFileURL, sourceURL.pathExtension.lowercased() == "ipa",
              expectedBuild > installedBuild, expectedBuild <= 2_147_483_647,
              installedBuild > 0,
              expectedSHA256.range(
                of: "^[0-9a-f]{64}$", options: .regularExpression
              ) != nil
        else { throw WebReaderLocalIPAReviewError.invalidReference }

        // Open the SOURCE only once, refusing symlink, FIFO and directory
        // substitutions before any read or copy. Its descriptor remains
        // bound to the original inode even if its filename is renamed.
        let sourceFD = Darwin.open(
            sourceURL.path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK
        )
        guard sourceFD >= 0 else {
            throw WebReaderLocalIPAReviewError.unreadableFile
        }
        defer { _ = Darwin.close(sourceFD) }
        var original = stat()
        guard Darwin.fstat(sourceFD, &original) == 0,
              (original.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) else {
            throw WebReaderLocalIPAReviewError.unreadableFile
        }
        let candidateSize = Int64(original.st_size)
        guard candidateSize > 0, candidateSize <= maximumSize else {
            throw WebReaderLocalIPAReviewError.tooLarge
        }

        let fm = FileManager.default
        do {
            try fm.createDirectory(at: directory, withIntermediateDirectories: true,
                                   attributes: [.posixPermissions: 0o700])
        } catch {
            throw WebReaderLocalIPAReviewError.failedToCopy
        }
        // An opened directory descriptor anchors every create/unlink to the
        // SAME folder even when its pathname is replaced. The final path
        // component cannot point to Library or Documents via a symlink.
        let dirFD = Darwin.open(
            directory.path,
            O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK
        )
        guard dirFD >= 0 else { throw WebReaderLocalIPAReviewError.failedToCopy }
        defer { _ = Darwin.close(dirFD) }
        var dirInfo = stat()
        guard Darwin.fstat(dirFD, &dirInfo) == 0,
              (dirInfo.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR) else {
            throw WebReaderLocalIPAReviewError.failedToCopy
        }
        guard let storage = try? fm.attributesOfFileSystem(forPath: directory.path),
              let free = storage[.systemFreeSize] as? NSNumber,
              hasEnoughSpace(freeBytes: free.int64Value, ipaBytes: candidateSize) else {
            throw WebReaderLocalIPAReviewError.insufficientSpace
        }

        let fileName = "WebReader-Build" + String(expectedBuild) +
            "-local-" + UUID().uuidString + ".ipa"
        let saved = directory.appendingPathComponent(fileName)
        // O_EXCL prevents collisions and O_NOFOLLOW prevents substituting a
        // link for the target; neither an existing file nor a source is ever
        // overwritten. The FD is private to this process and no appinst is
        // involved.
        let outputFD = Darwin.openat(
            dirFD, fileName,
            O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW,
            mode_t(0o600)
        )
        guard outputFD >= 0 else { throw WebReaderLocalIPAReviewError.failedToCopy }
        let ownsTemporary = true
        var keep = false
        defer {
            if ownsTemporary && !keep {
                _ = Darwin.unlinkat(dirFD, fileName, 0)
            }
        }
        var copySucceeded = false
        var writtenBytes: Int64 = 0
        var destinationBefore = stat()
        var destinationAfter = stat()
        do {
            guard Darwin.fchmod(outputFD, mode_t(0o600)) == 0,
                  Darwin.fstat(outputFD, &destinationBefore) == 0,
                  (destinationBefore.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) else {
                throw WebReaderLocalIPAReviewError.failedToCopy
            }
            var buffer = [UInt8](repeating: 0, count: 64 * 1024)
            while writtenBytes < candidateSize {
                let requested = Int(min(Int64(buffer.count),
                                        candidateSize - writtenBytes))
                let count = buffer.withUnsafeMutableBytes { raw -> Int in
                    return Darwin.read(sourceFD, raw.baseAddress, requested)
                }
                if count < 0 && errno == EINTR { continue }
                if count <= 0 {
                    throw WebReaderLocalIPAReviewError.failedToCopy
                }
                var offset = 0
                while offset < count {
                    let amount = buffer.withUnsafeBytes { raw -> Int in
                        return Darwin.write(
                            outputFD,
                            raw.baseAddress!.advanced(by: offset),
                            count - offset
                        )
                    }
                    if amount < 0 && errno == EINTR { continue }
                    if amount <= 0 {
                        throw WebReaderLocalIPAReviewError.failedToCopy
                    }
                    offset += amount
                }
                writtenBytes += Int64(count)
            }
            var sourceAfter = stat()
            guard Darwin.fsync(outputFD) == 0,
                  Darwin.fstat(sourceFD, &sourceAfter) == 0,
                  Darwin.fstat(outputFD, &destinationAfter) == 0,
                  writtenBytes == candidateSize,
                  original.st_dev == sourceAfter.st_dev,
                  original.st_ino == sourceAfter.st_ino,
                  original.st_size == sourceAfter.st_size,
                  original.st_mtimespec.tv_sec == sourceAfter.st_mtimespec.tv_sec,
                  original.st_mtimespec.tv_nsec == sourceAfter.st_mtimespec.tv_nsec,
                  original.st_ctimespec.tv_sec == sourceAfter.st_ctimespec.tv_sec,
                  original.st_ctimespec.tv_nsec == sourceAfter.st_ctimespec.tv_nsec,
                  destinationBefore.st_ino == destinationAfter.st_ino,
                  destinationAfter.st_size == candidateSize else {
                throw WebReaderLocalIPAReviewError.failedToCopy
            }
            copySucceeded = true
        } catch {
            _ = Darwin.close(outputFD)
            throw WebReaderLocalIPAReviewError.failedToCopy
        }
        _ = Darwin.close(outputFD)
        guard copySucceeded else { throw WebReaderLocalIPAReviewError.failedToCopy }
        var destinationByName = stat()
        guard Darwin.fstatat(dirFD, fileName, &destinationByName,
                             AT_SYMLINK_NOFOLLOW) == 0,
              (destinationByName.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
              destinationByName.st_dev == destinationAfter.st_dev,
              destinationByName.st_ino == destinationAfter.st_ino else {
            throw WebReaderLocalIPAReviewError.failedToCopy
        }
        // The auditor reopens the freshly copied PRIVATE file to confirm its
        // full digest and structural identity; its own audit is same-FD and
        // rejects changes that happen while it is inspecting.
        // This object is a LOCAL EXPECTATION, not a signed manifest or a
        // GitHub Release. The native auditor compares exact size/SHA, ZIP
        // entries, Info.plist, build, bundle, executable and iOS version.
        var expected = WebReaderVerifiedUpdate(
            build: expectedBuild, minimumIOS: "12.0",
            ipaURL: saved, ipaSize: candidateSize,
            sha256: expectedSHA256, publishedAt: "",
            releaseNotes: []
        )
        expected.provenance = .manualLocalFile
        let report: WebReaderIPAAuditReport
        do {
            report = try WebReaderNativeIPAAuditor.inspect(
                ipaURL: saved, signedUpdate: expected,
                installedBuild: installedBuild, installedIOS: installedIOS
            )
        } catch {
            throw WebReaderLocalIPAReviewError.invalidIPA
        }
        guard report.build == expectedBuild,
              report.verifiedSHA256 == expectedSHA256 else {
            throw WebReaderLocalIPAReviewError.invalidIPA
        }
        var verifiedByName = stat()
        guard Darwin.fstatat(dirFD, fileName, &verifiedByName,
                             AT_SYMLINK_NOFOLLOW) == 0,
              (verifiedByName.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
              verifiedByName.st_dev == destinationAfter.st_dev,
              verifiedByName.st_ino == destinationAfter.st_ino else {
            throw WebReaderLocalIPAReviewError.invalidIPA
        }
        keep = true
        return WebReaderLocalIPAReview(
            copiedIPAURL: saved, build: report.build,
            expectedSHA256: expectedSHA256, ipaBytes: candidateSize,
            zipEntries: report.zipEntries,
            stagingDevice: UInt64(destinationAfter.st_dev),
            stagingInode: UInt64(destinationAfter.st_ino)
        )
    }

    /// Recheck the copied bytes immediately before the manual Share Sheet.
    /// The hash reference remains observational and never authorizes install.
    static func recheck(
        _ review: WebReaderLocalIPAReview,
        installedBuild: Int, installedIOS: OperatingSystemVersion
    ) throws {
        var expected = WebReaderVerifiedUpdate(
            build: review.build, minimumIOS: "12.0",
            ipaURL: review.copiedIPAURL, ipaSize: review.ipaBytes,
            sha256: review.expectedSHA256, publishedAt: "", releaseNotes: []
        )
        expected.provenance = .manualLocalFile
        // Bind the share-time check to the same inode that import verified.
        // A byte-identical replacement has the same SHA but NOT the same
        // staging identity and must be explicitly re-imported.
        let checkFD = Darwin.open(
            review.copiedIPAURL.path,
            O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK
        )
        guard checkFD >= 0 else { throw WebReaderLocalIPAReviewError.invalidIPA }
        defer { _ = Darwin.close(checkFD) }
        var before = stat()
        guard Darwin.fstat(checkFD, &before) == 0,
              (before.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
              UInt64(before.st_dev) == review.stagingDevice,
              UInt64(before.st_ino) == review.stagingInode else {
            throw WebReaderLocalIPAReviewError.invalidIPA
        }
        do {
            _ = try WebReaderNativeIPAAuditor.inspect(
                ipaURL: review.copiedIPAURL, signedUpdate: expected,
                installedBuild: installedBuild, installedIOS: installedIOS
            )
        } catch {
            throw WebReaderLocalIPAReviewError.invalidIPA
        }
        var after = stat()
        var currentPath = stat()
        guard Darwin.fstat(checkFD, &after) == 0,
              Darwin.lstat(review.copiedIPAURL.path, &currentPath) == 0,
              (currentPath.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
              currentPath.st_dev == before.st_dev,
              currentPath.st_ino == before.st_ino,
              after.st_dev == before.st_dev, after.st_ino == before.st_ino,
              after.st_size == before.st_size,
              after.st_mtimespec.tv_sec == before.st_mtimespec.tv_sec,
              after.st_mtimespec.tv_nsec == before.st_mtimespec.tv_nsec,
              after.st_ctimespec.tv_sec == before.st_ctimespec.tv_sec,
              after.st_ctimespec.tv_nsec == before.st_ctimespec.tv_nsec else {
            throw WebReaderLocalIPAReviewError.invalidIPA
        }
    }

    /// Delete ONLY the imported QA copy we created, never Library or
    /// chapter directories. No application installation is ever performed.
    static func discard(_ review: WebReaderLocalIPAReview,
                        directory: URL = defaultDirectory) {
        let file = review.copiedIPAURL.standardizedFileURL
        let fileName = file.lastPathComponent
        let expectedPrefix = "WebReader-Build" + String(review.build) +
            "-local-"
        guard file.deletingLastPathComponent().standardizedFileURL ==
                directory.standardizedFileURL,
              fileName.hasPrefix(expectedPrefix),
              fileName.hasSuffix(".ipa"),
              UUID(uuidString: String(
                fileName.dropFirst(expectedPrefix.count).dropLast(4)
              )) != nil else { return }
        // A previous path-based removeItem could be redirected if another
        // process swapped the staging directory for a symlink. Anchor the
        // unlink to a non-symlinked directory FD and accept only regular IPA
        // copies with a matching UUID-derived filename.
        let directoryFD = Darwin.open(
            directory.path,
            O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK
        )
        guard directoryFD >= 0 else { return }
        defer { _ = Darwin.close(directoryFD) }
        var recorded = stat()
        guard Darwin.fstatat(
            directoryFD, fileName, &recorded, AT_SYMLINK_NOFOLLOW
        ) == 0,
              (recorded.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
              UInt64(recorded.st_dev) == review.stagingDevice,
              UInt64(recorded.st_ino) == review.stagingInode else {
            return
        }
        _ = Darwin.unlinkat(directoryFD, fileName, 0)
    }
}


// MARK: - Owner-confirmed cleanup of stale local QA copies

/// A candidate identifies a REGULAR file already found inside the *specific*
/// QA directory. It grants no permission to install, migrate or read Library.
struct WebReaderLocalQAStaleCandidate: Equatable {
    let fileName: String
    let byteCount: Int64
    let fileDevice: UInt64
    let fileInode: UInt64
    let modifiedSeconds: Int64
    let modifiedNanoseconds: Int64
    let changedSeconds: Int64
    let changedNanoseconds: Int64
}

struct WebReaderLocalQAStorageInventory {
    let eligible: [WebReaderLocalQAStaleCandidate]
    let eligibleBytes: Int64
    let ignoredEntries: Int
    let inspectionLimited: Bool
    let installationAuthorized: Bool = false
}

enum WebReaderLocalQAStorageError: Error {
    case invalidDirectory
    case unreadable
    case tooManyEntries
}

/// Never automatically deletes after launch. Only the screen's owner-confirmed
/// action may call discardConfirmed. A 24-hour quarantine and a strict name
/// grammar limit scope; revalidate both pathname and inode at deletion time.
///
/// Not a privileged deletion service: a process sharing sandbox write access
/// could race the interval between fstatat and unlinkat; such a threat needs
/// stronger OS isolation, not merely a nicer UI. This operates only as mobile.
enum WebReaderLocalQAStorage {
    static let minimumAgeSeconds: Int64 = 24 * 60 * 60
    static let maximumScannedNames = 512

    static func isQAName(_ name: String) -> Bool {
        guard name.hasPrefix("WebReader-Build"),
              name.hasSuffix(".ipa"), name.utf8.count <= 90 else {
            return false
        }
        // Exact 9-digit-or-shorter positive build and an entire UUID, not
        // substring matching. Never accept traversal, subdirectories or
        // names that coincide with backups or downloaded chapters.
        guard name.range(
            of: "^WebReader-Build[1-9][0-9]{0,8}-local-" +
                "[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-" +
                "[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\\.ipa$",
            options: .regularExpression
        ) != nil else { return false }
        return true
    }

    private static func openDirectory(_ directory: URL) throws -> Int32 {
        guard directory.isFileURL else {
            throw WebReaderLocalQAStorageError.invalidDirectory
        }
        let fd = Darwin.open(
            directory.path,
            O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK
        )
        guard fd >= 0 else { throw WebReaderLocalQAStorageError.invalidDirectory }
        var st = stat()
        guard Darwin.fstat(fd, &st) == 0,
              (st.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR) else {
            _ = Darwin.close(fd)
            throw WebReaderLocalQAStorageError.invalidDirectory
        }
        return fd
    }

    static func inventory(
        directory: URL = WebReaderLocalIPAReviewer.defaultDirectory,
        now: Date = Date(),
        protected: WebReaderLocalIPAReview? = nil
    ) throws -> WebReaderLocalQAStorageInventory {
        let fm = FileManager.default
        // The first import creates the folder. No import yet is zero bytes,
        // not a reason to create a directory or scan elsewhere.
        var dirStatus = stat()
        if Darwin.lstat(directory.path, &dirStatus) != 0 && errno == ENOENT {
            return WebReaderLocalQAStorageInventory(
                eligible: [], eligibleBytes: 0,
                ignoredEntries: 0, inspectionLimited: false
            )
        }
        let dirFD = try openDirectory(directory)
        defer { _ = Darwin.close(dirFD) }
        let names: [String]
        do {
            names = try fm.contentsOfDirectory(atPath: directory.path)
        } catch { throw WebReaderLocalQAStorageError.unreadable }
        if names.count > maximumScannedNames {
            throw WebReaderLocalQAStorageError.tooManyEntries
        }
        let cutoff = Int64(now.timeIntervalSince1970) - minimumAgeSeconds
        var eligible: [WebReaderLocalQAStaleCandidate] = []
        var ignored = 0
        var total: Int64 = 0
        for name in names {
            guard isQAName(name) else { ignored += 1; continue }
            var st = stat()
            guard Darwin.fstatat(dirFD, name, &st, AT_SYMLINK_NOFOLLOW) == 0,
                  (st.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
                  st.st_nlink == 1,
                  st.st_size > 0,
                  st.st_size <= WebReaderLocalIPAReviewer.maximumSize,
                  Int64(st.st_mtimespec.tv_sec) <= cutoff,
                  Int64(st.st_ctimespec.tv_sec) <= cutoff,
                  !(UInt64(st.st_dev) == protected?.stagingDevice &&
                    UInt64(st.st_ino) == protected?.stagingInode) else {
                ignored += 1
                continue
            }
            let bytes = Int64(st.st_size)
            guard total <= Int64.max - bytes else {
                throw WebReaderLocalQAStorageError.unreadable
            }
            total += bytes
            eligible.append(WebReaderLocalQAStaleCandidate(
                fileName: name, byteCount: bytes,
                fileDevice: UInt64(st.st_dev), fileInode: UInt64(st.st_ino),
                modifiedSeconds: Int64(st.st_mtimespec.tv_sec),
                modifiedNanoseconds: Int64(st.st_mtimespec.tv_nsec),
                changedSeconds: Int64(st.st_ctimespec.tv_sec),
                changedNanoseconds: Int64(st.st_ctimespec.tv_nsec)
            ))
        }
        return WebReaderLocalQAStorageInventory(
            eligible: eligible.sorted { $0.fileName < $1.fileName },
            eligibleBytes: total, ignoredEntries: ignored,
            inspectionLimited: false
        )
    }

    /// Returns false when a file changed since the owner's inventory,
    /// became young, is protected, linked, missing or no longer regular.
    /// Caller must present a separate UI confirmation BEFORE calling.
    @discardableResult
    static func discardConfirmed(
        _ candidate: WebReaderLocalQAStaleCandidate,
        directory: URL = WebReaderLocalIPAReviewer.defaultDirectory,
        now: Date = Date(),
        protected: WebReaderLocalIPAReview? = nil
    ) -> Bool {
        guard isQAName(candidate.fileName),
              candidate.byteCount > 0,
              candidate.byteCount <= WebReaderLocalIPAReviewer.maximumSize,
              !(candidate.fileDevice == protected?.stagingDevice &&
                candidate.fileInode == protected?.stagingInode) else { return false }
        guard let dirFD = try? openDirectory(directory) else { return false }
        defer { _ = Darwin.close(dirFD) }
        // A second fd-based inspection precedes unlinkat. That avoids
        // following a symlink or deleting a newer candidate under this name.
        var st = stat()
        let cutoff = Int64(now.timeIntervalSince1970) - minimumAgeSeconds
        guard Darwin.fstatat(dirFD, candidate.fileName, &st,
                             AT_SYMLINK_NOFOLLOW) == 0,
              (st.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
              st.st_nlink == 1,
              Int64(st.st_size) == candidate.byteCount,
              UInt64(st.st_dev) == candidate.fileDevice,
              UInt64(st.st_ino) == candidate.fileInode,
              Int64(st.st_mtimespec.tv_sec) == candidate.modifiedSeconds,
              Int64(st.st_mtimespec.tv_nsec) == candidate.modifiedNanoseconds,
              Int64(st.st_ctimespec.tv_sec) == candidate.changedSeconds,
              Int64(st.st_ctimespec.tv_nsec) == candidate.changedNanoseconds,
              Int64(st.st_mtimespec.tv_sec) <= cutoff,
              Int64(st.st_ctimespec.tv_sec) <= cutoff else { return false }
        return Darwin.unlinkat(dirFD, candidate.fileName, 0) == 0
    }
}


// MARK: - Owner-confirmed cleanup of completed/abandoned GitHub Release downloads

/// Read-only recovery snapshot. A stale partial may be a previously killed
/// download; NEVER treat it as a resumable, integrity-verified IPA. No network,
/// file writes, deletion, privilege escalation or automatic retry is allowed.
struct WebReaderReleaseRecoverySummary {
    let interruptedFiles: Int
    let interruptedBytes: Int64
    let completedFiles: Int
    let completedBytes: Int64
    let ignoredEntries: Int
    let canResumePartial: Bool = false
    let cleanupRequiresOwnerConfirmation: Bool = true
    let installationAuthorized: Bool = false

    static func readOnly(
        _ inventory: WebReaderLocalQAStorageInventory
    ) -> WebReaderReleaseRecoverySummary {
        var partialCount = 0
        var partialBytes: Int64 = 0
        var completedCount = 0
        var completedBytes: Int64 = 0
        for entry in inventory.eligible {
            if entry.fileName.hasSuffix(".partial") {
                partialCount += 1
                partialBytes += entry.byteCount
            } else if entry.fileName.hasSuffix(".ipa") {
                completedCount += 1
                completedBytes += entry.byteCount
            }
        }
        return WebReaderReleaseRecoverySummary(
            interruptedFiles: partialCount,
            interruptedBytes: partialBytes,
            completedFiles: completedCount,
            completedBytes: completedBytes,
            ignoredEntries: inventory.ignoredEntries
        )
    }
}

/// Separate from WebReaderLocalQAImports. Handles ONLY files created by the
/// download stager inside Application Support/WebReaderUpdates. This never
/// deletes source IPAs, chapter downloads, SQLite, backups or exported files.
/// The caller must obtain explicit owner consent before calling discardConfirmed.
enum WebReaderReleaseCacheStorage {
    static let minimumAgeSeconds: Int64 = 24 * 60 * 60
    static let maximumScannedNames = 512

    static var defaultDirectory: URL {
        return FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        )[0].appendingPathComponent("WebReaderUpdates", isDirectory: true)
    }

    static func isManagedName(_ name: String) -> Bool {
        guard name.utf8.count <= 100 else { return false }
        let completed = "^WebReader-build[1-9][0-9]{0,8}-" +
            "[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-" +
            "[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\\.ipa$"
        let abandoned = "^\\.webreader-" +
            "[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-" +
            "[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\\.partial$"
        return name.range(of: completed, options: .regularExpression) != nil ||
            name.range(of: abandoned, options: .regularExpression) != nil
    }

    private static func openDirectory(_ directory: URL) throws -> Int32 {
        guard directory.isFileURL else {
            throw WebReaderLocalQAStorageError.invalidDirectory
        }
        let fd = Darwin.open(
            directory.path,
            O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK
        )
        guard fd >= 0 else { throw WebReaderLocalQAStorageError.invalidDirectory }
        var info = stat()
        guard Darwin.fstat(fd, &info) == 0,
              (info.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR) else {
            _ = Darwin.close(fd)
            throw WebReaderLocalQAStorageError.invalidDirectory
        }
        return fd
    }

    private static func matches(
        _ candidate: WebReaderLocalQAStaleCandidate, _ st: stat,
        now: Date
    ) -> Bool {
        let cutoff = Int64(now.timeIntervalSince1970) - minimumAgeSeconds
        return (st.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) &&
            st.st_nlink == 1 &&
            st.st_size >= 0 &&
            st.st_size <= WebReaderLocalIPAReviewer.maximumSize &&
            (candidate.fileName.hasSuffix(".partial") || st.st_size > 0) &&
            UInt64(st.st_dev) == candidate.fileDevice &&
            UInt64(st.st_ino) == candidate.fileInode &&
            Int64(st.st_size) == candidate.byteCount &&
            Int64(st.st_mtimespec.tv_sec) == candidate.modifiedSeconds &&
            Int64(st.st_mtimespec.tv_nsec) == candidate.modifiedNanoseconds &&
            Int64(st.st_ctimespec.tv_sec) == candidate.changedSeconds &&
            Int64(st.st_ctimespec.tv_nsec) == candidate.changedNanoseconds &&
            Int64(st.st_mtimespec.tv_sec) <= cutoff &&
            Int64(st.st_ctimespec.tv_sec) <= cutoff
    }

    static func inventory(
        directory: URL = defaultDirectory, now: Date = Date(),
        protectedName: String? = nil
    ) throws -> WebReaderLocalQAStorageInventory {
        var status = stat()
        if Darwin.lstat(directory.path, &status) != 0 {
            if errno == ENOENT {
                return WebReaderLocalQAStorageInventory(
                    eligible: [], eligibleBytes: 0,
                    ignoredEntries: 0, inspectionLimited: false
                )
            }
            throw WebReaderLocalQAStorageError.unreadable
        }
        let fd = try openDirectory(directory)
        defer { _ = Darwin.close(fd) }
        // Listing supplies names only. File identity and metadata are always
        // anchored to the already-open, non-symlinked directory descriptor.
        let names: [String]
        do {
            names = try FileManager.default.contentsOfDirectory(atPath: directory.path)
        } catch { throw WebReaderLocalQAStorageError.unreadable }
        guard names.count <= maximumScannedNames else {
            throw WebReaderLocalQAStorageError.tooManyEntries
        }
        var eligible: [WebReaderLocalQAStaleCandidate] = []
        var ignored = 0
        var bytes: Int64 = 0
        for name in names {
            guard isManagedName(name), name != protectedName else {
                ignored += 1
                continue
            }
            var st = stat()
            guard Darwin.fstatat(fd, name, &st, AT_SYMLINK_NOFOLLOW) == 0 else {
                ignored += 1
                continue
            }
            let candidate = WebReaderLocalQAStaleCandidate(
                fileName: name, byteCount: Int64(st.st_size),
                fileDevice: UInt64(st.st_dev), fileInode: UInt64(st.st_ino),
                modifiedSeconds: Int64(st.st_mtimespec.tv_sec),
                modifiedNanoseconds: Int64(st.st_mtimespec.tv_nsec),
                changedSeconds: Int64(st.st_ctimespec.tv_sec),
                changedNanoseconds: Int64(st.st_ctimespec.tv_nsec)
            )
            guard matches(candidate, st, now: now) else {
                ignored += 1
                continue
            }
            guard bytes <= Int64.max - candidate.byteCount else {
                throw WebReaderLocalQAStorageError.unreadable
            }
            bytes += candidate.byteCount
            eligible.append(candidate)
        }
        return WebReaderLocalQAStorageInventory(
            eligible: eligible.sorted { $0.fileName < $1.fileName },
            eligibleBytes: bytes, ignoredEntries: ignored,
            inspectionLimited: false
        )
    }

    /// No scan, no recursion, no shell. Rechecks the exact candidate after
    /// owner confirmation. This is NOT an atomic operation against a hostile
    /// process with write permission to the same sandbox directory.
    static func discardConfirmed(
        _ candidate: WebReaderLocalQAStaleCandidate,
        directory: URL = defaultDirectory, now: Date = Date(),
        protectedName: String? = nil
    ) -> Bool {
        guard isManagedName(candidate.fileName),
              candidate.fileName != protectedName else { return false }
        guard let fd = try? openDirectory(directory) else { return false }
        defer { _ = Darwin.close(fd) }
        var st = stat()
        guard Darwin.fstatat(
            fd, candidate.fileName, &st, AT_SYMLINK_NOFOLLOW
        ) == 0, matches(candidate, st, now: now) else { return false }
        return Darwin.unlinkat(fd, candidate.fileName, 0) == 0
    }
}
