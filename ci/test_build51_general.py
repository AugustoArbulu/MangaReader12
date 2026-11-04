#!/usr/bin/env python3
"""Execute bounded Build51 UIKit-adjacent helpers in Foundation Swift offline.

No user data, network, filesystem deletion outside a fresh temp test root,
source-sites or account credentials accessed.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent.parent
LIB=(ROOT/"MangaReader12/UI/LibraryViewController.swift").read_text()
DL=(ROOT/"MangaReader12/UI/DownloadsViewController.swift").read_text()
BROWSER=(ROOT/"MangaReader12/UI/SourceBrowserViewController.swift").read_text()
MAIN=(ROOT/"MangaReader12/UI/MainTabBarController.swift").read_text()
PROJECT=(ROOT/"MangaReader12.xcodeproj/project.pbxproj").read_text()
def between(src,start,end):
    assert src.count(start)==src.count(end)==1, (start,end)
    return src.split(start,1)[1].split(end,1)[0]
LIBHELPER=between(LIB,"// BEGIN BUILD51_PINNED_LIBRARY","// END BUILD51_PINNED_LIBRARY")
DLHELPER=between(DL,"// BEGIN BUILD51_DOWNLOAD_STORAGE_METER","// END BUILD51_DOWNLOAD_STORAGE_METER")
import re
builds = [int(item) for item in re.findall(r"CURRENT_PROJECT_VERSION = (\d+);", PROJECT)]
assert len(builds) == 2 and builds[0] == builds[1] and builds[0] >= 51
assert f"Build {builds[0]} • compatível com iOS 12.0" in MAIN
assert "let pinnedIDs = LibraryPinnedWorks.all()" in LIB
assert "if leftPinned != rightPinned { return leftPinned }" in LIB
assert "self?.reloadLibrary()" in LIB
assert 'style: .normal, title: pinned ? "Desfixar" : "Fixar"' in LIB
assert "UILongPressGestureRecognizer(" in LIB
assert "togglePin: @escaping (LibraryMangaRecord) -> Void" in LIB
assert "LibraryPinnedWorks.contains(" in LIB
assert "storageInfo" in DL and "DispatchQueue.global(qos: .utility)" in DL
assert "refreshStorageIfNeeded(force: false)" in DL
assert "refreshStorageIfNeeded(force: true)" in DL
assert "supportsTagExclusions: Bool?" in BROWSER
assert "singleTypeStatus: Bool?" in BROWSER
assert "remoteSelection.statuses.removeAll()" in BROWSER
assert "remoteSelection.types.removeAll()" in BROWSER
assert "options.allowsTagExclusions" in BROWSER
assert "tags.isEmpty || clean(tags, maxCount: 60)" in BROWSER
assert "genre filter unavailable" not in BROWSER.lower()

TEST=r'''
import Foundation

func insist(_ expression: Bool, _ message: String) {
    if !expression { fatalError(message) }
}
let suite = "mr12.ci.build51.pins"
guard let store = UserDefaults(suiteName: suite) else { fatalError("suite") }
store.removePersistentDomain(forName: suite)
insist(!LibraryPinnedWorks.contains(sourceID: "a", mangaID: "bc", defaults: store), "initial unpinned")
let id1=LibraryPinnedWorks.identity(sourceID: "a",mangaID:"bc")
let id2=LibraryPinnedWorks.identity(sourceID: "ab",mangaID:"c")
insist(id1 != id2, "length prefix avoids identity collision")
insist(LibraryPinnedWorks.toggle(sourceID:"a",mangaID:"bc",defaults:store), "pin")
insist(LibraryPinnedWorks.contains(sourceID:"a",mangaID:"bc",defaults:store), "persisted")
insist(!LibraryPinnedWorks.contains(sourceID:"ab",mangaID:"c",defaults:store), "isolated sources")
insist(!LibraryPinnedWorks.toggle(sourceID:"a",mangaID:"bc",defaults:store), "unpin")
insist(LibraryPinnedWorks.all(defaults:store).isEmpty, "no retained pin")
store.removePersistentDomain(forName: suite)

let root=FileManager.default.temporaryDirectory
    .appendingPathComponent("build51-offline-storage-fixture", isDirectory:true)
try? FileManager.default.removeItem(at:root)
try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
defer { try? FileManager.default.removeItem(at:root) }
try FileManager.default.createDirectory(
    at:root.appendingPathComponent("chapter",isDirectory:true),
    withIntermediateDirectories:true)
try Data(repeating: 3,count: 1300).write(
    to:root.appendingPathComponent("chapter/page-0.bin"))
try Data(repeating: 4,count: 700).write(
    to:root.appendingPathComponent("chapter/page-1.bin"))
try Data(repeating: 5,count: 300).write(
    to:root.appendingPathComponent(".hidden"))
let metrics=DownloadStorageMeter.inspect(root:root)
insist(metrics.files == 2,"2 page files, no hidden files")
insist(metrics.bytes == 2000,"exact disk byte estimate")
insist(!metrics.truncated,"bounded scan not truncated")
insist(metrics.label.contains("Armazenamento:"),"UI label")
let capped=DownloadStorageMeter.inspect(root:root,maximumFiles:1)
insist(capped.files == 1 && capped.truncated,"bounded scan truncation visible")
insist(capped.label.contains("≥"),"incomplete estimate indicated")
print("PASS Build51: stable pinned identities/toggle, bounded async-ready offline byte metering")
'''
with tempfile.TemporaryDirectory(prefix="mr12-build51-") as tmp:
    probe=Path(tmp)/"main.swift"
    probe.write_text("import Foundation\n"+LIBHELPER+DLHELPER+TEST)
    result=subprocess.run(["xcrun","swift",str(probe)],capture_output=True,
                          text=True,timeout=120)
    if result.returncode!=0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(result.returncode)
    print(result.stdout.strip())
