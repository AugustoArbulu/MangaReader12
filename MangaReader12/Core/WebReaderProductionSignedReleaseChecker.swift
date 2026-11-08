import Foundation

/// Build69 Phase AM: real iOS12 transport for a future *production-signed*
/// WebReader release manifest. Explicit user action only. The current app
/// has NO editorial trust root, so it returns .disabled BEFORE any network.
///
/// This deliberately does not use the injectable development key, GitHub
/// Release SHA-256, a password, or GitHub Actions API credentials as trust.
/// A future owner-reviewed build must independently provision the public
/// signing key and its SPKI pin before this channel becomes usable.
enum WebReaderSignedProductionChannel {
    static let manifestURL = URL(string:
        "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/" +
        "main/updates/channel-production-v2.json"
    )!
    static let maximumResponseBytes = 64 * 1024
}

final class WebReaderProductionSignedReleaseChecker:
    NSObject, URLSessionDataDelegate, URLSessionTaskDelegate {

    private let installedBuild: Int
    private let installedIOS: OperatingSystemVersion
    private let stateLock = NSLock()
    private var session: URLSession?
    private var task: URLSessionDataTask?
    private var completion: ((WebReaderUpdateCheckResult) -> Void)?
    private var responseData = Data()

    init(installedBuild: Int, installedIOS: OperatingSystemVersion) {
        self.installedBuild = installedBuild
        self.installedIOS = installedIOS
        super.init()
    }

    func check(completion callback: @escaping (WebReaderUpdateCheckResult) -> Void) {
        // No GitHub request while the owner-controlled publisher key/pin
        // are absent. Even a valid but UNTRUSTED signature never enrolls it.
        guard WebReaderProductionPublisherTrust.isProvisioned else {
            callback(.disabled)
            return
        }
        stateLock.lock()
        guard task == nil && completion == nil else {
            stateLock.unlock()
            callback(.failed(.busy))
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
        let connection = URLSession(configuration: config, delegate: self,
                                    delegateQueue: nil)
        var request = URLRequest(
            url: WebReaderSignedProductionChannel.manifestURL,
            cachePolicy: .reloadIgnoringLocalCacheData,
            timeoutInterval: 12
        )
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("WebReader-iOS12-SignedChannel", forHTTPHeaderField: "User-Agent")
        let next = connection.dataTask(with: request)
        session = connection
        task = next
        completion = callback
        responseData = Data()
        stateLock.unlock()
        next.resume()
    }

    func cancel() {
        stateLock.lock()
        let active = task
        stateLock.unlock()
        active?.cancel()
    }

    func urlSession(
        _ session: URLSession, task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        // No redirects, even to an adjacent GitHub/CDN hostname. Pinning
        // authenticates manifest bytes, not arbitrary redirect targets.
        completionHandler(nil)
    }

    func urlSession(
        _ session: URLSession, dataTask: URLSessionDataTask,
        didReceive response: URLResponse,
        completionHandler: @escaping (URLSession.ResponseDisposition) -> Void
    ) {
        stateLock.lock()
        let active = self.session === session && task === dataTask
        stateLock.unlock()
        guard active else {
            completionHandler(.cancel)
            return
        }
        guard let http = response as? HTTPURLResponse,
              http.url == WebReaderSignedProductionChannel.manifestURL else {
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
              mime == "application/json" || mime == "text/json" else {
            completionHandler(.cancel)
            finish(.failed(.unexpectedContentType))
            return
        }
        guard response.expectedContentLength <=
            Int64(WebReaderSignedProductionChannel.maximumResponseBytes) else {
            completionHandler(.cancel)
            finish(.failed(.oversizedResponse))
            return
        }
        completionHandler(.allow)
    }

    func urlSession(
        _ session: URLSession, dataTask: URLSessionDataTask,
        didReceive data: Data
    ) {
        stateLock.lock()
        guard self.session === session && task === dataTask else {
            stateLock.unlock()
            return
        }
        let limit = WebReaderSignedProductionChannel.maximumResponseBytes
        guard data.count <= limit - responseData.count else {
            stateLock.unlock()
            dataTask.cancel()
            finish(.failed(.oversizedResponse))
            return
        }
        responseData.append(data)
        stateLock.unlock()
    }

    func urlSession(
        _ session: URLSession, task: URLSessionTask,
        didCompleteWithError error: Error?
    ) {
        stateLock.lock()
        let active = self.session === session && self.task === task
        let bytes = responseData
        stateLock.unlock()
        guard active else { return }
        if error != nil {
            finish(.failed(.transport))
            return
        }
        do {
            let preview =
                try WebReaderProductionPublisherTrust.inspectProductionManifestReadOnly(
                    envelopeData: bytes, installedBuild: installedBuild,
                    installedIOS: installedIOS
                )
            // A signed manifest preview is not an install authorization.
            finish(.updateAvailable(preview.update))
        } catch WebReaderUpdateValidationError.notNewer {
            // This result can only be reached after verification by the
            // independently provisioned editorial key and SPKI fingerprint.
            finish(.upToDate)
        } catch {
            finish(.failed(.invalidSignedManifest))
        }
    }

    private func finish(_ result: WebReaderUpdateCheckResult) {
        stateLock.lock()
        let callback = completion
        completion = nil
        task = nil
        responseData = Data()
        let oldSession = session
        session = nil
        stateLock.unlock()
        oldSession?.invalidateAndCancel()
        callback?(result)
    }
}
