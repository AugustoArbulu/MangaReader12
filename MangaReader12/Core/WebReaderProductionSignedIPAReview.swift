import Foundation

/// Phase CF: the future production updater's ONLY read-only entry point for
/// jointly verifying a signed production-v2 manifest and a local IPA.
///
/// Unlike the generic laboratory verifier, callers CANNOT supply a key,
/// pin, channel or trust-generation. The public key and SPKI fingerprint must
/// be independently approved and compiled into the reviewed application.
/// Today's Build70 has NONE of those values: this always fails closed.
///
/// Even a successful future result is not an installation authorization:
/// the file may change, the appinst helper peer remains unauthenticated and
/// no approval/anti-rollback ledger is bound to an immutable installer handle.
enum WebReaderProductionSignedIPAReview {
    static func inspectReadOnly(
        envelopeData: Data,
        localIPAURL: URL,
        installedBuild: Int,
        installedIOS: OperatingSystemVersion
    ) throws -> WebReaderSignedIPAReviewResult {
        // This guard MUST come before any file I/O or signed-manifest parsing.
        guard WebReaderProductionPublisherTrust.isProvisioned,
              let pin = WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256,
              let publicKey = WebReaderUpdateChannel.productionPublicKeyX963
        else {
            throw WebReaderPublisherTrustError.noProvisionedOwnerTrust
        }
        return try WebReaderSignedIPAReview.inspectReadOnly(
            envelopeData: envelopeData,
            independentlyTrustedPublicKeyX963: publicKey,
            independentlyTrustedSPKISHA256: pin,
            localIPAURL: localIPAURL,
            installedBuild: installedBuild,
            installedIOS: installedIOS,
            expectedChannel: "production"
        )
    }
}
