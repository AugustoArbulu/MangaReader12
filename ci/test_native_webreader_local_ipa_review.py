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
    CORE / "WebReaderIPADownloadBudget.swift",
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
require(args.count == 8, "expected six synthetic inputs and scratch root")
let valid = URL(fileURLWithPath: args[1])
let old = URL(fileURLWithPath: args[2])
let wrongBundle = URL(fileURLWithPath: args[3])
let wrongIOS = URL(fileURLWithPath: args[4])
let corrupt = URL(fileURLWithPath: args[5])
let root = URL(fileURLWithPath: args[6], isDirectory: true)
let folder = root.appendingPathComponent("QA-import", isDirectory: true)
let fifo = URL(fileURLWithPath: args[7])
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
// Disk headroom is required BEFORE any multi-megabyte QA copy.
let small: Int64 = 20 * 1024 * 1024
let minimumFree = WebReaderLocalIPAReviewer.requiredFreeBytes(ipaBytes: small)
require(minimumFree >= small + 16 * 1024 * 1024, "16 MiB headroom")
require(!WebReaderLocalIPAReviewer.hasEnoughSpace(
    freeBytes: small, ipaBytes: small
), "fail closed when free bytes only cover file size")
require(WebReaderLocalIPAReviewer.hasEnoughSpace(
    freeBytes: minimumFree, ipaBytes: small
), "exact required free bytes accepted")
require(!WebReaderLocalIPAReviewer.hasEnoughSpace(
    freeBytes: 1_000_000, ipaBytes: 0
), "zero-byte candidates cannot be copied")
require(!WebReaderLocalIPAReviewer.hasEnoughSpace(
    freeBytes: Int64.max,
    ipaBytes: WebReaderLocalIPAReviewer.maximumSize + 1
), "over-limit file cannot bypass free-space check")
require(WebReaderLocalIPAReviewer.requiredFreeBytes(
    ipaBytes: WebReaderLocalIPAReviewer.maximumSize
) == 576 * 1024 * 1024, "at most 64 MiB extra headroom")
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
denied("source FIFO without writer") { try imported(fifo) }
let oversize = root.appendingPathComponent("large.ipa")
let file = FileManager.default.createFile(atPath: oversize.path, contents: Data())
require(file, "create oversized sparse IPA")
let fd = FileHandle(forWritingAtPath: oversize.path)!
fd.truncateFile(atOffset: UInt64(WebReaderLocalIPAReviewer.maximumSize + 1))
fd.closeFile()
denied("512MiB limit") { try imported(oversize) }

// A preexisting symlink at the staging directory must NEVER cause the
// reviewer to write inside another application folder or user Library.
let mockLibrary = root.appendingPathComponent("mock-library", isDirectory: true)
try! FileManager.default.createDirectory(at: mockLibrary,
                                        withIntermediateDirectories: false,
                                        attributes: nil)
let linkedFolder = root.appendingPathComponent("redirected-QA-directory")
try! FileManager.default.createSymbolicLink(
    at: linkedFolder, withDestinationURL: mockLibrary
)
do {
    let item = try WebReaderLocalIPAReviewer.importForReview(
        sourceURL: valid, expectedBuild: 67, expectedSHA256: expected,
        installedBuild: 66, installedIOS: ios, directory: linkedFolder
    )
    WebReaderLocalIPAReviewer.discard(item, directory: linkedFolder)
    fatalError("staging directory symlink unexpectedly accepted")
} catch WebReaderLocalIPAReviewError.failedToCopy {
    // Expected: no copy must be written into the symlink target.
}
require((try! FileManager.default.contentsOfDirectory(
    atPath: mockLibrary.path
)).isEmpty, "symlink target is not modified")

let allAfterRejections = (try? FileManager.default.contentsOfDirectory(
    atPath: folder.path
)) ?? []
require(allAfterRejections.isEmpty, "failed imports must delete temporary copies")

let review = try! imported(valid)
require(review.build == 67, "read-only archive build")
let copiedInfo = try! FileManager.default.attributesOfItem(
    atPath: review.copiedIPAURL.path
)
let copiedPermissions = copiedInfo[.posixPermissions] as! NSNumber
require((copiedPermissions.intValue & 0o777) == 0o600,
        "imported QA copy is private, not inherited world-readable")
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

// A hostile replacement of an approved QA copy with a symlink must not
// cause discard to follow the link or unlink any original owner IPA.
let symlinkReview = try! imported(valid)
try! FileManager.default.removeItem(at: symlinkReview.copiedIPAURL)
try! FileManager.default.createSymbolicLink(
    at: symlinkReview.copiedIPAURL, withDestinationURL: valid
)
WebReaderLocalIPAReviewer.discard(symlinkReview, directory: folder)
let stillSymlink = try! FileManager.default.destinationOfSymbolicLink(
    atPath: symlinkReview.copiedIPAURL.path
)
require(!stillSymlink.isEmpty, "discard refused symlinked QA candidate")
require(try! Data(contentsOf: valid) == original, "owner IPA unaffected by symlink")
try! FileManager.default.removeItem(at: symlinkReview.copiedIPAURL)

// A copied-bytes-identical replacement has the same SHA256, but different
// inode. Share and discard must not treat it as the original audited copy.
let swappedReview = try! imported(valid)
let originalCopyLocation = root.appendingPathComponent(
    "saved-original-candidate.ipa"
)
try! FileManager.default.moveItem(
    at: swappedReview.copiedIPAURL, to: originalCopyLocation
)
try! FileManager.default.copyItem(
    at: valid, to: swappedReview.copiedIPAURL
)
do {
    try WebReaderLocalIPAReviewer.recheck(
        swappedReview, installedBuild: 66, installedIOS: ios
    )
    fatalError("byte-identical replacement accepted as original QA inode")
} catch WebReaderLocalIPAReviewError.invalidIPA {
    // Even with equal digests, the receipt must identify the original file.
}
WebReaderLocalIPAReviewer.discard(swappedReview, directory: folder)
require(FileManager.default.fileExists(
    atPath: swappedReview.copiedIPAURL.path
), "cannot delete byte-identical foreign inode")
require(try! Data(contentsOf: swappedReview.copiedIPAURL) == original,
        "replacement remains untouched after refused cleanup")
try! FileManager.default.removeItem(at: swappedReview.copiedIPAURL)
try! FileManager.default.moveItem(
    at: originalCopyLocation, to: swappedReview.copiedIPAURL
)
try! WebReaderLocalIPAReviewer.recheck(
    swappedReview, installedBuild: 66, installedIOS: ios
)
WebReaderLocalIPAReviewer.discard(swappedReview, directory: folder)
require(!FileManager.default.fileExists(
    atPath: swappedReview.copiedIPAURL.path
), "restoring the verified inode allows cleanup")

// If the whole staging directory changes into a symlink after review,
// refuse cleanup, even if the same file name is planted in the destination.
let redirectReview = try! imported(valid)
let savedFile = redirectReview.copiedIPAURL.lastPathComponent
let moved = root.appendingPathComponent("actual-QA-folder", isDirectory: true)
try! FileManager.default.moveItem(at: folder, to: moved)
let simulatedVictim = mockLibrary.appendingPathComponent(savedFile)
try! Data("do not remove another file".utf8).write(to: simulatedVictim)
try! FileManager.default.createSymbolicLink(
    at: folder, withDestinationURL: mockLibrary
)
WebReaderLocalIPAReviewer.discard(redirectReview, directory: folder)
require(try! Data(contentsOf: simulatedVictim) ==
        Data("do not remove another file".utf8),
        "replaced directory did not delete mock Library data")
try! FileManager.default.removeItem(at: folder)
try! FileManager.default.moveItem(at: moved, to: folder)
WebReaderLocalIPAReviewer.discard(redirectReview, directory: folder)
require(!FileManager.default.fileExists(
    atPath: redirectReview.copiedIPAURL.path
), "restored directory allows unlink of exact private copy")
print("PASS local iOS12 IPA review: 19 negative cases, inode-anchored copy, private staging, protected discard, no install")
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
    fifo = folder / "sourcepipe.ipa"
    import os
    os.mkfifo(fifo)
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
         str(wrong_ios), str(corrupt), str(folder), str(fifo)],
        check=True, timeout=90, env=env
    )
