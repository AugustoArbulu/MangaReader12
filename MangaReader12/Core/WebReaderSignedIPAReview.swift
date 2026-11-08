import Foundation

/// Phase T: compose signed publisher metadata with a *separate* same-FD
/// read-only audit of an IPA selected by the owner. This is not an installer.
///
/// The pin MUST be independently trusted, before obtaining any release data.
/// This never enrolls a key, performs network operations, shares a file,
/// executes appinst, or authenticates a Chimera peer. The returned result is
/// observation only and must NEVER be treated as an installation ticket.
enum WebReaderSignedIPAReviewError: Error {
    case inconsistentSignedMetadata
}

struct WebReaderSignedIPAReviewResult {
    let build: Int
    let bundleID: String
    let minimumIOS: String
    let signedSHA256: String
    let observedSHA256: String
    let signedSPKISHA256: String
    let zipEntries: Int
    let signedManifestChecked: Bool = true
    let localZIPAndDigestChecked: Bool = true
    // Ad-hoc executable code-signature checking is host-only and was NOT run.
    let nativeExecutableSignatureChecked: Bool = false
    let publisherIdentityProvenByDevice: Bool = false
    let fileLockedForLaterUse: Bool = false
    let peerAuthenticated: Bool = false
    let consentForInstallVerified: Bool = false
    let installationAuthorized: Bool = false
    let installationPerformed: Bool = false
}

enum WebReaderSignedIPAReview {
    static func inspectReadOnly(
        envelopeData: Data,
        independentlyTrustedPublicKeyX963: Data,
        independentlyTrustedSPKISHA256: String?,
        localIPAURL: URL,
        installedBuild: Int,
        installedIOS: OperatingSystemVersion
    ) throws -> WebReaderSignedIPAReviewResult {
        // Never accept public GitHub Releases metadata (unsigned) as an
        // editor-signed manifest. The independent SPKI pin is mandatory.
        let signed = try WebReaderSignedReleaseTrustGate.inspectReadOnlyV2(
            envelopeData: envelopeData,
            publicKeyX963: independentlyTrustedPublicKeyX963,
            independentlyTrustedSPKISHA256: independentlyTrustedSPKISHA256,
            installedBuild: installedBuild, installedIOS: installedIOS
        )
        // This routine independently verifies the real local IPA's hash,
        // bounds, ZIP entries, executable filename, Info.plist and version
        // using one opened O_NOFOLLOW regular-file descriptor. It rehashes
        // and rechecks inode/mtime/ctime before returning.
        let audited = try WebReaderNativeIPAAuditor.inspect(
            ipaURL: localIPAURL, signedUpdate: signed.update,
            installedBuild: installedBuild, installedIOS: installedIOS
        )
        guard audited.bundleID == "com.example.MangaReader12",
              audited.build == signed.update.build,
              audited.minimumIOS == signed.update.minimumIOS,
              audited.verifiedSHA256 == signed.update.sha256 else {
            throw WebReaderSignedIPAReviewError.inconsistentSignedMetadata
        }
        // The file could change AFTER this result is issued. It is not
        // locked for use by a future privileged helper; never authorize
        // installation on the basis of this read-only receipt.
        return WebReaderSignedIPAReviewResult(
            build: audited.build, bundleID: audited.bundleID,
            minimumIOS: audited.minimumIOS,
            signedSHA256: signed.update.sha256,
            observedSHA256: audited.verifiedSHA256,
            signedSPKISHA256: signed.observedSPKISHA256,
            zipEntries: audited.zipEntries
        )
    }
}
