#!/bin/bash
# Reproducible, source-pinned libwebp 1.6.0 for iOS 12 arm64.
# No source-site, manga or CDN requests. Required for every Xcode build.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/.ci-webp"
TARBALL="$WORK/libwebp-1.6.0.tar.gz"
SOURCE="$WORK/libwebp-1.6.0"
OUTPUT="$WORK/ios-build"
LIBDIR="$WORK/lib"
VERSION="1.6.0"
SHA256="e4ab7009bf0629fd11982d4c2aa83964cf244cffba7347ecd39019a9e38c4564"
URL="https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-${VERSION}.tar.gz"

mkdir -p "$WORK" "$LIBDIR"
if [[ ! -f "$TARBALL" ]]; then
  curl --fail --location --silent --show-error --retry 2 --connect-timeout 20 \
       --max-time 180 --output "$TARBALL" "$URL"
fi
echo "$SHA256  $TARBALL" | shasum -a 256 --check
if [[ ! -f "$SOURCE/CMakeLists.txt" ]]; then
  tar -xzf "$TARBALL" -C "$WORK"
fi
test -f "$SOURCE/src/webp/decode.h"
test -f "$SOURCE/COPYING"

cmake -S "$SOURCE" -B "$OUTPUT" \
    -DCMAKE_SYSTEM_NAME=iOS \
    -DCMAKE_OSX_SYSROOT=iphoneos \
    -DCMAKE_OSX_ARCHITECTURES=arm64 \
    -DCMAKE_OSX_DEPLOYMENT_TARGET=12.0 \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DWEBP_LINK_STATIC=ON \
    -DWEBP_ENABLE_SIMD=OFF \
    -DWEBP_USE_THREAD=OFF \
    -DWEBP_BUILD_CWEBP=OFF \
    -DWEBP_BUILD_DWEBP=OFF \
    -DWEBP_BUILD_EXTRAS=OFF \
    -DWEBP_BUILD_WEBPINFO=OFF \
    -DWEBP_BUILD_VWEBP=OFF \
    -DWEBP_BUILD_WEBP_JS=OFF \
    -DWEBP_BUILD_GIF2WEBP=OFF \
    -DWEBP_BUILD_IMG2WEBP=OFF \
    -DWEBP_BUILD_ANIM_UTILS=OFF \
    -DWEBP_BUILD_WEBPMUX=OFF \
    -DWEBP_BUILD_LIBWEBPMUX=OFF
cmake --build "$OUTPUT" --target webp --parallel 4

# CMake may choose a single-config generator or Xcode multi-config.
LIBFILE="$(find "$OUTPUT" -type f -name libwebp.a | head -1)"
if [[ -z "$LIBFILE" || ! -f "$LIBFILE" ]]; then
  echo "libwebp.a not produced" >&2
  exit 1
fi
cp "$LIBFILE" "$LIBDIR/libwebp.a"
xcrun lipo -info "$LIBDIR/libwebp.a"
echo "PASS: verified libwebp $VERSION pinned source, iOS arm64 archive"
