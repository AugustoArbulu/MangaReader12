import Foundation
import Darwin

/// Self-contained read-only Chimera experiment for a separately installed IPA.
/// The embedded executable supports only PING/PONG and cannot call appinst.
/// A successful result does NOT prove access to the jailbreak installer.
enum WebReaderChimeraSelfTest {
    struct Report {
        let status: String
        let detail: String
        let passed: Bool

        var text: String {
            return [
                "WebReader Chimera Test • iOS 12",
                "Resultado: " + status,
                detail,
                "appinst: " + appinstPresence,
                "Nenhuma IPA instalada; nenhum appinst executado"
            ].joined(separator: "\n")
        }
    }

    private static var appinstPresence: String {
        let path = "/usr/bin/appinst"
        return FileManager.default.isExecutableFile(atPath: path)
            ? "arquivo executável encontrado (não iniciado)"
            : "não detectado pelo sandbox (não iniciado)"
    }

    static func run(completion: @escaping (Report) -> Void) {
        DispatchQueue.global(qos: .utility).async {
            let result = perform()
            DispatchQueue.main.async {
                completion(result)
            }
        }
    }

    private static func perform() -> Report {
        guard Bundle.main.bundleIdentifier ==
            "com.example.MangaReader12.chimeraoneapp"
        else {
            return Report(status: "Bloqueado",
                          detail: "Este teste só funciona na IPA separada.",
                          passed: false)
        }

        let helper = Bundle.main.bundleURL
            .appendingPathComponent("WebReaderEmbeddedPing", isDirectory: false)
        guard FileManager.default.isExecutableFile(atPath: helper.path) else {
            return Report(status: "Helper ausente",
                          detail: "Executável de teste não encontrado na IPA.",
                          passed: false)
        }

        let directory = WebReaderHelperPingProbe.diagnosticDirectory
        do {
            try FileManager.default.createDirectory(
                at: directory, withIntermediateDirectories: true,
                attributes: [.posixPermissions: 0o700]
            )
        } catch {
            return Report(status: "Pasta indisponível",
                          detail: "O app não conseguiu criar a pasta local WR.",
                          passed: false)
        }

        // No shell, no installation command, no root privileges.
        // The signed helper is embedded inside THIS diagnostic bundle.
        let rawArgs = [
            "WebReaderEmbeddedPing", "serve", directory.path
        ]
        var arguments: [UnsafeMutablePointer<CChar>?] =
            rawArgs.map { strdup($0) }
        arguments.append(nil)
        defer {
            for argument in arguments {
                if let value = argument { free(value) }
            }
        }
        var environment: [UnsafeMutablePointer<CChar>?] = [nil]
        var processID: pid_t = 0
        let spawnError: Int32 = helper.path.withCString { executable in
            return arguments.withUnsafeMutableBufferPointer { argv in
                return environment.withUnsafeMutableBufferPointer { envp in
                    return posix_spawn(
                        &processID, executable, nil, nil,
                        argv.baseAddress, envp.baseAddress
                    )
                }
            }
        }
        guard spawnError == 0, processID > 0 else {
            return Report(
                status: "Execução bloqueada",
                detail: "O iOS/Chimera não iniciou o helper. Código: " +
                    String(spawnError),
                passed: false
            )
        }

        // The child exits after a single PING/PONG. Bound the test to ~5s.
        var exited = false
        var successfulPing = false
        for _ in 0..<25 {
            if case .responded = WebReaderHelperPingProbe.inspect() {
                successfulPing = true
                break
            }
            var status: Int32 = 0
            let finished = waitpid(processID, &status, WNOHANG)
            if finished == processID || finished < 0 {
                exited = true
                break
            }
            usleep(160_000)
        }

        if !exited {
            if !successfulPing {
                _ = kill(processID, SIGTERM)
            }
            var status: Int32 = 0
            _ = waitpid(processID, &status, 0)
        }

        if successfulPing {
            return Report(
                status: "PING/PONG aprovado",
                detail: "O app iniciou um processo local e recebeu a resposta. " +
                    "Isso ainda não significa que appinst pode instalar IPAs.",
                passed: true
            )
        }
        return Report(
            status: "Helper não respondeu",
            detail: "O processo não abriu o socket ou encerrou antes do teste. " +
                "Verificar permissões e sandbox do Chimera.",
            passed: false
        )
    }
}
