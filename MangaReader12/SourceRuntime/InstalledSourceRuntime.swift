import Foundation

final class InstalledSourceRuntimeLoader {
    private let installer: SourceScriptInstaller

    init(installer: SourceScriptInstaller) {
        self.installer = installer
    }

    static func defaultLoader() throws -> InstalledSourceRuntimeLoader {
        return InstalledSourceRuntimeLoader(
            installer: try SourceScriptInstaller.defaultInstaller()
        )
    }

    func load(
        sourceID: String,
        completion: @escaping (Result<JavaScriptSourceRuntime, Error>) -> Void
    ) {
        let installed: InstalledSourceScript

        do {
            installed = try installer.active(sourceID: sourceID)
        } catch {
            completion(.failure(error))
            return
        }

        guard let script = String(data: installed.scriptData, encoding: .utf8) else {
            completion(.failure(InstalledSourceRuntimeError.scriptNotUTF8))
            return
        }

        let runtime = JavaScriptSourceRuntime(manifest: installed.manifest)
        runtime.load(script: script) { result in
            switch result {
            case .success:
                runtime.validateContract { validation in
                    switch validation {
                    case .success:
                        completion(.success(runtime))
                    case .failure(let error):
                        completion(.failure(error))
                    }
                }

            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
}

enum InstalledSourceRuntimeError: Error, LocalizedError {
    case scriptNotUTF8

    var errorDescription: String? {
        switch self {
        case .scriptNotUTF8:
            return "Installed source script is not valid UTF-8."
        }
    }
}
