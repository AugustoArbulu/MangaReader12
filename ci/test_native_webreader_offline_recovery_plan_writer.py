#!/usr/bin/env python3
"""Build69 BR: real native Swift tests of crash-safe bounded recovery metadata.

Uses only disposable files; never reads the real user's WebReader directory.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
READER = ROOT / "MangaReader12/Downloads/WebReaderOfflineRecoveryPlanReader.swift"
WRITER = ROOT / "MangaReader12/Downloads/WebReaderOfflineRecoveryPlanWriter.swift"

SWIFT = r'''
import Foundation
import Darwin

func insist(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fatalError(message) }
}
func expectDenied(_ context: String, _ action: () throws -> Void) {
    do {
        try action()
        fatalError("accepted invalid recovery write: " + context)
    } catch is WebReaderOfflineRecoveryPlanWriter.WriteError {
        // Refusal by the dedicated writer is required.
    } catch {
        fatalError("unexpected exception while writing " + context + ": " +
                   String(describing: error))
    }
}
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let directory = root.appendingPathComponent("chapter", isDirectory: true)
let fm = FileManager.default
try fm.createDirectory(at: directory, withIntermediateDirectories: true)
let file = directory.appendingPathComponent("_download-plan.json")
let valid = Data("{\"schemaVersion\":1}".utf8)
let changed = Data("{\"schemaVersion\":1,\"queueOrder\":-1}".utf8)
try WebReaderOfflineRecoveryPlanWriter.write(data: valid, to: file)
let roundTrip = try WebReaderOfflineRecoveryPlanReader.read(from: file)
insist(roundTrip == valid, "new plan round trip")
let info = try fm.attributesOfItem(atPath: file.path)
let mode = (info[.posixPermissions] as? NSNumber)?.intValue ?? -1
insist(mode == 0o600, "plan stored with private 0600 permissions")

try WebReaderOfflineRecoveryPlanWriter.write(data: changed, to: file)
let changedRoundTrip = try WebReaderOfflineRecoveryPlanReader.read(from: file)
insist(changedRoundTrip == changed, "reprioritized plan replaced atomically")

expectDenied("empty data", {
    try WebReaderOfflineRecoveryPlanWriter.write(data: Data(), to: file)
})
expectDenied("17MiB over 16MiB", {
    try WebReaderOfflineRecoveryPlanWriter.write(
        data: Data(repeating: 1, count: 16 * 1024 * 1024 + 1), to: file
    )
})
let afterDenials = try WebReaderOfflineRecoveryPlanReader.read(from: file)
insist(afterDenials == changed, "failed writes preserve previous ordinary plan")

let wrong = directory.appendingPathComponent("unrelated-user-data.json")
try Data("OWNER DATA".utf8).write(to: wrong)
expectDenied("unexpected filename", {
    try WebReaderOfflineRecoveryPlanWriter.write(data: valid, to: wrong)
})
let userData = try Data(contentsOf: wrong)
insist(userData == Data("OWNER DATA".utf8), "unrelated data preserved")

try fm.removeItem(at: file)
try fm.createSymbolicLink(at: file, withDestinationURL: wrong)
expectDenied("existing symlink", {
    try WebReaderOfflineRecoveryPlanWriter.write(data: valid, to: file)
})
let dataAfterSymlink = try Data(contentsOf: wrong)
insist(dataAfterSymlink == Data("OWNER DATA".utf8), "symlink target unchanged")
let linkValues = try file.resourceValues(forKeys: [.isSymbolicLinkKey])
insist(file.isFileURL && linkValues.isSymbolicLink == true,
       "link not replaced")
try fm.removeItem(at: file)

try fm.createDirectory(at: file, withIntermediateDirectories: false)
expectDenied("existing directory", {
    try WebReaderOfflineRecoveryPlanWriter.write(data: valid, to: file)
})
insist(fm.fileExists(atPath: file.path), "unsafe directory not removed")
try fm.removeItem(at: file)

let brokenRoot = root.appendingPathComponent("linked-chapter")
try fm.createSymbolicLink(at: brokenRoot, withDestinationURL: directory)
expectDenied("linked chapter directory", {
    try WebReaderOfflineRecoveryPlanWriter.write(
        data: valid, to: brokenRoot.appendingPathComponent("_download-plan.json")
    )
})
try WebReaderOfflineRecoveryPlanWriter.write(data: valid, to: file)
let finalBytes = try Data(contentsOf: file)
insist(finalBytes == valid, "successful writer still usable after refusals")
let contents = try fm.contentsOfDirectory(atPath: directory.path)
insist(contents.filter { $0.hasPrefix(".wr69-plan-") }.isEmpty,
       "no temporary recovery metadata remains")
print("PASS native Swift BR: bounded private atomic plan write/replace, old bytes preserved")
'''
with tempfile.TemporaryDirectory(prefix="wr69-br-atomic-writer-") as temp:
    root = Path(temp)
    main = root / "main.swift"
    main.write_text(SWIFT, encoding="utf-8")
    binary = root / "native-writer"
    compile = subprocess.run(
        ["swiftc", "-swift-version", "5", str(READER), str(WRITER),
         str(main), "-o", str(binary)],
        capture_output=True, text=True, timeout=120
    )
    if compile.returncode:
        raise RuntimeError("BR Swift compiler: " + compile.stderr[-4500:])
    run = subprocess.run(
        [str(binary), str(root)], capture_output=True, text=True, timeout=45
    )
    if run.returncode:
        raise RuntimeError("BR Swift runtime: " + run.stderr[-4500:])
    print(run.stdout.strip())
