import Foundation
import Compression
import ImageIO

// ZIP central-directory parser for a deliberately restricted subset of CBZ.
// Only JPEG/PNG images, ZIP stored/DEFLATE, no encryption, no ZIP64, no links.
// Entries are ALWAYS written to generated filenames in a private staging
// directory, never to archive-supplied paths. Archives are untrusted input.
enum SafeCBZError: Error, LocalizedError {
    case invalidArchive
    case tooLarge
    case unsupported
    case unsafeEntry
    case corruptedEntry
    case noImages

    var errorDescription: String? {
        switch self {
        case .invalidArchive:
            return "Arquivo ZIP/CBZ inválido ou truncado."
        case .tooLarge:
            return "O arquivo excede os limites seguros para este iOS antigo."
        case .unsupported:
            return "Este ZIP usa criptografia, ZIP64 ou um formato não suportado."
        case .unsafeEntry:
            return "O arquivo contém caminhos, links ou entradas inseguras."
        case .corruptedEntry:
            return "Há uma imagem danificada ou com verificação CRC inválida."
        case .noImages:
            return "O arquivo não contém imagens JPEG/PNG compatíveis."
        }
    }
}

private struct SafeCBZEntry {
    let name: String
    let nameBytes: [UInt8]
    let method: UInt16
    let flags: UInt16
    let crc32: UInt32
    let compressedSize: Int
    let expandedSize: Int
    let localOffset: UInt64
    let imageExtension: String
}

enum SafeCBZArchive {
    private static let maxArchiveBytes: UInt64 = 450 * 1024 * 1024
    private static let maxIndexBytes = 8 * 1024 * 1024
    private static let maxEntries = 2000
    private static let maxImages = 1200
    private static let maxImageBytes = 20 * 1024 * 1024
    private static let maxTotalBytes = 400 * 1024 * 1024
    private static let maxImagePixels = 42_000_000

    private static func u16(_ bytes: [UInt8], _ offset: Int) -> UInt16? {
        guard offset >= 0, offset <= bytes.count - 2 else { return nil }
        return UInt16(bytes[offset]) | (UInt16(bytes[offset + 1]) << 8)
    }

    private static func u32(_ bytes: [UInt8], _ offset: Int) -> UInt32? {
        guard offset >= 0, offset <= bytes.count - 4 else { return nil }
        return UInt32(bytes[offset]) |
            (UInt32(bytes[offset + 1]) << 8) |
            (UInt32(bytes[offset + 2]) << 16) |
            (UInt32(bytes[offset + 3]) << 24)
    }

    private static func read(
        _ file: FileHandle, at offset: UInt64,
        count: Int, fileSize: UInt64
    ) throws -> [UInt8] {
        guard count >= 0,
              offset <= fileSize,
              UInt64(count) <= fileSize - offset else {
            throw SafeCBZError.invalidArchive
        }
        file.seek(toFileOffset: offset)
        let bytes = [UInt8](file.readData(ofLength: count))
        guard bytes.count == count else { throw SafeCBZError.invalidArchive }
        return bytes
    }

    // Returns generated filenames (not the untrusted archive member names).
    static func extract(archiveURL: URL, into directory: URL) throws -> [String] {
        let attributes = try FileManager.default.attributesOfItem(
            atPath: archiveURL.path
        )
        guard let number = attributes[.size] as? NSNumber else {
            throw SafeCBZError.invalidArchive
        }
        let length = number.uint64Value
        guard length >= 22, length <= maxArchiveBytes else {
            throw SafeCBZError.tooLarge
        }
        let file = try FileHandle(forReadingFrom: archiveURL)
        defer { file.closeFile() }

        let tailLength = Int(min(length, 65_557))
        let tail = try read(
            file, at: length - UInt64(tailLength),
            count: tailLength, fileSize: length
        )
        var endRecord: Int?
        for i in stride(from: tail.count - 22, through: 0, by: -1) {
            if u32(tail, i) == 0x06054B50,
               let commentLength = u16(tail, i + 20),
               i + 22 + Int(commentLength) == tail.count {
                endRecord = i
                break
            }
        }
        guard let end = endRecord,
              u16(tail, end + 4) == 0,
              u16(tail, end + 6) == 0,
              let totalRecords = u16(tail, end + 10),
              totalRecords == u16(tail, end + 8),
              let indexSizeRaw = u32(tail, end + 12),
              let indexOffsetRaw = u32(tail, end + 16) else {
            throw SafeCBZError.invalidArchive
        }
        let count = Int(totalRecords)
        let indexSize = Int(indexSizeRaw)
        let indexOffset = UInt64(indexOffsetRaw)
        guard count > 0, count <= maxEntries,
              indexSize > 0, indexSize <= maxIndexBytes,
              indexOffset <= length,
              UInt64(indexSize) <= length - indexOffset,
              indexOffset + UInt64(indexSize) <= length - UInt64(tailLength) + UInt64(end) else {
            throw SafeCBZError.tooLarge
        }
        let index = try read(
            file, at: indexOffset, count: indexSize, fileSize: length
        )
        var offset = 0
        var entries: [SafeCBZEntry] = []
        var seen = Set<String>()
        var totalExpanded = 0

        for _ in 0..<count {
            guard u32(index, offset) == 0x02014B50,
                  let flags = u16(index, offset + 8),
                  let method = u16(index, offset + 10),
                  let crc = u32(index, offset + 16),
                  let compressedRaw = u32(index, offset + 20),
                  let expandedRaw = u32(index, offset + 24),
                  let filenameLength = u16(index, offset + 28),
                  let extraLength = u16(index, offset + 30),
                  let commentLength = u16(index, offset + 32),
                  u16(index, offset + 34) == 0,
                  let external = u32(index, offset + 38),
                  let localOffsetRaw = u32(index, offset + 42) else {
                throw SafeCBZError.invalidArchive
            }
            let recordLength = 46 + Int(filenameLength) +
                Int(extraLength) + Int(commentLength)
            guard recordLength >= 46,
                  offset <= index.count - recordLength else {
                throw SafeCBZError.invalidArchive
            }

            let pathBytes = Array(index[(offset + 46)..<(offset + 46 + Int(filenameLength))])
            offset += recordLength
            guard !pathBytes.isEmpty,
                  !pathBytes.contains(0),
                  !pathBytes.contains(92), // backslash
                  (flags & 0x0001) == 0, // encrypted
                  (flags & 0x0040) == 0, // strong encryption
                  (flags & 0x2000) == 0,
                  compressedRaw != UInt32.max,
                  expandedRaw != UInt32.max,
                  localOffsetRaw != UInt32.max else {
                throw SafeCBZError.unsupported
            }
            // ZIP symlinks have Unix file mode 0120000.
            let unixType = (external >> 16) & 0xF000
            guard unixType != 0xA000 else { throw SafeCBZError.unsafeEntry }

            let filenameData = Data(pathBytes)
            let name = String(data: filenameData, encoding: .utf8) ??
                String(data: filenameData, encoding: .isoLatin1)
            guard let path = name,
                  !path.hasPrefix("/"),
                  !path.contains(":"),
                  !path.unicodeScalars.contains(where: { $0.value < 32 }),
                  !path.split(separator: "/", omittingEmptySubsequences: false)
                    .contains(where: { $0 == "." || $0 == ".." }) else {
                throw SafeCBZError.unsafeEntry
            }
            if path.hasSuffix("/") { continue } // directory, never extracted
            let extensionValue = (path as NSString).pathExtension.lowercased()
            let ext: String
            switch extensionValue {
            case "jpg", "jpeg": ext = "jpg"
            case "png": ext = "png"
            default: continue
            }
            if path.hasPrefix("__MACOSX/") ||
                (path as NSString).lastPathComponent.hasPrefix(".") {
                continue
            }
            let unique = path.lowercased()
            guard seen.insert(unique).inserted else {
                throw SafeCBZError.unsafeEntry
            }
            guard method == 0 || method == 8 else {
                throw SafeCBZError.unsupported
            }
            let expanded = Int(expandedRaw)
            let compressed = Int(compressedRaw)
            guard expanded > 0, expanded <= maxImageBytes,
                  compressed > 0, compressed <= maxImageBytes,
                  (method != 0 || compressed == expanded),
                  expanded <= compressed * 150,
                  totalExpanded <= maxTotalBytes - expanded else {
                throw SafeCBZError.tooLarge
            }
            totalExpanded += expanded
            entries.append(SafeCBZEntry(
                name: path, nameBytes: pathBytes, method: method,
                flags: flags, crc32: crc, compressedSize: compressed,
                expandedSize: expanded, localOffset: UInt64(localOffsetRaw),
                imageExtension: ext
            ))
            guard entries.count <= maxImages else {
                throw SafeCBZError.tooLarge
            }
        }
        guard offset == index.count else { throw SafeCBZError.invalidArchive }
        guard !entries.isEmpty else { throw SafeCBZError.noImages }
        if let free = try? directory.resourceValues(
            forKeys: [.volumeAvailableCapacityKey]
        ).volumeAvailableCapacity,
           free < totalExpanded + 64 * 1024 * 1024 {
            throw SafeCBZError.tooLarge
        }
        entries.sort {
            $0.name.localizedStandardCompare($1.name) == .orderedAscending
        }

        var outputs: [String] = []
        for (index, entry) in entries.enumerated() {
            let local = try read(
                file, at: entry.localOffset, count: 30, fileSize: length
            )
            guard u32(local, 0) == 0x04034B50,
                  u16(local, 6) == entry.flags,
                  u16(local, 8) == entry.method,
                  let localNameSize = u16(local, 26),
                  let localExtraSize = u16(local, 28),
                  Int(localNameSize) == entry.nameBytes.count else {
                throw SafeCBZError.corruptedEntry
            }
            let localName = try read(
                file, at: entry.localOffset + 30,
                count: Int(localNameSize), fileSize: length
            )
            guard localName == entry.nameBytes else {
                throw SafeCBZError.corruptedEntry
            }
            let dataOffset = entry.localOffset + 30 +
                UInt64(localNameSize) + UInt64(localExtraSize)
            guard dataOffset <= indexOffset,
                  UInt64(entry.compressedSize) <= indexOffset - dataOffset else {
                throw SafeCBZError.corruptedEntry
            }
            let compressed = try read(
                file, at: dataOffset,
                count: entry.compressedSize, fileSize: length
            )
            let output: [UInt8]
            if entry.method == 0 {
                output = compressed
            } else {
                let expanded = entry.expandedSize
                var destination = [UInt8](repeating: 0, count: expanded)
                let decompressed = compressed.withUnsafeBufferPointer { src in
                    destination.withUnsafeMutableBufferPointer { dest -> Int in
                        guard let from = src.baseAddress,
                              let to = dest.baseAddress else { return 0 }
                        return compression_decode_buffer(
                            to, expanded, from, entry.compressedSize,
                            nil, COMPRESSION_ZLIB
                        )
                    }
                }
                guard decompressed == expanded else {
                    throw SafeCBZError.corruptedEntry
                }
                output = destination
            }
            guard output.count == entry.expandedSize,
                  crc32(output) == entry.crc32,
                  isImage(output, ext: entry.imageExtension) else {
                throw SafeCBZError.corruptedEntry
            }
            let outputName = String(format: "page-%05d.%@", index + 1, entry.imageExtension)
            try Data(output).write(
                to: directory.appendingPathComponent(outputName),
                options: .atomic
            )
            outputs.append(outputName)
        }
        return outputs
    }

    private static let crcTable: [UInt32] = (0..<256).map { value in
        var x = UInt32(value)
        for _ in 0..<8 {
            x = (x & 1) == 1 ? (x >> 1) ^ 0xEDB88320 : (x >> 1)
        }
        return x
    }

    private static func crc32(_ bytes: [UInt8]) -> UInt32 {
        var value: UInt32 = 0xFFFFFFFF
        for byte in bytes {
            let index = Int((value ^ UInt32(byte)) & 0xFF)
            value = crcTable[index] ^ (value >> 8)
        }
        return ~value
    }

    private static func isImage(_ bytes: [UInt8], ext: String) -> Bool {
        if ext == "png" {
            guard bytes.starts(with: [137, 80, 78, 71, 13, 10, 26, 10]) else {
                return false
            }
        } else {
            guard bytes.starts(with: [0xFF, 0xD8, 0xFF]) else { return false }
        }
        guard let source = CGImageSourceCreateWithData(Data(bytes) as CFData, nil),
              CGImageSourceGetCount(source) > 0,
              let props = CGImageSourceCopyPropertiesAtIndex(source, 0, nil)
                as? [CFString: Any],
              let width = props[kCGImagePropertyPixelWidth] as? NSNumber,
              let height = props[kCGImagePropertyPixelHeight] as? NSNumber else {
            return false
        }
        let w = width.intValue
        let h = height.intValue
        return w > 0 && h > 0 && w <= 16_000 && h <= 16_000 &&
            w <= maxImagePixels / h
    }
}
