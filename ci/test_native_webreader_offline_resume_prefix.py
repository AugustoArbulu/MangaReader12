#!/usr/bin/env python3
"""Build69 BO: real Swift resume-prefix checks on disposable files only."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Downloads/WebReaderOfflineResumePrefix.swift"
SWIFT = r'''
import Foundation

func check(_ yes: @autoclosure () -> Bool, _ message: String) {
    if !yes() { fatalError(message) }
}
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let folder = root.appendingPathComponent("chapter", isDirectory: true)
let fm = FileManager.default
try fm.createDirectory(at: folder, withIntermediateDirectories: false)
func page(_ number: Int) -> URL {
    folder.appendingPathComponent(String(format: "page-%05d.bin", number))
}
func count(_ planned: Int = 5) -> Int {
    WebReaderOfflineResumePrefix.count(directory: folder, plannedPages: planned)
}
check(count() == 0, "empty resumable directory starts from first page")
try Data([0x89,0x50,0x4e,0x47]).write(to: page(0))
check(count() == 1, "first valid file reused")
try Data([1,2,3]).write(to: page(1))
check(count() == 2, "valid two-page prefix")
check(count(1) == 1, "bounded planned count")
try Data([1,2,3]).write(to: page(3))
check(count() == 2, "out-of-order page must not be reused")
try Data().write(to: page(2))
check(count() == 2, "zero-length page invalid")
try fm.removeItem(at: page(2))
let elsewhere = root.appendingPathComponent("unrelated-user-content")
try Data([1,2,3,4]).write(to: elsewhere)
try fm.createSymbolicLink(at: page(2), withDestinationURL: elsewhere)
check(count() == 2, "a page symlink cannot be reused")
let targetBefore = try Data(contentsOf: elsewhere)
check(targetBefore.count == 4, "target not touched")
try fm.removeItem(at: page(2))
try fm.createDirectory(at: page(2), withIntermediateDirectories: false)
check(count() == 2, "page-shaped directory is not an image")
try fm.removeItem(at: page(2))
try Data(repeating: 1, count: 256).write(to: page(2))
check(count() == 4, "proper contiguous prefix ending at page3")
check(count(4) == 4, "complete subset of four files")
check(count(0) == 0 && count(-3) == 0 && count(5001) == 0,
      "invalid unbounded plans are denied")
try fm.removeItem(at: folder)
try fm.createSymbolicLink(at: folder, withDestinationURL: root)
check(count() == 0, "symlinked chapter folder must not be used")
let targetAfter = try Data(contentsOf: elsewhere)
check(targetAfter.count == 4, "no mutations")
print("PASS native Swift BO: safe resumable prefix, gaps, symlinks and legacy data")
'''
with tempfile.TemporaryDirectory(prefix="wr69-bo-resume-") as temp:
    directory = Path(temp)
    main = directory / "main.swift"
    main.write_text(SWIFT, encoding="utf-8")
    exe = directory / "test-resume"
    r = subprocess.run(
        ["swiftc", "-swift-version", "5", str(SOURCE), str(main),
         "-o", str(exe)], capture_output=True, text=True, timeout=120,
    )
    if r.returncode:
        raise RuntimeError("BO Swift compile failed: " + r.stderr[-3000:])
    r = subprocess.run(
        [str(exe), str(directory)],
        capture_output=True, text=True, timeout=35,
    )
    if r.returncode:
        raise RuntimeError("BO Swift run failed: " + r.stderr[-3000:])
    print(r.stdout.strip())
