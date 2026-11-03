// Offline-only Asura tile reassembly research prototype.
// Not linked to MangaReader12 app, ReaderImageLoader or downloads.
// No network, premium data, site requests or source credentials.
import Foundation
import CoreGraphics

enum AsuraTileReassemblyProbe {
    static let maxTiles = 80
    static let maxPixels = 40_000_000

    static func validLayout(
        width: Int, height: Int,
        columns: Int, rows: Int,
        tiles: [Int]
    ) -> Bool {
        guard columns >= 1, rows >= 1,
              columns <= 16, rows <= 16,
              columns * rows <= maxTiles,
              tiles.count == columns * rows,
              width > 0, height > 0,
              width <= 32_000, height <= 32_000,
              width <= maxPixels / height,
              width % columns == 0, height % rows == 0 else { return false }

        var used = Set<Int>()
        for index in tiles {
            guard index >= 0, index < tiles.count,
                  used.insert(index).inserted else {
                return false
            }
        }
        return true
    }

    static func reorder(
        image: CGImage,
        tiles: [Int],
        columns: Int,
        rows: Int
    ) -> CGImage? {
        guard validLayout(
            width: image.width, height: image.height,
            columns: columns, rows: rows, tiles: tiles
        ) else { return nil }
        let tw = image.width / columns
        let th = image.height / rows
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let info = CGImageAlphaInfo.premultipliedLast.rawValue |
            CGBitmapInfo.byteOrder32Big.rawValue
        guard let context = CGContext(
            data: nil,
            width: image.width, height: image.height,
            bitsPerComponent: 8, bytesPerRow: image.width * 4,
            space: colorSpace, bitmapInfo: info
        ) else { return nil }

        // Upstream Keiyoushi/Android mapping:
        // for source slot w: tile destination slot = tiles[w].
        // CGImage.cropping uses source pixel coordinates; CGContext's
        // destination origin is bottom-left, thus invert destination row.
        for sourceIndex in 0..<tiles.count {
            let destinationIndex = tiles[sourceIndex]
            let sourceColumn = sourceIndex % columns
            let sourceRow = sourceIndex / columns
            let destinationColumn = destinationIndex % columns
            let destinationRow = destinationIndex / columns
            let sourceRect = CGRect(
                x: sourceColumn * tw, y: sourceRow * th,
                width: tw, height: th
            )
            guard let tile = image.cropping(to: sourceRect) else { return nil }
            let destinationRect = CGRect(
                x: destinationColumn * tw,
                y: (rows - 1 - destinationRow) * th,
                width: tw, height: th
            )
            context.draw(tile, in: destinationRect)
        }
        return context.makeImage()
    }
}

private func require(_ condition: Bool, _ message: String) {
    if !condition { fatalError("Asura offline tile regression: " + message) }
}

private func rgbaImage(_ pixels: [UInt8], width: Int, height: Int) -> CGImage {
    let bytes = Data(pixels)
    let provider = CGDataProvider(data: bytes as CFData)!
    let info = CGBitmapInfo(rawValue:
        CGImageAlphaInfo.premultipliedLast.rawValue |
        CGBitmapInfo.byteOrder32Big.rawValue
    )
    return CGImage(
        width: width, height: height,
        bitsPerComponent: 8, bitsPerPixel: 32,
        bytesPerRow: width * 4,
        space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: info,
        provider: provider, decode: nil,
        shouldInterpolate: false, intent: .defaultIntent
    )!
}

private func pixels(_ image: CGImage) -> [UInt8] {
    guard let provider = image.dataProvider,
          let bytes = provider.data as Data? else {
        fatalError("Cannot read synthetic output pixels")
    }
    return Array(bytes)
}

// Four distinct 1×1 source tiles, two columns × two rows, RGBA.
let red: [UInt8] = [255, 0, 0, 255]
let green: [UInt8] = [0, 255, 0, 255]
let blue: [UInt8] = [0, 0, 255, 255]
let yellow: [UInt8] = [255, 255, 0, 255]
let original = red + green + blue + yellow
let image = rgbaImage(original, width: 2, height: 2)

let identity = AsuraTileReassemblyProbe.reorder(
    image: image, tiles: [0, 1, 2, 3], columns: 2, rows: 2
)!
require(pixels(identity) == original, "identity permutation changed source pixels")

let swapColumns = AsuraTileReassemblyProbe.reorder(
    image: image, tiles: [1, 0, 3, 2], columns: 2, rows: 2
)!
require(pixels(swapColumns) == (green + red + yellow + blue),
    "source tile -> destination tile mapping was incorrect")

let swapRows = AsuraTileReassemblyProbe.reorder(
    image: image, tiles: [2, 3, 0, 1], columns: 2, rows: 2
)!
require(pixels(swapRows) == (blue + yellow + red + green),
    "vertical destination mapping was incorrect")

// Public source's typical 4×5 tile layout: identity is lossless.
var pixels20 = [UInt8]()
for slot in 0..<20 {
    let r = UInt8(slot * 10)
    let g = UInt8(255 - slot * 10)
    let b = UInt8(slot)
    pixels20.append(contentsOf: [r, g, b, 255])
}
let image20 = rgbaImage(pixels20, width: 4, height: 5)
let restored20 = AsuraTileReassemblyProbe.reorder(
    image: image20, tiles: Array(0..<20), columns: 4, rows: 5
)!
require(pixels(restored20) == pixels20, "4×5 identity layout changed pixels")

// No duplicate, out-of-range, missing, huge or non-divisible tile layouts.
require(AsuraTileReassemblyProbe.reorder(
    image: image, tiles: [0, 0, 2, 3], columns: 2, rows: 2
) == nil, "duplicate destination index was accepted")
require(AsuraTileReassemblyProbe.reorder(
    image: image, tiles: [0, 1, 2, 4], columns: 2, rows: 2
) == nil, "out-of-range index was accepted")
require(AsuraTileReassemblyProbe.reorder(
    image: image, tiles: [0, 1, 2], columns: 2, rows: 2
) == nil, "partial permutation was accepted")
require(!AsuraTileReassemblyProbe.validLayout(
    width: 32000, height: 32000, columns: 4, rows: 5,
    tiles: Array(0..<20)
), "huge image dimensions were accepted")
require(!AsuraTileReassemblyProbe.validLayout(
    width: 5, height: 4, columns: 2, rows: 2,
    tiles: [0, 1, 2, 3]
), "non-divisible pixel dimensions were accepted")
require(!AsuraTileReassemblyProbe.validLayout(
    width: 2, height: 2, columns: 0, rows: 2,
    tiles: [0, 1, 2, 3]
), "zero columns were accepted")
print("PASS Asura CoreGraphics offline: 2x2 permutations, 4x5 identity, bounds, invalid tiles")
