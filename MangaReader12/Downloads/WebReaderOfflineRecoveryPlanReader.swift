import Foundation
import Darwin

/// Build69 BQ — bounded, descriptor-based recovery-plan reader.
///
/// A crashed download may leave a malformed or unexpectedly large
/// _download-plan.json file. Never load that file unboundedly on app startup,
/// or follow a symbolic link outside the current sandbox. Rejection does not
/// delete images or modify the recoverable chapter directory.
enum WebReaderOfflineRecoveryPlanReader {
    enum PlanError: Error {
        case unavailableOrUnsafe
        case tooLarge
        case changedWhileReading
    }

    static let maxBytes = 16 * 1024 * 1024

    static func read(from url: URL) throws -> Data {
        let fd = Darwin.open(url.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        guard fd >= 0 else { throw PlanError.unavailableOrUnsafe }
        defer { _ = Darwin.close(fd) }

        var before = stat()
        guard Darwin.fstat(fd, &before) == 0,
              (before.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) else {
            throw PlanError.unavailableOrUnsafe
        }
        guard before.st_size > 0, before.st_size <= off_t(maxBytes) else {
            throw PlanError.tooLarge
        }

        let expected = Int(before.st_size)
        var result = Data()
        result.reserveCapacity(expected)
        var buffer = [UInt8](repeating: 0, count: 64 * 1024)
        while result.count < expected {
            let wanted = min(buffer.count, expected - result.count)
            let actual = buffer.withUnsafeMutableBytes { bytes -> Int in
                return Darwin.read(fd, bytes.baseAddress, wanted)
            }
            guard actual > 0, actual <= wanted else {
                throw PlanError.changedWhileReading
            }
            result.append(contentsOf: buffer.prefix(actual))
        }
        var after = stat()
        guard Darwin.fstat(fd, &after) == 0,
              after.st_dev == before.st_dev,
              after.st_ino == before.st_ino,
              after.st_size == before.st_size,
              after.st_mtimespec.tv_sec == before.st_mtimespec.tv_sec,
              after.st_mtimespec.tv_nsec == before.st_mtimespec.tv_nsec,
              after.st_ctimespec.tv_sec == before.st_ctimespec.tv_sec,
              after.st_ctimespec.tv_nsec == before.st_ctimespec.tv_nsec else {
            throw PlanError.changedWhileReading
        }
        return result
    }
}
