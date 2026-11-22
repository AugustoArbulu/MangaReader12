import Foundation

/// Build69 BO — Only reuse an existing, real, nonempty *prefix* of pages.
///
/// Interrupted transfers may have partial files. This read-only check does
/// not try to decode images or modify the folder. It refuses symlinked
/// directories and files, devices and directories masquerading as pages.
/// A return value of zero is a safe retry from the first page, not data loss.
enum WebReaderOfflineResumePrefix {
    static let maximumPlannedPages = 5_000
    static let maximumPageBytes: Int64 = 20 * 1024 * 1024

    static func count(
        directory: URL,
        plannedPages: Int,
        fileManager: FileManager = .default
    ) -> Int {
        guard plannedPages > 0 && plannedPages <= maximumPlannedPages else {
            return 0
        }
        guard let folder = try? directory.resourceValues(forKeys: [
            .isDirectoryKey, .isSymbolicLinkKey
        ]), folder.isDirectory == true, folder.isSymbolicLink != true else {
            return 0
        }
        var valid = 0
        while valid < plannedPages {
            let file = directory.appendingPathComponent(
                String(format: "page-%05d.bin", valid), isDirectory: false
            )
            guard let attributes = try? file.resourceValues(forKeys: [
                .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey
            ]), attributes.isRegularFile == true,
                  attributes.isSymbolicLink != true,
                  let bytes = attributes.fileSize,
                  bytes > 0, Int64(bytes) <= maximumPageBytes else {
                break
            }
            valid += 1
        }
        return valid
    }
}
