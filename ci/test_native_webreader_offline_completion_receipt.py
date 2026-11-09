#!/usr/bin/env python3
"""Build69 BM native Swift receipt: old chapters work; new ones catch lost tail.

All files live under a disposable directory. This test never scans real
user downloads, never uses network, and never triggers installation.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Downloads/WebReaderOfflineCompletionReceipt.swift"

SWIFT = r'''
import Foundation

func expect(_ result: @autoclosure () -> Bool, _ reason: String) {
    if !result() { fatalError(reason) }
}
func reject(_ reason: String, _ callback: () throws -> Void) {
    do {
        try callback()
        fatalError("receipt should have rejected " + reason)
    } catch let e as WebReaderOfflineCompletionReceipt.ReceiptError {
        expect(e == .invalidReceipt || e == .invalidCount, "receipt-specific error")
    } catch {
        fatalError("unexpected rejection " + reason + ": " + String(describing: error))
    }
}
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let fm = FileManager.default
let old = root.appendingPathComponent("old", isDirectory: true)
let current = root.appendingPathComponent("new", isDirectory: true)
try fm.createDirectory(at: old, withIntermediateDirectories: true)
try fm.createDirectory(at: current, withIntermediateDirectories: true)
let oldLegacy = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
    directory: old, actualPages: 2)
expect(oldLegacy == false, "Build68 legacy directory must remain usable")
try WebReaderOfflineCompletionReceipt.write(
    directory: current, expectedPages: 3
)
let receipt = current.appendingPathComponent(
    WebReaderOfflineCompletionReceipt.filename
)
let onDisk = try Data(contentsOf: receipt)
expect(String(data: onDisk, encoding: .utf8) == "WR-OFFLINE-COMPLETE-V1:3\n",
       "new receipt is a small count-only private text marker")
let validReceipt = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
    directory: current, actualPages: 3)
expect(validReceipt == true, "valid new receipt")
reject("last page missing", {
    _ = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: current, actualPages: 2)
})
reject("extra unexpected page", {
    _ = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: current, actualPages: 4)
})
reject("empty marker", {
    try Data().write(to: receipt, options: .atomic)
    _ = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: current, actualPages: 3)
})
reject("malformed marker", {
    try Data("WR-OFFLINE-COMPLETE-V1:003\n".utf8)
        .write(to: receipt, options: .atomic)
    _ = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: current, actualPages: 3)
})
reject("oversized marker", {
    try Data(repeating: 0x61, count: 65).write(to: receipt, options: .atomic)
    _ = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: current, actualPages: 3)
})
try fm.removeItem(at: receipt)
let elsewhere = root.appendingPathComponent("target")
try Data("WR-OFFLINE-COMPLETE-V1:3\n".utf8).write(to: elsewhere)
try fm.createSymbolicLink(at: receipt, withDestinationURL: elsewhere)
reject("symlinked marker", {
    _ = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: current, actualPages: 3)
})
let targetData = try Data(contentsOf: elsewhere)
expect(targetData.count > 0, "symlink target untouched")
try fm.removeItem(at: receipt)
try fm.createDirectory(at: receipt, withIntermediateDirectories: false)
reject("directory masquerading as marker", {
    _ = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
        directory: current, actualPages: 3)
})
for invalid in (0, -1, 100000) {
    reject("invalid page count", {
        try WebReaderOfflineCompletionReceipt.write(
            directory: old, expectedPages: invalid)
    })
}
let legacyAfter = try WebReaderOfflineCompletionReceipt.verifyIfPresent(
    directory: old, actualPages: 2)
expect(legacyAfter == false, "legacy chapter still has no receipt after failed writes")
print("PASS native Swift BM: optional legacy receipt, missing final page, malformed/symlink rejection")
'''
with tempfile.TemporaryDirectory(prefix="wr69-bm-completion-") as td:
    root = Path(td)
    main = root / "main.swift"
    main.write_text(SWIFT)
    exe = root / "receipt-tests"
    compile_result = subprocess.run(
        ["swiftc", "-swift-version", "5", str(SOURCE), str(main),
         "-o", str(exe)], capture_output=True, text=True, timeout=120
    )
    if compile_result.returncode != 0:
        raise RuntimeError("BM Swift compile: " + compile_result.stderr[-3500:])
    result = subprocess.run(
        [str(exe), str(root)], capture_output=True, text=True, timeout=45
    )
    if result.returncode != 0:
        raise RuntimeError("BM Swift runtime: " + result.stderr[-3500:])
    print(result.stdout.strip())
