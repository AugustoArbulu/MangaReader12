#!/usr/bin/env python3
"""Build69 BQ: real Swift bounded plan reader rejects unsafe disk inputs.

All sources are temporary synthetic files, not actual download plans.
A FIFO test confirms O_NONBLOCK prevents hanging on an unwritten pipe.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
READER = ROOT / "MangaReader12/Downloads/WebReaderOfflineRecoveryPlanReader.swift"
SWIFT = r'''
import Foundation
let path = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: false)
let expected = CommandLine.arguments[2]
if expected == "valid" {
    let data = try WebReaderOfflineRecoveryPlanReader.read(from: path)
    guard data == Data("{\"schemaVersion\":1}".utf8) else {
        fatalError("wrong original bytes")
    }
} else {
    do {
        _ = try WebReaderOfflineRecoveryPlanReader.read(from: path)
        fatalError("unsafe or missing plan accepted: " + expected)
    } catch is WebReaderOfflineRecoveryPlanReader.PlanError {
        // Expected fail-closed.
    }
}
print("PASS native BQ: " + expected)
'''
with tempfile.TemporaryDirectory(prefix="wr69-bq-recovery-") as temp:
    root = Path(temp)
    main = root / "main.swift"
    main.write_text(SWIFT, encoding="utf-8")
    exe = root / "read-plan-test"
    compiled = subprocess.run(
        ["swiftc", "-swift-version", "5", str(READER), str(main), "-o", str(exe)],
        capture_output=True, text=True, timeout=120
    )
    if compiled.returncode:
        raise RuntimeError("BQ native Swift compile failed:\n" + compiled.stderr[-3500:])

    def check(path, mode):
        result = subprocess.run(
            [str(exe), str(path), mode],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError("BQ failed (" + mode + "):\n" + result.stderr[-3500:])
        print(result.stdout.strip())

    valid = root / "valid.json"
    content = b'{"schemaVersion":1}'
    valid.write_bytes(content)
    check(valid, "valid")
    assert valid.read_bytes() == content

    empty = root / "empty.json"
    empty.write_bytes(b"")
    check(empty, "empty")
    huge = root / "huge.json"
    with huge.open("wb") as stream:
        stream.truncate(16 * 1024 * 1024 + 1)
    check(huge, "oversized")
    folder = root / "directory"
    folder.mkdir()
    check(folder, "directory")
    linked = root / "linked.json"
    linked.symlink_to(valid)
    check(linked, "symlink")
    fifo = root / "pipe.json"
    os.mkfifo(fifo)
    check(fifo, "fifo")
    check(root / "nonexistent.json", "missing")
    assert valid.read_bytes() == content
    assert linked.is_symlink()
    assert huge.stat().st_size == 16 * 1024 * 1024 + 1
    print("PASS native Swift BQ: no writes and no blocking on FIFOs")
