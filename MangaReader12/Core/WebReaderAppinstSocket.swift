import Foundation
import Darwin

/// Nonprivileged iOS12 client for the one-shot mobile-user appinst CLI bridge.
///
/// This client NEVER launches a process or calls appinst. A separately started
/// same-UID CLI server receives a fixed-size, bounded install request only
/// after the WebReader user explicitly confirms in the updates UI.
///
/// The socket is NOT code-signature authenticated. Do not reuse this protocol
/// for a root daemon or treat a successful PONG as installer authorization.
enum WebReaderAppinstSocket {
    private static let socketName = "wri.sock"
    private static let installHeader = Data("WRINST1\n".utf8)
    private static let inspectHeader = Data("WRPING1\n".utf8)
    private static let confirmation = Data("I-CONFIRM-INSTALL".utf8)

    enum Result: Equatable {
        case unavailable
        case rejected
        case completed
        case failed
        case diagnosticReady
        case diagnosticFailure(String)

        var text: String {
            switch self {
            case .unavailable:
                return "Ponte appinst não está em execução no Chimera"
            case .rejected:
                return "Conexão ou resposta do instalador rejeitada"
            case .completed:
                return "appinst relatou sucesso; confira a versão depois de reabrir o app"
            case .failed:
                return "Ponte appinst relatou falha; a instalação não foi confirmada"
            case .diagnosticReady:
                return "Ponte mobile respondeu PONG; instalação não executada"
            case .diagnosticFailure(let detail):
                return "Diagnóstico IPC: " + detail + " • nenhuma instalação executada"
            }
        }
    }

    static func checkConnection(completion: @escaping (Result) -> Void) {
        DispatchQueue.global(qos: .utility).async {
            let result = exchange(request: inspectHeader, expectingInstall: false)
            DispatchQueue.main.async { completion(result) }
        }
    }

    static func install(
        ipaURL: URL, expectedSHA256: String,
        completion: @escaping (Result) -> Void
    ) {
        DispatchQueue.global(qos: .utility).async {
            let result = performInstall(ipaURL: ipaURL, sha: expectedSHA256)
            DispatchQueue.main.async { completion(result) }
        }
    }

    private static func performInstall(
        ipaURL: URL, sha: String,
        directory: URL = WebReaderHelperPingProbe.diagnosticDirectory
    ) -> Result {
        guard ipaURL.isFileURL,
              sha.range(of: "^[a-f0-9]{64}$",
                        options: .regularExpression) != nil
        else { return .rejected }
        let bytes = Array(ipaURL.path.utf8)
        guard bytes.count >= 70, bytes.count <= 1024,
              !bytes.contains(0), ipaURL.path.hasPrefix("/")
        else { return .rejected }

        var request = Data()
        request.append(installHeader)
        request.append(UInt8(bytes.count >> 8))
        request.append(UInt8(bytes.count & 0xFF))
        request.append(contentsOf: bytes)
        request.append(contentsOf: sha.utf8)
        request.append(confirmation)
        return exchange(request: request, expectingInstall: true,
                        directory: directory)
    }

    private static func exchange(
        request: Data, expectingInstall: Bool,
        directory: URL = WebReaderHelperPingProbe.diagnosticDirectory
    ) -> Result {
        // Only reveal detailed failure stages in a read-only PING probe.
        // Real installer requests must stay fail-closed and return .rejected.
        func reject(_ stage: String, error code: Int32 = 0) -> Result {
            return expectingInstall ? .rejected :
                .diagnosticFailure(stage + " (errno=" + String(code) + ")")
        }
        let fm = FileManager.default
        do {
            try fm.createDirectory(
                at: directory, withIntermediateDirectories: true,
                attributes: [.posixPermissions: 0o700]
            )
        } catch {
            return reject("criar pasta WR: " + String((error as NSError).code))
        }

        var directoryEntry = stat()
        let directoryStatus = directory.path.withCString { lstat($0, &directoryEntry) }
        if directoryStatus != 0 { return reject("lstat pasta WR", error: errno) }
        guard (directoryEntry.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR)
        else { return reject("pasta WR não é diretório") }
        guard directoryEntry.st_uid == geteuid()
        else { return reject("proprietário WR diferente de mobile") }
        guard (directoryEntry.st_mode & 0o077) == 0
        else { return reject("permissões WR não são privadas") }

        let socketPath = directory.appendingPathComponent(socketName).path
        var entry = stat()
        if socketPath.withCString({ lstat($0, &entry) }) != 0 {
            let errorCode = errno
            return errorCode == ENOENT ? .unavailable :
                reject("lstat socket", error: errorCode)
        }
        guard (entry.st_mode & mode_t(S_IFMT)) == mode_t(S_IFSOCK)
        else { return reject("wri.sock não é socket") }
        guard entry.st_uid == geteuid()
        else { return reject("UID do socket diferente de mobile") }
        guard (entry.st_mode & 0o077) == 0
        else { return reject("permissões do socket não são privadas") }

        var address = sockaddr_un()
        let count = MemoryLayout<sockaddr_un>.size
        let pathBytes = Array(socketPath.utf8) + [0]
        guard pathBytes.count < MemoryLayout.size(ofValue: address.sun_path)
        else { return reject("caminho do socket excede limite do iOS12") }
        address.sun_family = sa_family_t(AF_UNIX)
        address.sun_len = UInt8(count)
        withUnsafeMutableBytes(of: &address.sun_path) { buffer in
            for i in pathBytes.indices { buffer[i] = pathBytes[i] }
        }

        let fd = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else { return reject("socket(AF_UNIX)", error: errno) }
        defer { _ = Darwin.close(fd) }
        var noSigPipe: Int32 = 1
        guard setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &noSigPipe,
                         socklen_t(MemoryLayout<Int32>.size)) == 0
        else { return reject("setsockopt NOSIGPIPE", error: errno) }

        var timeout = timeval(tv_sec: expectingInstall ? 190 : 3, tv_usec: 0)
        guard setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout,
                         socklen_t(MemoryLayout<timeval>.size)) == 0
        else { return reject("setsockopt RCVTIMEO", error: errno) }
        guard setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout,
                         socklen_t(MemoryLayout<timeval>.size)) == 0
        else { return reject("setsockopt SNDTIMEO", error: errno) }

        let connected = withUnsafePointer(to: &address) { pointer -> Int32 in
            return pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(fd, $0, socklen_t(count))
            }
        }
        guard connected == 0 else {
            return expectingInstall ? .unavailable : reject("connect", error: errno)
        }

        var peerUID = uid_t.max
        var peerGID = gid_t.max
        guard getpeereid(fd, &peerUID, &peerGID) == 0
        else { return reject("getpeereid", error: errno) }
        guard peerUID == geteuid()
        else { return reject("UID do peer não corresponde ao app") }

        var sent = 0
        let written = request.withUnsafeBytes { buffer -> Bool in
            guard let base = buffer.baseAddress else { return false }
            while sent < request.count {
                let n = Darwin.send(fd, base.advanced(by: sent),
                                    request.count - sent, 0)
                if n <= 0 { return false }
                sent += n
            }
            return true
        }
        guard written else { return reject("send PING", error: errno) }
        var response = [UInt8](repeating: 0, count: 8)
        var received = 0
        while received < response.count {
            let remaining = response.count - received
            let n = response.withUnsafeMutableBytes { buffer -> Int in
                guard let base = buffer.baseAddress else { return -1 }
                return Darwin.recv(fd, base.advanced(by: received),
                                   remaining, 0)
            }
            if n <= 0 { return reject("recv PONG", error: n == 0 ? 0 : errno) }
            received += n
        }
        if expectingInstall {
            if response == Array("WRDONE1\n".utf8) { return .completed }
            if response == Array("WRFAIL1\n".utf8) { return .failed }
        } else if response == Array("WRPONG1\n".utf8) {
            return .diagnosticReady
        }
        return reject("resposta não corresponde a PONG")
    }

    // PING-only alternative for Chimera's iOS12 AF_UNIX sandbox denial.
    // Intentionally no IPA path, no appinst operation and no authorization.
    // The TCP port MUST NOT be reused for installation without a completely
    // separate authentication and protocol/security review.
    static func checkLoopbackConnection(
        completion: @escaping (Result) -> Void
    ) {
        DispatchQueue.global(qos: .utility).async {
            let result = pingLoopback()
            DispatchQueue.main.async { completion(result) }
        }
    }

    private static func pingLoopback() -> Result {
        func rejected(_ stage: String, _ errorCode: Int32 = 0) -> Result {
            return .diagnosticFailure("TCP local " + stage +
                " (errno=" + String(errorCode) + ")")
        }

        // Keep the service bound to 127.0.0.1, not an external HTTP endpoint.
        // There is no file-system or sandbox-container access in this path.
        let fd = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { return rejected("socket(AF_INET)", errno) }
        defer { _ = Darwin.close(fd) }

        var noSigPipe: Int32 = 1
        guard setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &noSigPipe,
                         socklen_t(MemoryLayout<Int32>.size)) == 0
        else { return rejected("NOSIGPIPE", errno) }

        var timeout = timeval(tv_sec: 3, tv_usec: 0)
        guard setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout,
                         socklen_t(MemoryLayout<timeval>.size)) == 0
        else { return rejected("RCVTIMEO", errno) }
        guard setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout,
                         socklen_t(MemoryLayout<timeval>.size)) == 0
        else { return rejected("SNDTIMEO", errno) }

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = UInt16(38971).bigEndian
        address.sin_addr = in_addr(s_addr: UInt32(0x7f000001).bigEndian)
        let connected = withUnsafePointer(to: &address) { pointer -> Int32 in
            return pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(fd, $0,
                    socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard connected == 0 else { return rejected("connect", errno) }

        let request = Array("WRPING1\\n".utf8)
        var sent = 0
        while sent < request.count {
            let amount = request.withUnsafeBytes { bytes -> Int in
                guard let base = bytes.baseAddress else { return -1 }
                return Darwin.send(fd, base.advanced(by: sent),
                                   request.count - sent, 0)
            }
            guard amount > 0 else { return rejected("send PING", errno) }
            sent += amount
        }

        var response = [UInt8](repeating: 0, count: 8)
        var received = 0
        while received < response.count {
            let amount = response.withUnsafeMutableBytes { bytes -> Int in
                guard let base = bytes.baseAddress else { return -1 }
                return Darwin.recv(fd, base.advanced(by: received),
                                   response.count - received, 0)
            }
            guard amount > 0
            else { return rejected("recv PONG", amount == 0 ? 0 : errno) }
            received += amount
        }
        guard response == Array("WRPONG1\\n".utf8)
        else { return rejected("resposta diferente de PONG") }
        return .diagnosticReady
    }

    /// Host-only injection for the loopback PING integration test.
    static func hostLoopbackProbe() -> Result {
        return pingLoopback()
    }

    /// Test-only injection for native macOS harnesses; never a production UI path.
    static func hostProbe(directory: URL) -> Result {
        return exchange(request: inspectHeader, expectingInstall: false,
                        directory: directory)
    }

    /// Only for deterministic macOS CI against a fake appinst binary.
    static func hostInstall(
        directory: URL, ipaURL: URL, sha256: String
    ) -> Result {
        return performInstall(ipaURL: ipaURL, sha: sha256, directory: directory)
    }
}
