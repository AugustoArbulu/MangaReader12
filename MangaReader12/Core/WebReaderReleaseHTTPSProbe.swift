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
    let finalHost: String?
    let redirectsFollowed: Int

    var reportLine: String {
        let destination = finalHost != nil && finalHost != host ?
            " → " + (finalHost ?? host) : ""
        let suffix = redirectsFollowed > 0 ?
            " • redirects: " + String(redirectsFollowed) : ""
        if let status = httpStatus {
            return label + " [" + host + destination + "]: HTTPS respondeu, HTTP " +
                String(status) + suffix
        }
        let domain = errorDomain ?? "desconhecido"
        return label + " [" + host + destination + "]: falha " + domain + " " +
            String(errorCode ?? 0) + suffix
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
        ),
        // Verified GitHub CLI public Release v2.103.2; 1,971-byte
        // checksums asset, tested with HEAD ONLY. It is not a WebReader IPA.
        Endpoint(
            label: "Asset real (GitHub CLI)",
            url: URL(string:
                "https://github.com/cli/cli/releases/download/v2.103.2/" +
                "gh_2.103.2_checksums.txt"
            )!
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
    private var redirectCount = 0

    /// A GitHub Release asset may redirect to a signed, temporary CDN URL.
    /// No redirects are permitted for the first three fixed diagnostic URLs.
    /// Never follows to an arbitrary website, a plain HTTP URL or a URL with
    /// embedded credentials. The request remains HEAD throughout.
    static func permitsAssetRedirect(
        _ url: URL, forEndpointIndex index: Int, alreadyFollowed: Int
    ) -> Bool {
        guard index == 3, alreadyFollowed < 2,
              let components = URLComponents(
                url: url, resolvingAgainstBaseURL: false
              ),
              components.scheme == "https",
              components.user == nil, components.password == nil,
              components.port == nil,
              components.host == "release-assets.githubusercontent.com" ||
                  components.host == "objects.githubusercontent.com"
        else { return false }
        return true
    }

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
            self.redirectCount = 0

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
        redirectCount = 0
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
        // Follow only known GitHub release-asset hosts for the dedicated
        // GitHub CLI checksum probe. The other three probes never redirect.
        // Authentication or a WebReader update is NEVER inferred from this.
        stateQueue.async {
            guard self.session === session,
                  self.activeTask === task,
                  self.onFinish != nil,
                  let next = request.url,
                  request.httpMethod == "HEAD",
                  Self.permitsAssetRedirect(
                      next, forEndpointIndex: self.position,
                      alreadyFollowed: self.redirectCount
                  )
            else {
                completionHandler(nil)
                return
            }
            self.redirectCount += 1
            completionHandler(request)
        }
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
                errorCode: status == nil ? nsError?.code : nil,
                finalHost: task.response?.url?.host,
                redirectsFollowed: self.redirectCount
            ))
            self.activeTask = nil
            self.position += 1
            self.startNext()
        }
    }
}
