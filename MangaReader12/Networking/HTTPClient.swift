import Foundation

struct HTTPPolicy {
    let allowedDomains: [String]
    let timeout: TimeInterval
    let maxRedirects: Int
    let maxResponseBytes: Int
    let userAgent: String
    let allowsInsecureHTTP: Bool

    init(
        allowedDomains: [String],
        timeout: TimeInterval = 20,
        maxRedirects: Int = 5,
        maxResponseBytes: Int = 8 * 1024 * 1024,
        userAgent: String = "MangaReader12/0.1 (iOS 12+)",
        allowsInsecureHTTP: Bool = false
    ) {
        self.allowedDomains = allowedDomains.map { $0.lowercased() }
        self.timeout = max(1, min(timeout, 60))
        self.maxRedirects = max(0, min(maxRedirects, 10))
        self.maxResponseBytes = max(1024, maxResponseBytes)
        self.userAgent = userAgent
        self.allowsInsecureHTTP = allowsInsecureHTTP
    }

    func validatedURL(_ rawValue: String) throws -> URL {
        guard let url = URL(string: rawValue), let scheme = url.scheme?.lowercased() else {
            throw HTTPClientError.invalidURL
        }

        if scheme != "https" && !(allowsInsecureHTTP && scheme == "http") {
            throw HTTPClientError.blockedScheme(scheme)
        }

        guard let host = url.host?.lowercased(), isHostAllowed(host) else {
            throw HTTPClientError.domainNotAllowed(url.host ?? "")
        }

        return url
    }

    func isURLAllowed(_ url: URL) -> Bool {
        guard let scheme = url.scheme?.lowercased(), let host = url.host?.lowercased() else {
            return false
        }
        let schemeAllowed = scheme == "https" || (allowsInsecureHTTP && scheme == "http")
        return schemeAllowed && isHostAllowed(host)
    }

    private func isHostAllowed(_ host: String) -> Bool {
        return allowedDomains.contains { domain in
            host == domain || host.hasSuffix("." + domain)
        }
    }
}

struct HTTPRequest {
    var method: String
    var url: String
    var headers: [String: String]
    var body: Data?

    init(method: String = "GET", url: String, headers: [String: String] = [:], body: Data? = nil) {
        self.method = method
        self.url = url
        self.headers = headers
        self.body = body
    }
}

struct HTTPResponse {
    let statusCode: Int
    let headers: [String: String]
    let data: Data
    let finalURL: String
}

enum HTTPClientError: Error, LocalizedError {
    case invalidURL
    case blockedScheme(String)
    case domainNotAllowed(String)
    case invalidResponse
    case responseTooLarge(Int)
    case tooManyRedirects

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL."
        case .blockedScheme(let scheme):
            return "Blocked URL scheme: \(scheme)."
        case .domainNotAllowed(let domain):
            return "Domain is not allowed for this source: \(domain)."
        case .invalidResponse:
            return "The server returned an invalid HTTP response."
        case .responseTooLarge(let bytes):
            return "Response exceeded the allowed size (\(bytes) bytes)."
        case .tooManyRedirects:
            return "Redirect limit exceeded."
        }
    }
}

private final class RedirectGuard: NSObject, URLSessionTaskDelegate {
    private let policy: HTTPPolicy
    private let lock = NSLock()
    private var redirectCounts: [Int: Int] = [:]

    init(policy: HTTPPolicy) {
        self.policy = policy
        super.init()
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        guard let destination = request.url, policy.isURLAllowed(destination) else {
            completionHandler(nil)
            return
        }

        lock.lock()
        let nextCount = (redirectCounts[task.taskIdentifier] ?? 0) + 1
        redirectCounts[task.taskIdentifier] = nextCount
        lock.unlock()

        if nextCount > policy.maxRedirects {
            completionHandler(nil)
        } else {
            completionHandler(request)
        }
    }

    func finish(taskIdentifier: Int) {
        lock.lock()
        redirectCounts.removeValue(forKey: taskIdentifier)
        lock.unlock()
    }
}

final class HTTPClient {
    let policy: HTTPPolicy
    private let redirectGuard: RedirectGuard
    private let session: URLSession

    init(policy: HTTPPolicy, cookieStorage: HTTPCookieStorage = .shared) {
        self.policy = policy
        self.redirectGuard = RedirectGuard(policy: policy)

        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = policy.timeout
        configuration.timeoutIntervalForResource = policy.timeout + 10
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.httpShouldSetCookies = true
        configuration.httpCookieStorage = cookieStorage
        configuration.httpAdditionalHeaders = ["User-Agent": policy.userAgent]

        self.session = URLSession(
            configuration: configuration,
            delegate: redirectGuard,
            delegateQueue: nil
        )
    }

    deinit {
        session.invalidateAndCancel()
    }

    @discardableResult
    func send(_ request: HTTPRequest, completion: @escaping (Result<HTTPResponse, Error>) -> Void) -> URLSessionDataTask? {
        let url: URL
        do {
            url = try policy.validatedURL(request.url)
        } catch {
            completion(.failure(error))
            return nil
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = request.method.uppercased()
        urlRequest.httpBody = request.body
        urlRequest.timeoutInterval = policy.timeout

        for (key, value) in request.headers {
            urlRequest.setValue(value, forHTTPHeaderField: key)
        }

        var task: URLSessionDataTask? = nil
        task = session.dataTask(with: urlRequest) { [weak self] data, response, error in
            defer {
                if let identifier = task?.taskIdentifier {
                    self?.redirectGuard.finish(taskIdentifier: identifier)
                }
            }

            if let error = error {
                completion(.failure(error))
                return
            }

            guard let httpResponse = response as? HTTPURLResponse else {
                completion(.failure(HTTPClientError.invalidResponse))
                return
            }

            let payload = data ?? Data()
            guard payload.count <= (self?.policy.maxResponseBytes ?? 0) else {
                completion(.failure(HTTPClientError.responseTooLarge(payload.count)))
                return
            }

            var headers: [String: String] = [:]
            for (key, value) in httpResponse.allHeaderFields {
                headers[String(describing: key)] = String(describing: value)
            }

            let result = HTTPResponse(
                statusCode: httpResponse.statusCode,
                headers: headers,
                data: payload,
                finalURL: httpResponse.url?.absoluteString ?? request.url
            )
            completion(.success(result))
        }
        task.resume()
        return task
    }
}
