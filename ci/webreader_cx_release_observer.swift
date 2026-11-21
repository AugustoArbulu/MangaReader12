import Foundation

/*
 * Post-DA DB2: fixed-origin read-only GitHub Release discovery, HOST/CROSS-
 * COMPILE LAB ONLY. This is NOT wired into the installed CX daemon or DA app.
 *
 * We intentionally reuse the EXACT iOS12 Swift parser and HTTPS transport
 * from WebReaderUpdateChecker. Public GitHub metadata is NOT a signed
 * publisher statement, and no response can authorize downloading or
 * installing any IPA. Only explicit "--live" performs one HTTPS GET.
 *
 * Historical Build70 already used "Phase DB" for UID custody in Nov 10.
 * DB2 is a separate Nov 21 post-DA track, not a replacement for those tests.
 */

enum WRDB2Observation: Equatable {
    case noPublicRelease
    case metadataNewer(Int)
    case metadataNotNewer
    case unexpectedHTTP(Int)
    case malformedMetadata
    case networkFailure
    case invalidState

    var token: String {
        switch self {
        case .noPublicRelease: return "NO_ACCESSIBLE_LATEST_RELEASE_HTTP_404"
        case .metadataNewer(let build): return "UNTRUSTED_NEWER_METADATA_BUILD_\(build)"
        case .metadataNotNewer: return "METADATA_NOT_NEWER_UNTRUSTED"
        case .unexpectedHTTP(let status): return "UNEXPECTED_HTTP_\(status)"
        case .malformedMetadata: return "INVALID_UNTRUSTED_METADATA"
        case .networkFailure: return "NETWORK_OR_TLS_FAILURE"
        case .invalidState: return "INVALID_CHECK_STATE"
        }
    }
}

@main
struct WRDB2HostProbe {
    static let installedBuild = 70
    static let ios = OperatingSystemVersion(
        majorVersion: 12, minorVersion: 5, patchVersion: 8
    )
    static let fixedURL =
        "https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest"

    static func interpret(_ result: WebReaderUpdateCheckResult) -> WRDB2Observation {
        switch result {
        case .updateAvailable(let update):
            // JSON was parsed, but nobody signed the metadata independently.
            guard update.provenance == .publicGitHubRelease,
                  update.build > installedBuild else { return .invalidState }
            return .metadataNewer(update.build)
        case .upToDate: return .metadataNotNewer
        case .failed(.unexpectedHTTPStatus(404)):
            // A 404 may mean zero Releases, private repo, or GitHub access
            // denial. NEVER promote 404 to "up to date".
            return .noPublicRelease
        case .failed(.unexpectedHTTPStatus(let status)):
            return .unexpectedHTTP(status)
        case .failed(.invalidGitHubRelease), .failed(.oversizedResponse),
             .failed(.unexpectedContentType):
            return .malformedMetadata
        case .failed(.transport): return .networkFailure
        case .failed(.busy), .failed(.invalidSignedManifest),
             .failed(.unsupportedManifestURL), .disabled:
            return .invalidState
        }
    }

    static func printObservation(_ status: WRDB2Observation) {
        print("WR_DB2_SOURCE=FIXED_PUBLIC_GITHUB_HTTPS_METADATA_ONLY")
        print("WR_DB2_OBSERVATION=\(status.token)")
        print("WR_DB2_PUBLIC_RELEASE_IS_SIGNED_PUBLISHER=NO")
        print("WR_DB2_OWNER_TRUST_PROVISIONED=NO")
        print("WR_DB2_PEER_AUTHENTICATED=NO")
        print("WR_DB2_IPA_DOWNLOADED=NO")
        print("WR_DB2_INSTALL_AUTHORIZED=NO")
        print("WR_DB2_INSTALL_PERFORMED=NO")
    }

    static func selftest() -> Bool {
        guard WebReaderGitHubReleaseParser.apiURL.absoluteString == fixedURL
        else { return false }

        func check(_ result: WebReaderUpdateCheckResult,
                   expected: WRDB2Observation) -> Bool {
            interpret(result) == expected
        }

        let sha = String(repeating: "a", count: 64)
        let asset = "WebReader-Build71-iOS12-adhoc.ipa"
        let valid: [String: Any] = [
            "tag_name": "build71",
            "draft": false, "prerelease": false,
            "published_at": "2026-11-21T00:00:00Z",
            "body": "synthetic, not published",
            "assets": [[
                "name": asset,
                "size": 45678,
                "digest": "sha256:" + sha,
                "state": "uploaded",
                "browser_download_url":
                  "https://github.com/AugustoArbulu/MangaReader12/releases/" +
                  "download/build71/" + asset
            ]]
        ]
        guard let bytes = try? JSONSerialization.data(
            withJSONObject: valid, options: [.sortedKeys]
        ) else { return false }
        let fake = WebReaderGitHubReleaseParser.parse(
            bytes, installedBuild: installedBuild, installedIOS: ios
        )
        guard check(fake, expected: .metadataNewer(71)),
              check(.failed(.unexpectedHTTPStatus(404)),
                    expected: .noPublicRelease),
              check(.failed(.unexpectedHTTPStatus(403)),
                    expected: .unexpectedHTTP(403)),
              check(.failed(.transport), expected: .networkFailure),
              check(.failed(.invalidGitHubRelease),
                    expected: .malformedMetadata)
        else { return false }

        // Missing asset, duplicate keys, mismatched repository and arbitrary
        // URL are all rejected by the SAME native parser used in the app.
        var missing = valid
        missing["assets"] = []
        guard let broken = try? JSONSerialization.data(withJSONObject: missing),
              check(WebReaderGitHubReleaseParser.parse(
                  broken, installedBuild: installedBuild, installedIOS: ios
              ), expected: .malformedMetadata)
        else { return false }

        let duplicate = bytes.dropLast() +
                        Data(",\"tag_name\":\"build72\"}".utf8)
        guard check(WebReaderGitHubReleaseParser.parse(
            duplicate, installedBuild: installedBuild, installedIOS: ios
        ), expected: .malformedMetadata)
        else { return false }
        return true
    }

    static func liveCheck() -> WRDB2Observation {
        // This experiment is a one-shot, on-demand public metadata request.
        // The fixed URL is compiled into the shared WebReaderUpdateChecker.
        let observer = WebReaderUpdateChecker(
            installedBuild: installedBuild,
            installedIOS: ios,
            usePublicGitHubReleases: true
        )
        let done = DispatchSemaphore(value: 0)
        var result: WebReaderUpdateCheckResult?
        observer.check { value in
            result = value
            done.signal()
        }
        guard done.wait(timeout: .now() + 26) == .success else {
            observer.cancel()
            return .networkFailure
        }
        guard let observed = result else { return .invalidState }
        return interpret(observed)
    }

    static func main() {
        let args = CommandLine.arguments
        guard args.count == 2 else {
            fputs("Usage: wr-db2-release-observer --selftest | --live\n", stderr)
            exit(2)
        }
        switch args[1] {
        case "--selftest":
            guard selftest() else { exit(3) }
            print("WR_DB2_SYNTHETIC_PARSER_SELFTEST=PASS")
            printObservation(.metadataNewer(71))
        case "--live":
            printObservation(liveCheck())
        default:
            // No CLI-supplied network host, path, URL or release number.
            exit(2)
        }
    }
}
