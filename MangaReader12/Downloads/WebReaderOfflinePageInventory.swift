import Foundation

/// Build69 BH: strict, read-only inspection of local chapter page filenames.
///
/// A completed SQLite record can outlive or outnumber the actual page files.
/// Never silently collapse a sparse chapter (page 0, page 2) into two pages,
/// and never dereference a symlink as a downloaded image. This uses file
/// metadata only; image integrity still requires opening the reader offline.
/// No network, no database writes, no file deletion and no directory creation.
enum WebReaderOfflinePageInventory {
    enum AuditError: Error, Equatable {
        case missingPages
        case incompletePages
        case unsafePageFile
        case tooManyPages
    }

    static let maximumPages = 99_999

    static func inspect(
        directory: URL,
        fileManager: FileManager = .default
    ) throws -> [URL] {
        let folder = try directory.resourceValues(forKeys: [
            .isDirectoryKey, .isSymbolicLinkKey
        ])
        guard folder.isDirectory == true,
              folder.isSymbolicLink != true else {
            throw AuditError.unsafePageFile
        }
        let files = try fileManager.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [
                .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey
            ],
            options: [.skipsHiddenFiles]
        ).filter { url in
            url.lastPathComponent.hasPrefix("page-") &&
                url.pathExtension == "bin"
        }.sorted { $0.lastPathComponent < $1.lastPathComponent }

        guard !files.isEmpty else { throw AuditError.missingPages }
        guard files.count <= maximumPages else { throw AuditError.tooManyPages }
        for (index, file) in files.enumerated() {
            let expected = String(format: "page-%05d.bin", index)
            guard file.lastPathComponent == expected else {
                throw AuditError.incompletePages
            }
            let meta = try file.resourceValues(forKeys: [
                .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey
            ])
            guard meta.isSymbolicLink != true, meta.isRegularFile == true,
                  let byteCount = meta.fileSize, byteCount > 0 else {
                throw AuditError.unsafePageFile
            }
        }
        return files
    }
}
