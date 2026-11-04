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
import re
versions = [int(v) for v in re.findall(r"CURRENT_PROJECT_VERSION = (\d+);", PBX)]
assert len(versions) == 2 and versions[0] == versions[1] and versions[0] >= 49
assert PBX.count("SWIFT_OBJC_BRIDGING_HEADER") == 2
assert PBX.count('"$(SRCROOT)/.ci-webp/lib"') == 2
assert PBX.count('"-lwebp"') == 2
assert "#include <webp/decode.h>" in BRIDGE
assert "WebPGetInfo(" in ART
assert "WebPDecodeBGRAInto(" in ART
assert "WebPImageDecoder.thumbnail(from: data)" in ART
assert "MR12WebPDecodeScaledBGRA(" in ART
assert "WebPInitDecoderConfig(&config)" in BRIDGE
assert "config.options.use_scaling = 1" in BRIDGE
assert "WebPDecode(data, input_size, &config)" in BRIDGE
assert "WebPImageDecoder.thumbnail(from: response.data)" in (
    ROOT / "MangaReader12/UI/SourceBrowserViewController.swift"
).read_text(encoding="utf-8")
assert "64_000_000 / h" in ART
assert "min(420" in ART
assert "CGDataProvider(data: pixels as CFData)" in ART
assert "maximumReaderPixels = 24_000_000" in ART
assert "maximumCoverPixels = 4_000_000" in ART
assert "ImageCompatibilityDecoder.page(response.data)" in READER
assert READER.count("ImageCompatibilityDecoder.page(data)") == 2
assert "WebPImageDecoder.image(from: data) != nil" in DOWNLOAD
assert "MR12WebPDecodePageScaledBGRA" in BRIDGE
assert "MR12WebPDecodePageScaledBGRA(" in ART
assert "CGImageSourceGetStatusAtIndex" in DOWNLOAD
assert "PNG requires its final IEND chunk" in DOWNLOAD

# This real lossless 2x2 RGBA image was created locally with Pillow; the
# bytes are fixed in this test, no Pillow runtime dependency.
webp = base64.b64decode(
    "UklGRh4AAABXRUJQVlA4TBEAAAAvAUAAEAdQj8IXpYCBiOh/AAA="
)
assert len(webp) == 38
# Fixed offline 2500x2000 lossless WebP fixture (RGBA 224,112,48,255).
# The bytes were generated once with Pillow outside CI. libwebp decodes
# these bytes; it need not link its unrelated encoder/sharpyuv libraries.
large_webp = base64.b64decode("UklGRvQAAABXRUJQVlA4TOgAAAAvw8nzAQdQuIIXpv8BAEX6/58i+p/63//+97///e9///vf//73v//973//+9///ve///3vf//73//+97///e9///vf//73v//973//+9///ve///3vf//73//+97///e9///vf//73v//973//+9///ve///3vf//73//+97///e9///vf//73v//973//+9///ve///3vf//73//+97///e9///vf//73v//973//+9///ve///3vf//73//+97///e9///vf//73v//973//+9///ve///3vf//73//+97///e9//5sH")
assert len(large_webp) == 252
TEST_C = r'''
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <webp/decode.h>
#include "MR12WebPBridge.h"
static const uint8_t valid[] = { __DATA__ };
static const uint8_t large[] = { __LARGE_DATA__ };
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
  // A 2500x2000 WebP exceeds the old 4 MP cover limit.
  // Decode directly to 420x336 without a full-size RGBA allocation.
  int source_w = 0, source_h = 0;
  if (WebPGetInfo(large, sizeof(large), &source_w, &source_h) != 1 ||
      source_w != 2500 || source_h != 2000) return 10;
  const int small_w = 420, small_h = 336;
  const size_t small_size = (size_t)small_w*small_h*4;
  uint8_t* small = calloc(1, small_size);
  if (!small) return 11;
  if (!MR12WebPDecodeScaledBGRA(large, sizeof(large),
                               small, small_size, small_w, small_h,
                               small_w*4)) return 12;
  // BGRA for input RGBA (224,112,48,255).
  if (small[0] != 48 || small[1] != 112 ||
      small[2] != 224 || small[3] != 255) return 13;
  if (MR12WebPDecodeScaledBGRA(large, sizeof(large)/2,
                              small,small_size,small_w,small_h,
                              small_w*4)) return 14;
  if (MR12WebPDecodeScaledBGRA(large,sizeof(large),
                              small,small_size-1,small_w,small_h,
                              small_w*4)) return 15;
  if (MR12WebPDecodeScaledBGRA((const uint8_t*)"<html>",6,
                              small,small_size,small_w,small_h,
                              small_w*4)) return 16;
  free(small);
  puts("PASS: libwebp real WebP, rejected bad bytes, scaled 5 MP cover to 420x336 safely");
  return 0;
}
'''.replace("__DATA__", ", ".join(str(b) for b in webp)).replace(
    "__LARGE_DATA__", ", ".join(str(b) for b in large_webp)
)

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
           "-I", str(ROOT/"MangaReader12/Networking"),
           str(work/"decode.c"), str(archives[0]), "-lm", "-o",
           str(work/"decode")]
    subprocess.run(cmd, check=True)
    result = subprocess.run([str(work/"decode")], check=True,
                            capture_output=True, text=True)
    print(result.stdout.strip())
print("PASS Build49: real codec bytes, iOS Xcode bridge, online/cover/offline wiring")
