import Foundation
import CommonCrypto
import CoreFoundation

/// Build68 / Phase S — strictly read-only bridge between an independently
/// provisioned public-key fingerprint and the existing iOS12 ECDSA verifier.
///
/// This does NOT establish who controls an arbitrary public key. The expected
/// fingerprint must come from a genuinely independent, owner-trusted channel.
/// Production has no trusted pin/key configured; this is NOT wired to the UI.
/// Successful verification can never authorize installation or IPC requests.
enum WebReaderSignedReleaseTrustError: Error {
    case missingIndependentTrustAnchor
    case invalidPublicKey
    case trustAnchorMismatch
    case unsupportedEnvelopeVersion
}

struct WebReaderSignedReleasePreview {
    let update: WebReaderVerifiedUpdate
    let observedSPKISHA256: String
    let signatureVerifiedAgainstSuppliedKey: Bool = true
    let ownerIdentityEstablishedByDevice: Bool = false
    let nativeIPACodeSignatureVerified: Bool = false
    let peerAuthenticated: Bool = false
    let userConsentVerified: Bool = false
    let installationAuthorized: Bool = false
    let installationPerformed: Bool = false
}

enum WebReaderSignedReleaseTrustGate {
    // Canonical P-256 SubjectPublicKeyInfo DER for an uncompressed X9.63 point.
    // The 65-byte public point is appended; never append arbitrary ASN.1.
    private static let p256SPKIPrefix: [UInt8] = [
        0x30, 0x59, 0x30, 0x13, 0x06, 0x07, 0x2a, 0x86, 0x48, 0xce,
        0x3d, 0x02, 0x01, 0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d,
        0x03, 0x01, 0x07, 0x03, 0x42, 0x00
    ]

    /// The SPKI fingerprint is obtained from separately trusted policy,
    /// NEVER from the downloaded manifest, IPA, or an editable GitHub field.
    /// If the owner has not provisioned a trust anchor, this method denies.
    static func inspectReadOnlyV2(
        envelopeData: Data,
        publicKeyX963: Data,
        independentlyTrustedSPKISHA256: String?,
        installedBuild: Int,
        installedIOS: OperatingSystemVersion
    ) throws -> WebReaderSignedReleasePreview {
        guard let pin = independentlyTrustedSPKISHA256,
              pin.range(
                of: "^[0-9a-f]{64}$", options: .regularExpression
              ) != nil else {
            throw WebReaderSignedReleaseTrustError.missingIndependentTrustAnchor
        }
        guard publicKeyX963.count == 65,
              publicKeyX963.first == 0x04 else {
            throw WebReaderSignedReleaseTrustError.invalidPublicKey
        }
        let spki = Data(p256SPKIPrefix) + publicKeyX963
        var digest = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        _ = spki.withUnsafeBytes { raw -> UnsafeMutablePointer<UInt8>? in
            return CC_SHA256(raw.baseAddress, CC_LONG(raw.count), &digest)
        }
        let observed = digest.map { String(format: "%02x", $0) }.joined()
        guard observed == pin else {
            throw WebReaderSignedReleaseTrustError.trustAnchorMismatch
        }
        // Require signed v2 specifically: legacy v1 assets and envelopes
        // cannot be elevated by simply supplying a matching public key.
        guard envelopeData.count > 0, envelopeData.count <= 64 * 1024,
              WebReaderStrictJSON.accepts(envelopeData),
              let envelope = try? JSONSerialization.jsonObject(
                with: envelopeData, options: []
              ) as? [String: Any],
              let version = envelope["schemaVersion"] as? NSNumber,
              CFGetTypeID(version) != CFBooleanGetTypeID(),
              version.intValue == 2,
              version.stringValue == "2" else {
            throw WebReaderSignedReleaseTrustError.unsupportedEnvelopeVersion
        }
        let verified = try WebReaderUpdateManifestVerifier.verify(
            envelopeData: envelopeData,
            publicKeyX963: publicKeyX963,
            installedBuild: installedBuild,
            installedIOS: installedIOS
        )
        return WebReaderSignedReleasePreview(
            update: verified, observedSPKISHA256: observed
        )
    }
}
