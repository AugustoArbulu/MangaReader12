import Foundation
import Compression
import CommonCrypto
import Darwin

/// Read-only, bounded ZIP/IPA and identity inspection for the exact bytes
/// referenced by an authenticated WebReader release manifest.
///
/// No extraction, symlink following, appinst execution, process launching,
/// sandbox migration, or installation. A future privileged helper must redo
/// ALL checks independently before installing.
enum WebReaderIPAAuditError: Error {
    case unreadable
    case hashMismatch
    case malformedZIP
    case unsafeEntry
    case unsupportedZIP
    case excessiveSize
    case corruptPlist
    case identityMismatch
    case incompatibleIOS
    case oldBuild
}

struct WebReaderIPAAuditReport {
    let bundleID: String
    let build: Int
    let minimumIOS: String
    let zipEntries: Int
    let verifiedSHA256: String
}

enum WebReaderNativeIPAAuditor {
    private static let root = "Payload/MangaReader12.app/"
    private static let plistName = root + "Info.plist"
    private static let executableName = root + "MangaReader12"
    private static let maxArchiveBytes: UInt64 = 512 * 1024 * 1024
    private static let maxIndexBytes = 16 * 1024 * 1024
    private static let maxEntries = 20_000
    private static let maxPlistBytes = 1024 * 1024
    private static let maxExpandedTotal: UInt64 = 1024 * 1024 * 1024

    private struct Entry {
        let name: String
        let originalName: [UInt8]
        let method: UInt16
        let flags: UInt16
        let crc: UInt32
        let packed: UInt32
        let expanded: UInt32
        let offset: UInt64
        let isDirectory: Bool
    }

    private static func u16(_ b: [UInt8], _ i: Int) -> UInt16? {
        guard i >= 0, i <= b.count - 2 else { return nil }
        return UInt16(b[i]) | (UInt16(b[i + 1]) << 8)
    }
    private static func u32(_ b: [UInt8], _ i: Int) -> UInt32? {
        guard i >= 0, i <= b.count - 4 else { return nil }
        return UInt32(b[i]) | (UInt32(b[i + 1]) << 8) |
            (UInt32(b[i + 2]) << 16) | (UInt32(b[i + 3]) << 24)
    }
    private static func read(
        _ file: FileHandle, at offset: UInt64, count: Int, size: UInt64
    ) throws -> [UInt8] {
        guard count >= 0, offset <= size,
              UInt64(count) <= size - offset else {
            throw WebReaderIPAAuditError.malformedZIP
        }
        file.seek(toFileOffset: offset)
        let b = [UInt8](file.readData(ofLength: count))
        guard b.count == count else { throw WebReaderIPAAuditError.unreadable }
        return b
    }

    /// Hash the SAME opened regular-file descriptor used by ZIP inspection.
    /// Never reopen by filename between hash, ZIP parse and final hash.
    private static func fileSHA256(_ file: FileHandle) -> String {
        file.seek(toFileOffset: 0)
        var ctx = CC_SHA256_CTX()
        CC_SHA256_Init(&ctx)
        while true {
            let chunk = file.readData(ofLength: 64 * 1024)
            if chunk.isEmpty { break }
            chunk.withUnsafeBytes { ptr in
                _ = CC_SHA256_Update(&ctx, ptr.baseAddress, CC_LONG(chunk.count))
            }
        }
        var digest = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        CC_SHA256_Final(&digest, &ctx)
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    private static let crcTable: [UInt32] = (0..<256).map { i in
        var x = UInt32(i)
        for _ in 0..<8 {
            x = (x & 1) != 0 ? (x >> 1) ^ 0xEDB88320 : x >> 1
        }
        return x
    }
    private static func crc32(_ bytes: [UInt8]) -> UInt32 {
        var crc: UInt32 = 0xFFFFFFFF
        for byte in bytes {
            crc = crcTable[Int((crc ^ UInt32(byte)) & 0xFF)] ^ (crc >> 8)
        }
        return ~crc
    }

    private static func version(_ text: String) -> [Int]? {
        let pieces = text.split(separator: ".", omittingEmptySubsequences: false)
        guard pieces.count == 2 || pieces.count == 3 else { return nil }
        var result: [Int] = []
        for piece in pieces {
            guard !piece.isEmpty, piece.count <= 2,
                  piece.allSatisfy({ $0 >= "0" && $0 <= "9" }),
                  let n = Int(piece) else { return nil }
            result.append(n)
        }
        if result.count == 2 { result.append(0) }
        return result
    }

    private static func validatedPath(_ raw: [UInt8]) throws -> (String, Bool) {
        guard !raw.isEmpty, !raw.contains(0), !raw.contains(92),
              let name = String(data: Data(raw), encoding: .utf8),
              !name.hasPrefix("/"), !name.contains(":"),
              !name.unicodeScalars.contains(where: { $0.value < 32 }) else {
            throw WebReaderIPAAuditError.unsafeEntry
        }
        let directory = name.hasSuffix("/")
        let stripped = directory ? String(name.dropLast()) : name
        let pieces = stripped.split(separator: "/", omittingEmptySubsequences: false)
        guard !pieces.isEmpty,
              !pieces.contains(where: { $0.isEmpty || $0 == "." || $0 == ".." }),
              name == "Payload/" || name == "Payload/MangaReader12.app/" ||
                name.hasPrefix(root) else {
            throw WebReaderIPAAuditError.unsafeEntry
        }
        return (name, directory)
    }

    static func inspect(
        ipaURL: URL, signedUpdate: WebReaderVerifiedUpdate,
        installedBuild: Int, installedIOS: OperatingSystemVersion
    ) throws -> WebReaderIPAAuditReport {
        // open(O_NOFOLLOW) prevents following a substituted last-component
        // symlink, including on a jailbroken device with a writable sandbox.
        // fstat binds the descriptor to a regular file and a fixed size.
        guard ipaURL.isFileURL else { throw WebReaderIPAAuditError.unreadable }
        let descriptor = Darwin.open(
            ipaURL.path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW
        )
        guard descriptor >= 0 else { throw WebReaderIPAAuditError.unreadable }
        var opened = stat()
        guard Darwin.fstat(descriptor, &opened) == 0,
              (opened.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
              opened.st_size >= 22 else {
            Darwin.close(descriptor)
            throw WebReaderIPAAuditError.unreadable
        }
        let file = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
        defer { file.closeFile() }
        let size = UInt64(opened.st_size)
        guard size <= maxArchiveBytes,
              signedUpdate.ipaSize > 0,
              size == UInt64(signedUpdate.ipaSize) else {
            throw WebReaderIPAAuditError.excessiveSize
        }
        guard fileSHA256(file) == signedUpdate.sha256 else {
            throw WebReaderIPAAuditError.hashMismatch
        }
        let tailLength = Int(min(size, 65_557))
        let tail = try read(
            file, at: size - UInt64(tailLength),
            count: tailLength, size: size
        )
        var eocd: Int?
        for i in stride(from: tail.count - 22, through: 0, by: -1) {
            if u32(tail, i) == 0x06054B50,
               let comment = u16(tail, i + 20),
               i + 22 + Int(comment) == tail.count {
                eocd = i
                break
            }
        }
        guard let end = eocd,
              u16(tail, end + 4) == 0,
              u16(tail, end + 6) == 0,
              let entriesCount = u16(tail, end + 10),
              entriesCount == u16(tail, end + 8),
              let length = u32(tail, end + 12),
              let indexStart = u32(tail, end + 16),
              entriesCount > 0,
              Int(entriesCount) <= maxEntries,
              length > 0, Int(length) <= maxIndexBytes,
              indexStart != UInt32.max, length != UInt32.max
        else { throw WebReaderIPAAuditError.unsupportedZIP }

        let directoryOffset = UInt64(indexStart)
        let directoryLength = UInt64(length)
        let endOffset = size - UInt64(tailLength) + UInt64(end)
        guard directoryOffset <= size,
              directoryLength <= size - directoryOffset,
              directoryOffset + directoryLength == endOffset else {
            throw WebReaderIPAAuditError.malformedZIP
        }
        let index = try read(
            file, at: directoryOffset, count: Int(length), size: size
        )
        var seen = Set<String>()
        var entries: [Entry] = []
        var offset = 0
        var expandedTotal: UInt64 = 0
        for _ in 0..<Int(entriesCount) {
            guard u32(index, offset) == 0x02014B50,
                  let flags = u16(index, offset + 8),
                  let method = u16(index, offset + 10),
                  let crc = u32(index, offset + 16),
                  let compressed = u32(index, offset + 20),
                  let expanded = u32(index, offset + 24),
                  let nameLength = u16(index, offset + 28),
                  let extraLength = u16(index, offset + 30),
                  let commentLength = u16(index, offset + 32),
                  u16(index, offset + 34) == 0,
                  let attributes = u32(index, offset + 38),
                  let local = u32(index, offset + 42),
                  compressed != UInt32.max, expanded != UInt32.max,
                  local != UInt32.max,
                  (flags & 0x0001) == 0, (flags & 0x0040) == 0,
                  (flags & 0x2000) == 0,
                  method == 0 || method == 8
            else { throw WebReaderIPAAuditError.unsupportedZIP }

            let recordLength = 46 + Int(nameLength) + Int(extraLength) +
                Int(commentLength)
            guard recordLength >= 46, offset <= index.count - recordLength else {
                throw WebReaderIPAAuditError.malformedZIP
            }
            let nameBytes = Array(
                index[(offset + 46)..<(offset + 46 + Int(nameLength))]
            )
            offset += recordLength
            let (name, directory) = try validatedPath(nameBytes)
            let normalized = name.precomposedStringWithCanonicalMapping
                .lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            guard seen.insert(normalized).inserted else {
                throw WebReaderIPAAuditError.unsafeEntry
            }
            let unixType = (attributes >> 16) & 0xF000
            guard unixType == 0 || unixType == 0x8000 || unixType == 0x4000,
                  (unixType != 0x4000 || directory),
                  (unixType != 0x8000 || !directory),
                  (!directory || (compressed == 0 && expanded == 0)),
                  (method != 0 || compressed == expanded),
                  UInt64(expanded) <= maxExpandedTotal - expandedTotal else {
                throw WebReaderIPAAuditError.unsafeEntry
            }
            expandedTotal += UInt64(expanded)
            if name == plistName {
                guard expanded > 0, expanded <= UInt32(maxPlistBytes),
                      compressed > 0, compressed <= UInt32(maxPlistBytes) else {
                    throw WebReaderIPAAuditError.excessiveSize
                }
            }
            entries.append(Entry(
                name: name, originalName: nameBytes, method: method,
                flags: flags, crc: crc, packed: compressed,
                expanded: expanded, offset: UInt64(local),
                isDirectory: directory
            ))
        }
        guard offset == index.count,
              let plist = entries.first(where: { $0.name == plistName && !$0.isDirectory }),
              entries.contains(where: { $0.name == executableName &&
                  !$0.isDirectory && $0.expanded >= 4 }) else {
            throw WebReaderIPAAuditError.malformedZIP
        }

        // Every local ZIP header must agree with its central-directory
        // counterpart. No extracted paths, links or executable files.
        var plistContents: [UInt8]?
        for entry in entries {
            let local = try read(
                file, at: entry.offset, count: 30, size: size
            )
            guard u32(local, 0) == 0x04034B50,
                  u16(local, 6) == entry.flags,
                  u16(local, 8) == entry.method,
                  let nameSize = u16(local, 26),
                  let extraSize = u16(local, 28),
                  Int(nameSize) == entry.originalName.count else {
                throw WebReaderIPAAuditError.malformedZIP
            }
            let localName = try read(
                file, at: entry.offset + 30,
                count: Int(nameSize), size: size
            )
            guard localName == entry.originalName else {
                throw WebReaderIPAAuditError.malformedZIP
            }
            let dataOffset = entry.offset + 30 + UInt64(nameSize) +
                UInt64(extraSize)
            guard dataOffset <= directoryOffset,
                  UInt64(entry.packed) <= directoryOffset - dataOffset else {
                throw WebReaderIPAAuditError.malformedZIP
            }
            if entry.name == plistName {
                let compressed = try read(
                    file, at: dataOffset, count: Int(entry.packed), size: size
                )
                let bytes: [UInt8]
                if entry.method == 0 {
                    bytes = compressed
                } else {
                    var decoded = [UInt8](
                        repeating: 0, count: Int(entry.expanded)
                    )
                    let length = compressed.withUnsafeBufferPointer { source in
                        decoded.withUnsafeMutableBufferPointer { target -> Int in
                            guard let src = source.baseAddress,
                                  let dst = target.baseAddress else { return 0 }
                            return compression_decode_buffer(
                                dst, target.count, src, source.count,
                                nil, COMPRESSION_ZLIB
                            )
                        }
                    }
                    guard length == Int(entry.expanded) else {
                        throw WebReaderIPAAuditError.corruptPlist
                    }
                    bytes = decoded
                }
                guard bytes.count == Int(entry.expanded),
                      crc32(bytes) == entry.crc else {
                    throw WebReaderIPAAuditError.corruptPlist
                }
                plistContents = bytes
            }
        }

        guard let bytes = plistContents,
              let properties = try? PropertyListSerialization.propertyList(
                from: Data(bytes), options: [], format: nil
              ) as? [String: Any],
              properties["CFBundleIdentifier"] as? String ==
                "com.example.MangaReader12",
              properties["CFBundleExecutable"] as? String == "MangaReader12",
              properties["CFBundleDisplayName"] as? String == "WebReader",
              let rawBuild = properties["CFBundleVersion"] as? String,
              rawBuild.range(
                of: "^[1-9][0-9]{0,9}$", options: .regularExpression
              ) != nil,
              let build = Int(rawBuild),
              build == signedUpdate.build,
              let rawIOS = properties["MinimumOSVersion"] as? String,
              rawIOS == signedUpdate.minimumIOS else {
            throw WebReaderIPAAuditError.identityMismatch
        }
        guard build > installedBuild else {
            throw WebReaderIPAAuditError.oldBuild
        }
        guard let minimum = version(rawIOS),
              minimum.lexicographicallyPrecedes([
                installedIOS.majorVersion, installedIOS.minorVersion,
                installedIOS.patchVersion
              ]) || minimum == [
                installedIOS.majorVersion, installedIOS.minorVersion,
                installedIOS.patchVersion
              ] else {
            throw WebReaderIPAAuditError.incompatibleIOS
        }
        // A malicious process may replace a file *during* ZIP inspection.
        // We cannot authorize installation from this check, but we do reject
        // a changed inode or in-place mutation before returning a review.
        let finalDigest = fileSHA256(file)
        var finished = stat()
        guard Darwin.fstat(descriptor, &finished) == 0,
              finalDigest == signedUpdate.sha256,
              opened.st_dev == finished.st_dev,
              opened.st_ino == finished.st_ino,
              opened.st_size == finished.st_size,
              opened.st_mtimespec.tv_sec == finished.st_mtimespec.tv_sec,
              opened.st_mtimespec.tv_nsec == finished.st_mtimespec.tv_nsec,
              opened.st_ctimespec.tv_sec == finished.st_ctimespec.tv_sec,
              opened.st_ctimespec.tv_nsec == finished.st_ctimespec.tv_nsec else {
            throw WebReaderIPAAuditError.hashMismatch
        }
        return WebReaderIPAAuditReport(
            bundleID: "com.example.MangaReader12", build: build,
            minimumIOS: rawIOS, zipEntries: entries.count,
            verifiedSHA256: finalDigest
        )
    }
}
