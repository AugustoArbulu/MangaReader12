#!/usr/bin/env python3
"""Native Swift macOS test for manual iOS12 IPA import (no real device/installer).

Exercises WebReaderLocalIPAReviewer and the same native ZIP/SHA auditor used
by the WebReader app. Creates disposable synthetic ZIP fixtures, never a
signed or installable IPA. No GitHub network, account, token, appinst or root.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile

from test_validate_webreader_ipa import make_ipa

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
SOURCES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderGitHubReleaseParser.swift",
    CORE / "WebReaderUpdateChecker.swift",
    CORE / "WebReaderNativeIPAAuditor.swift",
    CORE / "WebReaderIPAStager.swift",
]
HARNESS = r'''
import Foundation

func require(_ condition: @autoclosure () -> Bool, _ description: String) {
    if !condition() { fatalError(description) }
}
func denied(_ label: String, _ action: () throws -> WebReaderLocalIPAReview) {
    do {
        let result = try action()
        WebReaderLocalIPAReviewer.discard(result)
        fatalError("Unexpected accepted local import: " + label)
    } catch is WebReaderLocalIPAReviewError {
        // Explicit fail closed: no privilege or installation.
    } catch {
        fatalError("Unexpected error in local import " + label + ": " +
                   String(describing: error))
    }
}
let args = CommandLine.arguments
require(args.count == 7, "expected five synthetic inputs and scratch root")
let valid = URL(fileURLWithPath: args[1])
let old = URL(fileURLWithPath: args[2])
let wrongBundle = URL(fileURLWithPath: args[3])
let wrongIOS = URL(fileURLWithPath: args[4])
let corrupt = URL(fileURLWithPath: args[5])
let root = URL(fileURLWithPath: args[6], isDirectory: true)
let folder = root.appendingPathComponent("QA-import", isDirectory: true)
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
let hash = args[0] // This is executable path; replaced below with fixture hash.
let expected = ProcessInfo.processInfo.environment["QA_FIXTURE_SHA"]!
require(expected.count == 64, "fixture digest must be a full SHA256")
func imported(
    _ src: URL, build: Int = 67, digest: String? = nil
) throws -> WebReaderLocalIPAReview {
    return try WebReaderLocalIPAReviewer.importForReview(
        sourceURL: src, expectedBuild: build,
        expectedSHA256: digest ?? expected, installedBuild: 66,
        installedIOS: ios, directory: folder
    )
}
denied("empty hash") { try imported(valid, digest: "") }
denied("short hash") { try imported(valid, digest: "abc") }
denied("uppercase hash") { try imported(valid, digest: expected.uppercased()) }
denied("wrong hash") {
    try imported(valid, digest: String(repeating: "0", count: 64))
}
denied("same build downgrade") { try imported(valid, build: 66) }
denied("old build downgrade") { try imported(valid, build: 65) }
denied("zero build") { try imported(valid, build: 0) }
denied("nonsensical build") { try imported(valid, build: 2147483647) }
denied("valid archive different reference version") {
    try imported(valid, build: 68)
}
denied("actual IPA has old version") { try imported(old) }
denied("wrong application bundle") { try imported(wrongBundle) }
denied("requires iOS13") { try imported(wrongIOS) }
denied("invalid ZIP even with matching hash") {
    let bytes = try! Data(contentsOf: corrupt)
    let h = bytes.reduce(into: [UInt8]()) { _, _ in } // Not used.
    _ = h
    // Corrupt fixture's checksum is passed as a known full 64-char digest.
    let bad = ProcessInfo.processInfo.environment["QA_BAD_SHA"]!
    return try imported(corrupt, digest: bad)
}
let renamed = root.appendingPathComponent("disguised.txt")
try! FileManager.default.copyItem(at: valid, to: renamed)
denied("wrong extension") { try imported(renamed) }
let link = root.appendingPathComponent("symlink.ipa")
try! FileManager.default.createSymbolicLink(at: link, withDestinationURL: valid)
denied("source symlink") { try imported(link) }
let missing = root.appendingPathComponent("missing.ipa")
denied("missing candidate") { try imported(missing) }
let oversize = root.appendingPathComponent("large.ipa")
let file = FileManager.default.createFile(atPath: oversize.path, contents: Data())
require(file, "create oversized sparse IPA")
let fd = FileHandle(forWritingAtPath: oversize.path)!
fd.truncateFile(atOffset: UInt64(WebReaderLocalIPAReviewer.maximumSize + 1))
fd.closeFile()
denied("512MiB limit") { try imported(oversize) }

let allAfterRejections = (try? FileManager.default.contentsOfDirectory(
    atPath: folder.path
)) ?? []
require(allAfterRejections.isEmpty, "failed imports must delete temporary copies")

let review = try! imported(valid)
require(review.build == 67, "read-only archive build")
require(review.expectedSHA256 == expected, "exact manually supplied SHA")
require(review.ipaBytes > 0 && review.zipEntries >= 2, "ZIP index audited")
require(review.manualSourceOnly, "local files not signed manifest")
require(!review.publisherAuthenticated, "local hash cannot authenticate publisher")
require(!review.installationAuthorized && !review.installationPerformed,
        "no installation from import")
require(review.copiedIPAURL != valid && review.copiedIPAURL.isFileURL,
        "copy stays isolated from original Files/Filza candidate")
require(review.copiedIPAURL.lastPathComponent.hasPrefix(
    "WebReader-Build67-local-"), "unique name uses same build")
try! WebReaderLocalIPAReviewer.recheck(
    review, installedBuild: 66, installedIOS: ios
)
let original = try! Data(contentsOf: valid)
try! Data("tampered".utf8).write(to: review.copiedIPAURL)
do {
    try WebReaderLocalIPAReviewer.recheck(
        review, installedBuild: 66, installedIOS: ios
    )
    fatalError("modified staged local IPA passed recheck")
} catch is WebReaderLocalIPAReviewError {
    // Expected
}
WebReaderLocalIPAReviewer.discard(review, directory: folder)
require(!FileManager.default.fileExists(atPath: review.copiedIPAURL.path),
        "discard removes local review copy only")
require(try! Data(contentsOf: valid) == original,
        "discard never touches user-selected original IPA")
require(!FileManager.default.fileExists(atPath: missing.path),
        "discard must not generate fake files")
print("PASS local iOS12 IPA review: 16 negative cases, isolated copy, SHA/ZIP/identity, recheck, safe discard, no install")
'''
with tempfile.TemporaryDirectory(prefix="wr67-local-ipa-") as directory:
    folder = Path(directory)
    valid, digest = make_ipa(folder, build="67")
    original = folder / "user-update.ipa"
    shutil.copy2(valid, original)
    make_ipa(folder, build="66")
    old = folder / "old.ipa"
    shutil.copy2(valid, old)
    make_ipa(folder, build="67", bundle="attacker.example")
    wrong_bundle = folder / "other-bundle.ipa"
    shutil.copy2(valid, wrong_bundle)
    make_ipa(folder, build="67", minimum="13.0")
    wrong_ios = folder / "ios13.ipa"
    shutil.copy2(valid, wrong_ios)
    corrupt = folder / "corrupt.ipa"
    corrupt.write_bytes(b"not a ZIP at all")
    import hashlib
    bad_hash = hashlib.sha256(corrupt.read_bytes()).hexdigest()
    main = folder / "main.swift"
    main.write_text(HARNESS)
    out = folder / "qa-local-import"
    subprocess.run(
        ["swiftc", "-swift-version", "5", *map(str, SOURCES),
         str(main), "-framework", "Security", "-o", str(out)],
        check=True, timeout=120
    )
    import os
    env = dict(os.environ, QA_FIXTURE_SHA=digest, QA_BAD_SHA=bad_hash)
    subprocess.run(
        [str(out), str(original), str(old), str(wrong_bundle),
         str(wrong_ios), str(corrupt), str(folder)],
        check=True, timeout=90, env=env
    )
