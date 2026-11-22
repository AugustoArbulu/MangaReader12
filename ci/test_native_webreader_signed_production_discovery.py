#!/usr/bin/env python3
"""Compile and exercise real iOS12-compatible signed production channel code.

The production editorial key and independently provisioned fingerprint remain
ABSENT in this test. A signed fixture from a temporary key is verified by the
separate native Phase S test, never enrolled here. No real network or IPA.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
SOURCES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderSignedReleaseTrustGate.swift",
    CORE / "WebReaderProductionPublisherTrust.swift",
    CORE / "WebReaderProductionSignedReleaseChecker.swift",
]

SWIFT = r'''
import Foundation

// Only test scaffolding: production channel definitions live in real target.
enum WebReaderUpdateChannel {
    static let productionPublicKeyX963: Data? = nil
}
enum WebReaderUpdateCheckError: Error, Equatable {
    case busy
    case unsupportedManifestURL
    case transport
    case unexpectedHTTPStatus(Int)
    case unexpectedContentType
    case oversizedResponse
    case invalidSignedManifest
    case invalidGitHubRelease
}
enum WebReaderUpdateCheckResult {
    case disabled
    case updateAvailable(WebReaderVerifiedUpdate)
    case upToDate
    case failed(WebReaderUpdateCheckError)
}

func ensure(_ value: @autoclosure () -> Bool, _ message: String) {
    if !value() { fatalError(message) }
}
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
let raw = WebReaderSignedProductionChannel.manifestURL
ensure(raw.scheme == "https", "production endpoint HTTPS")
ensure(raw.host == "raw.githubusercontent.com", "production endpoint fixed")
ensure(raw.path ==
       "/AugustoArbulu/MangaReader12/main/updates/channel-production-v2.json",
       "fixed v2 production metadata URL")
ensure(WebReaderSignedProductionChannel.maximumResponseBytes == 64 * 1024,
       "signed response bounded")
ensure(!WebReaderProductionPublisherTrust.isProvisioned,
       "editorial trust root intentionally absent")
let checker = WebReaderProductionSignedReleaseChecker(
    installedBuild: 68, installedIOS: ios
)
ensure(checker.verifiedEnvelopeCopy() == nil,
       "no signed v2 bytes can appear before owner trust is configured")

for _ in 0..<3 {
    let semaphore = DispatchSemaphore(value: 0)
    var count = 0
    checker.check { result in
        count += 1
        switch result {
        case .disabled: break
        default: fatalError("no publisher pin must deny before HTTP request")
        }
        semaphore.signal()
    }
    ensure(semaphore.wait(timeout: .now() + 2) == .success,
           "nil production trust returns immediately")
    ensure(count == 1, "exactly one denial callback")
    ensure(checker.verifiedEnvelopeCopy() == nil,
           "disabled channel did not cache any signed manifest")
    checker.cancel() // no effect, no task opened
}
ensure(WebReaderProductionPublisherTrust.productionTrustGeneration == 0,
       "never promote trust generation from the network")
ensure(WebReaderProductionPublisherTrust.revokedPublisherPins.isEmpty,
       "no production trust was provisioned by the test")
print("PASS native signed production discovery: fixed HTTPS endpoint, fail-closed zero-session readiness, no publisher key, no install")
'''

with tempfile.TemporaryDirectory(prefix="wr69-prod-signed-discovery-") as temp:
    root = Path(temp)
    harness = root / "main.swift"
    binary = root / "signed-production-discovery"
    harness.write_text(SWIFT)
    subprocess.run([
        "swiftc", "-swift-version", "5",
        *map(str, SOURCES), str(harness),
        "-framework", "Security", "-o", str(binary)
    ], check=True, timeout=120)
    subprocess.run([str(binary)], check=True, timeout=45)
