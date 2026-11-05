#!/usr/bin/env python3
"""Offline integration test of the exact native iOS12 HTTPS probe Swift source.

No actual requests leave the macOS runner. Uses an ephemeral URLProtocol
fixture with response codes or synthetic TLS failures, never an IPA.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Core/WebReaderReleaseHTTPSProbe.swift"

HARNESS = r'''
import Foundation

func ensure(_ predicate: @autoclosure () -> Bool, _ reason: String) {
    if !predicate() { fatalError(reason) }
}
final class FakeHTTPSProtocol: URLProtocol {
    static let lock = NSLock()
    static var requests: [(String, String)] = []
    static var simulateTLSFailure = false

    override class func canInit(with request: URLRequest) -> Bool { return true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        return request
    }
    override func startLoading() {
        FakeHTTPSProtocol.lock.lock()
        let url = request.url!
        FakeHTTPSProtocol.requests.append((
            url.host ?? "missing", request.httpMethod ?? "missing"
        ))
        let failing = FakeHTTPSProtocol.simulateTLSFailure
        FakeHTTPSProtocol.lock.unlock()

        if failing && url.host == "raw.githubusercontent.com" {
            client?.urlProtocol(self, didFailWithError: NSError(
                domain: NSURLErrorDomain, code: -1200, userInfo: [:]
            ))
            return
        }
        let status: Int
        switch url.host {
        case "raw.githubusercontent.com": status = 200
        case "github.com": status = 302
        case "release-assets.githubusercontent.com": status = 403
        default: fatalError("unexpected host: " + String(url.host ?? ""))
        }
        let response = HTTPURLResponse(
            url: url, statusCode: status, httpVersion: "HTTP/1.1",
            headerFields: [:]
        )!
        client?.urlProtocol(
            self, didReceive: response, cacheStoragePolicy: .notAllowed
        )
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

func perform() -> [WebReaderHTTPSProbeResult] {
    let instance = WebReaderReleaseHTTPSProbe(
        testProtocolClasses: [FakeHTTPSProtocol.self]
    )
    let completed = DispatchSemaphore(value: 0)
    var output: [WebReaderHTTPSProbeResult] = []
    instance.run { results in
        output = results
        completed.signal()
    }
    ensure(completed.wait(timeout: .now() + 12) == .success, "probe timed out")
    return output
}

ensure(WebReaderReleaseHTTPSProbe.endpoints.count == 3,
       "three fixed GitHub diagnostic endpoints")
for item in WebReaderReleaseHTTPSProbe.endpoints {
    ensure(item.url.scheme == "https", "must use HTTPS")
}
let normal = perform()
ensure(normal.count == 3, "results count")
ensure(normal[0].httpStatus == 200, "raw HEAD 200")
ensure(normal[1].httpStatus == 302, "GitHub redirect status only")
ensure(normal[2].httpStatus == 403, "CDN HTTP 403 still demonstrates TLS")
ensure(normal[2].reportLine.contains("HTTP 403"), "HTTP failure preserved")
ensure(normal.allSatisfy({ $0.errorDomain == nil }), "HTTP is not TLS failure")

FakeHTTPSProtocol.lock.lock()
let firstRequests = FakeHTTPSProtocol.requests
FakeHTTPSProtocol.simulateTLSFailure = true
FakeHTTPSProtocol.lock.unlock()
ensure(firstRequests.count == 3, "exactly one HEAD per host")
ensure(firstRequests.allSatisfy({ $0.1 == "HEAD" }), "HEAD only")
ensure(firstRequests.map({ $0.0 }) == [
    "raw.githubusercontent.com", "github.com",
    "release-assets.githubusercontent.com"
], "fixed host set and order")

let failing = perform()
ensure(failing.count == 3, "still returns complete diagnostic after failure")
ensure(failing[0].httpStatus == nil, "synthetic TLS error has no HTTP status")
ensure(failing[0].errorDomain == NSURLErrorDomain, "NSError domain")
ensure(failing[0].errorCode == -1200, "TLS -1200 maintained")
ensure(failing[0].reportLine.contains("-1200"), "copyable status")
ensure(failing[1].httpStatus == 302, "continues after TLS failure")
print("PASS iOS12 read-only GitHub HEAD diagnostics, HTTP vs TLS distinction")
'''
with tempfile.TemporaryDirectory(prefix="webreader-https-probe-") as tmp:
    root = Path(tmp)
    main = root / "main.swift"
    binary = root / "https-diagnostic"
    main.write_text(HARNESS, encoding="utf-8")
    subprocess.run([
        "swiftc", "-swift-version", "5", str(SOURCE),
        str(main), "-o", str(binary)
    ], check=True)
    subprocess.run([str(binary)], check=True)
