import Foundation
import Darwin
import CommonCrypto

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
    private static let inspectHeader = Data("WRPING1\n".utf8)
#if WEBREADER_HOST_TEST
    // NEVER compiled into the iOS production client.
    private static let installHeader = Data("WRINST1\n".utf8)
    private static let confirmation = Data("I-CONFIRM-INSTALL".utf8)
#endif

    enum Result: Equatable {
        case unavailable
        case rejected
        case completed
        case failed
        case diagnosticReady
        case diagnosticFailure(String)
        case pairingAccepted
        case pairingDenied

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
            case .pairingAccepted:
                return "Código temporário validado nos dois sentidos; " +
                    "NENHUMA IPA instalada e identidade do app NÃO autenticada"
            case .pairingDenied:
                return "Código temporário incorreto ou sessão consumida; " +
                    "nenhuma instalação executada"
            }
        }
    }

    static func checkConnection(completion: @escaping (Result) -> Void) {
        DispatchQueue.global(qos: .utility).async {
            let result = exchange(request: inspectHeader, expectingInstall: false)
            DispatchQueue.main.async { completion(result) }
        }
    }

    // Build62 security gate: a localhost PONG, GitHub account digest or
    // HMAC pairing code DOES NOT authenticate the requesting iOS app.
    // Until a separately reviewed installer-side publisher and peer policy
    // exists, a running application must NEVER transmit WRINST1 or a path
    // to an installation-capable helper. Keep the explicit FAKE-appinst
    // host harness below for protocol regression tests only.
    static let liveInstallationEnabled = false

    static func install(
        ipaURL: URL, expectedSHA256: String,
        completion: @escaping (Result) -> Void
    ) {
        // Security invariant independent of UI button visibility.
        // This call performs no network I/O and never creates install IPC.
        _ = ipaURL
        _ = expectedSHA256
        DispatchQueue.main.async { completion(.rejected) }
    }

#if WEBREADER_HOST_TEST
    // Synthetic macOS FAKE-appinst regression harness only.
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
#endif

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

        let request = Array("WRPING1\n".utf8)
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
            let remaining = response.count - received
            let amount = response.withUnsafeMutableBytes { bytes -> Int in
                guard let base = bytes.baseAddress else { return -1 }
                return Darwin.recv(fd, base.advanced(by: received),
                                   remaining, 0)
            }
            guard amount > 0
            else { return rejected("recv PONG", amount == 0 ? 0 : errno) }
            received += amount
        }
        guard response == Array("WRPONG1\n".utf8)
        else { return rejected("resposta diferente de PONG") }
        return .diagnosticReady
    }

    /// Manual one-use proof-of-possession laboratory on 127.0.0.1:38972.
    /// This MUST remain independent of installation and not be interpreted as
    /// code-signature authentication. The code is never stored or sent raw.
    static func checkPairedLoopback(
        code: String, completion: @escaping (Result) -> Void
    ) {
        DispatchQueue.global(qos: .utility).async {
            let result = pairLoopback(code: code)
            DispatchQueue.main.async { completion(result) }
        }
    }

    private static func pairLoopback(code supplied: String) -> Result {
        func failure(_ stage: String, _ number: Int32 = 0) -> Result {
            return .diagnosticFailure("Pareamento " + stage +
                " (errno=" + String(number) + ")")
        }
        let code = supplied.trimmingCharacters(in: .whitespacesAndNewlines)
            .uppercased()
        let key = Array(code.utf8)
        guard key.count == 16,
              key.allSatisfy({ ($0 >= 48 && $0 <= 57) ||
                               ($0 >= 65 && $0 <= 70) })
        else { return failure("código deve ter 16 caracteres hexadecimais") }

        // HMAC-SHA256 over a fresh server nonce. Distinct domain labels
        // prevent replaying the client proof as a server proof.
        func mac(_ domain: String, nonce: [UInt8]) -> [UInt8] {
            let message = Array(domain.utf8) + nonce
            var output = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
            key.withUnsafeBytes { keyBytes in
                message.withUnsafeBytes { messageBytes in
                    output.withUnsafeMutableBytes { outputBytes in
                        CCHmac(CCHmacAlgorithm(kCCHmacAlgSHA256),
                               keyBytes.baseAddress, keyBytes.count,
                               messageBytes.baseAddress, messageBytes.count,
                               outputBytes.baseAddress)
                    }
                }
            }
            return output
        }

        let fd = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { return failure("socket", errno) }
        defer { _ = Darwin.close(fd) }
        var noSigPipe: Int32 = 1
        guard setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &noSigPipe,
                         socklen_t(MemoryLayout<Int32>.size)) == 0
        else { return failure("NOSIGPIPE", errno) }
        var timeout = timeval(tv_sec: 3, tv_usec: 0)
        guard setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout,
                         socklen_t(MemoryLayout<timeval>.size)) == 0
        else { return failure("RCVTIMEO", errno) }
        guard setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout,
                         socklen_t(MemoryLayout<timeval>.size)) == 0
        else { return failure("SNDTIMEO", errno) }

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = UInt16(38972).bigEndian
        address.sin_addr = in_addr(s_addr: UInt32(0x7f000001).bigEndian)
        let connected = withUnsafePointer(to: &address) { pointer -> Int32 in
            return pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(fd, $0,
                    socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard connected == 0 else { return failure("connect", errno) }

        func writeAll(_ bytes: [UInt8]) -> Bool {
            var written = 0
            return bytes.withUnsafeBytes { buffer in
                guard let base = buffer.baseAddress else { return false }
                while written < bytes.count {
                    let count = Darwin.send(fd, base.advanced(by: written),
                                            bytes.count - written, 0)
                    if count <= 0 { return false }
                    written += count
                }
                return true
            }
        }
        func readExact(_ length: Int) -> [UInt8]? {
            var bytes = [UInt8](repeating: 0, count: length)
            var received = 0
            while received < length {
                let remaining = length - received
                let count = bytes.withUnsafeMutableBytes { buffer -> Int in
                    guard let base = buffer.baseAddress else { return -1 }
                    return Darwin.recv(fd, base.advanced(by: received),
                                       remaining, 0)
                }
                if count <= 0 { return nil }
                received += count
            }
            return bytes
        }
        guard writeAll(Array("WRPAIR1\n".utf8)) else {
            return failure("enviar início", errno)
        }
        guard let challenge = readExact(24),
              Array(challenge.prefix(8)) == Array("WRCHAL1\n".utf8)
        else { return failure("desafio inválido") }
        let nonce = Array(challenge.suffix(16))
        let proof = Array("WRAUTH1\n".utf8) + mac("WR-PAIR-CLIENT-V1", nonce: nonce)
        guard writeAll(proof) else { return failure("enviar prova", errno) }
        guard let header = readExact(8) else {
            return failure("resposta ausente", errno)
        }
        if header == Array("WRDENY1\n".utf8) { return .pairingDenied }
        guard header == Array("WROKAY1\n".utf8),
              let serverProof = readExact(32) else {
            return failure("resposta inesperada")
        }
        let expected = mac("WR-PAIR-SERVER-V1", nonce: nonce)
        var difference: UInt8 = 0
        for i in 0..<32 { difference |= serverProof[i] ^ expected[i] }
        guard difference == 0 else { return failure("prova do servidor inválida") }
        return .pairingAccepted
    }

    /// Mac CI harness only; no UI installation paths call this.
    static func hostPairProbe(code: String) -> Result {
        return pairLoopback(code: code)
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

#if WEBREADER_HOST_TEST
    /// Only for deterministic macOS CI against a FAKE appinst binary.
    static func hostInstall(
        directory: URL, ipaURL: URL, sha256: String
    ) -> Result {
        return performInstall(ipaURL: ipaURL, sha: sha256, directory: directory)
    }
#endif
}
