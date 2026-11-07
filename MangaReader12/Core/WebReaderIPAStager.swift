import Foundation
import CommonCrypto

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
