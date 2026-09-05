import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

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

// MARK: - Source API v1 contract

enum SourceContractFunction: String, CaseIterable {
    case metadata
    case popular
    case search
    case details
    case chapters
    case pages

    static var requiredNames: [String] {
        return allCases.map { $0.rawValue }
    }
}

struct SourceMetadata: Codable, Equatable {
    let id: String
    let name: String
    let lang: String
    let version: String
}

struct SourceMangaSummary: Codable, Equatable {
    let id: String
    let title: String
    let cover: String?
    let url: String?
}

struct SourcePagedMangaResult: Codable, Equatable {
    let items: [SourceMangaSummary]
    let hasNextPage: Bool
}

// MARK: - Repository catalog v1

struct RepositoryCatalog: Codable, Equatable {
    let name: String
    let apiVersion: Int
    let sources: [SourceManifest]

    func validate() throws {
        guard !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw RepositoryCatalogError.missingName
        }

        guard apiVersion == 1 else {
            throw RepositoryCatalogError.unsupportedAPIVersion(apiVersion)
        }

        guard !sources.isEmpty else {
            throw RepositoryCatalogError.emptySources
        }

        var sourceIDs = Set<String>()

        for source in sources {
            try source.validate()

            guard sourceIDs.insert(source.id).inserted else {
                throw RepositoryCatalogError.duplicateSourceID(source.id)
            }
        }
    }
}

enum RepositoryCatalogError: Error, LocalizedError {
    case missingName
    case unsupportedAPIVersion(Int)
    case emptySources
    case duplicateSourceID(String)
    case invalidAppVersion(String)

    var errorDescription: String? {
        switch self {
        case .missingName:
            return "Repository name is empty."
        case .unsupportedAPIVersion(let version):
            return "Unsupported repository API version: \(version)."
        case .emptySources:
            return "Repository catalog contains no sources."
        case .duplicateSourceID(let sourceID):
            return "Repository catalog contains duplicate source ID: \(sourceID)."
        case .invalidAppVersion(let version):
            return "App version format is invalid: \(version)."
        }
    }
}

enum RepositorySourceAction: String, Codable, Equatable {
    case install
    case update
    case unchanged
    case incompatible
}

struct RepositorySourcePlan: Equatable {
    let sourceID: String
    let currentVersion: String?
    let availableVersion: String
    let action: RepositorySourceAction
}

enum NumericVersionComparator {
    static func compare(_ lhs: String, _ rhs: String) -> ComparisonResult? {
        guard let left = components(lhs), let right = components(rhs) else {
            return nil
        }

        let count = max(left.count, right.count)

        for index in 0..<count {
            let leftValue = index < left.count ? left[index] : 0
            let rightValue = index < right.count ? right[index] : 0

            if leftValue < rightValue {
                return .orderedAscending
            }

            if leftValue > rightValue {
                return .orderedDescending
            }
        }

        return .orderedSame
    }

    private static func components(_ value: String) -> [Int]? {
        let parts = value.split(separator: ".", omittingEmptySubsequences: false)
        guard !parts.isEmpty, parts.count <= 4 else {
            return nil
        }

        var values: [Int] = []

        for part in parts {
            guard !part.isEmpty,
                  part.allSatisfy({ $0 >= "0" && $0 <= "9" }),
                  let number = Int(part) else {
                return nil
            }

            values.append(number)
        }

        return values
    }
}

enum RepositoryCatalogPlanner {
    static func plan(
        catalog: RepositoryCatalog,
        installed: [String: SourceManifest],
        appVersion: String
    ) throws -> [RepositorySourcePlan] {
        try catalog.validate()

        guard NumericVersionComparator.compare(appVersion, appVersion) != nil else {
            throw RepositoryCatalogError.invalidAppVersion(appVersion)
        }

        return catalog.sources.map { source in
            let current = installed[source.id]

            let compatibility = NumericVersionComparator.compare(
                appVersion,
                source.minAppVersion
            )

            let action: RepositorySourceAction

            if compatibility == .orderedAscending {
                action = .incompatible
            } else if let current = current {
                let versionComparison = NumericVersionComparator.compare(
                    source.version,
                    current.version
                )

                action = versionComparison == .orderedDescending
                    ? .update
                    : .unchanged
            } else {
                action = .install
            }

            return RepositorySourcePlan(
                sourceID: source.id,
                currentVersion: current?.version,
                availableVersion: source.version,
                action: action
            )
        }
    }
}

// MARK: - Repository transport + source integrity

enum RepositoryTransportError: Error, LocalizedError {
    case invalidRepositoryURL
    case invalidScriptURL
    case httpStatus(Int)
    case catalogDecodeFailed(String)
    case integrityMismatch(expected: String, actual: String)

    var errorDescription: String? {
        switch self {
        case .invalidRepositoryURL:
            return "Repository URL must be a valid HTTPS URL."
        case .invalidScriptURL:
            return "Source script URL must be a valid HTTPS URL."
        case .httpStatus(let status):
            return "Repository request returned HTTP \(status)."
        case .catalogDecodeFailed(let message):
            return "Could not decode repository catalog: \(message)"
        case .integrityMismatch(let expected, let actual):
            return "Source script SHA-256 mismatch. Expected \(expected), got \(actual)."
        }
    }
}

enum RepositoryTransportPolicy {
    static func httpPolicy(
        for rawURL: String,
        maxResponseBytes: Int
    ) throws -> HTTPPolicy {
        guard let url = URL(string: rawURL),
              url.scheme?.lowercased() == "https",
              let host = url.host?.lowercased(),
              !host.isEmpty else {
            throw RepositoryTransportError.invalidRepositoryURL
        }

        return HTTPPolicy(
            allowedDomains: [host],
            timeout: 20,
            maxRedirects: 5,
            maxResponseBytes: maxResponseBytes
        )
    }

    static func scriptPolicy(
        for manifest: SourceManifest,
        maxResponseBytes: Int = 4 * 1024 * 1024
    ) throws -> HTTPPolicy {
        try manifest.validate()

        guard let url = URL(string: manifest.script),
              url.scheme?.lowercased() == "https",
              let host = url.host?.lowercased(),
              !host.isEmpty else {
            throw RepositoryTransportError.invalidScriptURL
        }

        return HTTPPolicy(
            allowedDomains: [host],
            timeout: 20,
            maxRedirects: 5,
            maxResponseBytes: maxResponseBytes
        )
    }
}

enum SourceScriptIntegrityStatus: Equatable {
    case notProvided
    case verified
}

enum SourceScriptIntegrity {
    static func verify(
        data: Data,
        manifest: SourceManifest
    ) throws -> SourceScriptIntegrityStatus {
        guard let expected = manifest.sha256, !expected.isEmpty else {
            return .notProvided
        }

        let actual = SHA256Digest.hex(data)

        guard actual.caseInsensitiveCompare(expected) == .orderedSame else {
            throw RepositoryTransportError.integrityMismatch(
                expected: expected.lowercased(),
                actual: actual
            )
        }

        return .verified
    }
}

struct RepositoryScriptPayload {
    let data: Data
    let integrity: SourceScriptIntegrityStatus
}

final class RepositoryRemoteClient {
    let repositoryURL: String

    private let catalogClient: HTTPClient
    private let lock = NSLock()
    private var activeScriptClients: [UUID: HTTPClient] = [:]

    init(repositoryURL: String) throws {
        self.repositoryURL = repositoryURL
        self.catalogClient = HTTPClient(
            policy: try RepositoryTransportPolicy.httpPolicy(
                for: repositoryURL,
                maxResponseBytes: 2 * 1024 * 1024
            )
        )
    }

    @discardableResult
    func fetchCatalog(
        completion: @escaping (Result<RepositoryCatalog, Error>) -> Void
    ) -> URLSessionDataTask? {
        return catalogClient.send(
            HTTPRequest(
                method: "GET",
                url: repositoryURL,
                headers: ["Accept": "application/json"]
            )
        ) { result in
            switch result {
            case .success(let response):
                guard (200...299).contains(response.statusCode) else {
                    completion(.failure(
                        RepositoryTransportError.httpStatus(response.statusCode)
                    ))
                    return
                }

                do {
                    completion(.success(
                        try Self.decodeCatalog(response.data)
                    ))
                } catch {
                    completion(.failure(error))
                }

            case .failure(let error):
                completion(.failure(error))
            }
        }
    }

    @discardableResult
    func fetchScript(
        for manifest: SourceManifest,
        completion: @escaping (Result<RepositoryScriptPayload, Error>) -> Void
    ) -> URLSessionDataTask? {
        let client: HTTPClient

        do {
            client = HTTPClient(
                policy: try RepositoryTransportPolicy.scriptPolicy(for: manifest)
            )
        } catch {
            completion(.failure(error))
            return nil
        }

        let token = UUID()

        lock.lock()
        activeScriptClients[token] = client
        lock.unlock()

        return client.send(
            HTTPRequest(
                method: "GET",
                url: manifest.script,
                headers: ["Accept": "application/javascript, text/javascript, text/plain;q=0.9, */*;q=0.1"]
            )
        ) { [weak self] result in
            defer {
                self?.lock.lock()
                self?.activeScriptClients.removeValue(forKey: token)
                self?.lock.unlock()
            }

            switch result {
            case .success(let response):
                guard (200...299).contains(response.statusCode) else {
                    completion(.failure(
                        RepositoryTransportError.httpStatus(response.statusCode)
                    ))
                    return
                }

                do {
                    let integrity = try SourceScriptIntegrity.verify(
                        data: response.data,
                        manifest: manifest
                    )

                    completion(.success(
                        RepositoryScriptPayload(
                            data: response.data,
                            integrity: integrity
                        )
                    ))
                } catch {
                    completion(.failure(error))
                }

            case .failure(let error):
                completion(.failure(error))
            }
        }
    }

    static func decodeCatalog(_ data: Data) throws -> RepositoryCatalog {
        do {
            let catalog = try JSONDecoder().decode(
                RepositoryCatalog.self,
                from: data
            )
            try catalog.validate()
            return catalog
        } catch let error as RepositoryCatalogError {
            throw error
        } catch let error as ManifestValidationError {
            throw error
        } catch {
            throw RepositoryTransportError.catalogDecodeFailed(
                error.localizedDescription
            )
        }
    }
}

// Pure Swift SHA-256 keeps iOS 12 compatibility without CryptoKit.
enum SHA256Digest {
    private static let constants: [UInt32] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
        0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
        0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
        0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
        0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
        0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
        0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    ]

    static func hex(_ data: Data) -> String {
        var message = [UInt8](data)
        let bitLength = UInt64(message.count) * 8

        message.append(0x80)
        while message.count % 64 != 56 {
            message.append(0)
        }

        for shift in stride(from: 56, through: 0, by: -8) {
            message.append(UInt8((bitLength >> UInt64(shift)) & 0xff))
        }

        var hash: [UInt32] = [
            0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
            0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
        ]

        for offset in stride(from: 0, to: message.count, by: 64) {
            var words = [UInt32](repeating: 0, count: 64)

            for index in 0..<16 {
                let base = offset + index * 4
                words[index] =
                    (UInt32(message[base]) << 24) |
                    (UInt32(message[base + 1]) << 16) |
                    (UInt32(message[base + 2]) << 8) |
                    UInt32(message[base + 3])
            }

            for index in 16..<64 {
                let s0 =
                    rotateRight(words[index - 15], by: 7) ^
                    rotateRight(words[index - 15], by: 18) ^
                    (words[index - 15] >> 3)

                let s1 =
                    rotateRight(words[index - 2], by: 17) ^
                    rotateRight(words[index - 2], by: 19) ^
                    (words[index - 2] >> 10)

                words[index] = words[index - 16]
                    &+ s0
                    &+ words[index - 7]
                    &+ s1
            }

            var a = hash[0]
            var b = hash[1]
            var c = hash[2]
            var d = hash[3]
            var e = hash[4]
            var f = hash[5]
            var g = hash[6]
            var h = hash[7]

            for index in 0..<64 {
                let sum1 =
                    rotateRight(e, by: 6) ^
                    rotateRight(e, by: 11) ^
                    rotateRight(e, by: 25)

                let choice = (e & f) ^ ((~e) & g)
                let temp1 = h
                    &+ sum1
                    &+ choice
                    &+ constants[index]
                    &+ words[index]

                let sum0 =
                    rotateRight(a, by: 2) ^
                    rotateRight(a, by: 13) ^
                    rotateRight(a, by: 22)

                let majority = (a & b) ^ (a & c) ^ (b & c)
                let temp2 = sum0 &+ majority

                h = g
                g = f
                f = e
                e = d &+ temp1
                d = c
                c = b
                b = a
                a = temp1 &+ temp2
            }

            hash[0] = hash[0] &+ a
            hash[1] = hash[1] &+ b
            hash[2] = hash[2] &+ c
            hash[3] = hash[3] &+ d
            hash[4] = hash[4] &+ e
            hash[5] = hash[5] &+ f
            hash[6] = hash[6] &+ g
            hash[7] = hash[7] &+ h
        }

        return hash.map { String(format: "%08x", $0) }.joined()
    }

    private static func rotateRight(_ value: UInt32, by amount: UInt32) -> UInt32 {
        return (value >> amount) | (value << (32 - amount))
    }
}
