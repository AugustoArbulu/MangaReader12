#!/usr/bin/env python3
"""Execute REAL Swift in-memory sequencing code on macOS, no installation.

The signature+same-FD IPA gate is simulated here ONLY to isolate the sequence
state machine. Its real cryptographic/ZIP implementation is exercised by
ci/test_native_webreader_signed_ipa_joint_audit.py in the same CI workflow.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Core/WebReaderSignedPreviewSequence.swift"

SWIFT = r'''
import Foundation

enum SimulatedSignatureFailure: Error { case badSignature, oldBuild }

struct WebReaderSignedIPAReviewResult {
    let build: Int
    let installationAuthorized: Bool = false
    let installationPerformed: Bool = false
}

enum WebReaderSignedIPAReview {
    static func inspectReadOnly(
        envelopeData: Data,
        independentlyTrustedPublicKeyX963: Data,
        independentlyTrustedSPKISHA256: String?,
        localIPAURL: URL,
        installedBuild: Int,
        installedIOS: OperatingSystemVersion
    ) throws -> WebReaderSignedIPAReviewResult {
        guard independentlyTrustedSPKISHA256 == "synthetic-known-pin",
              independentlyTrustedPublicKeyX963 == Data([0x04]),
              let value = envelopeData.first,
              localIPAURL.lastPathComponent != "corrupt",
              installedIOS.majorVersion == 12 else {
            throw SimulatedSignatureFailure.badSignature
        }
        guard Int(value) > installedBuild else {
            throw SimulatedSignatureFailure.oldBuild
        }
        return WebReaderSignedIPAReviewResult(build: Int(value))
    }
}

func insist(_ good: @autoclosure () -> Bool, _ label: String) {
    if !good() { fatalError(label) }
}
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
let testURL = URL(fileURLWithPath: "/synthetic/valid")
let corruptURL = URL(fileURLWithPath: "/synthetic/corrupt")

func review(
    _ sequence: WebReaderSignedPreviewSequence, _ build: UInt8,
    pin: String? = "synthetic-known-pin", file: URL = testURL
) throws -> WebReaderSignedIPAReviewResult {
    return try sequence.inspectReadOnly(
        envelopeData: Data([build]), publicKeyX963: Data([0x04]),
        independentlyTrustedSPKISHA256: pin, localIPAURL: file
    )
}
func mustReject(_ work: () throws -> Void, _ reason: String) {
    do { try work(); fatalError("accepted: " + reason) }
    catch is SimulatedSignatureFailure {}
    catch is WebReaderSignedPreviewSequenceError {}
    catch { fatalError("unexpected error " + reason) }
}

do {
    _ = try WebReaderSignedPreviewSequence(installedBuild: -1, installedIOS: ios)
    fatalError("negative installedBuild accepted")
} catch WebReaderSignedPreviewSequenceError.invalidInstalledBuild {}
do {
    _ = try WebReaderSignedPreviewSequence(
        installedBuild: 2_147_483_648, installedIOS: ios
    )
    fatalError("unbounded build accepted")
} catch WebReaderSignedPreviewSequenceError.invalidInstalledBuild {}

let s = try! WebReaderSignedPreviewSequence(installedBuild: 66, installedIOS: ios)
insist(s.statusReadOnly().highestSuccessfullyReviewedBuild == 66,
       "initial high water = installed build")
insist(try! review(s, 69).build == 69, "new version accepted once")
mustReject({ _ = try review(s, 69) }, "duplicate candidate")
mustReject({ _ = try review(s, 67) }, "older candidate after 69")
mustReject({ _ = try review(s, 70, pin: "attacker") }, "wrong trusted pin")
mustReject({ _ = try review(s, 70, file: corruptURL) }, "corrupt archive")
insist(s.statusReadOnly().highestSuccessfullyReviewedBuild == 69,
       "rejected candidates never advance high-water mark")
insist(try! review(s, 70).build == 70, "new valid candidate advances")
insist(!s.statusReadOnly().installationAuthorized &&
       !s.statusReadOnly().installationPerformed,
       "session cannot authorize or perform installation")
insist(!s.statusReadOnly().isPersistent &&
       !s.statusReadOnly().installerLedgerVerified,
       "in-memory session is NOT a durable anti-rollback ledger")

// A fresh app process/session loses the high-water mark. This limitation is
// intended and must never be represented as privileged rollback protection.
let newSession = try! WebReaderSignedPreviewSequence(
    installedBuild: 66, installedIOS: ios
)
insist(newSession.statusReadOnly().highestSuccessfullyReviewedBuild == 66,
       "fresh process has no signed-history persistence")

// Simulate 40 concurrent attempts to review exactly the same valid candidate.
// Exactly one must succeed, all later attempts must fail for this session.
let concurrent = try! WebReaderSignedPreviewSequence(
    installedBuild: 66, installedIOS: ios
)
let counter = NSLock()
var successes = 0
DispatchQueue.concurrentPerform(iterations: 40) { _ in
    if let result = try? review(concurrent, 71), result.build == 71 {
        counter.lock()
        successes += 1
        counter.unlock()
    }
}
insist(successes == 1, "duplicate concurrent reviews must not advance twice")
insist(concurrent.statusReadOnly().highestSuccessfullyReviewedBuild == 71,
       "concurrent last-reviewed stable")
print("PASS native Swift signed preview sequencing: monotonic session, failed checks no state changes, 1/40 concurrent accepted; NO INSTALL")
'''
with tempfile.TemporaryDirectory(prefix="wr68-monotonic-preview-") as temp:
    root = Path(temp)
    harness = root / "main.swift"
    executable = root / "preview-sequence"
    harness.write_text(SWIFT)
    subprocess.run([
        "swiftc", "-swift-version", "5", str(SOURCE),
        str(harness), "-o", str(executable)
    ], check=True, timeout=120)
    subprocess.run([str(executable)], check=True, timeout=60)
