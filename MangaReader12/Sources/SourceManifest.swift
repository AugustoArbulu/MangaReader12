import Foundation

struct SourceManifest: Codable, Equatable {
    let id: String
    let name: String
    let version: String
    let lang: String
    let author: String
    let script: String
    let icon: String?
    let apiVersion: Int
    let minAppVersion: String
    let domains: [String]
    let nsfw: Bool
    let sha256: String?

    func validate() throws {
        guard id.range(of: "^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$", options: .regularExpression) != nil else {
            throw ManifestValidationError.invalidID
        }

        guard !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw ManifestValidationError.missingName
        }

        guard apiVersion == 1 else {
            throw ManifestValidationError.unsupportedAPIVersion(apiVersion)
        }

        guard Self.isNumericVersion(version), Self.isNumericVersion(minAppVersion) else {
            throw ManifestValidationError.invalidVersion
        }

        guard let scriptURL = URL(string: script), scriptURL.scheme?.lowercased() == "https" else {
            throw ManifestValidationError.invalidScriptURL
        }

        guard !domains.isEmpty else {
            throw ManifestValidationError.emptyDomains
        }

        for domain in domains {
            let normalized = domain.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
            guard !normalized.isEmpty,
                  normalized.range(of: "^[a-z0-9.-]+$", options: .regularExpression) != nil,
                  !normalized.hasPrefix("."),
                  !normalized.hasSuffix(".") else {
                throw ManifestValidationError.invalidDomain(domain)
            }
        }

        if let hash = sha256, !hash.isEmpty {
            guard hash.range(of: "^[A-Fa-f0-9]{64}$", options: .regularExpression) != nil else {
                throw ManifestValidationError.invalidSHA256
            }
        }
    }

    private static func isNumericVersion(_ value: String) -> Bool {
        let parts = value.split(separator: ".", omittingEmptySubsequences: false)
        guard !parts.isEmpty, parts.count <= 4 else { return false }
        return parts.allSatisfy { part in
            !part.isEmpty && part.allSatisfy { $0 >= "0" && $0 <= "9" }
        }
    }
}

enum ManifestValidationError: Error, LocalizedError {
    case invalidID
    case missingName
    case unsupportedAPIVersion(Int)
    case invalidVersion
    case invalidScriptURL
    case emptyDomains
    case invalidDomain(String)
    case invalidSHA256

    var errorDescription: String? {
        switch self {
        case .invalidID:
            return "Source ID is invalid."
        case .missingName:
            return "Source name is empty."
        case .unsupportedAPIVersion(let version):
            return "Unsupported source API version: \(version)."
        case .invalidVersion:
            return "Source version format is invalid."
        case .invalidScriptURL:
            return "Source script URL must be HTTPS."
        case .emptyDomains:
            return "Source manifest has no allowed domains."
        case .invalidDomain(let domain):
            return "Invalid source domain: \(domain)."
        case .invalidSHA256:
            return "Source SHA-256 must contain 64 hexadecimal characters."
        }
    }
}
