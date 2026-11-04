// libwebp is built from a SHA256-verified 1.6.0 source archive by
// ci/prepare_libwebp_ios.sh for arm64 iOS 12.0. BSD-3-Clause license.
// No runtime download; the codec is statically linked into MangaReader12.
#ifndef MR12_WEBP_BRIDGE_H
#define MR12_WEBP_BRIDGE_H
#include <webp/decode.h>
#include <stddef.h>
#include <stdint.h>

// Full, bounded decoding directly into a caller-owned *scaled* BGRA buffer.
// The Swift caller checks the original dimensions and allocates at most
// 420*420*4 bytes. Keep the C union/config ABI away from the Swift importer.
// Return false for invalid/incomplete WebP; never return partial frames.
static inline int MR12WebPDecodeScaledBGRA(
    const uint8_t *data, size_t input_size,
    uint8_t *output, size_t output_size,
    int scaled_width, int scaled_height, int stride) {
  if (!data || !output || input_size < 20 || input_size > 20 * 1024 * 1024 ||
      scaled_width < 1 || scaled_height < 1 ||
      scaled_width > 420 || scaled_height > 420 ||
      stride != scaled_width * 4 ||
      output_size != (size_t)stride * (size_t)scaled_height) {
    return 0;
  }
  WebPDecoderConfig config;
  if (!WebPInitDecoderConfig(&config)) return 0;
  config.options.use_scaling = 1;
  config.options.scaled_width = scaled_width;
  config.options.scaled_height = scaled_height;
  config.options.use_threads = 0;
  config.output.colorspace = MODE_BGRA;
  config.output.is_external_memory = 1;
  config.output.u.RGBA.rgba = output;
  config.output.u.RGBA.size = output_size;
  config.output.u.RGBA.stride = stride;
  const VP8StatusCode status = WebPDecode(data, input_size, &config);
  WebPFreeDecBuffer(&config.output);
  return status == VP8_STATUS_OK;
}
/*
 * Decode large vertical WebP chapter images with a strict bounded output.
 * Same static libwebp, no new dependencies or remote conversions. The full
 * bitstream must decode successfully before the output is accepted.
 */
static inline int MR12WebPDecodePageScaledBGRA(
    const uint8_t *data, size_t input_size,
    uint8_t *output, size_t output_size,
    int scaled_width, int scaled_height, int stride) {
  if (!data || !output || input_size < 20 || input_size > 20 * 1024 * 1024 ||
      scaled_width < 1 || scaled_height < 1 ||
      scaled_width > 32768 || scaled_height > 32768 ||
      (size_t)scaled_width * (size_t)scaled_height > 24000000 ||
      stride != scaled_width * 4 ||
      output_size != (size_t)stride * (size_t)scaled_height) return 0;
  WebPDecoderConfig config;
  if (!WebPInitDecoderConfig(&config)) return 0;
  config.options.use_scaling = 1;
  config.options.scaled_width = scaled_width;
  config.options.scaled_height = scaled_height;
  config.options.use_threads = 0;
  config.output.colorspace = MODE_BGRA;
  config.output.is_external_memory = 1;
  config.output.u.RGBA.rgba = output;
  config.output.u.RGBA.size = output_size;
  config.output.u.RGBA.stride = stride;
  const VP8StatusCode status = WebPDecode(data, input_size, &config);
  WebPFreeDecBuffer(&config.output);
  return status == VP8_STATUS_OK;
}

#endif
