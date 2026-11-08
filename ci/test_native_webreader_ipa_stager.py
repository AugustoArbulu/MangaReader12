#!/usr/bin/env python3
"""Offline Swift integration test for a staged IPA from signed update metadata.

No real network, real release keys, helper, appinst, or IPA installation.
"""
from pathlib import Path
import subprocess
import tempfile

from test_validate_webreader_ipa import make_ipa

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
FILES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderUpdateChecker.swift",
    CORE / "WebReaderGitHubReleaseParser.swift",
    CORE / "WebReaderNativeIPAAuditor.swift",
    CORE / "WebReaderIPADownloadBudget.swift",
    CORE / "WebReaderIPAStager.swift",
]
HARNESS = r'''
import Foundation
import Security
import CommonCrypto

func check(_ state: @autoclosure () -> Bool, _ message: String) {
    if !state() { fatalError(message) }
}
func serialize(_ data: [String: Any]) -> Data {
    return try! JSONSerialization.data(withJSONObject: data, options: [.sortedKeys])
}
func sha256(_ data: Data) -> String {
    var digest = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
    data.withUnsafeBytes { bytes in
        _ = CC_SHA256(bytes.baseAddress, CC_LONG(data.count), &digest)
    }
    return digest.map { String(format: "%02x", $0) }.joined()
}

final class IPAStubProtocol: URLProtocol {
    static let lock = NSLock()
    static var requests = 0
    static var status = 200
    static var mime = "application/octet-stream"
    static var contentEncoding: String?
    static var contentRange: String?
    static var body = Data()
    static var sentPartially = false
    static var keepOpenForCancel = false
    static let firstChunkDelivered = DispatchSemaphore(value: 0)

    override class func canInit(with request: URLRequest) -> Bool { return true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        return request
    }
    override func startLoading() {
        IPAStubProtocol.lock.lock()
        IPAStubProtocol.requests += 1
        let status = IPAStubProtocol.status
        let mime = IPAStubProtocol.mime
        let contentEncoding = IPAStubProtocol.contentEncoding
        let contentRange = IPAStubProtocol.contentRange
        let bytes = IPAStubProtocol.body
        let split = IPAStubProtocol.sentPartially
        let hang = IPAStubProtocol.keepOpenForCancel
        IPAStubProtocol.lock.unlock()
        var headers: [String: String] = ["Content-Type": mime]
        if let value = contentEncoding { headers["Content-Encoding"] = value }
        if let value = contentRange { headers["Content-Range"] = value }
        let response = HTTPURLResponse(
            url: request.url!, statusCode: status, httpVersion: "HTTP/1.1",
            headerFields: headers
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        if hang {
            client?.urlProtocol(self, didLoad: Data(bytes.prefix(5)))
            IPAStubProtocol.firstChunkDelivered.signal()
            return // Keep an unfinished transfer for explicit cancellation.
        }
        if split {
            let first = Data(bytes.prefix(5))
            let second = Data(bytes.dropFirst(5))
            client?.urlProtocol(self, didLoad: first)
            client?.urlProtocol(self, didLoad: second)
        } else if !bytes.isEmpty {
            client?.urlProtocol(self, didLoad: bytes)
        }
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

let attrs: [String: Any] = [
    kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
    kSecAttrKeySizeInBits as String: 256
]
var err: Unmanaged<CFError>?
let secret = SecKeyCreateRandomKey(attrs as CFDictionary, &err)!
let publicKey = SecKeyCopyPublicKey(secret)!
let pubBytes = SecKeyCopyExternalRepresentation(publicKey, &err)! as Data
// Actual valid synthetic ZIP/IPA generated offline by the Python fixture.
let sample = try! Data(contentsOf: URL(
    fileURLWithPath: CommandLine.arguments[1]
))
let expectedDigest = sha256(sample)
let releaseURL = "https://github.com/AugustoArbulu/MangaReader12/releases/download/build57/WebReader-iOS12-unsigned.ipa"
var payload: [String: Any] = [
    "schemaVersion": 1,
    "application": "WebReader",
    "bundleId": "com.example.MangaReader12",
    "channel": "development", "build": 57,
    "minimumIOS": "12.0", "ipaUrl": releaseURL,
    "ipaSize": sample.count, "sha256": expectedDigest,
    "releaseNotes": ["offline fixture only"],
    "publishedAt": "2026-11-05T03:00:00Z"
]
func signedManifest(_ details: [String: Any]) -> WebReaderVerifiedUpdate {
    let message = serialize(details)
    var signError: Unmanaged<CFError>?
    let signature = SecKeyCreateSignature(
        secret, .ecdsaSignatureMessageX962SHA256,
        message as CFData, &signError
    )! as Data
    let envelope = serialize([
        "schemaVersion": details["schemaVersion"]!, "algorithm": "ecdsa-p256-sha256",
        "payload": message.base64EncodedString(),
        "signature": signature.base64EncodedString()
    ])
    return try! WebReaderUpdateManifestVerifier.verify(
        envelopeData: envelope, publicKeyX963: pubBytes,
        installedBuild: 56,
        installedIOS: OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
    )
}
let good = signedManifest(payload)
let scratch = FileManager.default.temporaryDirectory.appendingPathComponent(
    "webreader-stager-" + UUID().uuidString
)
defer { try? FileManager.default.removeItem(at: scratch) }
func run(
    _ metadata: WebReaderVerifiedUpdate, useTransport: Bool = true,
    testFreeBytes: Int64? = nil, testInstalledBuild: Int? = nil,
    progress: ((Int) -> Void)? = nil
) -> WebReaderIPAStageResult {
    let stager = WebReaderIPAStager(
        verifiedUpdate: metadata, destinationDirectory: scratch,
        testProtocolClasses: useTransport ? [IPAStubProtocol.self] : nil,
        testAvailableSpace: testFreeBytes,
        testInstalledBuild: testInstalledBuild, onProgress: progress
    )
    let semaphore = DispatchSemaphore(value: 0)
    var result: WebReaderIPAStageResult?
    stager.stage { received in
        result = received
        semaphore.signal()
    }
    check(semaphore.wait(timeout: .now() + 10) == .success, "stager completed")
    return result!
}
func fail(
    _ metadata: WebReaderVerifiedUpdate,
    _ code: WebReaderIPAStageFailure
) {
    switch run(metadata) {
    case .failed(let actual): check(actual == code, "expected specific failure")
    case .staged: fatalError("unverified bytes were staged")
    }
}

check(!WebReaderUpdateChannel.isConfigured, "test only: production channel disabled")
switch run(good, useTransport: false) {
case .failed(.disabled): break
default: fatalError("must fail closed without producer key")
}
check(IPAStubProtocol.requests == 0, "disabled -> zero requests")

// A previously verified Release cannot be staged after the installed
// app catches up to that Build: no GET, no partial IPA, no downgrade.
for oldInstalled in [57, 58] {
    switch run(good, testInstalledBuild: oldInstalled) {
    case .failed(.notNewerThanInstalled): break
    default: fatalError("equal or newer installed Build must block download")
    }
}
check(IPAStubProtocol.requests == 0, "replayed/downgrade candidates zero GET")
switch run(good, testFreeBytes: 0, testInstalledBuild: 56) {
case .failed(.insufficientSpace): break
default: fatalError("newer candidate still subject to disk budget")
}
check(IPAStubProtocol.requests == 0, "newer candidate low-space zero GET")

IPAStubProtocol.body = sample
IPAStubProtocol.sentPartially = true
// Fail before any request or partial-file creation if free space would
// jeopardize manga downloads. No FileManager cleanup of existing chapters.
let beforeLowSpace = IPAStubProtocol.requests
switch run(good, testFreeBytes: 0) {
case .failed(.insufficientSpace): break
default: fatalError("low-space download was not refused")
}
check(IPAStubProtocol.requests == beforeLowSpace,
      "low-space admission must not request network bytes")
let entriesBeforeDownload = try! FileManager.default.contentsOfDirectory(
    atPath: scratch.path
)
check(entriesBeforeDownload.isEmpty,
      "insufficient space must not leave partial files")
var progressValues: [Int] = []
let progressLock = NSLock()
switch run(good, progress: { value in
    progressLock.lock()
    progressValues.append(value)
    progressLock.unlock()
}) {
case .staged(let path):
    check(path.lastPathComponent.hasSuffix(".ipa"), "staged IPA extension")
    let contents = try! Data(contentsOf: path)
    check(contents == sample, "identical signed bytes were staged")
    try! FileManager.default.removeItem(at: path)
default: fatalError("verified IPA must be staged")
}
check(IPAStubProtocol.requests == 1, "exactly one GET")
check(!progressValues.isEmpty, "download emits coarse progress")
check(progressValues.allSatisfy { $0 >= 5 && $0 <= 95 && $0 % 5 == 0 },
      "transfer progress bounded at 95 until integrity finalized")
check(progressValues == progressValues.sorted(), "download progress monotonic")

// A stalled partial download can be explicitly cancelled without leaving
// a partial file or requiring the user to close the WebReader updates screen.
IPAStubProtocol.keepOpenForCancel = true
let cancelled = WebReaderIPAStager(
    verifiedUpdate: good, destinationDirectory: scratch,
    testProtocolClasses: [IPAStubProtocol.self]
)
let cancelDone = DispatchSemaphore(value: 0)
var cancellationResult: WebReaderIPAStageResult?
cancelled.stage { result in
    cancellationResult = result
    cancelDone.signal()
}
check(IPAStubProtocol.firstChunkDelivered.wait(timeout: .now() + 10) == .success,
      "stalled transport began with a partial IPA")
cancelled.cancel()
check(cancelDone.wait(timeout: .now() + 10) == .success,
      "cancel invokes completion even without HTTP didComplete")
switch cancellationResult! {
case .failed(.cancelled): break
default: fatalError("explicit cancel misclassified as download failure")
}
cancelled.cancel() // Idempotent: must not fire the callback twice.
check((try! FileManager.default.contentsOfDirectory(
    atPath: scratch.path
)).filter { $0.hasSuffix(".partial") }.isEmpty,
    "cancel immediately removes incomplete IPA from private staging")
IPAStubProtocol.keepOpenForCancel = false

// Version 2 keeps the exact build-named, ad-hoc release filename. This does
// not test publisher signing: an ad-hoc seal is NOT publisher authentication.
var v2Details = payload
v2Details["schemaVersion"] = 2
v2Details["applicationIdentifier"] =
    "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
v2Details["ipaUrl"] =
    "https://github.com/AugustoArbulu/MangaReader12/releases/download/" +
    "build57/WebReader-Build57-iOS12-adhoc.ipa"
let v2 = signedManifest(v2Details)
IPAStubProtocol.body = sample
let priorRequests = IPAStubProtocol.requests
switch run(v2) {
case .staged(let url):
    check(try! Data(contentsOf: url) == sample,
          "exact v2 bytes staged for manual review")
    try! FileManager.default.removeItem(at: url)
default: fatalError("build-named v2 ad-hoc path should be stageable")
}
check(IPAStubProtocol.requests == priorRequests + 1,
      "exact v2 release generates one stub request")

// A release metadata object with a malicious filename or host must be
// rejected by the stager independently, even if a caller forged the struct.
func uncheckedUpdate(_ raw: String) -> WebReaderVerifiedUpdate {
    return WebReaderVerifiedUpdate(
        build: 57, minimumIOS: "12.0", ipaURL: URL(string: raw)!,
        ipaSize: Int64(sample.count), sha256: expectedDigest,
        publishedAt: "2026-11-07T00:00:00Z", releaseNotes: ["test only"]
    )
}
let forbiddenPaths = [
    "https://github.com/AugustoArbulu/MangaReader12/releases/" +
        "download/build57/WebReader-Build58-iOS12-adhoc.ipa",
    "https://github.com/AugustoArbulu/MangaReader12/releases/" +
        "download/build57/WebReader-Build57-iOS12-adhoc.ipa?x=1",
    "https://github.com/AugustoArbulu/MangaReader12/releases/" +
        "download/build57/WebReader-Build57-iOS12-adhoc.ipa#install",
    "https://github.com/another-account/MangaReader12/releases/" +
        "download/build57/WebReader-Build57-iOS12-adhoc.ipa",
    "https://example.org/releases/download/build57/" +
        "WebReader-Build57-iOS12-adhoc.ipa"
]
for forbidden in forbiddenPaths {
    let before = IPAStubProtocol.requests
    fail(uncheckedUpdate(forbidden), .invalidRelease)
    check(IPAStubProtocol.requests == before, "forbidden URL must not be fetched")
}


var wrongHash = payload
wrongHash["sha256"] = String(repeating: "0", count: 64)
fail(signedManifest(wrongHash), .integrityMismatch)

IPAStubProtocol.body = Data(sample.prefix(10))
fail(good, .sizeMismatch)

IPAStubProtocol.body = Data(repeating: 0x41, count: sample.count + 5)
fail(good, .sizeMismatch)

IPAStubProtocol.body = sample
IPAStubProtocol.status = 403
fail(good, .unexpectedHTTPStatus(403))
IPAStubProtocol.status = 200

IPAStubProtocol.mime = "text/html"
fail(good, .unexpectedContentType)
IPAStubProtocol.mime = "application/octet-stream"

// A full 200 response with Content-Encoding or Content-Range is still not
// an untransformed full-archive transfer. Refuse both before ZIP inspection.
IPAStubProtocol.contentEncoding = "gzip"
fail(good, .unexpectedContentType)
IPAStubProtocol.contentEncoding = "identity"
IPAStubProtocol.contentRange = "bytes 0-10/100"
fail(good, .unexpectedContentType)
IPAStubProtocol.contentRange = nil
IPAStubProtocol.contentEncoding = nil
IPAStubProtocol.body = sample
switch run(good) {
case .staged(let path):
    check(try! Data(contentsOf: path) == sample, "identity encoding is safe")
    try! FileManager.default.removeItem(at: path)
default: fatalError("normal full untransformed IPA should still work")
}

// Forged ZIP header with a correctly signed hash is still only staged,
// never installed; a subsequent IPA validator/helper must inspect Info.plist.
var notZip = payload
let plain = Data(repeating: 0x41, count: 30)
notZip["ipaSize"] = plain.count
notZip["sha256"] = sha256(plain)
IPAStubProtocol.body = plain
fail(signedManifest(notZip), .integrityMismatch)

// Valid SHA-256 and ZIP magic are not sufficient: reject a corrupt ZIP.
let corruptZIP = Data([0x50, 0x4B, 0x03, 0x04]) +
    Data(repeating: 0x42, count: 50)
var brokenMetadata = payload
brokenMetadata["ipaSize"] = corruptZIP.count
brokenMetadata["sha256"] = sha256(corruptZIP)
IPAStubProtocol.body = corruptZIP
fail(signedManifest(brokenMetadata), .invalidIPA)

let remaining = try! FileManager.default.contentsOfDirectory(atPath: scratch.path)
check(remaining.isEmpty, "failed downloads leave no IPA or partial files")
print("PASS native IPA stager: signed SHA256 plus complete ZIP/Info.plist identity checks, zero real network")
'''
with tempfile.TemporaryDirectory(prefix="webreader-stage-integration-") as dir:
    fixture, _ = make_ipa(Path(dir), build="57")
    main = Path(dir) / "main.swift"
    output = Path(dir) / "test"
    main.write_text(HARNESS)
    subprocess.run(
        ["swiftc", "-swift-version", "5", *map(str, FILES),
         str(main), "-framework", "Security", "-o", str(output)],
        check=True
    )
    subprocess.run([str(output), str(fixture)], check=True)
