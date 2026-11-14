import Foundation

/// Phase Y: a one-process, read-only monotonic review of signed local IPA
/// candidates. This is a QA *sequence*, NOT a rollback-safe installation
/// ledger. The in-memory high-water mark disappears on app restart and
/// cannot defend against filesystem snapshots, compromised root, or a
/// privileged installer. A future helper must maintain its own durable,
/// anti-rollback and owner-consent policy; this class grants none of them.
enum WebReaderSignedPreviewSequenceError: Error {
    case invalidInstalledBuild
    case oldOrRepeatedCandidate
}

struct WebReaderSignedPreviewSequenceStatus {
    let installedBuild: Int
    let highestSuccessfullyReviewedBuild: Int
    let isPersistent: Bool = false
    let installerLedgerVerified: Bool = false
    let installationAuthorized: Bool = false
    let installationPerformed: Bool = false
}

/// Created only by diagnostic/QA code. Production key provisioning is NOT
/// performed here; the key and independent pin remain explicit lab inputs.
final class WebReaderSignedPreviewSequence {
    private let lock = NSLock()
    private let installedBuild: Int
    private let installedIOS: OperatingSystemVersion
    private var highestReviewed: Int

    init(installedBuild: Int, installedIOS: OperatingSystemVersion) throws {
        guard installedBuild >= 0 && installedBuild <= 2_147_483_647 else {
            throw WebReaderSignedPreviewSequenceError.invalidInstalledBuild
        }
        self.installedBuild = installedBuild
        self.installedIOS = installedIOS
        self.highestReviewed = installedBuild
    }

    func inspectReadOnly(
        envelopeData: Data,
        publicKeyX963: Data,
        independentlyTrustedSPKISHA256: String?,
        localIPAURL: URL
    ) throws -> WebReaderSignedIPAReviewResult {
        // Serialize all reviews so concurrent requests cannot bypass the
        // session high-water mark. The signed content and same-FD IPA are
        // independently rechecked at EVERY call; no cached authorization.
        lock.lock()
        defer { lock.unlock() }
        let candidate = try WebReaderSignedIPAReview.inspectReadOnly(
            envelopeData: envelopeData,
            independentlyTrustedPublicKeyX963: publicKeyX963,
            independentlyTrustedSPKISHA256: independentlyTrustedSPKISHA256,
            localIPAURL: localIPAURL,
            installedBuild: highestReviewed,
            installedIOS: installedIOS
        )
        guard candidate.build > highestReviewed,
              candidate.build <= 2_147_483_647 else {
            throw WebReaderSignedPreviewSequenceError.oldOrRepeatedCandidate
        }
        highestReviewed = candidate.build
        return candidate
    }

    func statusReadOnly() -> WebReaderSignedPreviewSequenceStatus {
        lock.lock()
        defer { lock.unlock() }
        return WebReaderSignedPreviewSequenceStatus(
            installedBuild: installedBuild,
            highestSuccessfullyReviewedBuild: highestReviewed
        )
    }
}
