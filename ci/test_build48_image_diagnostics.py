#!/usr/bin/env python3
"""Compile and test the exact Build48 Swift image diagnostic helper offline.

No source-site requests, no user media, no privileged credentials.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
ARTWORK = (ROOT / "MangaReader12/UI/MangaArtwork.swift").read_text(encoding="utf-8")
READER = (ROOT / "MangaReader12/UI/ReaderViewController.swift").read_text(encoding="utf-8")
BROWSER = (ROOT / "MangaReader12/UI/SourceBrowserViewController.swift").read_text(encoding="utf-8")
START = "// BEGIN IMAGE_RESPONSE_DIAGNOSTICS"
END = "// END IMAGE_RESPONSE_DIAGNOSTICS"
assert ARTWORK.count(START) == ARTWORK.count(END) == 1
swift_helper = ARTWORK.split(START)[1].split(END)[0]
assert "enum ImageResponseDiagnostics" in swift_helper
assert "response.data" in READER
assert "ImageResponseDiagnostics.summary(" in READER
assert "case .invalidImageResponse(" in READER
assert "ImageResponseDiagnostics.format(response.data)" in BROWSER
assert 'sourceRecord.manifest.id == "kei.asurascans.en"' in BROWSER
assert "supportsDOMInspect: sourceRecord.manifest.id == \"kei.webtoons.en\"" in BROWSER
assert "chosenDirectly: true" in BROWSER
assert "URLs may contain tokens" in BROWSER

test = r'''
import Foundation

func check(_ pass: Bool, _ message: String) {
    if !pass { fatalError(message) }
}
func bytes(_ values: [UInt8]) -> Data { return Data(values) }
let png = bytes([137,80,78,71,13,10,26,10,0,0,0,0])
let jpg = bytes([255,216,255,224,0,16])
let webp = bytes([82,73,70,70,100,0,0,0,87,69,66,80,86,80,56,32])
let avif = bytes([0,0,0,28,102,116,121,112,97,118,105,102])
let gif = Data("GIF89a".utf8)
let html = Data("  <!DOCTYPE html><html>challenge</html>".utf8)
let json = Data("{\"blocked\":true}".utf8)
check(ImageResponseDiagnostics.format(png) == "PNG", "PNG")
check(ImageResponseDiagnostics.format(jpg) == "JPEG", "JPEG")
check(ImageResponseDiagnostics.format(webp) == "WebP", "WebP")
check(ImageResponseDiagnostics.format(avif) == "AVIF", "AVIF")
check(ImageResponseDiagnostics.format(gif) == "GIF", "GIF")
check(ImageResponseDiagnostics.format(html) == "HTML", "HTML")
check(ImageResponseDiagnostics.format(json) == "JSON-like", "JSON")
check(ImageResponseDiagnostics.format(Data()) == "empty", "empty")
check(ImageResponseDiagnostics.format(bytes([1,2,3,4,5])) == "unrecognized", "unknown")
check(ImageResponseDiagnostics.mime(["content-type":"IMAGE/WEBP; charset=utf-8"]) ==
      "image/webp", "MIME normalization")
check(ImageResponseDiagnostics.mime(["Content-Type":"text/html; charset=UTF-8"]) ==
      "text/html", "HTML MIME")
check(ImageResponseDiagnostics.mime(["Content-Type":"evil\nSECRET"]) ==
      "(invalid)", "untrusted MIME not echoed")
check(ImageResponseDiagnostics.host(
      "https://cdn.asurascans.com/secret/path.jpg?token=PRIVATE") ==
      "cdn.asurascans.com", "safe host")
check(ImageResponseDiagnostics.host(
      "https://user:secret@cdn.asurascans.com/path?token=PRIVATE") ==
      "cdn.asurascans.com", "do not emit URL credentials")
let report = ImageResponseDiagnostics.summary(
    data: html,
    headers: ["Content-Type":"text/html; charset=utf-8",
              "Set-Cookie":"session=SECRET"],
    status: 200,
    url: "https://cdn.asurascans.com/secret/path.jpg?token=PRIVATE")
check(report.contains("HTTP 200"), "status")
check(report.contains("formato=HTML"), "format")
check(report.contains("MIME=text/html"), "mime")
check(report.contains("host=cdn.asurascans.com"), "host")
for forbidden in ["PRIVATE", "SECRET", "/secret/", "token=", "Set-Cookie", "<html"] {
    check(!report.contains(forbidden), "leaked: " + forbidden)
}
let webpReport = ImageResponseDiagnostics.summary(
    data: webp, headers: ["CONTENT-TYPE":"image/webp"], status: 200,
    url: "https://cdn.asurascans.com/chapters/page.webp")
check(webpReport.contains("formato=WebP"), "webp report")
print("PASS Build48: PNG/JPEG/WebP/AVIF/HTML/JSON diagnosis, hostname-only reports, no token or response-body leakage")
'''
with tempfile.TemporaryDirectory(prefix="mr12-build48-") as tmp:
    file = Path(tmp) / "probe.swift"
    file.write_text("import Foundation\n" + swift_helper + test, encoding="utf-8")
    result = subprocess.run(["xcrun", "swift", str(file)], capture_output=True,
                            text=True, timeout=120)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(result.returncode)
    print(result.stdout.strip())
