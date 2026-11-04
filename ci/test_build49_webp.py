#!/usr/bin/env python3
"""libwebp 1.6.0 host decoder regression + iOS static-link source assertions.

No requests to Asura, WeebCentral or any image CDN. Official SHA-256
source archive was fetched by the preceding preparation step.
"""
from pathlib import Path
import base64
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / ".ci-webp/libwebp-1.6.0"
IOS_LIB = ROOT / ".ci-webp/lib/libwebp.a"
assert SOURCE.joinpath("src/webp/decode.h").exists()
assert IOS_LIB.exists()
PBX = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
ART = (ROOT / "MangaReader12/UI/MangaArtwork.swift").read_text()
READER = (ROOT / "MangaReader12/UI/ReaderViewController.swift").read_text()
DOWNLOAD = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
BRIDGE = (ROOT / "MangaReader12/Networking/MR12WebPBridge.h").read_text()
assert PBX.count("CURRENT_PROJECT_VERSION = 49;") == 2
assert PBX.count("SWIFT_OBJC_BRIDGING_HEADER") == 2
assert PBX.count('"$(SRCROOT)/.ci-webp/lib"') == 2
assert PBX.count('"-lwebp"') == 2
assert "#include <webp/decode.h>" in BRIDGE
assert "WebPGetInfo(" in ART
assert "WebPDecodeBGRAInto(" in ART
assert "CGDataProvider(data: pixels as CFData)" in ART
assert "maximumReaderPixels = 24_000_000" in ART
assert "maximumCoverPixels = 4_000_000" in ART
assert "WebPImageDecoder.image(from: response.data)" in READER
assert READER.count("WebPImageDecoder.image(from: data)") == 2
assert "WebPImageDecoder.image(from: data) != nil" in DOWNLOAD
assert "CGImageSourceGetStatusAtIndex" in DOWNLOAD
assert "PNG requires its final IEND chunk" in DOWNLOAD

# This real lossless 2x2 RGBA image was created locally with Pillow; the
# bytes are fixed in this test, no Pillow runtime dependency.
webp = base64.b64decode(
    "UklGRh4AAABXRUJQVlA4TBEAAAAvAUAAEAdQj8IXpYCBiOh/AAA="
)
assert len(webp) == 38
TEST_C = r'''
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <webp/decode.h>
static const uint8_t valid[] = { __DATA__ };
int main(void) {
  int width = 0, height = 0;
  uint8_t output[16] = {0};
  if (WebPGetDecoderVersion() < 0x010600) return 1;
  if (WebPGetInfo(valid, sizeof(valid), &width, &height) != 1) return 2;
  if (width != 2 || height != 2) return 3;
  if (!WebPDecodeBGRAInto(valid, sizeof(valid), output, sizeof(output), 8)) return 4;
  // 2x2 pixels: decode must return opaque/colorful pixel data, not zeros.
  if (output[0] == 0 && output[1] == 0 && output[2] == 0) return 5;
  if (output[3] == 0) return 6;
  // Metadata can sometimes survive a truncated file: full decode must fail.
  uint8_t corrupt[sizeof(valid)];
  memcpy(corrupt, valid, sizeof(valid));
  corrupt[sizeof(valid)-1] ^= 0xEE;
  if (WebPDecodeBGRAInto(valid, 16, output, sizeof(output), 8) != NULL) return 7;
  if (WebPDecodeBGRAInto((const uint8_t*)"<html>", 6,
                         output, sizeof(output), 8) != NULL) return 8;
  if (WebPGetInfo((const uint8_t*)"<html>", 6, &width, &height) != 0) return 9;
  puts("PASS: libwebp decoded real RGBA 2x2 and rejected truncated/non-WebP bytes");
  return 0;
}
'''.replace("__DATA__", ", ".join(str(b) for b in webp))

with tempfile.TemporaryDirectory(prefix="mr12-host-webp-") as root:
    work = Path(root)
    build = work / "build"
    common = [
        "-DBUILD_SHARED_LIBS=OFF", "-DWEBP_LINK_STATIC=ON",
        "-DWEBP_ENABLE_SIMD=OFF", "-DWEBP_USE_THREAD=OFF",
        "-DWEBP_BUILD_CWEBP=OFF", "-DWEBP_BUILD_DWEBP=OFF",
        "-DWEBP_BUILD_EXTRAS=OFF", "-DWEBP_BUILD_WEBPINFO=OFF",
        "-DWEBP_BUILD_VWEBP=OFF", "-DWEBP_BUILD_ANIM_UTILS=OFF",
        "-DWEBP_BUILD_GIF2WEBP=OFF", "-DWEBP_BUILD_IMG2WEBP=OFF",
        "-DWEBP_BUILD_WEBPMUX=OFF", "-DWEBP_BUILD_LIBWEBPMUX=OFF",
    ]
    subprocess.run(["cmake", "-S", str(SOURCE), "-B", str(build),
                    "-DCMAKE_BUILD_TYPE=Release"] + common, check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["cmake", "--build", str(build), "--target", "webp",
                    "--parallel", "4"], check=True, stdout=subprocess.DEVNULL)
    archives = list(build.rglob("libwebp.a"))
    assert archives, "host libwebp archive missing"
    (work / "decode.c").write_text(TEST_C)
    cmd = ["clang", "-std=c11", "-O2", "-I", str(SOURCE/"src"),
           str(work/"decode.c"), str(archives[0]), "-lm", "-o",
           str(work/"decode")]
    subprocess.run(cmd, check=True)
    result = subprocess.run([str(work/"decode")], check=True,
                            capture_output=True, text=True)
    print(result.stdout.strip())
print("PASS Build49: real codec bytes, iOS Xcode bridge, online/cover/offline wiring")
