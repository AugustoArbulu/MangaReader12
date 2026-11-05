import Foundation
import Darwin

/// Manual local IPC diagnostic for a separate, nonprivileged helper process.
/// This is NOT the Chimera installer, cannot install an IPA, and does not
/// authenticate release signatures or authorize any privileged operation.
/// A matching PONG only proves a same-UID process replied at this socket.
enum WebReaderHelperPingProbe {
    private static let socketName = "wrp.sock"
    private static let request = Array("WRPING1\n".utf8)
    private static let expected = Array("WRPONG1\n".utf8)

    static var diagnosticDirectory: URL {
        return FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        )[0].appendingPathComponent("WebReaderProbeIPC", isDirectory: true)
    }

    enum Result {
        case unavailable
        case unsafePath
        case rejected
        case responded

        var report: String {
            switch self {
            case .unavailable:
                return "Helper de diagnóstico: não encontrado (normal sem instalação)"
            case .unsafePath:
                return "Helper de diagnóstico: diretório/socket não confiável"
            case .rejected:
                return "Helper de diagnóstico: resposta incorreta ou conexão negada"
            case .responded:
                return "Helper de diagnóstico: PONG recebido; mesmo UID, NÃO autenticado"
            }
        }
    }

    static func run(completion: @escaping (Result) -> Void) {
        DispatchQueue.global(qos: .utility).async {
            let result = inspect()
            DispatchQueue.main.async {
                completion(result)
            }
        }
    }

    /// Only create an app-owned diagnostic directory on explicit user action.
    /// A future root helper must NEVER accept this path as trusted input.
    private static func inspect() -> Result {
        let directory = diagnosticDirectory
        let fileManager = FileManager.default
        do {
            try fileManager.createDirectory(
                at: directory, withIntermediateDirectories: true,
                attributes: [.posixPermissions: 0o700]
            )
        } catch {
            return .unsafePath
        }
        var dirStat = stat()
        guard directory.path.withCString({
            lstat($0, &dirStat)
        }) == 0,
            (dirStat.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR),
            dirStat.st_uid == geteuid(),
            (dirStat.st_mode & 0o077) == 0
        else {
            return .unsafePath
        }

        let socketPath = directory.appendingPathComponent(socketName).path
        var entry = stat()
        if socketPath.withCString({ lstat($0, &entry) }) != 0 {
            return .unavailable
        }
        guard (entry.st_mode & mode_t(S_IFMT)) == mode_t(S_IFSOCK),
              entry.st_uid == geteuid(),
              (entry.st_mode & 0o077) == 0
        else {
            return .unsafePath
        }

        var address = sockaddr_un()
        let addressSize = MemoryLayout<sockaddr_un>.size
        let encodedPath = Array(socketPath.utf8) + [0]
        guard encodedPath.count < MemoryLayout.size(ofValue: address.sun_path)
        else {
            return .unsafePath
        }
        address.sun_family = sa_family_t(AF_UNIX)
        address.sun_len = UInt8(addressSize)
        withUnsafeMutableBytes(of: &address.sun_path) { bytes in
            for i in encodedPath.indices {
                bytes[i] = encodedPath[i]
            }
        }
        let fd = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else { return .rejected }
        defer { _ = Darwin.close(fd) }
        var noSigPipe: Int32 = 1
        _ = setsockopt(
            fd, SOL_SOCKET, SO_NOSIGPIPE, &noSigPipe,
            socklen_t(MemoryLayout<Int32>.size)
        )
        var timeout = timeval(tv_sec: 2, tv_usec: 0)
        _ = setsockopt(
            fd, SOL_SOCKET, SO_RCVTIMEO, &timeout,
            socklen_t(MemoryLayout<timeval>.size)
        )
        _ = setsockopt(
            fd, SOL_SOCKET, SO_SNDTIMEO, &timeout,
            socklen_t(MemoryLayout<timeval>.size)
        )
        let connected = withUnsafePointer(to: &address) { ptr -> Int32 in
            return ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(fd, $0, socklen_t(addressSize))
            }
        }
        guard connected == 0 else { return .rejected }

        // Same UID is only an access check, NOT code-signature authentication.
        var peerUID = uid_t.max
        var peerGID = gid_t.max
        guard getpeereid(fd, &peerUID, &peerGID) == 0,
              peerUID == geteuid()
        else { return .rejected }

        var sent = 0
        while sent < request.count {
            let bytesSent = request.withUnsafeBytes { buffer -> Int in
                guard let start = buffer.baseAddress else { return -1 }
                return Darwin.send(
                    fd, start.advanced(by: sent), request.count - sent, 0
                )
            }
            guard bytesSent > 0 else { return .rejected }
            sent += bytesSent
        }

        var answer = [UInt8](repeating: 0, count: expected.count)
        var received = 0
        while received < answer.count {
            let count = answer.withUnsafeMutableBytes { buffer -> Int in
                guard let start = buffer.baseAddress else { return -1 }
                return Darwin.recv(
                    fd, start.advanced(by: received),
                    answer.count - received, 0
                )
            }
            guard count > 0 else { return .rejected }
            received += count
        }
        return answer == expected ? .responded : .rejected
    }
}
