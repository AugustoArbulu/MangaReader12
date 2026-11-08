#!/usr/bin/env python3
"""Native Swift cache-retention QA on macOS; synthetic files only, no install."""
from pathlib import Path
import subprocess
import tempfile

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
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let cache = root.appendingPathComponent("WebReaderUpdates", isDirectory: true)
let source = root.appendingPathComponent("original-Filza.ipa")
try! Data("owner source untouched".utf8).write(to: source)
let future = Date(timeIntervalSinceNow: 72 * 3600)

func inventory(
    _ when: Date = Date(), _ protected: String? = nil
) -> WebReaderLocalQAStorageInventory {
    return try! WebReaderReleaseCacheStorage.inventory(
        directory: cache, now: when, protectedName: protected
    )
}
func discard(
    _ candidate: WebReaderLocalQAStaleCandidate,
    when: Date = Date(), protected: String? = nil
) -> Bool {
    return WebReaderReleaseCacheStorage.discardConfirmed(
        candidate, directory: cache, now: when, protectedName: protected
    )
}
func make(_ name: String, contents: Data) -> URL {
    let url = cache.appendingPathComponent(name)
    try! contents.write(to: url)
    return url
}

let good = "WebReader-build69-11111111-2222-4333-8444-555555555555.ipa"
let kept = "WebReader-build70-11111111-2222-4333-8444-555555555555.ipa"
let partial = ".webreader-11111111-2222-4333-8444-555555555555.partial"
for name in [good, kept, partial] {
    insist(WebReaderReleaseCacheStorage.isManagedName(name), "valid cache grammar")
}
for name in [
    "../" + good, "WebReader-build0-11111111-2222-4333-8444-555555555555.ipa",
    "WebReader-Build69-11111111-2222-4333-8444-555555555555.ipa",
    "WebReader-build69-11111111-2222-4333-8444-555555555555.ipa.zip",
    ".webreader-../../Library.partial", "important.backup", ".partial"
] {
    insist(!WebReaderReleaseCacheStorage.isManagedName(name), "strict grammar")
}
let empty = inventory()
insist(empty.eligible.isEmpty && empty.eligibleBytes == 0, "missing cache empty")
insist(!FileManager.default.fileExists(atPath: cache.path), "inventory no mkdir")
try! FileManager.default.createDirectory(at: cache, withIntermediateDirectories: true)
let expectedFile = make(good, contents: Data("completed old IPA".utf8))
let active = make(kept, contents: Data("user selected IPA".utf8))
let abandoned = make(partial, contents: Data())
let stranger = make("Library.sqlite", contents: Data("preserved".utf8))
let linked = cache.appendingPathComponent(
    "WebReader-build71-11111111-2222-4333-8444-555555555555.ipa"
)
try! FileManager.default.linkItem(at: source, to: linked)
let symlink = cache.appendingPathComponent(
    "WebReader-build72-11111111-2222-4333-8444-555555555555.ipa"
)
try! FileManager.default.createSymbolicLink(at: symlink, withDestinationURL: source)

let fresh = inventory()
insist(fresh.eligible.count == 0, "24h retention is enforced")
let aged = inventory(future, kept)
insist(aged.eligible.count == 2 && aged.eligibleBytes == 17,
       "old completed and zero-byte partial, excluding protected active")
insist(aged.ignoredEntries == 4, "active, stranger, symlink, hardlink retained")
let candidate = aged.eligible.first { $0.fileName == good }!
let oldPartial = aged.eligible.first { $0.fileName == partial }!
insist(!discard(candidate), "recent file cannot be deleted")
insist(!discard(oldPartial), "recent empty partial cannot be deleted")
insist(!discard(candidate, when: future, protected: good),
       "protected name cannot be removed")
insist(!discard(candidate, when: future, protected: candidate.fileName),
       "protected build remains intact")

let backup = root.appendingPathComponent("moved-original-cache.ipa")
try! FileManager.default.moveItem(at: expectedFile, to: backup)
_ = make(good, contents: Data("completed old IPA".utf8))
insist(!discard(candidate, when: future), "identical bytes new inode rejected")
try! FileManager.default.removeItem(at: expectedFile)
try! FileManager.default.moveItem(at: backup, to: expectedFile)
insist(!discard(candidate, when: future), "changed ctime rejects stale receipt")
let refreshed = inventory(future, kept).eligible.first { $0.fileName == good }!
insist(discard(refreshed, when: future, protected: kept), "confirmed old cache removed")
insist(discard(oldPartial, when: future, protected: kept), "abandoned partial removed")
insist(!FileManager.default.fileExists(atPath: expectedFile.path), "removed old cache")
insist(!FileManager.default.fileExists(atPath: abandoned.path), "removed old partial")
insist(FileManager.default.fileExists(atPath: active.path), "active saved")
insist(FileManager.default.fileExists(atPath: stranger.path), "library-like file safe")
insist(try! Data(contentsOf: source) == Data("owner source untouched".utf8),
       "original owner file untouched")

let fakeSymlinkDir = root.appendingPathComponent("wrong-dir")
try! FileManager.default.createSymbolicLink(at: fakeSymlinkDir, withDestinationURL: cache)
do {
    _ = try WebReaderReleaseCacheStorage.inventory(directory: fakeSymlinkDir)
    fatalError("directory symlink accepted")
} catch WebReaderLocalQAStorageError.invalidDirectory {}

for index in 0..<509 {
    let file = cache.appendingPathComponent("foreign-" + String(index))
    try! Data().write(to: file)
}
do {
    _ = try WebReaderReleaseCacheStorage.inventory(directory: cache)
    fatalError("unbounded directory listing accepted")
} catch WebReaderLocalQAStorageError.tooManyEntries {}

print("PASS native release cache: 24h, inode/ctime, partial, name, bounded scan, protected active, source/library preserved, no appinst")
'''

with tempfile.TemporaryDirectory(prefix="webreader-release-cache-safe-") as tmp:
    folder = Path(tmp)
    runner = folder / "main.swift"
    runner.write_text(SWIFT)
    executable = folder / "release-cache-test"
    subprocess.run(
        ["swiftc", "-swift-version", "5", *map(str, SOURCES),
         str(runner), "-framework", "Security", "-o", str(executable)],
        check=True, timeout=120
    )
    subprocess.run([str(executable), str(folder)], check=True, timeout=90)
