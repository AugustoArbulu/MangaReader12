#!/usr/bin/env python3
"""Native macOS Swift QA inventory/cleanup tests — no installation, no root.

The files are disposable ZIP fixtures with no executable app. Test time is
injected to simulate copies aging; we never modify system clocks.
"""
from pathlib import Path
import hashlib
import os
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

SWIFT = r'''
import Foundation

func insist(_ condition: @autoclosure () -> Bool, _ label: String) {
    if !condition() { fatalError(label) }
}
let args = CommandLine.arguments
insist(args.count == 4, "root source expectedSHA")
let root = URL(fileURLWithPath: args[1], isDirectory: true)
let source = URL(fileURLWithPath: args[2])
let checksum = args[3]
let qa = root.appendingPathComponent("WebReaderLocalQAImports", isDirectory: true)
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
let future = Date(timeIntervalSinceNow: 72 * 3600)

func imported() -> WebReaderLocalIPAReview {
    return try! WebReaderLocalIPAReviewer.importForReview(
        sourceURL: source, expectedBuild: 69,
        expectedSHA256: checksum, installedBuild: 68,
        installedIOS: ios, directory: qa
    )
}
func inventory(
    _ when: Date = Date(),
    _ protected: WebReaderLocalIPAReview? = nil
) -> WebReaderLocalQAStorageInventory {
    return try! WebReaderLocalQAStorage.inventory(
        directory: qa, now: when, protected: protected
    )
}
func clean(_ c: WebReaderLocalQAStaleCandidate,
           now: Date = Date(),
           protected: WebReaderLocalIPAReview? = nil) -> Bool {
    return WebReaderLocalQAStorage.discardConfirmed(
        c, directory: qa, now: now, protected: protected
    )
}
func expectStorageError(_ location: URL) {
    do {
        _ = try WebReaderLocalQAStorage.inventory(directory: location)
        fatalError("Unsafe directory was accepted")
    } catch WebReaderLocalQAStorageError.invalidDirectory {
        // Expected refusal.
    } catch {
        fatalError("Unexpected inventory error: " + String(describing: error))
    }
}
insist(WebReaderLocalQAStorage.isQAName(
    "WebReader-Build69-local-12345678-1234-4abc-8def-1234567890ab.ipa"
), "strict expected filename")
for bad in [
    "../WebReader-Build69-local-12345678-1234-4abc-8def-1234567890ab.ipa",
    "WebReader-Build0-local-12345678-1234-4abc-8def-1234567890ab.ipa",
    "WebReader-Build69-local-12345678-1234-4abc-8def-1234567890ab.ipa.zip",
    "WebReader-Build69-local-../../Library.ipa",
    "backup.ipa", ".ipa",
    "WebReader-Build69-local-AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAA.ipa",
] {
    insist(!WebReaderLocalQAStorage.isQAName(bad),
           "reject unowned or malformed QA filename " + bad)
}

let virgin = inventory()
insist(virgin.eligible.isEmpty && virgin.eligibleBytes == 0,
       "missing QA folder reports zero and does not create anything")
insist(!FileManager.default.fileExists(atPath: qa.path),
       "inventory never creates a new staging folder")

let simulatedLibrary = root.appendingPathComponent("private-library", isDirectory: true)
try! FileManager.default.createDirectory(
    at: simulatedLibrary, withIntermediateDirectories: true
)
let fakeLink = root.appendingPathComponent("QA-symlink")
try! FileManager.default.createSymbolicLink(at: fakeLink,
                                            withDestinationURL: simulatedLibrary)
expectStorageError(fakeLink)
let fakeFile = root.appendingPathComponent("QA-file")
try! Data("not a directory".utf8).write(to: fakeFile)
expectStorageError(fakeFile)

let active = imported()
let old = imported()
insist(active.stagingInode != old.stagingInode,
       "each review import creates its own file identity")
let freshInventory = inventory()
insist(freshInventory.eligible.isEmpty &&
       freshInventory.ignoredEntries == 2,
       "recent copies are never eligible for cleanup")
let candidateInventory = inventory(future, active)
insist(candidateInventory.eligible.count == 1 &&
       candidateInventory.eligibleBytes == old.ipaBytes,
       "fake future makes only unprotected 24h-old copy eligible")
let candidate = candidateInventory.eligible[0]
insist(candidate.fileInode == old.stagingInode &&
       candidate.fileDevice == old.stagingDevice,
       "snapshot captures exactly the reviewed old inode")
insist(!clean(candidate), "without elapsed age deletion must fail")
insist(!clean(candidate, now: future, protected: old),
       "receipt for active review blocks deletion")
insist(FileManager.default.fileExists(atPath: old.copiedIPAURL.path),
       "no accidental deletion before explicit owner consent")

// The pattern is only one safeguard: any symlink, hardlink or unrelated
// document must remain untouched despite appearing inside the QA folder.
let stranger = qa.appendingPathComponent("Biblioteca-do-usuario.backup")
try! Data("user data".utf8).write(to: stranger)
let symlinkName = qa.appendingPathComponent(
    "WebReader-Build69-local-11111111-2222-4333-8444-555555555555.ipa"
)
try! FileManager.default.createSymbolicLink(
    at: symlinkName, withDestinationURL: source
)
let hardlinked = qa.appendingPathComponent(
    "WebReader-Build69-local-33333333-2222-4333-8444-555555555555.ipa"
)
try! FileManager.default.linkItem(at: source, to: hardlinked)
let mixed = inventory(future, active)
insist(mixed.eligible.count == 1 && mixed.ignoredEntries == 4,
       "exclude symlink hardlink unrelated and active review")
insist(!WebReaderLocalQAStorage.discardConfirmed(
    WebReaderLocalQAStaleCandidate(
        fileName: stranger.lastPathComponent, byteCount: 9,
        fileDevice: candidate.fileDevice,
        fileInode: candidate.fileInode,
        modifiedSeconds: candidate.modifiedSeconds,
        modifiedNanoseconds: candidate.modifiedNanoseconds,
        changedSeconds: candidate.changedSeconds,
        changedNanoseconds: candidate.changedNanoseconds
    ), directory: qa, now: future
), "cannot delete an unrelated library backup")

// A malicious rename+replacement at the same pathname must be rejected
// even when the replacement has byte-identical SHA-256.
let oldIdentity = root.appendingPathComponent("true-old.ipa")
try! FileManager.default.moveItem(at: old.copiedIPAURL, to: oldIdentity)
try! FileManager.default.copyItem(at: source, to: old.copiedIPAURL)
insist(!clean(candidate, now: future),
       "different inode under same path must not be deleted")
insist(try! Data(contentsOf: old.copiedIPAURL) ==
       Data(contentsOf: source), "foreign replacement remains in place")
try! FileManager.default.removeItem(at: old.copiedIPAURL)
try! FileManager.default.moveItem(at: oldIdentity, to: old.copiedIPAURL)

// A snapshot whose metadata is stale must also be refused; no path
// scanning or unauthenticated SHA is sufficient for deletion.
var mismatched = WebReaderLocalQAStaleCandidate(
    fileName: candidate.fileName,
    byteCount: candidate.byteCount,
    fileDevice: candidate.fileDevice,
    fileInode: candidate.fileInode,
    modifiedSeconds: candidate.modifiedSeconds,
    modifiedNanoseconds: candidate.modifiedNanoseconds,
    changedSeconds: candidate.changedSeconds,
    changedNanoseconds: candidate.changedNanoseconds + 1
)
insist(!clean(mismatched, now: future),
       "nanosecond ctime mismatch must refuse old snapshot")

// After the user's affirmative consent and still-valid receipt, exactly
// the old copy is discarded. Original Filza selection and active review
// remain intact.
insist(clean(candidate, now: future, protected: active),
       "an exact, aged non-active candidate is eligible after confirmation")
insist(!FileManager.default.fileExists(atPath: old.copiedIPAURL.path),
       "only explicitly selected stale QA inode was removed")
insist(FileManager.default.fileExists(atPath: active.copiedIPAURL.path),
       "currently reviewed QA file remains")
insist(FileManager.default.fileExists(atPath: stranger.path),
       "library-like unrecognized file remains")
insist(try! Data(contentsOf: source) ==
       Data(contentsOf: hardlinked), "original downloaded IPA unchanged")
WebReaderLocalIPAReviewer.discard(active, directory: qa)
try! FileManager.default.removeItem(at: symlinkName)
try! FileManager.default.removeItem(at: hardlinked)
try! FileManager.default.removeItem(at: stranger)
insist(inventory().eligible.isEmpty, "final QA cleanup inventory empty")
print("PASS native iOS12 QA inventory: 24h gating, 16 safety scenarios, active-file protection, regular-only, inode and nanosecond checks, explicit cleanup only")
'''
with tempfile.TemporaryDirectory(prefix="webreader-qa-storage-") as tmp:
    folder = Path(tmp)
    source, checksum = make_ipa(folder, build="69")
    assert checksum == hashlib.sha256(source.read_bytes()).hexdigest()
    runner = folder / "main.swift"
    runner.write_text(SWIFT)
    executable = folder / "local-qa-storage-test"
    subprocess.run(
        ["swiftc", "-swift-version", "5", *map(str, SOURCES),
         str(runner), "-framework", "Security", "-o", str(executable)],
        check=True, timeout=120,
    )
    subprocess.run(
        [str(executable), str(folder), str(source), checksum],
        check=True, timeout=90,
    )
