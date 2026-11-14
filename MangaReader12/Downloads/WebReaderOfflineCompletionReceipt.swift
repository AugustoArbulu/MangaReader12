import Foundation

/// Build69 BM: optional count-only completion receipt for newly downloaded pages.
///
/// Existing Build68 chapters have no receipt and remain readable (legacy
/// compatibility). For Build69 downloads a tiny hidden text receipt records
/// the expected number of image files. Later removal of the FINAL page can
/// then be detected, not just internal gaps. This is metadata, not a digital
/// signature, a server page-count attestation or evidence of image decoding.
enum WebReaderOfflineCompletionReceipt {
    enum ReceiptError: Error, Equatable {
        case invalidCount
        case invalidReceipt
    }

    static let filename = ".webreader-completion-v1"
    static let maximumPages = 99_999
    private static let prefix = "WR-OFFLINE-COMPLETE-V1:"

    static func write(
        directory: URL, expectedPages: Int
    ) throws {
        guard expectedPages >= 1 && expectedPages <= maximumPages else {
            throw ReceiptError.invalidCount
        }
        let text = prefix + String(expectedPages) + "\n"
        guard let data = text.data(using: .utf8) else {
            throw ReceiptError.invalidReceipt
        }
        // The caller already validated the actual page sequence. Only write
        // private metadata on NEW download completion, never on old reads.
        try data.write(
            to: directory.appendingPathComponent(filename, isDirectory: false),
            options: .atomic
        )
    }

    /// Returns false only for an old/legacy folder with no receipt.
    /// Invalid, symlinked or mismatched new receipts MUST NOT be ignored.
    @discardableResult
    static func verifyIfPresent(
        directory: URL, actualPages: Int,
        fileManager: FileManager = .default
    ) throws -> Bool {
        guard actualPages >= 1 && actualPages <= maximumPages else {
            throw ReceiptError.invalidCount
        }
        let entries = try fileManager.contentsOfDirectory(
            at: directory, includingPropertiesForKeys: [
                .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey
            ],
            options: []
        )
        guard let receipt = entries.first(where: {
            $0.lastPathComponent == filename
        }) else {
            return false // Build68 legacy: do not invalidate old chapters.
        }
        let values = try receipt.resourceValues(forKeys: [
            .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey
        ])
        guard values.isRegularFile == true,
              values.isSymbolicLink != true,
              let byteCount = values.fileSize,
              byteCount > 0, byteCount <= 64 else {
            throw ReceiptError.invalidReceipt
        }
        let handle = try FileHandle(forReadingFrom: receipt)
        defer { handle.closeFile() }
        let raw = handle.readData(ofLength: 65)
        guard raw.count == byteCount,
              let text = String(data: raw, encoding: .utf8),
              text == prefix + String(actualPages) + "\n" else {
            throw ReceiptError.invalidReceipt
        }
        return true
    }
}
