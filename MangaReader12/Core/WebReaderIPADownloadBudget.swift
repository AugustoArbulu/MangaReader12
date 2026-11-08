import Foundation
import Darwin

/// Phase Z: bounded, non-destructive free-space preflight for a downloaded IPA.
///
/// A single IPA may be up to 512 MiB and a failed download must not consume
/// the storage reserved for manga chapters, backups or the current app.
/// This is a best-effort admission check, NOT a guarantee: other apps can
/// allocate storage during transfer. No reservation, deletion or entitlement
/// change is performed here. Install authorization always remains disabled.
enum WebReaderIPADownloadBudget {
    static let maximumIPASize: Int64 = 512 * 1024 * 1024
    static let minimumReserve: Int64 = 32 * 1024 * 1024
    static let overheadReserve: Int64 = 8 * 1024 * 1024

    static func requiredFreeBytes(ipaBytes: Int64) -> Int64? {
        guard ipaBytes > 0, ipaBytes <= maximumIPASize else { return nil }
        let reserve = max(minimumReserve, ipaBytes / 8)
        let (first, overflow) = ipaBytes.addingReportingOverflow(reserve)
        guard !overflow else { return nil }
        let (needed, secondOverflow) = first.addingReportingOverflow(overheadReserve)
        return secondOverflow ? nil : needed
    }

    static func enoughSpace(freeBytes: Int64, ipaBytes: Int64) -> Bool {
        guard freeBytes >= 0,
              let needed = requiredFreeBytes(ipaBytes: ipaBytes)
        else { return false }
        return freeBytes >= needed
    }

    /// Open directory with O_NOFOLLOW, then query its actual filesystem.
    /// Symlinked destination directories and inaccessible volumes are denied.
    static func availableFreeBytes(in directory: URL) -> Int64? {
        guard directory.isFileURL else { return nil }
        let fd = Darwin.open(
            directory.path,
            O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK
        )
        guard fd >= 0 else { return nil }
        defer { _ = Darwin.close(fd) }
        var descriptorStat = stat()
        guard Darwin.fstat(fd, &descriptorStat) == 0,
              (descriptorStat.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR)
        else { return nil }
        var volume = statfs()
        guard Darwin.fstatfs(fd, &volume) == 0,
              volume.f_bsize > 0
        else { return nil }
        let (freeBytes, overflow) = UInt64(volume.f_bavail)
            .multipliedReportingOverflow(by: UInt64(volume.f_bsize))
        guard !overflow, freeBytes <= UInt64(Int64.max) else { return nil }
        return Int64(freeBytes)
    }
}
