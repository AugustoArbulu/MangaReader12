import Foundation

/// Phase CH: read-only association of a verified production-v2 manifest
/// with precisely the release candidate that the in-app downloader will stage.
///
/// A provenance enum by itself is a *claim*, not an authenticated envelope.
/// Never download a signed-channel candidate without checking the actual
/// signed bytes against the compiled owner root, channel, metadata and SHA.
/// This grants NO publisher identity beyond the separately enrolled root,
/// code-sign seal, immutable installer handle, IPC peer or install consent.
enum WebReaderSignedProductionEnvelopeBinding {
    static func matchesCompiledOwnerRootReadOnly(
        envelopeData: Data,
        update: WebReaderVerifiedUpdate,
        installedBuild: Int,
        installedIOS: OperatingSystemVersion
    ) -> Bool {
        // Fail before even interpreting untrusted manifest bytes.
        guard WebReaderProductionPublisherTrust.isProvisioned,
              let key = WebReaderUpdateChannel.productionPublicKeyX963,
              let pin = WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256
        else { return false }
        return matchesReadOnly(
            envelopeData: envelopeData, update: update,
            installedBuild: installedBuild, installedIOS: installedIOS,
            publicKeyX963: key, independentlyTrustedSPKISHA256: pin
        )
    }

    /// Pure verification utility for Mac fixtures using throwaway public
    /// points. Never called by production downloads with caller-chosen keys.
    /// Returning true does NOT permit installation or prove key ownership.
    static func matchesReadOnly(
        envelopeData: Data,
        update: WebReaderVerifiedUpdate,
        installedBuild: Int,
        installedIOS: OperatingSystemVersion,
        publicKeyX963: Data,
        independentlyTrustedSPKISHA256: String?
    ) -> Bool {
        guard update.provenance == .signedManifest,
              envelopeData.count > 0, envelopeData.count <= 64 * 1024,
              let signed = try? WebReaderSignedReleaseTrustGate.inspectReadOnlyV2(
                envelopeData: envelopeData,
                publicKeyX963: publicKeyX963,
                independentlyTrustedSPKISHA256: independentlyTrustedSPKISHA256,
                installedBuild: installedBuild, installedIOS: installedIOS,
                expectedChannel: "production"
              )
        else { return false }
        let verified = signed.update
        return verified.build == update.build &&
            verified.minimumIOS == update.minimumIOS &&
            verified.ipaURL == update.ipaURL &&
            verified.ipaSize == update.ipaSize &&
            verified.sha256 == update.sha256 &&
            verified.publishedAt == update.publishedAt &&
            verified.releaseNotes == update.releaseNotes
    }
}
