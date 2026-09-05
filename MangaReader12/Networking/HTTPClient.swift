import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

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
        guard let url = URL(string: rawValue),
              let scheme = url.scheme?.lowercased() else {
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
        guard let scheme = url.scheme?.lowercased(),
              let host = url.host?.lowercased() else {
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
    case timedOut
    case cancelled
    case transport(code: Int, message: String)

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
        case .timedOut:
            return "The request timed out."
        case .cancelled:
            return "The request was cancelled."
        case .transport(let code, let message):
            return "Network transport error \(code): \(message)"
        }
    }
}

struct HTTPResponseBuffer {
    let maxBytes: Int
    private(set) var data = Data()

    init(maxBytes: Int) {
        self.maxBytes = max(1, maxBytes)
    }

    mutating func append(_ chunk: Data) throws {
        guard chunk.count <= maxBytes - data.count else {
            let attemptedSize = data.count + chunk.count
            throw HTTPClientError.responseTooLarge(attemptedSize)
        }
        data.append(chunk)
    }

    func validateExpectedContentLength(_ length: Int64) throws {
        guard length > 0 else { return }
        guard length <= Int64(maxBytes) else {
            let reportedSize = length > Int64(Int.max) ? Int.max : Int(length)
            throw HTTPClientError.responseTooLarge(reportedSize)
        }
    }
}

private final class HTTPTaskState {
    let originalURL: String
    let completion: (Result<HTTPResponse, Error>) -> Void
    var response: HTTPURLResponse?
    var buffer: HTTPResponseBuffer
    var redirectCount = 0

    init(
        originalURL: String,
        maxResponseBytes: Int,
        completion: @escaping (Result<HTTPResponse, Error>) -> Void
    ) {
        self.originalURL = originalURL
        self.buffer = HTTPResponseBuffer(maxBytes: maxResponseBytes)
        self.completion = completion
    }
}

private final class HTTPClientSessionDelegate: NSObject, URLSessionDataDelegate, URLSessionTaskDelegate {
    private let policy: HTTPPolicy
    private let lock = NSLock()
    private var states: [Int: HTTPTaskState] = [:]

    init(policy: HTTPPolicy) {
        self.policy = policy
        super.init()
    }

    func register(
        task: URLSessionDataTask,
        originalURL: String,
        completion: @escaping (Result<HTTPResponse, Error>) -> Void
    ) {
        let state = HTTPTaskState(
            originalURL: originalURL,
            maxResponseBytes: policy.maxResponseBytes,
            completion: completion
        )

        lock.lock()
        states[task.taskIdentifier] = state
        lock.unlock()
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        guard let destination = request.url else {
            fail(taskIdentifier: task.taskIdentifier, error: HTTPClientError.invalidURL)
            completionHandler(nil)
            return
        }

        do {
            _ = try policy.validatedURL(destination.absoluteString)
        } catch {
            fail(taskIdentifier: task.taskIdentifier, error: error)
            completionHandler(nil)
            return
        }

        var shouldFail = false

        lock.lock()
        if let state = states[task.taskIdentifier] {
            state.redirectCount += 1
            shouldFail = state.redirectCount > policy.maxRedirects
        }
        lock.unlock()

        if shouldFail {
            fail(taskIdentifier: task.taskIdentifier, error: HTTPClientError.tooManyRedirects)
            completionHandler(nil)
        } else {
            completionHandler(request)
        }
    }

    func urlSession(
        _ session: URLSession,
        dataTask: URLSessionDataTask,
        didReceive response: URLResponse,
        completionHandler: @escaping (URLSession.ResponseDisposition) -> Void
    ) {
        guard let httpResponse = response as? HTTPURLResponse else {
            fail(taskIdentifier: dataTask.taskIdentifier, error: HTTPClientError.invalidResponse)
            completionHandler(.cancel)
            return
        }

        do {
            try state(for: dataTask.taskIdentifier)?.buffer.validateExpectedContentLength(response.expectedContentLength)
        } catch {
            fail(taskIdentifier: dataTask.taskIdentifier, error: error)
            completionHandler(.cancel)
            return
        }

        lock.lock()
        states[dataTask.taskIdentifier]?.response = httpResponse
        lock.unlock()

        completionHandler(.allow)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        var failure: Error?

        lock.lock()
        if let state = states[dataTask.taskIdentifier] {
            do {
                try state.buffer.append(data)
            } catch {
                failure = error
            }
        }
        lock.unlock()

        if let failure = failure {
            fail(taskIdentifier: dataTask.taskIdentifier, error: failure)
            dataTask.cancel()
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let state = takeState(taskIdentifier: task.taskIdentifier) else {
            return
        }

        if let error = error {
            state.completion(.failure(HTTPClient.classifyTransportError(error)))
            return
        }

        guard let httpResponse = state.response else {
            state.completion(.failure(HTTPClientError.invalidResponse))
            return
        }

        var headers: [String: String] = [:]
        for (key, value) in httpResponse.allHeaderFields {
            headers[String(describing: key)] = String(describing: value)
        }

        let result = HTTPResponse(
            statusCode: httpResponse.statusCode,
            headers: headers,
            data: state.buffer.data,
            finalURL: httpResponse.url?.absoluteString ?? state.originalURL
        )

        state.completion(.success(result))
    }

    private func state(for taskIdentifier: Int) -> HTTPTaskState? {
        lock.lock()
        let state = states[taskIdentifier]
        lock.unlock()
        return state
    }

    private func takeState(taskIdentifier: Int) -> HTTPTaskState? {
        lock.lock()
        let state = states.removeValue(forKey: taskIdentifier)
        lock.unlock()
        return state
    }

    private func fail(taskIdentifier: Int, error: Error) {
        guard let state = takeState(taskIdentifier: taskIdentifier) else {
            return
        }
        state.completion(.failure(error))
    }
}

final class HTTPClient {
    let policy: HTTPPolicy

    private let sessionDelegate: HTTPClientSessionDelegate
    private let session: URLSession

    init(policy: HTTPPolicy, cookieStorage: HTTPCookieStorage = .shared) {
        self.policy = policy
        self.sessionDelegate = HTTPClientSessionDelegate(policy: policy)

        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = policy.timeout
        configuration.timeoutIntervalForResource = policy.timeout + 10
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.httpShouldSetCookies = true
        configuration.httpCookieStorage = cookieStorage
        configuration.httpAdditionalHeaders = ["User-Agent": policy.userAgent]

        self.session = URLSession(
            configuration: configuration,
            delegate: sessionDelegate,
            delegateQueue: nil
        )
    }

    deinit {
        session.invalidateAndCancel()
    }

    @discardableResult
    func send(
        _ request: HTTPRequest,
        completion: @escaping (Result<HTTPResponse, Error>) -> Void
    ) -> URLSessionDataTask? {
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

        let task = session.dataTask(with: urlRequest)
        sessionDelegate.register(
            task: task,
            originalURL: request.url,
            completion: completion
        )
        task.resume()
        return task
    }

    static func classifyTransportError(_ error: Error) -> HTTPClientError {
        guard let urlError = error as? URLError else {
            return .transport(code: -1, message: error.localizedDescription)
        }

        switch urlError.code {
        case .timedOut:
            return .timedOut
        case .cancelled:
            return .cancelled
        default:
            return .transport(code: urlError.errorCode, message: urlError.localizedDescription)
        }
    }
}
