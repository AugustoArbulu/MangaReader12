#!/usr/bin/env python3
"""Execute the Build46 Swift offline image validator with local PNG fixtures.

No network, third-party fixtures, credentials or live-source requests.
"""
from pathlib import Path
import os
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift"
START = "// BEGIN IMAGE_PAYLOAD_VALIDATOR\n"
END = "// END IMAGE_PAYLOAD_VALIDATOR"
data = SOURCE.read_text(encoding="utf-8")
assert data.count(START) == 1
assert data.count(END) == 1
validator = data.split(START, 1)[1].split(END, 1)[0]

assert "CGImageSourceCreateWithData" in validator
assert "CGImageSourceGetStatusAtIndex" in validator
assert "statusComplete" in validator
assert "image/jpeg" not in validator, "no source-specific type check"
assert "response.data.write(to: destination" in data
assert data.index("ChapterDownloadImageValidator.canStore") < data.index(
    'let filename = String(format: "page-%05d.bin", index)'
)
assert "case invalidImagePayload" in data
assert "ChapterDownloadError.invalidImagePayload" in data

pbx = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
import re
versions = re.findall(r"CURRENT_PROJECT_VERSION = (\d+);", pbx)
assert len(versions) == 2 and versions[0] == versions[1]
assert int(versions[0]) >= 46, "ImageIO validation must remain enabled after Build46"
settings = (ROOT / "MangaReader12/UI/MainTabBarController.swift").read_text(encoding="utf-8")
assert f"Build {versions[0]} • compatível com iOS 12.0" in settings


def chunk(name: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload)) + name + payload +
        struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)
    )


# A valid one-pixel RGB PNG with correct CRCs.
png_bytes = (
    b"\x89PNG\r\n\x1a\n" +
    chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) +
    chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) +
    chunk(b"IEND", b"")
)

tests = """
import Foundation
import ImageIO

// The Build46 ImageIO regression test runs independently from the iOS UIKit
// target; Build49 WebP validity is tested by the native libwebp C tests.
enum WebPImageDecoder {
    static func isWebP(_ data: Data) -> Bool {
        let bytes = [UInt8](data.prefix(12))
        return bytes.count >= 12 &&
            Array(bytes[0..<4]) == [82,73,70,70] &&
            Array(bytes[8..<12]) == [87,69,66,80]
    }
    static func image(from data: Data) -> Data? { return nil }
}

""" + validator + """
func check(_ value: Bool, _ label: String) {
    if !value { fatalError("Image validator failed: " + label) }
}
let png = try! Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
let html = Data("<html><body>challenge</body></html>".utf8)
check(ChapterDownloadImageValidator.canStore(
    data: png, headers: ["Content-Type": "image/png"]), "valid png")
check(ChapterDownloadImageValidator.canStore(
    data: png, headers: [:]), "headerless png")
check(ChapterDownloadImageValidator.canStore(
    data: png, headers: ["content-type": "IMAGE/PNG"]), "case insensitive header")
check(!ChapterDownloadImageValidator.canStore(
    data: html, headers: ["Content-Type": "text/html; charset=utf-8"]), "HTML page")
check(!ChapterDownloadImageValidator.canStore(
    data: html, headers: ["Content-Type": "image/png"]), "falsely labelled HTML")
check(!ChapterDownloadImageValidator.canStore(
    data: png, headers: ["CONTENT-TYPE": "application/json"]), "JSON Content-Type")
check(!ChapterDownloadImageValidator.canStore(
    data: Data(), headers: [:]), "zero bytes")
check(!ChapterDownloadImageValidator.canStore(
    data: Data(png.prefix(24)), headers: [:]), "truncated PNG")
print("PASS Build46 ImageIO validation: valid image, missing MIME, HTML challenge, malformed bytes")
"""

with tempfile.TemporaryDirectory(prefix="mr12-image-test-") as tmp:
    root = Path(tmp)
    (root / "valid.png").write_bytes(png_bytes)
    (root / "validate.swift").write_text(tests, encoding="utf-8")
    result = subprocess.run(
        ["xcrun", "swift", str(root / "validate.swift"), str(root / "valid.png")],
        capture_output=True, text=True, timeout=90, check=False
    )
    if result.returncode:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(result.returncode)
    print(result.stdout.strip())
print("PASS Build46 offline image-validation integration")
