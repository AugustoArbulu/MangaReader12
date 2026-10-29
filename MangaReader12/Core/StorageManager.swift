import Foundation

struct StorageSnapshot {
    let databaseBytes: Int64
    let downloadsBytes: Int64
    let readerCacheBytes: Int64
    let coverCacheBytes: Int64

    var totalManagedBytes: Int64 {
        return databaseBytes + downloadsBytes + readerCacheBytes + coverCacheBytes
    }
}

final class StorageManager {
    private let fileManager: FileManager
    private let downloadsRepository: DownloadRepository

    init(
        fileManager: FileManager = .default,
        downloadsRepository: DownloadRepository
    ) {
        self.fileManager = fileManager
        self.downloadsRepository = downloadsRepository
    }

    static func defaultManager() throws -> StorageManager {
        return StorageManager(
            downloadsRepository: try DownloadRepository.defaultRepository()
        )
    }

    func snapshot() -> StorageSnapshot {
        return StorageSnapshot(
            databaseBytes: size(of: databaseURL()),
            downloadsBytes: size(of: downloadsDirectory()),
            readerCacheBytes: size(of: readerCacheDirectory()),
            coverCacheBytes: size(of: coverCacheDirectory())
        )
    }

    func clearReaderCache() throws {
        try recreateDirectory(readerCacheDirectory())
    }

    func clearCoverCache() throws {
        CoverImageLoader.shared.clearDiskCache()
        try recreateDirectory(coverCacheDirectory())
    }

    func clearAllDownloads() throws {
        let directory = downloadsDirectory()

        if fileManager.fileExists(atPath: directory.path) {
            try fileManager.removeItem(at: directory)
        }

        try fileManager.createDirectory(
            at: directory,
            withIntermediateDirectories: true,
            attributes: nil
        )

        try downloadsRepository.clearAll()
    }

    func reindexDownloads() throws -> Int {
        return try downloadsRepository.removeMissingFiles(
            fileManager: fileManager
        )
    }

    private func recreateDirectory(_ url: URL) throws {
        if fileManager.fileExists(atPath: url.path) {
            try fileManager.removeItem(at: url)
        }

        try fileManager.createDirectory(
            at: url,
            withIntermediateDirectories: true,
            attributes: nil
        )
    }

    private func databaseURL() -> URL {
        return applicationSupportRoot().appendingPathComponent("library.sqlite")
    }

    private func downloadsDirectory() -> URL {
        return applicationSupportRoot().appendingPathComponent(
            "Downloads",
            isDirectory: true
        )
    }

    private func readerCacheDirectory() -> URL {
        return cachesRoot().appendingPathComponent(
            "ReaderImageCache",
            isDirectory: true
        )
    }

    private func coverCacheDirectory() -> URL {
        return cachesRoot().appendingPathComponent(
            "CoverCache",
            isDirectory: true
        )
    }

    private func applicationSupportRoot() -> URL {
        let base = fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? fileManager.temporaryDirectory

        return base.appendingPathComponent("MangaReader12", isDirectory: true)
    }

    private func cachesRoot() -> URL {
        let base = fileManager.urls(
            for: .cachesDirectory,
            in: .userDomainMask
        ).first ?? fileManager.temporaryDirectory

        return base.appendingPathComponent("MangaReader12", isDirectory: true)
    }

    private func size(of url: URL) -> Int64 {
        guard fileManager.fileExists(atPath: url.path) else {
            return 0
        }

        var isDirectory: ObjCBool = false
        fileManager.fileExists(
            atPath: url.path,
            isDirectory: &isDirectory
        )

        if !isDirectory.boolValue {
            let attributes = try? fileManager.attributesOfItem(atPath: url.path)
            return (attributes?[.size] as? NSNumber)?.int64Value ?? 0
        }

        guard let enumerator = fileManager.enumerator(
            at: url,
            includingPropertiesForKeys: [.fileSizeKey],
            options: [.skipsHiddenFiles]
        ) else {
            return 0
        }

        var total: Int64 = 0

        for case let fileURL as URL in enumerator {
            if let values = try? fileURL.resourceValues(
                forKeys: [.fileSizeKey]
            ), let size = values.fileSize {
                total += Int64(size)
            }
        }

        return total
    }
}
