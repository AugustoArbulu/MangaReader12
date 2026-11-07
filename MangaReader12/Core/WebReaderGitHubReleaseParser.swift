import Foundation
import CoreFoundation

/// Personal updater channel: public GitHub Release metadata over standard HTTPS.
/// No custom signing key needed. The GitHub HTTPS account/release is the trust
/// source, NOT a cryptographically signed WebReader publisher manifest.
/// Every IPA is still checked against GitHub's SHA-256 and native IPA identity.
/// A future privileged helper must authenticate its own inputs independently.
enum WebReaderGitHubReleaseParser {
    static let apiURL = URL(string:
        "https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest"
    )!
    private static let legacyAssetName = "WebReader-iOS12-unsigned.ipa"
    private static let fixedRepo = "/AugustoArbulu/MangaReader12/releases/download/"
    private static let maximumIPA: Int64 = 512 * 1024 * 1024

    static func parse(
        _ bytes: Data, installedBuild: Int,
        installedIOS: OperatingSystemVersion
    ) -> WebReaderUpdateCheckResult {
        guard !bytes.isEmpty, bytes.count <= 128 * 1024,
              WebReaderStrictJSON.accepts(bytes),
              let json = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any],
              json["draft"] as? Bool == false,
              json["prerelease"] as? Bool == false,
              let tag = json["tag_name"] as? String,
              tag.hasPrefix("build"), tag.count <= 15,
              let build = Int(tag.dropFirst(5)),
              build > 0, build <= 2_147_483_647,
              tag == "build" + String(build),
              let published = json["published_at"] as? String,
              !published.isEmpty, published.count <= 64,
              let assets = json["assets"] as? [[String: Any]],
              assets.count <= 40
        else { return .failed(.invalidGitHubRelease) }
        guard build > installedBuild else { return .upToDate }
        guard installedIOS.majorVersion >= 12 else {
            return .failed(.invalidGitHubRelease)
        }

        // The legacy v1 asset and the exact build-named v2 ad-hoc asset
        // are alternative release conventions. Never silently pick one when
        // both exist: ambiguous release publication is a hard failure.
        // GitHub release metadata is NOT a signed publisher manifest, and
        // neither asset name grants an installer any authorization.
        let adHocAssetName = "WebReader-Build" + String(build) + "-iOS12-adhoc.ipa"
        let allowedAssetNames: Set<String> = [legacyAssetName, adHocAssetName]
        let selected = assets.filter {
            guard let name = $0["name"] as? String else { return false }
            return allowedAssetNames.contains(name)
        }
        guard selected.count == 1 else {
            return .failed(.invalidGitHubRelease)
        }
        let asset = selected[0]
        guard let selectedAssetName = asset["name"] as? String,
              allowedAssetNames.contains(selectedAssetName),
              asset["state"] as? String == "uploaded",
              let number = asset["size"] as? NSNumber,
              CFGetTypeID(number) != CFBooleanGetTypeID(),
              number.int64Value > 0, number.int64Value <= maximumIPA,
              number.doubleValue == Double(number.int64Value),
              let digestField = asset["digest"] as? String,
              digestField.hasPrefix("sha256:"),
              digestField.count == 71,
              let urlString = asset["browser_download_url"] as? String,
              let url = URL(string: urlString),
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.scheme == "https", components.host == "github.com",
              components.user == nil, components.password == nil,
              components.port == nil, components.query == nil,
              components.fragment == nil,
              components.percentEncodedPath ==
                fixedRepo + tag + "/" + selectedAssetName
        else { return .failed(.invalidGitHubRelease) }

        let digest = String(digestField.dropFirst(7))
        guard digest.range(
            of: "^[0-9a-f]{64}$", options: .regularExpression
        ) != nil else { return .failed(.invalidGitHubRelease) }

        let description = (json["body"] as? String ?? "")
        let notes = description
            .components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
            .prefix(5)
            .map { String($0.prefix(180)) }
        var update = WebReaderVerifiedUpdate(
            build: build, minimumIOS: "12.0",
            ipaURL: url, ipaSize: number.int64Value,
            sha256: digest, publishedAt: published,
            releaseNotes: notes.isEmpty ? ["Release oficial do GitHub"] : notes
        )
        update.provenance = .publicGitHubRelease
        return .updateAvailable(update)
    }
}
