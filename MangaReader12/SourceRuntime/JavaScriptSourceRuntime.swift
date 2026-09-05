import Foundation
import JavaScriptCore

@objc private protocol NativeBridgeExports: JSExport {
    func log(_ message: String)
    func storageGet(_ key: String) -> String?
    func storageSet(_ key: String, _ value: String)
    func cookieGet(_ urlString: String) -> String
    func cookieSet(_ urlString: String, _ cookieHeader: String)
    func resolveUrl(_ baseURL: String, _ relativeURL: String) -> String
    func get(_ urlString: String, _ callback: JSValue)
    func post(_ urlString: String, _ body: String, _ callback: JSValue)
    func httpRequest(_ requestJSON: String, _ callback: JSValue)
}

private struct BridgeRequest: Codable {
    let method: String?
    let url: String
    let headers: [String: String]?
    let body: String?
}

private struct BridgeResponse: Codable {
    let ok: Bool
    let status: Int?
    let headers: [String: String]?
    let body: String?
    let finalURL: String?
    let error: String?
}

private final class NativeBridge: NSObject, NativeBridgeExports {
    private let sourceID: String
    private let storage: SourceStorage
    private let httpClient: HTTPClient
    private let callbackQueue: DispatchQueue

    init(sourceID: String, httpClient: HTTPClient, callbackQueue: DispatchQueue) {
        self.sourceID = sourceID
        self.storage = SourceStorage(sourceID: sourceID)
        self.httpClient = httpClient
        self.callbackQueue = callbackQueue
        super.init()
    }

    func log(_ message: String) {
        print("[Source:\(sourceID)] \(message)")
    }

    func storageGet(_ key: String) -> String? {
        return storage.string(forKey: key)
    }

    func storageSet(_ key: String, _ value: String) {
        storage.set(value, forKey: key)
    }

    func cookieGet(_ urlString: String) -> String {
        guard let url = URL(string: urlString),
              let cookies = HTTPCookieStorage.shared.cookies(for: url) else {
            return ""
        }

        return cookies
            .map { "\($0.name)=\($0.value)" }
            .joined(separator: "; ")
    }

    func cookieSet(_ urlString: String, _ cookieHeader: String) {
        guard let url = URL(string: urlString) else { return }
        let cookies = HTTPCookie.cookies(
            withResponseHeaderFields: ["Set-Cookie": cookieHeader],
            for: url
        )
        HTTPCookieStorage.shared.setCookies(cookies, for: url, mainDocumentURL: nil)
    }

    func resolveUrl(_ baseURL: String, _ relativeURL: String) -> String {
        guard let base = URL(string: baseURL),
              let resolved = URL(string: relativeURL, relativeTo: base)?.absoluteURL else {
            return relativeURL
        }
        return resolved.absoluteString
    }

    func get(_ urlString: String, _ callback: JSValue) {
        perform(
            HTTPRequest(method: "GET", url: urlString),
            callback: callback
        )
    }

    func post(_ urlString: String, _ body: String, _ callback: JSValue) {
        perform(
            HTTPRequest(
                method: "POST",
                url: urlString,
                headers: ["Content-Type": "application/x-www-form-urlencoded; charset=utf-8"],
                body: body.data(using: .utf8)
            ),
            callback: callback
        )
    }

    func httpRequest(_ requestJSON: String, _ callback: JSValue) {
        guard let data = requestJSON.data(using: .utf8) else {
            deliver(
                BridgeResponse(ok: false, status: nil, headers: nil, body: nil, finalURL: nil, error: "Invalid request JSON."),
                callback: callback
            )
            return
        }

        do {
            let bridgeRequest = try JSONDecoder().decode(BridgeRequest.self, from: data)
            let request = HTTPRequest(
                method: bridgeRequest.method ?? "GET",
                url: bridgeRequest.url,
                headers: bridgeRequest.headers ?? [:],
                body: bridgeRequest.body?.data(using: .utf8)
            )
            perform(request, callback: callback)
        } catch {
            deliver(
                BridgeResponse(ok: false, status: nil, headers: nil, body: nil, finalURL: nil, error: error.localizedDescription),
                callback: callback
            )
        }
    }

    private func perform(_ request: HTTPRequest, callback: JSValue) {
        httpClient.send(request) { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let response):
                let body = String(data: response.data, encoding: .utf8)
                    ?? response.data.base64EncodedString()
                self.deliver(
                    BridgeResponse(
                        ok: true,
                        status: response.statusCode,
                        headers: response.headers,
                        body: body,
                        finalURL: response.finalURL,
                        error: nil
                    ),
                    callback: callback
                )

            case .failure(let error):
                self.deliver(
                    BridgeResponse(
                        ok: false,
                        status: nil,
                        headers: nil,
                        body: nil,
                        finalURL: nil,
                        error: error.localizedDescription
                    ),
                    callback: callback
                )
            }
        }
    }

    private func deliver(_ response: BridgeResponse, callback: JSValue) {
        let json: String
        do {
            let data = try JSONEncoder().encode(response)
            json = String(data: data, encoding: .utf8) ?? "{\"ok\":false,\"error\":\"Encoding failed\"}"
        } catch {
            json = "{\"ok\":false,\"error\":\"Encoding failed\"}"
        }

        callbackQueue.async {
            callback.call(withArguments: [json])
        }
    }
}

final class JavaScriptSourceRuntime {
    private let manifest: SourceManifest
    private let queue: DispatchQueue
    private let httpClient: HTTPClient
    private var context: JSContext?
    private var bridge: NativeBridge?
    private var lastException: String?

    init(manifest: SourceManifest) {
        self.manifest = manifest
        self.queue = DispatchQueue(label: "com.mangareader12.source-runtime.\(manifest.id)")
        self.httpClient = HTTPClient(
            policy: HTTPPolicy(allowedDomains: manifest.domains)
        )

        queue.sync {
            let context = JSContext()
            self.context = context

            let bridge = NativeBridge(
                sourceID: manifest.id,
                httpClient: self.httpClient,
                callbackQueue: self.queue
            )
            self.bridge = bridge
            context?.setObject(bridge, forKeyedSubscript: "Native" as NSString)
            context?.exceptionHandler = { [weak self] _, exception in
                self?.lastException = exception?.toString() ?? "Unknown JavaScript exception"
            }
        }
    }

    func load(script: String, completion: @escaping (Result<Void, Error>) -> Void) {
        queue.async {
            self.lastException = nil
            self.context?.evaluateScript(script)

            if let message = self.lastException {
                completion(.failure(SourceRuntimeError.javaScriptException(message)))
                return
            }

            guard let source = self.context?.objectForKeyedSubscript("source"),
                  !source.isUndefined,
                  !source.isNull else {
                completion(.failure(SourceRuntimeError.missingSourceObject))
                return
            }

            completion(.success(()))
        }
    }

    func call(_ functionName: String, arguments: [Any] = [], completion: @escaping (Result<Any?, Error>) -> Void) {
        queue.async {
            self.lastException = nil

            guard let source = self.context?.objectForKeyedSubscript("source"),
                  !source.isUndefined,
                  !source.isNull else {
                completion(.failure(SourceRuntimeError.missingSourceObject))
                return
            }

            guard let function = source.objectForKeyedSubscript(functionName),
                  !function.isUndefined,
                  !function.isNull else {
                completion(.failure(SourceRuntimeError.missingFunction(functionName)))
                return
            }

            let value = source.invokeMethod(functionName, withArguments: arguments)

            if let message = self.lastException {
                completion(.failure(SourceRuntimeError.javaScriptException(message)))
                return
            }

            completion(.success(value?.toObject()))
        }
    }

    func diagnosticBridgeCheck() -> Result<String, Error> {
        return queue.sync {
            self.lastException = nil
            let value = self.context?.evaluateScript(
                "Native.resolveUrl('https://example.com/series/1/', '../2')"
            )

            if let message = self.lastException {
                return .failure(SourceRuntimeError.javaScriptException(message))
            }

            guard let resolved = value?.toString(), resolved.contains("example.com") else {
                return .failure(SourceRuntimeError.invalidDiagnosticResult)
            }

            return .success(resolved)
        }
    }
}

enum SourceRuntimeError: Error, LocalizedError {
    case missingSourceObject
    case missingFunction(String)
    case javaScriptException(String)
    case invalidDiagnosticResult

    var errorDescription: String? {
        switch self {
        case .missingSourceObject:
            return "The extension did not expose a source object."
        case .missingFunction(let name):
            return "The source function '\(name)' is missing."
        case .javaScriptException(let message):
            return "JavaScript exception: \(message)"
        case .invalidDiagnosticResult:
            return "JavaScriptCore bridge diagnostic returned an invalid result."
        }
    }
}
