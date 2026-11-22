#!/usr/bin/env python3
"""Phase Z: run actual Swift Darwin fstatfs budget policy on macOS.

No network, IPA install, owner key, or filesystem deletion outside ephemeral
test directory. Synthetic 512 MiB sizes are arithmetic only; no large files.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Core/WebReaderIPADownloadBudget.swift"

SWIFT = r'''
import Foundation

func ensure(_ state: @autoclosure () -> Bool, _ name: String) {
    if !state() { fatalError(name) }
}
let path = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let missing = path.appendingPathComponent("absent", isDirectory: true)
let valid = path.appendingPathComponent("real", isDirectory: true)
let linked = path.appendingPathComponent("linked", isDirectory: true)
try! FileManager.default.createDirectory(at: valid, withIntermediateDirectories: true)
try! FileManager.default.createSymbolicLink(
    at: linked, withDestinationURL: valid
)
let policy = WebReaderIPADownloadBudget.self
ensure(policy.availableFreeBytes(in: missing) == nil, "missing directory denied")
ensure(policy.availableFreeBytes(in: linked) == nil, "symlink directory denied")
ensure(policy.availableFreeBytes(in: URL(string: "https://example.com")!) == nil,
       "nonfile URL denied")
guard let actual = policy.availableFreeBytes(in: valid) else {
    fatalError("normal writable temp filesystem unavailable")
}
ensure(actual > 0, "real filesystem has free space")
ensure(policy.requiredFreeBytes(ipaBytes: 0) == nil, "zero size denied")
ensure(policy.requiredFreeBytes(ipaBytes: -1) == nil, "negative size denied")
ensure(policy.requiredFreeBytes(ipaBytes: 512 * 1024 * 1024 + 1) == nil,
       "over 512 MiB denied")
ensure(policy.requiredFreeBytes(ipaBytes: 1) == 40 * 1024 * 1024 + 1,
       "small IPA requires 32 MiB reserve plus 8 MiB overhead")
let large = 512 * 1024 * 1024
let needed = policy.requiredFreeBytes(ipaBytes: Int64(large))!
ensure(needed == Int64(large + 64 * 1024 * 1024 + 8 * 1024 * 1024),
       "large IPA requires 12.5% safety reserve plus overhead")
ensure(policy.enoughSpace(freeBytes: needed, ipaBytes: Int64(large)),
       "exact threshold allowed")
ensure(!policy.enoughSpace(freeBytes: needed - 1, ipaBytes: Int64(large)),
       "one byte below threshold denied")
// The reserve must NEVER shrink when most of a large IPA has arrived.
let fixedReserve: Int64 = 72 * 1024 * 1024
ensure(policy.enoughSpaceDuringTransfer(
    freeBytes: fixedReserve, remainingBytes: 0, totalIPABytes: Int64(large)
), "exact original budget remains after last chunk")
ensure(!policy.enoughSpaceDuringTransfer(
    freeBytes: fixedReserve - 1, remainingBytes: 0, totalIPABytes: Int64(large)
), "cannot spend fixed original safety reserve on the final chunk")
ensure(policy.enoughSpaceDuringTransfer(
    freeBytes: needed, remainingBytes: Int64(large), totalIPABytes: Int64(large)
), "initial sampled transfer threshold equals preflight threshold")
ensure(!policy.enoughSpaceDuringTransfer(
    freeBytes: Int64.max, remainingBytes: Int64(large) + 1,
    totalIPABytes: Int64(large)
), "invalid remaining bytes denied")
ensure(!policy.enoughSpaceDuringTransfer(
    freeBytes: Int64.max, remainingBytes: -1, totalIPABytes: Int64(large)
), "negative remaining bytes denied")
ensure(!policy.enoughSpaceDuringTransfer(
    freeBytes: Int64.max, remainingBytes: 0, totalIPABytes: 0
), "zero original IPA denied")
ensure(!policy.enoughSpace(freeBytes: -1, ipaBytes: Int64(large)),
       "unknown free space denied")
ensure(!policy.enoughSpace(freeBytes: Int64.max, ipaBytes: Int64.max),
       "oversized IPA never allowed")
ensure(policy.enoughSpace(freeBytes: Int64.max, ipaBytes: 1),
       "ordinary small IPA with capacity accepted")
ensure(FileManager.default.fileExists(atPath: valid.path), "directory preserved")
ensure(FileManager.default.fileExists(atPath: linked.path), "symlink untouched")
ensure(!FileManager.default.fileExists(atPath: missing.path), "no automatic mkdir")
print("PASS native Swift Darwin fstatfs: bounded IPA budget, symlink denial, no cleanup or install")
'''

with tempfile.TemporaryDirectory(prefix="wr68-ipa-budget-synth-") as tmp:
    folder = Path(tmp)
    harness = folder / "main.swift"
    binary = folder / "ipa-budget-test"
    harness.write_text(SWIFT)
    subprocess.run([
        "swiftc", "-swift-version", "5", str(SOURCE), str(harness),
        "-o", str(binary)
    ], check=True, timeout=120)
    subprocess.run([str(binary), str(folder)], check=True, timeout=45)
