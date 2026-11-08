import Foundation
import Security
import CoreFoundation

// Native iOS12 signed-update verifier. Intentionally unused by the running
// WebReader UI until an authenticated release key and URL are configured.
// Never downloads, extracts, executes, or installs an IPA.
enum WebReaderUpdateValidationError: Error {
    case oversizedEnvelope
    case invalidEnvelope
    case invalidPublicKey
    case signatureRejected
    case invalidPayload
    case wrongApplication
    case notNewer
    case incompatibleIOS
    case disallowedURL
}

enum WebReaderUpdateProvenance: Equatable {
    case signedManifest
    case publicGitHubRelease
    // User-selected local IPA from Files/Filza. No release/editor authentication.
    case manualLocalFile
}

struct WebReaderVerifiedUpdate {
    let build: Int
    let minimumIOS: String
    let ipaURL: URL
    let ipaSize: Int64
    let sha256: String
    let publishedAt: String
    let releaseNotes: [String]
    // This marker describes *where* the app obtained the metadata.
    // It is not proof for a future privileged installer.
    var provenance: WebReaderUpdateProvenance = .signedManifest
}

enum WebReaderUpdateManifestVerifier {
    private static let maxEnvelopeBytes = 64 * 1024
    private static let maxPayloadBytes = 32 * 1024
    private static let maxIPABytes: Int64 = 512 * 1024 * 1024
    private static let bundleID = "com.example.MangaReader12"
    // Mirrors the entitlement recorded on the already installed Build65.
    // Matching it is NOT proof of signed publisher identity.
    private static let installedApplicationIdentifier =
        "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"

    static func verify(
        envelopeData: Data,
        publicKeyX963: Data,
        installedBuild: Int,
        installedIOS: OperatingSystemVersion
    ) throws -> WebReaderVerifiedUpdate {
        guard !envelopeData.isEmpty, envelopeData.count <= maxEnvelopeBytes else {
            throw WebReaderUpdateValidationError.oversizedEnvelope
        }
        // Foundation's JSONSerialization does not reject duplicate keys.
        // Check raw bytes first, including Unicode-escaped equivalent keys.
        guard WebReaderStrictJSON.accepts(envelopeData) else {
            throw WebReaderUpdateValidationError.invalidEnvelope
        }
        guard let envelope = try? JSONSerialization.jsonObject(
                with: envelopeData, options: []
            ) as? [String: Any],
            Set(envelope.keys) == Set([
                "schemaVersion", "algorithm", "payload", "signature"
            ]),
            let envelopeVersion = exactInteger(envelope["schemaVersion"]),
            envelopeVersion == 1 || envelopeVersion == 2,
            envelope["algorithm"] as? String == "ecdsa-p256-sha256",
            let payloadText = envelope["payload"] as? String,
            let signatureText = envelope["signature"] as? String,
            payloadText.count <= 44_000,
            signatureText.count <= 176,
            let payload = strictBase64(payloadText),
            let signature = strictBase64(signatureText),
            !payload.isEmpty, payload.count <= maxPayloadBytes,
            signature.count >= 64, signature.count <= 80
        else {
            throw WebReaderUpdateValidationError.invalidEnvelope
        }
        guard publicKeyX963.count == 65, publicKeyX963.first == 0x04 else {
            throw WebReaderUpdateValidationError.invalidPublicKey
        }
        let attrs: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrKeyClass as String: kSecAttrKeyClassPublic,
            kSecAttrKeySizeInBits as String: 256,
            kSecAttrIsPermanent as String: false
        ]
        var keyError: Unmanaged<CFError>?
        guard let key = SecKeyCreateWithData(
            publicKeyX963 as CFData, attrs as CFDictionary, &keyError
        ), SecKeyIsAlgorithmSupported(
            key, .verify, .ecdsaSignatureMessageX962SHA256
        ) else {
            throw WebReaderUpdateValidationError.invalidPublicKey
        }
        var verifyError: Unmanaged<CFError>?
        guard SecKeyVerifySignature(
            key, .ecdsaSignatureMessageX962SHA256,
            payload as CFData, signature as CFData, &verifyError
        ) else {
            throw WebReaderUpdateValidationError.signatureRejected
        }
        // The exact signed bytes must have unique decoded keys throughout.
        // Otherwise Foundation could silently choose a conflicting duplicate.
        guard WebReaderStrictJSON.accepts(payload) else {
            throw WebReaderUpdateValidationError.invalidPayload
        }
        // Never use unsigned fields from the wrapper for install policy.
        guard let manifest = try? JSONSerialization.jsonObject(
            with: payload, options: []
        ) as? [String: Any],
            let manifestVersion = exactInteger(manifest["schemaVersion"]),
            manifestVersion == envelopeVersion
        else {
            throw WebReaderUpdateValidationError.invalidPayload
        }
        var expectedKeys: Set<String> = [
            "schemaVersion", "application", "bundleId", "channel", "build",
            "minimumIOS", "ipaUrl", "ipaSize", "sha256", "releaseNotes",
            "publishedAt"
        ]
        if manifestVersion == 2 { expectedKeys.insert("applicationIdentifier") }
        guard Set(manifest.keys) == expectedKeys else {
            throw WebReaderUpdateValidationError.invalidPayload
        }
        guard manifest["application"] as? String == "WebReader",
            manifest["bundleId"] as? String == bundleID,
            manifest["channel"] as? String == "development",
            (manifestVersion == 1 ||
             manifest["applicationIdentifier"] as? String ==
                installedApplicationIdentifier)
        else {
            throw WebReaderUpdateValidationError.wrongApplication
        }
        guard let build = exactInteger(manifest["build"]),
            build > installedBuild, build <= 2_147_483_647
        else {
            throw WebReaderUpdateValidationError.notNewer
        }
        guard let minVersion = manifest["minimumIOS"] as? String,
            let minParts = versionComponents(minVersion),
            (minParts == versionComponents(installedIOS) ||
             minParts.lexicographicallyPrecedes(versionComponents(installedIOS)))
        else {
            throw WebReaderUpdateValidationError.incompatibleIOS
        }
        guard let size = exactInteger(manifest["ipaSize"]),
            size > 0, Int64(size) <= maxIPABytes,
            let sha = manifest["sha256"] as? String,
            validPattern(sha, pattern: "^[0-9a-f]{64}$"),
            let date = manifest["publishedAt"] as? String,
            validPattern(
                date,
                pattern: "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
            ),
            let notes = manifest["releaseNotes"] as? [String],
            notes.count <= 20, notes.allSatisfy({ !$0.isEmpty && $0.count <= 240 })
        else {
            throw WebReaderUpdateValidationError.invalidPayload
        }
        let assetName = manifestVersion == 1 ?
            "WebReader-iOS12-unsigned.ipa" :
            "WebReader-Build" + String(build) + "-iOS12-adhoc.ipa"
        guard let uri = manifest["ipaUrl"] as? String, uri.count <= 512,
            let components = URLComponents(string: uri),
            components.scheme == "https", components.host == "github.com",
            components.user == nil, components.password == nil,
            components.port == nil, components.query == nil,
            components.fragment == nil,
            components.percentEncodedPath ==
            "/AugustoArbulu/MangaReader12/releases/download/build" +
                String(build) + "/" + assetName,
            let url = components.url
        else {
            throw WebReaderUpdateValidationError.disallowedURL
        }
        return WebReaderVerifiedUpdate(
            build: build, minimumIOS: minVersion,
            ipaURL: url, ipaSize: Int64(size), sha256: sha,
            publishedAt: date, releaseNotes: notes
        )
    }

    private static func strictBase64(_ value: String) -> Data? {
        guard !value.isEmpty, value.count % 4 == 0,
            validPattern(value, pattern: "^[A-Za-z0-9+/]+={0,2}$")
        else { return nil }
        return Data(base64Encoded: value, options: [])
    }

    private static func exactInteger(_ object: Any?) -> Int? {
        guard let number = object as? NSNumber,
            CFGetTypeID(number) != CFBooleanGetTypeID()
        else { return nil }
        let value = number.stringValue
        guard validPattern(value, pattern: "^(0|[1-9][0-9]{0,11})$"),
            let parsed = Int(value)
        else { return nil }
        return parsed
    }

    private static func validPattern(_ text: String, pattern: String) -> Bool {
        return text.range(of: pattern, options: .regularExpression) != nil
    }

    private static func versionComponents(_ text: String) -> [Int]? {
        let components = text.split(separator: ".", omittingEmptySubsequences: false)
        guard components.count == 2 || components.count == 3 else { return nil }
        var parts: [Int] = []
        for component in components {
            guard !component.isEmpty, component.count <= 2,
                component.allSatisfy({ $0 >= "0" && $0 <= "9" }),
                let value = Int(component)
            else { return nil }
            parts.append(value)
        }
        if parts.count == 2 { parts.append(0) }
        return parts
    }

    private static func versionComponents(_ value: OperatingSystemVersion) -> [Int] {
        return [value.majorVersion, value.minorVersion, value.patchVersion]
    }
}
