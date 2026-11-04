#!/usr/bin/env python3
"""Build 52: run exact Swift dimension-planning helper, audit reader wiring.
No external requests and no media are loaded from the internet.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
ART = (ROOT / "MangaReader12/UI/MangaArtwork.swift").read_text()
READER = (ROOT / "MangaReader12/UI/ReaderViewController.swift").read_text()
HEADER = (ROOT / "MangaReader12/Networking/MR12WebPBridge.h").read_text()
START = "// BEGIN IMAGE_COMPATIBILITY_GEOMETRY"
END = "// END IMAGE_COMPATIBILITY_GEOMETRY"
assert ART.count(START) == ART.count(END) == 1
geometry = ART.split(START)[1].split(END)[0]
assert "enum ImageCompatibilityDecoder" in ART
assert "CGImageSourceCreateThumbnailAtIndex" in ART
assert "CGImageSourceGetStatusAtIndex(source, 0) == .statusComplete" in ART
assert "maximumEncodedBytes = 20 * 1024 * 1024" in ART
assert "ImageCompatibilityDecoder.cover(data)" in ART
assert "ImageCompatibilityDecoder.page(response.data)" in READER
assert READER.count("ImageCompatibilityDecoder.page(data)") == 2
assert "MR12WebPDecodePageScaledBGRA(" in HEADER
assert "AVIF" in ART and '["PNG", "JPEG", "GIF", "HEIC"]' in ART

runner = r"""
import Foundation
func ok(_ condition: Bool, _ name: String) {
    if !condition { fatalError(name) }
}
func check(_ w: Int, _ h: Int, _ pixels: Int, _ side: Int) -> (Int, Int)? {
    return ImageCompatibilityGeometry.scaled(
        width: w, height: h, maxPixels: pixels, maxDimension: side)
}
ok(check(800, 1200, 24_000_000, 32_768)?.0 == 800, "small unchanged")
ok(check(800, 1200, 24_000_000, 32_768)?.1 == 1200, "small unchanged height")
let longWebtoon = check(1000, 30000, 24_000_000, 32_768)!
ok(longWebtoon.0 > 0 && longWebtoon.1 > 0, "vertical accepted")
ok(longWebtoon.0 * longWebtoon.1 <= 24_000_000, "page memory")
ok(longWebtoon.1 <= 32_768, "page max dimension")
let largeCover = check(2500, 2000, 420 * 420, 420)!
ok(max(largeCover.0, largeCover.1) <= 420, "cover bound")
ok(largeCover.0 * largeCover.1 <= 420 * 420, "cover memory")
ok(check(0, 1000, 24_000_000, 32_768) == nil, "zero width rejected")
ok(check(1000, -1, 24_000_000, 32_768) == nil, "negative height rejected")
ok(check(100_000, 100_000, 24_000_000, 32_768) == nil, "decompression bomb rejected")
ok(check(500, 50_000, 24_000_000, 32_768) != nil, "tall original accepted")
ok(check(500, 100_001, 24_000_000, 32_768) == nil, "invalid dimension rejected")
ok(check(1, 1, 0, 100) == nil, "zero budget rejected")
print("PASS: Build 52 geometry and codec routing (host Swift)")
"""
with tempfile.TemporaryDirectory(prefix="mr12-build52-") as name:
    source = Path(name) / "main.swift"
    binary = Path(name) / "check"
    source.write_text("import Foundation\n" + geometry + "\n" + runner)
    subprocess.run(["swiftc", str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
