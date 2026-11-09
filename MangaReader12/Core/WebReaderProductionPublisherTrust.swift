import Foundation

/// Phase W: a separate, fail-closed *production* entry point for signed
/// WebReader releases. Unlike the laboratory verifier, this API never takes
/// its trusted fingerprint from a caller, a network payload or local app preferences.
///
/// The publisher's independently verified public key and fingerprint must
/// be compiled in a new reviewed iOS12 build by the owner. Until that
/// separate provisioning step, this method always denies. This file NEVER
/// executes an installation or accesses the device's reader library.
enum WebReaderPublisherTrustError: Error {
    case noProvisionedOwnerTrust
    case revokedOwnerKey
    case invalidOwnerTrustConfiguration
}

enum WebReaderProductionPublisherTrust {
    /// The owner-reviewed SPKI SHA-256 fingerprint is intentionally ABSENT.
    /// It must never be copied from the same GitHub Release or manifest.
    static let independentlyProvisionedSPKISHA256: String? = nil

    /// Key-generation metadata is a local, compiled policy, never a field
    /// supplied by GitHub. Generation zero means no production trust root.
    static let productionTrustGeneration = 0

    /// Revocations must be set by an independently reviewed app build;
    /// remote metadata cannot clear or replace this list.
    static let revokedPublisherPins: Set<String> = []

    /// Pure offline candidate review. Even true does NOT provision trust or
    /// authorize a network check; only isProvisioned uses compiled-in policy.
    /// It is exposed within the module for synthetic tests with throwaway keys.
    static func isCandidateReadyForReview(
        ownerPin: String?, generation: Int, publicKeyX963: Data?,
        revokedPins: Set<String>
    ) -> Bool {
        guard let pin = ownerPin,
              generation >= 1,
              pin.range(of: "^[0-9a-f]{64}$",
                        options: .regularExpression) != nil,
              let key = publicKeyX963,
              !revokedPins.contains(pin),
              // Validate the EC point and canonical SPKI fingerprint BEFORE
              // the production checker creates any network request.
              WebReaderSignedReleaseTrustGate.observedP256SPKISHA256(
                for: key
              ) == pin
        else { return false }
        return true
    }

    /// Only compiled, owner-reviewed constants may authorize HTTPS discovery;
    /// the preview never establishes Chimera peer identity or install consent.
    static var isProvisioned: Bool {
        return isCandidateReadyForReview(
            ownerPin: independentlyProvisionedSPKISHA256,
            generation: productionTrustGeneration,
            publicKeyX963: WebReaderUpdateChannel.productionPublicKeyX963,
            revokedPins: revokedPublisherPins
        )
    }

    /// Separate from the test-only injected-key inspection API.
    /// No trusted key/pin may be obtained from envelopeData.
    static func inspectProductionManifestReadOnly(
        envelopeData: Data, installedBuild: Int,
        installedIOS: OperatingSystemVersion
    ) throws -> WebReaderSignedReleasePreview {
        guard let pin = independentlyProvisionedSPKISHA256,
              let key = WebReaderUpdateChannel.productionPublicKeyX963,
              productionTrustGeneration >= 1
        else { throw WebReaderPublisherTrustError.noProvisionedOwnerTrust }
        guard !revokedPublisherPins.contains(pin) else {
            throw WebReaderPublisherTrustError.revokedOwnerKey
        }
        guard isProvisioned else {
            throw WebReaderPublisherTrustError.invalidOwnerTrustConfiguration
        }
        return try WebReaderSignedReleaseTrustGate.inspectReadOnlyV2(
            envelopeData: envelopeData, publicKeyX963: key,
            independentlyTrustedSPKISHA256: pin,
            installedBuild: installedBuild, installedIOS: installedIOS,
            expectedChannel: "production"
        )
    }
}
