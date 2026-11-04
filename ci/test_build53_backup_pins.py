#!/usr/bin/env python3
"""Build53: execute exact Foundation Swift backup preference codec offline."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BACKUP = (ROOT / "MangaReader12/Core/BackupManager.swift").read_text()
LIBRARY = (ROOT / "MangaReader12/UI/LibraryViewController.swift").read_text()
UI = (ROOT / "MangaReader12/UI/BackupViewController.swift").read_text()
assert BACKUP.count("struct BackupPreferenceValue: Codable {") == 1
fragment = BACKUP.split("struct BackupPreferenceValue: Codable {", 1)[1].split(
    "\nstruct BackupRestoreReport", 1)[0]
helper = "struct BackupPreferenceValue: Codable {" + fragment
assert '"library.pinned.sources.v1"' in BACKUP
assert '"library.pinned.sources.v1"' in LIBRARY
assert "obras fixadas" in UI
assert "static let formatVersion = 1" in BACKUP
assert "stringArrayValue: [String]?" in helper
assert "strings.count <= 10_000" in helper
runner = r'''
import Foundation
func check(_ pass: Bool, _ name: String) {
    if !pass { fatalError(name) }
}
let original = ["2:abc", "5:asura112", "3:wc000"]
let stored = BackupPreferenceValue.encode(original)!
check(stored.kind == "stringArray", "array encoder")
let data = try! JSONEncoder().encode(stored)
let decoded = try! JSONDecoder().decode(BackupPreferenceValue.self, from: data)
check((decoded.decodedValue() as? [String]) == original, "round trip pins")
let defaults = UserDefaults(suiteName: "mr12-build53-fixture")!
defaults.removePersistentDomain(forName: "mr12-build53-fixture")
defaults.set(decoded.decodedValue(), forKey: "library.pinned.sources.v1")
check(defaults.stringArray(forKey: "library.pinned.sources.v1") == original,
      "UserDefaults preference shape")
defaults.removePersistentDomain(forName: "mr12-build53-fixture")
// Old format-1 backup preferences have no stringArrayValue member.
let legacyData = Data(#"{"kind":"string","stringValue":"dark"}"#.utf8)
let legacy = try! JSONDecoder().decode(BackupPreferenceValue.self, from: legacyData)
check(legacy.decodedValue() as? String == "dark", "legacy backward compatibility")
check(BackupPreferenceValue.encode(Array(repeating: "x", count: 10001)) == nil,
      "reject >10k preference values")
check(BackupPreferenceValue.encode([String(repeating: "x", count: 2050)]) == nil,
      "reject oversized identity")
let normal = BackupPreferenceValue.encode(3)!
check(normal.decodedValue() as? Int == 3, "integer preference unchanged")
print("PASS: Build53 backup pin preference roundtrip + legacy restore")
'''
with tempfile.TemporaryDirectory(prefix="mr12-build53-") as temp:
    file = Path(temp) / "main.swift"
    binary = Path(temp) / "test"
    file.write_text("import Foundation\n" + helper + "\n" + runner)
    subprocess.run(["swiftc", str(file), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
