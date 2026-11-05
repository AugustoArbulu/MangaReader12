import Foundation

/// Manual, read-only HTTPS diagnostic for the iOS 12 default URLSession trust
/// stack. This probes only fixed GitHub endpoints with HTTP HEAD.
/// It DOES NOT authenticate a release, fetch an IPA, or prove that a signed
/// update can be installed. No ATS exceptions or custom TLS trust delegates.
struct WebReaderHTTPSProbeResult {
    let label: String
    let host: String
    let httpStatus: Int?
    let errorDomain: String?
    let errorCode: Int?

    var reportLine: String {
        if let status = httpStatus {
            return label + " [" + host + "]: HTTPS respondeu, HTTP " +
                String(status)
        }
        let domain = errorDomain ?? "desconhecido"
        return label + " [" + host + "]: falha " + domain + " " +
            String(errorCode ?? 0)
    }
}

final class WebReaderReleaseHTTPSProbe: NSObject, URLSessionDataDelegate,
    URLSessionTaskDelegate {

    struct Endpoint {
        let label: String
        let url: URL
    }

    // Exact, static origins. A CDN root response does not validate a
    // particular GitHub Release asset or its time-limited redirect URL.
    static let endpoints: [Endpoint] = [
        Endpoint(
            label: "Manifesto (GitHub Raw)",
            url: URL(string:
                "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/" +
                "main/PROJECT_STATE.md"
            )!
        ),
        Endpoint(
            label: "GitHub Releases",
            url: URL(string:
                "https://github.com/AugustoArbulu/MangaReader12/releases"
            )!
        ),
        Endpoint(
            label: "CDN de assets",
            url: URL(string: "https://release-assets.githubusercontent.com/")!
        )
    ]

    private let stateQueue = DispatchQueue(
        label: "webreader.release.https.probe.state"
    )
    private let testProtocols: [AnyClass]?
    private var session: URLSession?
    private var activeTask: URLSessionDataTask?
    private var onFinish: (([WebReaderHTTPSProbeResult]) -> Void)?
    private var results: [WebReaderHTTPSProbeResult] = []
    private var position = 0

    init(testProtocolClasses: [AnyClass]? = nil) {
        self.testProtocols = testProtocolClasses
        super.init()
    }

    func run(completion: @escaping ([WebReaderHTTPSProbeResult]) -> Void) {
        stateQueue.async {
            guard self.onFinish == nil else { return }
            self.onFinish = completion
            self.results = []
            self.position = 0

            let config = URLSessionConfiguration.ephemeral
            config.urlCache = nil
            config.urlCredentialStorage = nil
            config.httpCookieStorage = nil
            config.httpShouldSetCookies = false
            config.requestCachePolicy = .reloadIgnoringLocalCacheData
            config.timeoutIntervalForRequest = 10
            config.timeoutIntervalForResource = 15
            config.httpMaximumConnectionsPerHost = 1
            if let protocols = self.testProtocols {
                config.protocolClasses = protocols
            }
            self.session = URLSession(
                configuration: config, delegate: self, delegateQueue: nil
            )
            self.startNext()
        }
    }

    func cancel() {
        stateQueue.async {
            self.onFinish = nil
            self.activeTask?.cancel()
            self.activeTask = nil
            self.session?.invalidateAndCancel()
            self.session = nil
            self.results = []
        }
    }

    private func startNext() {
        guard onFinish != nil, let session = session else { return }
        guard position < Self.endpoints.count else {
            let callback = onFinish
            let completed = results
            onFinish = nil
            activeTask = nil
            self.session = nil
            session.invalidateAndCancel()
            callback?(completed)
            return
        }
        let endpoint = Self.endpoints[position]
        var request = URLRequest(
            url: endpoint.url,
            cachePolicy: .reloadIgnoringLocalCacheData,
            timeoutInterval: 10
        )
        request.httpMethod = "HEAD"
        request.setValue("WebReader-iOS12-HTTPS-Diagnostic", forHTTPHeaderField:
            "User-Agent")
        let task = session.dataTask(with: request)
        activeTask = task
        task.resume()
    }

    func urlSession(
        _ session: URLSession, task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        // A 3xx HTTP response is useful TLS evidence; never follow the URL
        // or claim that a release asset was downloaded.
        completionHandler(nil)
    }

    func urlSession(
        _ session: URLSession,
        dataTask: URLSessionDataTask,
        didReceive response: URLResponse,
        completionHandler: @escaping (URLSession.ResponseDisposition) -> Void
    ) {
        // HEAD response is enough. Never read body data or write files.
        completionHandler(.cancel)
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didCompleteWithError error: Error?
    ) {
        stateQueue.async {
            guard self.session === session,
                let current = self.activeTask,
                current === task,
                self.onFinish != nil,
                self.position < Self.endpoints.count
            else { return }
            let endpoint = Self.endpoints[self.position]
            let status = (task.response as? HTTPURLResponse)?.statusCode
            let nsError = error as NSError?
            self.results.append(WebReaderHTTPSProbeResult(
                label: endpoint.label,
                host: endpoint.url.host ?? "desconhecido",
                httpStatus: status,
                errorDomain: status == nil ? nsError?.domain : nil,
                errorCode: status == nil ? nsError?.code : nil
            ))
            self.activeTask = nil
            self.position += 1
            self.startNext()
        }
    }
}
