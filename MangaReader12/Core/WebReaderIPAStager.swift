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
    case storage
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
    private let stateLock = NSLock()
    private var session: URLSession?
    private var currentTask: URLSessionDataTask?
    private var completion: ((WebReaderIPAStageResult) -> Void)?
    private var stream: OutputStream?
    private var partialURL: URL?
    private var count: Int64 = 0
    private var digest = CC_SHA256_CTX()
    private var redirects = 0

    init(
        verifiedUpdate: WebReaderVerifiedUpdate,
        destinationDirectory: URL = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        )[0].appendingPathComponent("WebReaderUpdates", isDirectory: true),
        testProtocolClasses: [AnyClass]? = nil
    ) {
        self.update = verifiedUpdate
        self.destinationDirectory = destinationDirectory
        self.testProtocolClasses = testProtocolClasses
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
        stateLock.lock()
        guard currentTask == nil else {
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
        self.completion = callback
        self.stream = fileStream
        self.partialURL = staging
        self.count = 0
        self.redirects = 0
        CC_SHA256_Init(&digest)
        stateLock.unlock()
        task.resume()
    }

    func cancel() {
        stateLock.lock()
        let task = currentTask
        stateLock.unlock()
        task?.cancel()
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
            components.port == nil,
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
        if success {
            data.withUnsafeBytes { raw in
                _ = CC_SHA256_Update(&digest, raw.baseAddress, CC_LONG(data.count))
            }
            count += Int64(data.count)
        }
        stateLock.unlock()
        if !success { finish(.failed(.storage)) }
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
        do {
            try FileManager.default.moveItem(at: fileURL, to: destination)
            stateLock.lock()
            partialURL = nil
            stateLock.unlock()
            finish(.staged(destination))
        } catch {
            finish(.failed(.storage))
        }
    }

    private func finish(_ result: WebReaderIPAStageResult) {
        stateLock.lock()
        let callback = completion
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
        callback?(result)
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
            var destinationAfter = stat()
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
        keep = true
        return WebReaderLocalIPAReview(
            copiedIPAURL: saved, build: report.build,
            expectedSHA256: expectedSHA256, ipaBytes: candidateSize,
            zipEntries: report.zipEntries
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
        do {
            _ = try WebReaderNativeIPAAuditor.inspect(
                ipaURL: review.copiedIPAURL, signedUpdate: expected,
                installedBuild: installedBuild, installedIOS: installedIOS
            )
        } catch {
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
              (recorded.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) else {
            return
        }
        _ = Darwin.unlinkat(directoryFD, fileName, 0)
    }
}
