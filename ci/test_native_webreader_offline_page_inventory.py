#!/usr/bin/env python3
"""Build69 BH: execute actual Swift offline page inventory using disposable files.

Checks strict gaps/nonzero sizes, rejects symlinks and directories masquerading
as images, and keeps original image bytes unchanged. No network, no WebReader
user Library or on-device data are accessed.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SWIFT_SOURCE = ROOT / "MangaReader12/Downloads/WebReaderOfflinePageInventory.swift"

SWIFT_TEST = r'''
import Foundation

func check(_ result: @autoclosure () -> Bool, _ why: String) {
    if !result() { fatalError(why) }
}
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let folder = root.appendingPathComponent("chapter", isDirectory: true)
let fm = FileManager.default
try fm.createDirectory(at: folder, withIntermediateDirectories: true, attributes: nil)
func page(_ i: Int) -> URL {
    return folder.appendingPathComponent(String(format: "page-%05d.bin", i))
}
func save(_ i: Int, _ contents: Data = Data([0x89, 0x50, 0x4E, 0x47])) throws {
    try contents.write(to: page(i), options: .atomic)
}
func rejected(_ why: String) {
    do {
        _ = try WebReaderOfflinePageInventory.inspect(directory: folder)
        fatalError("accepted unsafe offline page set: " + why)
    } catch let error as WebReaderOfflinePageInventory.AuditError {
        check(error != .tooManyPages, "unexpected max-pages error")
    } catch {
        // macOS Foundation can reject a symlinked *directory* before it
        // returns URLResourceValues. That is also a fail-closed rejection.
        if why != "symbolic link chapter directory" {
            fatalError("unexpected error while checking " + why + ": " +
                       String(describing: error))
        }
    }
}
try save(0)
try save(1)
try save(2)
let snapshot = try WebReaderOfflinePageInventory.inspect(directory: folder)
check(snapshot.count == 3, "three files")
check(snapshot.map { $0.lastPathComponent } == [
    "page-00000.bin", "page-00001.bin", "page-00002.bin"
], "page indexes unchanged")
let originalBytes = try Data(contentsOf: page(0))
check(originalBytes.count == 4, "no bytes mutated")
try fm.removeItem(at: page(1))
rejected("gap in middle")
try save(1)
try fm.removeItem(at: page(0))
rejected("missing initial page")
try save(0)
try Data().write(to: page(2), options: .atomic)
rejected("empty last page")
try save(2)
try fm.removeItem(at: page(2))
try fm.createSymbolicLink(at: page(2), withDestinationURL: page(1))
rejected("symbolic link image")
try fm.removeItem(at: page(2))
try save(2)
try fm.createDirectory(at: page(3), withIntermediateDirectories: false, attributes: nil)
rejected("directory disguised as image")
try fm.removeItem(at: page(3))
let foreign = folder.appendingPathComponent("unrelated-file.txt")
try Data([1]).write(to: foreign)
let unaffectedPages = try WebReaderOfflinePageInventory.inspect(directory: folder)
check(unaffectedPages.count == 3,
      "unrelated marker must not rewrite or invalidate pages")
try save(10)
rejected("gap after last previous page")
try fm.removeItem(at: page(10))
try fm.removeItem(at: page(0))
try fm.removeItem(at: page(1))
try fm.removeItem(at: page(2))
rejected("no pages")
let moved = root.appendingPathComponent("target.bin")
try Data([1, 2]).write(to: moved)
try fm.removeItem(at: folder)
try fm.createSymbolicLink(at: folder, withDestinationURL: root)
rejected("symbolic link chapter directory")
let targetBytes = try Data(contentsOf: moved)
check(targetBytes.count == 2, "target untouched")
print("PASS native Swift BH: strict contiguous offline pages, no data mutation")
'''
with tempfile.TemporaryDirectory(prefix="wr69-bh-offline-pages-") as td:
    root = Path(td)
    test = root / "main.swift"
    test.write_text(SWIFT_TEST, encoding="utf-8")
    exe = root / "offline-test"
    subprocess.run(
        ["swiftc", "-swift-version", "5", str(SWIFT_SOURCE), str(test),
         "-o", str(exe)],
        check=True, capture_output=True, text=True, timeout=120,
    )
    result = subprocess.run(
        [str(exe), str(root)],
        capture_output=True, text=True, timeout=45,
    )
    if result.returncode != 0:
        raise RuntimeError("native offline test failed:\n" + result.stderr[-3000:])
    print(result.stdout.strip())
