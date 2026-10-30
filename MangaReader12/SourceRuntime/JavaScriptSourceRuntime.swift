import Foundation
import JavaScriptCore
import WebKit

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
    func htmlSelect(_ html: String, _ selectorsJSON: String, _ callback: JSValue)
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

    func htmlSelect(_ html: String, _ selectorsJSON: String, _ callback: JSValue) {
        // A standalone local DOMParser processes downloaded markup as inert
        // data. Its execution does not navigate to the source site, download
        // referenced resources or evaluate scripts embedded in that markup.
        HTMLSelectorService.shared.select(html: html, selectorsJSON: selectorsJSON) {
            [weak self] result in
            guard let self = self else { return }
            self.callbackQueue.async {
                callback.call(withArguments: [result])
            }
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

private final class SourcePendingCall {
    var finished = false
}


// MARK: - Inert HTML selector service for Keiyoushi source adapters.
//
// WKWebView supplies the WebKit HTML5 DOMParser and CSS selector engine already
// present in iOS 12; only inert DOMParser.parseFromString() is used on fetched
// markup. The only loaded page is a local empty HTML document. No site
// JavaScript runs; requests to third-party image/script resources are not
// generated by the parser. Results are bounded JSON values.
private final class HTMLSelectorService: NSObject, WKNavigationDelegate {
    static let shared = HTMLSelectorService()

    private var webView: WKWebView?
    private var ready = false
    private var jobs: [(String, String, (String) -> Void)] = []
    private var busy = false

    func select(
        html: String,
        selectorsJSON: String,
        completion: @escaping (String) -> Void
    ) {
        guard html.utf8.count <= 3 * 1024 * 1024,
              selectorsJSON.utf8.count <= 8192,
              let data = selectorsJSON.data(using: .utf8),
              let descriptors = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              descriptors.count <= 12 else {
            completion("{\"error\":\"HTML selector input exceeds safe limits.\"}")
            return
        }
        DispatchQueue.main.async {
            guard self.jobs.count < 4 else {
                completion(Self.errorJSON("HTML selector queue is full."))
                return
            }
            self.jobs.append((html, selectorsJSON, completion))
            self.ensureWebView()
            self.next()
        }
    }

    private func ensureWebView() {
        guard webView == nil else { return }
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.preferences.javaScriptEnabled = true
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = self
        webView = view
        view.loadHTMLString("<!doctype html><html><body></body></html>", baseURL: nil)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        ready = true
        next()
    }

    func webView(
        _ webView: WKWebView,
        didFail navigation: WKNavigation!,
        withError error: Error
    ) {
        failAll("HTML selector initialization failed: " + error.localizedDescription)
    }

    func webView(
        _ webView: WKWebView,
        didFailProvisionalNavigation navigation: WKNavigation!,
        withError error: Error
    ) {
        failAll("HTML selector initialization failed: " + error.localizedDescription)
    }

    private func failAll(_ reason: String) {
        ready = false
        busy = false
        webView?.navigationDelegate = nil
        webView = nil
        let tasks = jobs
        jobs.removeAll()
        for job in tasks {
            job.2(Self.errorJSON(reason))
        }
    }

    private static func errorJSON(_ reason: String) -> String {
        let value = ["error": reason]
        guard let data = try? JSONSerialization.data(withJSONObject: value),
              let text = String(data: data, encoding: .utf8) else {
            return "{\"error\":\"HTML parser unavailable\"}"
        }
        return text
    }

    private static func javascriptLiteral(_ value: String) -> String? {
        guard let encoded = try? JSONSerialization.data(withJSONObject: [value]),
              let literal = String(data: encoded, encoding: .utf8) else {
            return nil
        }
        return literal + "[0]"
    }

    private func next() {
        guard ready, !busy, !jobs.isEmpty, let browser = webView else { return }
        busy = true
        let job = jobs.removeFirst()
        guard let htmlLiteral = Self.javascriptLiteral(job.0),
              let selectorsLiteral = Self.javascriptLiteral(job.1) else {
            busy = false
            job.2(Self.errorJSON("Could not encode HTML for inert parsing."))
            next()
            return
        }

        let script = """
        (function () {
          "use strict";
          var html = \(htmlLiteral);
          var specs = JSON.parse(\(selectorsLiteral));
          var doc = new DOMParser().parseFromString(html, "text/html");
          var result = {};
          function info(node) {
            if (!node) return null;
            var attrs = {};
            for (var k = 0; k < node.attributes.length; k++) {
              var a = node.attributes[k];
              var maxValue = a.name === "data-page" ? (2 * 1024 * 1024) : 4096;
              if (a.name.length < 100 && a.value.length <= maxValue) attrs[a.name] = a.value;
            }
            return {text: (node.textContent || "").trim().slice(0, 8192),
                    attrs: attrs};
          }
          Object.keys(specs).forEach(function (name) {
            var config = specs[name];
            if (!config || typeof config.selector !== "string" ||
                config.selector.length > 500) throw new Error("Invalid selector");
            var matches = doc.querySelectorAll(config.selector);
            var array = [];
            for (var i = 0; i < Math.min(200, matches.length); i++) {
              var node = matches[i];
              var item = info(node);
              item.fields = {};
              var fields = config.fields || {};
              Object.keys(fields).slice(0, 16).forEach(function (field) {
                var target = fields[field];
                if (typeof target !== "string" || target.length > 500)
                  throw new Error("Invalid nested selector");
                item.fields[field] = info(node.querySelector(target));
              });
              array.push(item);
            }
            result[name] = array;
          });
          return JSON.stringify({results: result});
        })();
        """
        browser.evaluateJavaScript(script) { [weak self] value, error in
            guard let self = self else { return }
            if let error = error {
                job.2(Self.errorJSON("HTML selector error: " + error.localizedDescription))
            } else if let text = value as? String, text.utf8.count <= 4 * 1024 * 1024 {
                job.2(text)
            } else {
                job.2(Self.errorJSON("HTML selector output exceeded safe limits."))
            }
            self.busy = false
            self.next()
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
            do {
                try self.loadUnlocked(script: script)
                completion(.success(()))
            } catch {
                completion(.failure(error))
            }
        }
    }

    func validateContract(completion: @escaping (Result<Void, Error>) -> Void) {
        queue.async {
            do {
                _ = try self.sourceObjectUnlocked(validatingContract: true)
                completion(.success(()))
            } catch {
                completion(.failure(error))
            }
        }
    }

    func call(_ functionName: String, arguments: [Any] = [], completion: @escaping (Result<Any?, Error>) -> Void) {
        queue.async {
            do {
                let value = try self.invokeUnlocked(functionName, arguments: arguments)
                completion(.success(value?.toObject()))
            } catch {
                completion(.failure(error))
            }
        }
    }

    func callDecoded<T: Decodable>(
        _ functionName: String,
        arguments: [Any] = [],
        as type: T.Type,
        completion: @escaping (Result<T, Error>) -> Void
    ) {
        queue.async {
            // Existing demo sources return a value synchronously. Real HTTP
            // sources can instead accept one additional callback argument and
            // return undefined. All callbacks and the timeout are finalized
            // on the private serial JS queue, never on the UI thread.
            let pending = SourcePendingCall()
            let finish: (Result<T, Error>) -> Void = { result in
                guard !pending.finished else { return }
                pending.finished = true
                completion(result)
            }

            let callbackBlock: @convention(block) (JSValue) -> Void = { [weak self] response in
                guard let self = self else { return }
                self.queue.async {
                    guard !pending.finished else { return }
                    do {
                        try self.raiseSourceFailureIfNeeded(response)
                        finish(.success(try self.decodeUnlocked(type, from: response)))
                    } catch {
                        finish(.failure(error))
                    }
                }
            }

            do {
                guard let context = self.context,
                      let callback = JSValue(object: callbackBlock, in: context) else {
                    throw SourceRuntimeError.invalidDiagnosticResult
                }
                let result = try self.invokeUnlocked(
                    functionName,
                    arguments: arguments + [callback],
                    allowAsync: true
                )
                if let result = result, !result.isUndefined, !result.isNull {
                    try self.raiseSourceFailureIfNeeded(result)
                    finish(.success(try self.decodeUnlocked(type, from: result)))
                } else {
                    // Selected Keiyoushi HTML adapters perform one HTTPS
                    // request followed by inert WebKit DOM selection.
                    let timeout: TimeInterval = self.manifest.id.hasPrefix("kei.") ? 40 : 25
                    self.queue.asyncAfter(deadline: .now() + timeout) {
                        guard !pending.finished else { return }
                        finish(.failure(SourceRuntimeError.sourceTimeout(functionName)))
                    }
                }
            } catch {
                finish(.failure(error))
            }
        }
    }

    private func raiseSourceFailureIfNeeded(_ response: JSValue) throws {
        let reason = response.objectForKeyedSubscript("__sourceError")
        if let reason = reason, !reason.isNull, !reason.isUndefined {
            throw SourceRuntimeError.remoteError(
                reason.toString() ?? "Falha na fonte."
            )
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

    func diagnosticSourceContractCheck() -> Result<String, Error> {
        return queue.sync {
            do {
                try self.loadUnlocked(script: Self.contractFixtureScript)
                _ = try self.sourceObjectUnlocked(validatingContract: true)

                let metadata: SourceMetadata = try self.decodeUnlocked(
                    SourceMetadata.self,
                    from: try self.invokeUnlocked("metadata", arguments: [])
                )
                let popular: SourcePagedMangaResult = try self.decodeUnlocked(
                    SourcePagedMangaResult.self,
                    from: try self.invokeUnlocked("popular", arguments: [1])
                )
                let search: SourcePagedMangaResult = try self.decodeUnlocked(
                    SourcePagedMangaResult.self,
                    from: try self.invokeUnlocked("search", arguments: ["fixture", 1, []])
                )
                let details: Manga = try self.decodeUnlocked(
                    Manga.self,
                    from: try self.invokeUnlocked("details", arguments: ["m1"])
                )
                let chapters: [Chapter] = try self.decodeUnlocked(
                    [Chapter].self,
                    from: try self.invokeUnlocked("chapters", arguments: ["m1"])
                )
                let pages: [Page] = try self.decodeUnlocked(
                    [Page].self,
                    from: try self.invokeUnlocked("pages", arguments: ["c1"])
                )

                guard metadata.id == manifest.id,
                      popular.items.count == 1,
                      search.items.count == 1,
                      details.id == "m1",
                      chapters.count == 1,
                      pages.count == 1 else {
                    throw SourceRuntimeError.invalidDiagnosticResult
                }

                return .success("6 methods + typed DTO decoding OK")
            } catch {
                return .failure(error)
            }
        }
    }

    private func loadUnlocked(script: String) throws {
        self.lastException = nil
        self.context?.evaluateScript(script)

        if let message = self.lastException {
            throw SourceRuntimeError.javaScriptException(message)
        }

        _ = try sourceObjectUnlocked(validatingContract: false)
    }

    private func sourceObjectUnlocked(validatingContract: Bool) throws -> JSValue {
        guard let source = self.context?.objectForKeyedSubscript("source"),
              !source.isUndefined,
              !source.isNull else {
            throw SourceRuntimeError.missingSourceObject
        }

        if validatingContract {
            for functionName in SourceContractFunction.requiredNames {
                guard let function = source.objectForKeyedSubscript(functionName),
                      !function.isUndefined,
                      !function.isNull else {
                    throw SourceRuntimeError.missingFunction(functionName)
                }
            }
        }

        return source
    }

    private func invokeUnlocked(
        _ functionName: String,
        arguments: [Any],
        allowAsync: Bool = false
    ) throws -> JSValue? {
        self.lastException = nil
        let source = try sourceObjectUnlocked(validatingContract: false)

        guard let function = source.objectForKeyedSubscript(functionName),
              !function.isUndefined,
              !function.isNull else {
            throw SourceRuntimeError.missingFunction(functionName)
        }

        let value = source.invokeMethod(functionName, withArguments: arguments)

        if let message = self.lastException {
            throw SourceRuntimeError.javaScriptException(message)
        }

        if value == nil || value?.isUndefined == true || value?.isNull == true {
            if allowAsync { return nil }
            throw SourceRuntimeError.invalidFunctionResult(functionName)
        }

        return value
    }

    private func decodeUnlocked<T: Decodable>(_ type: T.Type, from value: JSValue?) throws -> T {
        guard let object = value?.toObject(),
              JSONSerialization.isValidJSONObject(object) else {
            throw SourceRuntimeError.nonJSONResult
        }

        do {
            let data = try JSONSerialization.data(withJSONObject: object, options: [])
            return try JSONDecoder().decode(type, from: data)
        } catch {
            throw SourceRuntimeError.decodeFailed(error.localizedDescription)
        }
    }

    private static let contractFixtureScript = """
    var source = {
      metadata: function() {
        return {
          id: "diagnostic-source",
          name: "Diagnostic Source",
          lang: "en",
          version: "1.0.0"
        };
      },

      popular: function(page) {
        return {
          items: [
            {
              id: "m1",
              title: "Fixture Manga",
              cover: "https://example.com/cover.jpg",
              url: "https://example.com/manga/m1"
            }
          ],
          hasNextPage: false
        };
      },

      search: function(query, page, filters) {
        return {
          items: [
            {
              id: "m1",
              title: "Fixture Manga",
              cover: null,
              url: "https://example.com/manga/m1"
            }
          ],
          hasNextPage: false
        };
      },

      details: function(mangaId) {
        return {
          id: mangaId,
          title: "Fixture Manga",
          altTitles: ["Fixture Alt"],
          cover: "https://example.com/cover.jpg",
          author: "Fixture Author",
          artist: "Fixture Artist",
          description: "Local source contract fixture.",
          status: "ongoing",
          genres: ["Test"],
          url: "https://example.com/manga/" + mangaId
        };
      },

      chapters: function(mangaId) {
        return [
          {
            id: "c1",
            name: "Chapter 1",
            number: 1,
            volume: 1,
            date: "2026-09-05",
            scanlator: "Fixture",
            language: "en",
            url: "https://example.com/chapter/c1"
          }
        ];
      },

      pages: function(chapterId) {
        return [
          {
            index: 0,
            imageUrl: "https://example.com/page/1.jpg",
            headers: {
              Referer: "https://example.com/"
            }
          }
        ];
      }
    };
    """
}

enum SourceRuntimeError: Error, LocalizedError {
    case missingSourceObject
    case missingFunction(String)
    case javaScriptException(String)
    case invalidFunctionResult(String)
    case nonJSONResult
    case decodeFailed(String)
    case invalidDiagnosticResult
    case remoteError(String)
    case sourceTimeout(String)

    var errorDescription: String? {
        switch self {
        case .missingSourceObject:
            return "The extension did not expose a source object."
        case .missingFunction(let name):
            return "The source function '\(name)' is missing."
        case .javaScriptException(let message):
            return "JavaScript exception: \(message)"
        case .invalidFunctionResult(let name):
            return "The source function '\(name)' returned no usable value."
        case .nonJSONResult:
            return "The source returned a value that cannot be represented as JSON."
        case .decodeFailed(let message):
            return "Could not decode source result: \(message)"
        case .invalidDiagnosticResult:
            return "JavaScriptCore source contract diagnostic returned an invalid result."
        case .remoteError(let reason):
            return "Source failed: \(reason)"
        case .sourceTimeout(let method):
            return "Source timed out while calling \(method)."
        }
    }
}
