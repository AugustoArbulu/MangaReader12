#!/usr/bin/env python3
"""Swift native offline tests for the personal GitHub Releases update channel.

Zero network, no IPA installation, no publisher secret. Exercises the actual
iOS12 Swift Release parser with valid/malformed JSON and sha256 metadata.
"""
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
]
HARNESS = r'''
import Foundation
import Security

func check(_ condition: @autoclosure () -> Bool, _ explanation: String) {
    if !condition() { fatalError(explanation) }
}
func json(_ value: [String: Any]) -> Data {
    return try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
}
func fixture(_ tag: String = "build57", digest: String = String(repeating:"a",count:64)) -> [String: Any] {
    return [
        "tag_name": tag,
        "draft": false, "prerelease": false,
        "published_at": "2026-11-05T03:00:00Z",
        "body": "Correções no leitor\nMelhorias nas fontes",
        "assets": [[
            "name": "WebReader-iOS12-unsigned.ipa",
            "size": 12345, "digest": "sha256:" + digest,
            "state": "uploaded",
            "browser_download_url": "https://github.com/AugustoArbulu/MangaReader12/releases/download/" + tag + "/WebReader-iOS12-unsigned.ipa"
        ]]
    ]
}
let ios = OperatingSystemVersion(majorVersion:12, minorVersion:5, patchVersion:8)
func parse(_ item: [String: Any], installedBuild: Int = 56) -> WebReaderUpdateCheckResult {
    return WebReaderGitHubReleaseParser.parse(
        json(item), installedBuild: installedBuild, installedIOS: ios
    )
}
func shouldReject(_ fixture: [String: Any], _ title: String) {
    switch parse(fixture) {
    case .failed(.invalidGitHubRelease): break
    default: fatalError("Not rejected: " + title)
    }
}
check(
    WebReaderGitHubReleaseParser.apiURL.absoluteString ==
      "https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest",
    "API endpoint exact"
)
switch parse(fixture()) {
case .updateAvailable(let update):
    check(update.provenance == .publicGitHubRelease, "GitHub source explicit")
    check(update.build == 57, "build parsed")
    check(update.sha256 == String(repeating:"a",count:64), "digest")
    check(update.ipaSize == 12345, "size")
    check(update.minimumIOS == "12.0", "expected min iOS from policy")
    check(update.releaseNotes.count == 2, "notes")
default: fatalError("valid official release rejected")
}
switch parse(fixture("build56")) {
case .upToDate: break
default: fatalError("same version should not stage")
}
var invalid = fixture()
invalid["draft"] = true
shouldReject(invalid, "draft")
invalid = fixture()
invalid["prerelease"] = true
shouldReject(invalid, "prerelease")
invalid = fixture("build057")
shouldReject(invalid, "noncanonical build tag")
invalid = fixture("hello57")
shouldReject(invalid, "wrong release tag")
invalid = fixture()
invalid["published_at"] = ""
shouldReject(invalid, "no published date")
invalid = fixture()
invalid["assets"] = []
shouldReject(invalid, "no IPA")
invalid = fixture()
invalid["assets"] = [fixture()["assets"] as! [[String:Any]]][0] +
    (fixture()["assets"] as! [[String:Any]])
shouldReject(invalid, "duplicate IPA asset")
func changedAsset(_ f: [String: Any], _ change: (inout [String:Any]) -> Void) -> [String:Any] {
    var copy = f
    var asset = (copy["assets"] as! [[String:Any]])[0]
    change(&asset)
    copy["assets"] = [asset]
    return copy
}
shouldReject(changedAsset(fixture()) { $0["digest"] = NSNull() }, "missing digest")
shouldReject(changedAsset(fixture()) { $0["digest"] = "sha256:BAD" }, "invalid digest")
shouldReject(changedAsset(fixture()) { $0["size"] = 0 }, "zero size")
shouldReject(changedAsset(fixture()) { $0["size"] = true }, "boolean size")
shouldReject(changedAsset(fixture()) { $0["size"] = 7.5 }, "fractional size")
shouldReject(changedAsset(fixture()) { $0["size"] = 600 * 1024 * 1024 }, "too big")
shouldReject(changedAsset(fixture()) { $0["state"] = "pending" }, "asset not uploaded")
shouldReject(changedAsset(fixture()) {
  $0["browser_download_url"] =
  "https://github.com/other/repo/releases/download/build57/WebReader-iOS12-unsigned.ipa"
}, "wrong repo")
shouldReject(changedAsset(fixture()) {
  $0["browser_download_url"] =
  "http://github.com/AugustoArbulu/MangaReader12/releases/download/build57/WebReader-iOS12-unsigned.ipa"
}, "insecure transport")
shouldReject(changedAsset(fixture()) {
  $0["browser_download_url"] =
  "https://github.com/AugustoArbulu/MangaReader12/releases/download/build57/WebReader-iOS12-unsigned.ipa?token=x"
}, "unexpected query")
shouldReject(changedAsset(fixture()) {
  $0["name"] = "other.ipa"
}, "wrong asset")
let duplicatedKeys = Data(#"{"tag_name":"build57","tag_name":"build58"}"#.utf8)
switch WebReaderGitHubReleaseParser.parse(
    duplicatedKeys, installedBuild:56, installedIOS:ios
) {
case .failed(.invalidGitHubRelease): break
default: fatalError("duplicate JSON keys accepted")
}
let oversized = Data(repeating:0x20, count:128 * 1024 + 1)
switch WebReaderGitHubReleaseParser.parse(
    oversized, installedBuild:56, installedIOS:ios
) {
case .failed(.invalidGitHubRelease): break
default: fatalError("oversized JSON accepted")
}
print("PASS GitHub Release parser: exact repo/assets, integer size, SHA256 and no signature bypass")
'''
with tempfile.TemporaryDirectory(prefix="webreader-github-releases-") as directory:
    p = Path(directory)
    main = p / "main.swift"
    binary = p / "checker"
    main.write_text(HARNESS)
    subprocess.run(["swiftc", "-swift-version", "5", *map(str,SOURCES),
                    str(main), "-framework", "Security", "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
