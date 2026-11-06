#!/usr/bin/env python3
"""Build65 offline chapter relocation regression; no device operations."""
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
manager = (root / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
database = (root / "MangaReader12/Database/SQLiteDatabase.swift").read_text()
workflow = (root / ".github/workflows/build.yml").read_text()
begin = manager.index("// BEGIN OFFLINE_PATH_RELOCATION")
end = manager.index("// END OFFLINE_PATH_RELOCATION", begin)
helper = manager[begin:end]

assert "enum OfflineDownloadPath" in helper
assert "let directory = try chapterDirectory(" in manager
assert "URL(fileURLWithPath: localPath, isDirectory: true)" not in manager
assert "repository.rebindCompletedPath(" in manager
assert "fileManager.removeItem(at: current)" in manager
assert "fileManager.removeItem(atPath: localPath)" not in manager
assert "func rebindCompletedPath(" in database
assert "WHERE state = 'completed'" in database
assert "record.localPath == expected.path" in database
assert "OfflineDownloadPath.chapterDirectory(" in database
assert "ci/test_build65_offline_relocation.py" in workflow

swift = shutil.which("swift")
runner = [swift] if swift else ["xcrun", "swift"]
fixture = '''import Foundation
%s
let fm = FileManager.default
let root = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
  .appendingPathComponent("WR-B65-" + UUID().uuidString, isDirectory: true)
defer { try? fm.removeItem(at: root) }
let oldRoot = root.appendingPathComponent("OLD/Library/Application Support")
let newRoot = root.appendingPathComponent("NEW/Library/Application Support")
let oldDir = OfflineDownloadPath.chapterDirectory(
  applicationSupport: oldRoot, sourceID: "kei.weebcentral",
  mangaID: "abc/a", chapterID: "chapter1")
let newDir = OfflineDownloadPath.chapterDirectory(
  applicationSupport: newRoot, sourceID: "kei.weebcentral",
  mangaID: "abc/a", chapterID: "chapter1")
precondition(oldDir.path != newDir.path)
precondition(!fm.fileExists(atPath: oldDir.path))
try fm.createDirectory(at: newDir, withIntermediateDirectories: true)
let page = newDir.appendingPathComponent("page-00000.bin")
try Data([0x01, 0x02, 0x03]).write(to: page)
precondition(fm.fileExists(atPath: page.path))
precondition(OfflineDownloadPath.safeComponent(".") == "item")
precondition(OfflineDownloadPath.safeComponent("..") == "item")
precondition(!OfflineDownloadPath.safeComponent("../../etc").contains("/"))
precondition(newDir.path.hasPrefix(newRoot.path))
print("PASS: actual Swift helper resolves relocated downloaded pages")
''' % helper
with tempfile.TemporaryDirectory(prefix="wr65-") as temp:
    path = Path(temp) / "fixture.swift"
    path.write_text(fixture)
    result = subprocess.run(runner + [str(path)], capture_output=True,
                            text=True, timeout=90)
    print(result.stdout, end="")
    assert result.returncode == 0, result.stderr
print("PASS: safe completed-only DB rebind and conservative download reindex")
