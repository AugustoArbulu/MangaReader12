import Foundation
import Darwin

/// Build69 BR: bounded, atomic local writes of *recovery metadata* only.
///
/// The plan may include temporary HTTP headers and must never be published
/// in an unrestricted-size or world-readable file. Existing regular plans
/// may be replaced for "Prioritize", but symlinks/special files may not.
/// The app's chapter images and SQLite download rows are never touched.
enum WebReaderOfflineRecoveryPlanWriter {
    enum WriteError: Error {
        case invalidPayload
        case unsafeDirectory
        case unsafeDestination
        case ioFailure
    }

    static let maxBytes = WebReaderOfflineRecoveryPlanReader.maxBytes
    private static let destinationName = "_download-plan.json"

    static func write(data: Data, to url: URL) throws {
        guard !data.isEmpty, data.count <= maxBytes,
              url.lastPathComponent == destinationName else {
            throw WriteError.invalidPayload
        }

        let folder = url.deletingLastPathComponent()
        let dirFD = Darwin.open(
            folder.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC
        )
        guard dirFD >= 0 else { throw WriteError.unsafeDirectory }
        defer { _ = Darwin.close(dirFD) }

        var folderStat = stat()
        guard Darwin.fstat(dirFD, &folderStat) == 0,
              (folderStat.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR) else {
            throw WriteError.unsafeDirectory
        }

        // Check the existing item without following a symlink. A normal
        // existing plan must be replaceable when the queue order changes.
        func safeExistingDestination() -> Bool {
            var destination = stat()
            let result = Darwin.fstatat(
                dirFD, destinationName, &destination, AT_SYMLINK_NOFOLLOW
            )
            if result == 0 {
                return (destination.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG)
            }
            return errno == ENOENT
        }
        guard safeExistingDestination() else {
            throw WriteError.unsafeDestination
        }

        let temporaryName = ".wr69-plan-" + UUID().uuidString + ".tmp"
        let fd = Darwin.openat(
            dirFD, temporaryName,
            O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC,
            mode_t(0o600)
        )
        guard fd >= 0 else { throw WriteError.ioFailure }
        var createdTemporary = true
        defer {
            _ = Darwin.close(fd)
            if createdTemporary {
                _ = Darwin.unlinkat(dirFD, temporaryName, 0)
            }
        }

        // Write the exact payload (possibly in several partial writes).
        // The destination remains unchanged until the entire temporary
        // payload has been flushed and the final rename succeeds.
        try data.withUnsafeBytes { raw in
            guard let base = raw.baseAddress else {
                throw WriteError.invalidPayload
            }
            var written = 0
            while written < raw.count {
                let next = Darwin.write(
                    fd, base.advanced(by: written), raw.count - written
                )
                if next < 0 && errno == EINTR { continue }
                guard next > 0, next <= raw.count - written else {
                    throw WriteError.ioFailure
                }
                written += next
            }
        }
        guard Darwin.fsync(fd) == 0 else { throw WriteError.ioFailure }

        // Retain the old iOS file protection after first unlock. On macOS
        // this optional protection attribute is not always implemented.
        let temporaryURL = folder.appendingPathComponent(temporaryName)
        try? FileManager.default.setAttributes(
            [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
            ofItemAtPath: temporaryURL.path
        )

        // A symlink/special destination appearing during the write is
        // explicitly rejected instead of silently being replaced.
        guard safeExistingDestination() else {
            throw WriteError.unsafeDestination
        }
        guard Darwin.renameat(
            dirFD, temporaryName, dirFD, destinationName
        ) == 0 else {
            throw WriteError.ioFailure
        }
        createdTemporary = false
    }
}
