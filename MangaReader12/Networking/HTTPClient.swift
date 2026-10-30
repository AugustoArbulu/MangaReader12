import Foundation
import Network
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
    private let secureFallbackLock = NSLock()
    private var secureFallbacks: [UUID: MangaDexSecureHTTP1Operation] = [:]

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
            completion: { [weak self] result in
                guard case .failure(let error) = result,
                      let self = self,
                      self.shouldRetryMangaDexTLS(error: error, request: request) else {
                    completion(result)
                    return
                }
                self.retryMangaDexViaNetwork(request: request, completion: completion)
            }
        )
        task.resume()
        return task
    }

    private func shouldRetryMangaDexTLS(error: Error, request: HTTPRequest) -> Bool {
        guard let url = URL(string: request.url),
              url.scheme == "https",
              url.host?.lowercased() == "api.mangadex.org",
              request.method.uppercased() == "GET",
              request.body == nil else {
            return false
        }
        if case .transport(let code, _) = error as? HTTPClientError {
            return code == -1200
        }
        return false
    }

    private func retryMangaDexViaNetwork(
        request: HTTPRequest,
        completion: @escaping (Result<HTTPResponse, Error>) -> Void
    ) {
        let identifier = UUID()
        let operation = MangaDexSecureHTTP1Operation(
            request: request,
            limit: policy.maxResponseBytes
        )
        secureFallbackLock.lock()
        secureFallbacks[identifier] = operation
        secureFallbackLock.unlock()
        operation.start { [weak self] result in
            self?.secureFallbackLock.lock()
            self?.secureFallbacks.removeValue(forKey: identifier)
            self?.secureFallbackLock.unlock()
            completion(result)
        }
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


// MARK: - Narrow iOS 12 MangaDex TLS fallback (Network.framework)
//
// On some physical iOS 12.5.8 devices CFNetwork rejects the peer protocol
// version (-9836) for MangaDex, while NWConnection with default system
// TLS trust completes the handshake. Network.framework is a TLS byte stream,
// not an HTTP client: this intentionally bounded HTTP/1.1 GET transport is
// used only for api.mangadex.org after URLSession fails with -1200.
//
// No certificate trust override, HTTP downgrade, proxy, cookies, unrelated
// host retry, automatic redirect or unrestricted response size is permitted.
private enum MangaDexHTTP1Error: Error, LocalizedError {
    case badHTTPResponse
    case unsupportedTransferEncoding
    case unsupportedCompression
    case responseTooLarge
    case incompleteResponse
    case timedOut
    case transport(String)

    var errorDescription: String? {
        switch self {
        case .badHTTPResponse: return "MangaDex returned an invalid HTTP/1.1 response."
        case .unsupportedTransferEncoding: return "Unsupported MangaDex HTTP transfer encoding."
        case .unsupportedCompression: return "Compressed MangaDex response was not negotiated."
        case .responseTooLarge: return "MangaDex response exceeded the safe size limit."
        case .incompleteResponse: return "MangaDex closed the secure connection before finishing HTTP."
        case .timedOut: return "MangaDex secure Network.framework request timed out."
        case .transport(let value): return "MangaDex secure Network.framework transport: " + value
        }
    }
}

private enum MangaDexHTTP1Decoder {
    static let boundary = Data([13, 10, 13, 10])
    static let crlf = Data([13, 10])
    static let maxHeaderBytes = 32 * 1024

    // Nil means we need more bytes. Never return partial or unchecked data.
    static func decode(
        bytes: Data,
        complete: Bool,
        limit: Int,
        finalURL: String
    ) throws -> HTTPResponse? {
        guard let range = bytes.range(of: boundary) else {
            if bytes.count > maxHeaderBytes { throw MangaDexHTTP1Error.responseTooLarge }
            if complete { throw MangaDexHTTP1Error.incompleteResponse }
            return nil
        }
        guard range.lowerBound <= maxHeaderBytes else {
            throw MangaDexHTTP1Error.responseTooLarge
        }
        let headerData = bytes.subdata(in: 0..<range.lowerBound)
        guard let headerText = String(data: headerData, encoding: .utf8) else {
            throw MangaDexHTTP1Error.badHTTPResponse
        }
        let lines = headerText.components(separatedBy: "\r\n")
        guard let first = lines.first else { throw MangaDexHTTP1Error.badHTTPResponse }
        let statusParts = first.split(separator: " ", omittingEmptySubsequences: true)
        guard statusParts.count >= 2,
              (statusParts[0] == "HTTP/1.1" || statusParts[0] == "HTTP/1.0"),
              let status = Int(statusParts[1]),
              (100...599).contains(status),
              status != 100 else {
            throw MangaDexHTTP1Error.badHTTPResponse
        }
        var headers: [String: String] = [:]
        for line in lines.dropFirst() {
            guard !line.isEmpty,
                  let colon = line.firstIndex(of: ":") else {
                throw MangaDexHTTP1Error.badHTTPResponse
            }
            let name = String(line[..<colon]).lowercased()
            let value = String(line[line.index(after: colon)...])
                .trimmingCharacters(in: .whitespaces)
            guard !name.isEmpty, !name.contains(" "), !value.contains("\0") else {
                throw MangaDexHTTP1Error.badHTTPResponse
            }
            headers[name] = headers[name].map { $0 + ", " + value } ?? value
        }
        if let encoding = headers["content-encoding"],
           !encoding.isEmpty, encoding.lowercased() != "identity" {
            throw MangaDexHTTP1Error.unsupportedCompression
        }
        let bodyStart = range.upperBound
        let body = bytes.subdata(in: bodyStart..<bytes.count)
        var decoded: Data?
        if let transfer = headers["transfer-encoding"]?.lowercased(),
           !transfer.isEmpty {
            guard transfer == "chunked" else {
                throw MangaDexHTTP1Error.unsupportedTransferEncoding
            }
            decoded = try decodeChunked(body, limit: limit)
        } else if let length = headers["content-length"] {
            guard let count = Int(length), count >= 0, count <= limit else {
                throw MangaDexHTTP1Error.responseTooLarge
            }
            if body.count >= count {
                decoded = body.subdata(in: 0..<count)
            }
        } else if complete {
            guard body.count <= limit else { throw MangaDexHTTP1Error.responseTooLarge }
            decoded = body
        }
        guard let data = decoded else {
            if complete { throw MangaDexHTTP1Error.incompleteResponse }
            return nil
        }
        guard data.count <= limit else { throw MangaDexHTTP1Error.responseTooLarge }
        return HTTPResponse(
            statusCode: status,
            headers: headers,
            data: data,
            finalURL: finalURL
        )
    }

    private static func decodeChunked(_ bytes: Data, limit: Int) throws -> Data? {
        var cursor = 0
        var output = Data()
        while cursor < bytes.count {
            guard let lineEnd = bytes.range(of: crlf, in: cursor..<bytes.count)?.lowerBound else {
                if bytes.count - cursor > 128 { throw MangaDexHTTP1Error.badHTTPResponse }
                return nil
            }
            guard lineEnd - cursor <= 128,
                  let line = String(data: bytes.subdata(in: cursor..<lineEnd), encoding: .ascii),
                  let sizePart = line.split(separator: ";", maxSplits: 1).first,
                  let length = Int(sizePart.trimmingCharacters(in: .whitespaces), radix: 16),
                  length >= 0 else {
                throw MangaDexHTTP1Error.badHTTPResponse
            }
            cursor = lineEnd + 2
            guard length <= limit - output.count else {
                throw MangaDexHTTP1Error.responseTooLarge
            }
            guard length <= bytes.count - cursor else { return nil }
            if length == 0 {
                // The terminal zero-size chunk is followed by CRLF, or
                // optional HTTP trailer lines; no body data follows it.
                guard bytes.count - cursor >= 2 else { return nil }
                if bytes[cursor] == 13 && bytes[cursor + 1] == 10 {
                    return output
                }
                guard bytes.range(of: boundary, in: cursor..<bytes.count) != nil else {
                    return nil
                }
                return output
            }
            output.append(bytes.subdata(in: cursor..<(cursor + length)))
            cursor += length
            guard bytes.count - cursor >= 2 else { return nil }
            guard bytes[cursor] == 13, bytes[cursor + 1] == 10 else {
                throw MangaDexHTTP1Error.badHTTPResponse
            }
            cursor += 2
        }
        return nil
    }
}

private final class MangaDexSecureHTTP1Operation {
    private let request: HTTPRequest
    private let limit: Int
    private let queue = DispatchQueue(label: "com.mangareader12.mangadex-secure-http1")
    private var connection: NWConnection?
    private var buffer = Data()
    private var finished = false
    private var completion: ((Result<HTTPResponse, Error>) -> Void)?

    init(request: HTTPRequest, limit: Int) {
        self.request = request
        self.limit = min(max(1024, limit), 8 * 1024 * 1024)
    }

    func start(completion: @escaping (Result<HTTPResponse, Error>) -> Void) {
        self.completion = completion
        queue.async {
            guard let url = URL(string: self.request.url),
                  url.scheme == "https",
                  url.host?.lowercased() == "api.mangadex.org",
                  self.request.method.uppercased() == "GET",
                  self.request.body == nil,
                  let parts = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
                self.finish(.failure(MangaDexHTTP1Error.badHTTPResponse))
                return
            }

            let path = parts.percentEncodedPath.isEmpty ? "/" : parts.percentEncodedPath
            let query = parts.percentEncodedQuery.map { "?" + $0 } ?? ""
            var requestText = "GET " + path + query +
                " HTTP/1.1\r\nHost: api.mangadex.org\r\n" +
                "Connection: close\r\nAccept-Encoding: identity\r\n" +
                "User-Agent: MangaReader12/0.1 (iOS 12+)\r\n"
            let forbidden = Set([
                "host", "connection", "content-length", "transfer-encoding",
                "accept-encoding", "user-agent", "via"
            ])
            for (name, value) in self.request.headers.sorted(by: { $0.key < $1.key }) {
                guard !forbidden.contains(name.lowercased()),
                      !name.isEmpty,
                      name.range(of: "^[A-Za-z0-9-]+$", options: .regularExpression) != nil,
                      !value.contains("\r"), !value.contains("\n") else {
                    continue
                }
                requestText += name + ": " + value + "\r\n"
            }
            requestText += "\r\n"
            guard let bytes = requestText.data(using: .utf8) else {
                self.finish(.failure(MangaDexHTTP1Error.badHTTPResponse))
                return
            }

            // No custom verify block or TLS downgrade: iOS evaluates trust.
            let parameters = NWParameters(
                tls: NWProtocolTLS.Options(),
                tcp: NWProtocolTCP.Options()
            )
            let network = NWConnection(
                host: NWEndpoint.Host("api.mangadex.org"),
                port: NWEndpoint.Port(rawValue: 443)!,
                using: parameters
            )
            self.connection = network
            network.stateUpdateHandler = { [weak self] state in
                guard let self = self, !self.finished else { return }
                switch state {
                case .ready:
                    network.send(
                        content: bytes,
                        completion: .contentProcessed({ error in
                            if let error = error {
                                self.finish(.failure(MangaDexHTTP1Error.transport(
                                    String(describing: error)
                                )))
                            } else {
                                self.receiveMore()
                            }
                        })
                    )
                case .failed(let error):
                    self.finish(.failure(MangaDexHTTP1Error.transport(
                        String(describing: error)
                    )))
                case .cancelled:
                    self.finish(.failure(MangaDexHTTP1Error.transport("cancelled")))
                default:
                    break
                }
            }
            network.start(queue: self.queue)
            self.queue.asyncAfter(deadline: .now() + 22) { [weak self] in
                guard let self = self, !self.finished else { return }
                self.finish(.failure(MangaDexHTTP1Error.timedOut))
            }
        }
    }

    private func receiveMore() {
        guard let network = connection, !finished else { return }
        network.receive(minimumIncompleteLength: 1, maximumLength: 64 * 1024) {
            [weak self] data, _, complete, error in
            guard let self = self, !self.finished else { return }
            if let error = error {
                self.finish(.failure(MangaDexHTTP1Error.transport(
                    String(describing: error)
                )))
                return
            }
            if let data = data, !data.isEmpty {
                self.buffer.append(data)
            }
            // The extra 32 KB is reserved for HTTP headers. Chunk framing
            // consumes additional bytes so allow at most 64 KB of overhead.
            if self.buffer.count > self.limit + 64 * 1024 {
                self.finish(.failure(MangaDexHTTP1Error.responseTooLarge))
                return
            }
            do {
                if let response = try MangaDexHTTP1Decoder.decode(
                    bytes: self.buffer,
                    complete: complete,
                    limit: self.limit,
                    finalURL: self.request.url
                ) {
                    self.finish(.success(response))
                } else if !complete {
                    self.receiveMore()
                }
            } catch {
                self.finish(.failure(error))
            }
        }
    }

    private func finish(_ result: Result<HTTPResponse, Error>) {
        guard !finished else { return }
        finished = true
        connection?.stateUpdateHandler = nil
        connection?.cancel()
        connection = nil
        buffer.removeAll(keepingCapacity: false)
        let callback = completion
        completion = nil
        callback?(result)
    }
}
