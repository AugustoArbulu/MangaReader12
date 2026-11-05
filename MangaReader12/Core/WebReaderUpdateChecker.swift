import Foundation

/// Phase 3 read-only update discovery for WebReader / iOS 12.
/// No release public key is shipped, so production discovery is FAIL-CLOSED.
/// Does not download IPAs, execute commands, install, or touch the Library.
enum WebReaderUpdateChannel {
    static let developmentManifestURL = URL(string:
        "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/" +
        "main/updates/channel-development-v1.json"
    )!

    /// Deliberately absent until the owner provisions a real release signing key.
    /// Fixture keys must never be committed, bundled or treated as production keys.
    static let productionPublicKeyX963: Data? = nil

    static var isConfigured: Bool { return productionPublicKeyX963 != nil }
}

enum WebReaderUpdateCheckError: Error, Equatable {
    case busy
    case unsupportedManifestURL
    case transport
    case unexpectedHTTPStatus(Int)
    case unexpectedContentType
    case oversizedResponse
    case invalidSignedManifest
}

enum WebReaderUpdateCheckResult {
    case disabled
    case updateAvailable(WebReaderVerifiedUpdate)
    case upToDate
    case failed(WebReaderUpdateCheckError)
}

/// Explicit, one-shot check. Never automatically performs network operations.
/// An injectable URLProtocol allows 100% offline tests with temporary keys.
final class WebReaderUpdateChecker: NSObject, URLSessionDataDelegate, URLSessionTaskDelegate {
    private let manifestURL: URL
    private let pinnedPublicKeyX963: Data?
    private let installedBuild: Int
    private let installedIOS: OperatingSystemVersion
    private let protocolClasses: [AnyClass]?
    private let stateLock = NSLock()

    private static let maxResponseBytes = 64 * 1024
    private var session: URLSession?
    private var currentTask: URLSessionDataTask?
    private var completion: ((WebReaderUpdateCheckResult) -> Void)?
    private var accumulatedData = Data()

    init(
        manifestURL: URL = WebReaderUpdateChannel.developmentManifestURL,
        publicKeyX963: Data? = WebReaderUpdateChannel.productionPublicKeyX963,
        installedBuild: Int,
        installedIOS: OperatingSystemVersion,
        protocolClasses: [AnyClass]? = nil
    ) {
        self.manifestURL = manifestURL
        self.pinnedPublicKeyX963 = publicKeyX963
        self.installedBuild = installedBuild
        self.installedIOS = installedIOS
        self.protocolClasses = protocolClasses
        super.init()
    }

    /// Calls completion exactly once (on the caller's thread when disabled,
    /// otherwise on URLSession's delegate queue). UIKit callers dispatch to main.
    func check(completion: @escaping (WebReaderUpdateCheckResult) -> Void) {
        guard let key = pinnedPublicKeyX963,
            key.count == 65, key.first == 0x04
        else {
            completion(.disabled)
            return
        }
        guard manifestURL.absoluteString ==
            WebReaderUpdateChannel.developmentManifestURL.absoluteString
        else {
            completion(.failed(.unsupportedManifestURL))
            return
        }

        stateLock.lock()
        if currentTask != nil {
            stateLock.unlock()
            completion(.failed(.busy))
            return
        }
        let config = URLSessionConfiguration.ephemeral
        config.urlCache = nil
        config.urlCredentialStorage = nil
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.timeoutIntervalForRequest = 12
        config.timeoutIntervalForResource = 20
        config.httpMaximumConnectionsPerHost = 1
        if let protocolClasses = protocolClasses {
            config.protocolClasses = protocolClasses
        }
        let session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
        var request = URLRequest(
            url: manifestURL, cachePolicy: .reloadIgnoringLocalCacheData,
            timeoutInterval: 12
        )
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let task = session.dataTask(with: request)
        self.session = session
        self.currentTask = task
        self.completion = completion
        self.accumulatedData = Data()
        stateLock.unlock()
        task.resume()
    }

    func cancel() {
        stateLock.lock()
        let active = currentTask
        stateLock.unlock()
        active?.cancel()
    }

    // Do not follow redirects, even from a GitHub or CDN endpoint.
    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        completionHandler(nil)
    }

    func urlSession(
        _ session: URLSession,
        dataTask: URLSessionDataTask,
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
        guard let mime = http.mimeType?.lowercased(),
            mime == "application/json" || mime == "text/json"
        else {
            completionHandler(.cancel)
            finish(.failed(.unexpectedContentType))
            return
        }
        guard response.expectedContentLength <= Int64(Self.maxResponseBytes) else {
            completionHandler(.cancel)
            finish(.failed(.oversizedResponse))
            return
        }
        completionHandler(.allow)
    }

    func urlSession(
        _ session: URLSession,
        dataTask: URLSessionDataTask,
        didReceive data: Data
    ) {
        stateLock.lock()
        guard self.session === session && currentTask === dataTask else {
            stateLock.unlock()
            return
        }
        if data.count > Self.maxResponseBytes - accumulatedData.count {
            stateLock.unlock()
            dataTask.cancel()
            finish(.failed(.oversizedResponse))
            return
        }
        accumulatedData.append(data)
        stateLock.unlock()
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didCompleteWithError error: Error?
    ) {
        stateLock.lock()
        let active = self.session === session && currentTask === task
        let bytes = accumulatedData
        stateLock.unlock()
        guard active else { return }
        if error != nil {
            finish(.failed(.transport))
            return
        }
        guard let key = pinnedPublicKeyX963 else {
            finish(.disabled)
            return
        }
        do {
            let update = try WebReaderUpdateManifestVerifier.verify(
                envelopeData: bytes, publicKeyX963: key,
                installedBuild: installedBuild, installedIOS: installedIOS
            )
            finish(.updateAvailable(update))
        } catch WebReaderUpdateValidationError.notNewer {
            // Signature was verified before version is checked.
            finish(.upToDate)
        } catch {
            finish(.failed(.invalidSignedManifest))
        }
    }

    private func finish(_ result: WebReaderUpdateCheckResult) {
        stateLock.lock()
        let callback = completion
        completion = nil
        currentTask = nil
        accumulatedData = Data()
        let oldSession = session
        session = nil
        stateLock.unlock()
        oldSession?.invalidateAndCancel()
        callback?(result)
    }
}
