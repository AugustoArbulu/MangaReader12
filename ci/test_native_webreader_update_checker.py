#!/usr/bin/env python3
"""Offline native URLSession UpdateChecker regression; NO real network or IPA install."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "MangaReader12/Core"
SOURCES = [
    BASE / "WebReaderStrictJSON.swift",
    BASE / "WebReaderUpdateManifestVerifier.swift",
    BASE / "WebReaderUpdateChecker.swift",
]
HARNESS = r'''
import Foundation
import Security

func check(_ value: @autoclosure () -> Bool, _ label: String) {
    if !value() { fatalError(label) }
}
func asJSON(_ value: [String: Any]) -> Data {
    return try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
}

final class StubManifestURLProtocol: URLProtocol {
    static let lock = NSLock()
    static var requests = 0
    static var responseStatus = 200
    static var contentType = "application/json"
    static var responseBody = Data()

    override class func canInit(with request: URLRequest) -> Bool { return true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        return request
    }
    override func startLoading() {
        StubManifestURLProtocol.lock.lock()
        StubManifestURLProtocol.requests += 1
        let status = StubManifestURLProtocol.responseStatus
        let type = StubManifestURLProtocol.contentType
        let bytes = StubManifestURLProtocol.responseBody
        StubManifestURLProtocol.lock.unlock()

        let response = HTTPURLResponse(
            url: request.url!, statusCode: status, httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": type]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        if !bytes.isEmpty { client?.urlProtocol(self, didLoad: bytes) }
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

let attributes: [String: Any] = [
    kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
    kSecAttrKeySizeInBits as String: 256
]
var keyError: Unmanaged<CFError>?
let privateKey = SecKeyCreateRandomKey(attributes as CFDictionary, &keyError)!
let publicKey = SecKeyCopyPublicKey(privateKey)!
let publicBytes = SecKeyCopyExternalRepresentation(publicKey, &keyError)! as Data
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)

var payload: [String: Any] = [
    "schemaVersion": 1,
    "application": "WebReader",
    "bundleId": "com.example.MangaReader12",
    "channel": "development",
    "build": 57,
    "minimumIOS": "12.0",
    "ipaUrl": "https://github.com/AugustoArbulu/MangaReader12/releases/download/build57/WebReader-iOS12-unsigned.ipa",
    "ipaSize": 17300000,
    "sha256": String(repeating: "a", count: 64),
    "releaseNotes": ["Test fixture; not a real release"],
    "publishedAt": "2026-11-04T16:00:00Z"
]
func makeEnvelope(_ manifest: [String: Any]) -> Data {
    let message = asJSON(manifest)
    var error: Unmanaged<CFError>?
    let signature = SecKeyCreateSignature(
        privateKey, .ecdsaSignatureMessageX962SHA256,
        message as CFData, &error
    )! as Data
    return asJSON([
        "schemaVersion": 1,
        "algorithm": "ecdsa-p256-sha256",
        "payload": message.base64EncodedString(),
        "signature": signature.base64EncodedString()
    ])
}
func runCheck(
    key: Data?, url: URL = WebReaderUpdateChannel.developmentManifestURL
) -> WebReaderUpdateCheckResult {
    let checker = WebReaderUpdateChecker(
        manifestURL: url, publicKeyX963: key,
        installedBuild: 56, installedIOS: ios,
        protocolClasses: [StubManifestURLProtocol.self]
    )
    let done = DispatchSemaphore(value: 0)
    var result: WebReaderUpdateCheckResult?
    checker.check { received in
        result = received
        done.signal()
    }
    check(done.wait(timeout: .now() + 8) == .success, "checker finished")
    return result!
}
func expectFailure(
    _ code: WebReaderUpdateCheckError, key: Data? = publicBytes
) {
    switch runCheck(key: key) {
    case .failed(let received):
        check(code == received, "wrong failure kind")
    default:
        fatalError("expected failure")
    }
}

check(!WebReaderUpdateChannel.isConfigured, "no production public key")
switch runCheck(key: nil) {
case .disabled: break
default: fatalError("must fail closed without a signing key")
}
check(StubManifestURLProtocol.requests == 0, "disabled must never touch network")

// Even a signed payload is never fetched from an arbitrary origin.
switch runCheck(key: publicBytes, url: URL(string: "https://example.org/update.json")!) {
case .failed(.unsupportedManifestURL): break
default: fatalError("untrusted manifest URL rejected")
}
check(StubManifestURLProtocol.requests == 0, "untrusted URL must not touch network")

StubManifestURLProtocol.responseBody = makeEnvelope(payload)
switch runCheck(key: publicBytes) {
case .updateAvailable(let update):
    check(update.build == 57 && update.ipaSize == 17300000, "signed update")
default: fatalError("valid authenticated update")
}
check(StubManifestURLProtocol.requests == 1, "exactly one GET")

// A correctly signed installed/older version is up-to-date, not offered.
payload["build"] = 56
payload["ipaUrl"] = "https://github.com/AugustoArbulu/MangaReader12/releases/download/build56/WebReader-iOS12-unsigned.ipa"
StubManifestURLProtocol.responseBody = makeEnvelope(payload)
switch runCheck(key: publicBytes) {
case .upToDate: break
default: fatalError("signed current version must not be offered")
}
payload["build"] = 57
payload["ipaUrl"] = "https://github.com/AugustoArbulu/MangaReader12/releases/download/build57/WebReader-iOS12-unsigned.ipa"

StubManifestURLProtocol.responseBody = Data("invalid-json".utf8)
expectFailure(.invalidSignedManifest)

StubManifestURLProtocol.responseBody = makeEnvelope(payload)
StubManifestURLProtocol.responseStatus = 403
expectFailure(.unexpectedHTTPStatus(403))
StubManifestURLProtocol.responseStatus = 200

StubManifestURLProtocol.contentType = "text/html"
expectFailure(.unexpectedContentType)
StubManifestURLProtocol.contentType = "application/json"

StubManifestURLProtocol.responseBody = Data(repeating: 0x41, count: 65 * 1024)
expectFailure(.oversizedResponse)

StubManifestURLProtocol.responseBody = makeEnvelope(payload)
var wrongKeyError: Unmanaged<CFError>?
let randomPrivate = SecKeyCreateRandomKey(attributes as CFDictionary, &wrongKeyError)!
let randomPublic = SecKeyCopyPublicKey(randomPrivate)!
let randomKeyBytes = SecKeyCopyExternalRepresentation(randomPublic, &wrongKeyError)! as Data
expectFailure(.invalidSignedManifest, key: randomKeyBytes)


// Duplicate keys in a correctly signed payload cannot be treated as a new build.
let signedPayload = asJSON(payload)
let signedPayloadText = String(data: signedPayload, encoding: .utf8)!
let duplicateText = "{\"bundleId\":\"com.example.MangaReader12\"," +
    String(signedPayloadText.dropFirst())
let duplicateBytes = Data(duplicateText.utf8)
var duplicateSignError: Unmanaged<CFError>?
let duplicateSignature = SecKeyCreateSignature(
    privateKey, .ecdsaSignatureMessageX962SHA256,
    duplicateBytes as CFData, &duplicateSignError
)! as Data
StubManifestURLProtocol.responseBody = asJSON([
    "schemaVersion": 1, "algorithm": "ecdsa-p256-sha256",
    "payload": duplicateBytes.base64EncodedString(),
    "signature": duplicateSignature.base64EncodedString()
])
expectFailure(.invalidSignedManifest)

print("PASS: iOS12 read-only UpdateChecker enforces signed-only, bounded, fail-closed URLSession checks")
'''
with tempfile.TemporaryDirectory(prefix="webreader-update-checker-") as work:
    root = Path(work)
    main = root / "main.swift"
    main.write_text(HARNESS)
    exe = root / "check"
    subprocess.run(
        ["swiftc", "-swift-version", "5", *map(str, SOURCES),
         str(main), "-framework", "Security", "-o", str(exe)],
        check=True
    )
    subprocess.run([str(exe)], check=True)
