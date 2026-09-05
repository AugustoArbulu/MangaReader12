# IOS12_COMPATIBILITY

## Current verdict

**Proven on physical iOS 12 hardware for Milestone 0.**

The canonical build path is Xcode 15.4 on macOS 14. GitHub Actions successfully produced an arm64 Release binary whose Mach-O minimum OS is iOS 12.0, and that IPA was re-signed with Sideloadly, installed and launched on a physical iOS 12 device.

## Toolchain

| Item | Decision / status |
|---|---|
| Deployment target | iOS 12.0 — locked |
| Xcode | 15.4 |
| Compiler | Swift 5.10 |
| Swift language mode | Swift 5 |
| SDK in validated M0 build | iOS 17.5 |
| CI host | GitHub Actions macos-14 while available |
| Device architecture | arm64 — validated |
| Physical iOS 12 launch | validated |
| Simulator | No claim of iOS 12 simulator testing |

## Milestone 1 framework audit

| Framework/API | Use | iOS 12 policy |
|---|---|---|
| UIKit | UI | baseline |
| Foundation / URLSession | native networking | baseline |
| JavaScriptCore | extension runtime | baseline |
| SQLite3 system library | persistence | baseline |
| DispatchQueue | concurrency | baseline |
| UserDefaults | temporary source-key storage foundation | baseline |
| HTTPCookieStorage | initial cookie bridge | baseline; isolation hardening pending |

No SwiftUI, Combine, required Swift Concurrency, SceneDelegate, or iOS-13-only UI APIs are introduced by M1A.

## WebView/cookie warning

WKWebView does not automatically share Foundation's cookie storage. M1A does not yet introduce WKWebView fallback. When it is added, cookie synchronization must be explicit and tested specifically on iOS 12.

## Current M1A security posture

- HTTPS required by default.
- Requests are restricted to manifest-declared domains and their subdomains.
- Request timeout is bounded.
- Redirect count is bounded and redirect destinations are rechecked against policy.
- Response size has an initial post-receive cap; streaming cancellation is still required before hardening is considered complete.
- Source storage is namespaced by source ID.
- Arbitrary filesystem access is not exposed to JavaScript.

## APIs deliberately avoided

- SwiftUI
- Combine
- iOS 13 scene lifecycle as a requirement
- required Swift Concurrency (`async`/`await`)
- modern-only document-picker initializers
- system dynamic colors such as `UIColor.systemBackground` unless availability-gated

## CI retirement risk

GitHub's hosted macOS 14 image remains a time-sensitive dependency. The project must not silently raise the deployment target to keep CI alive. A preserved Xcode 15.4 runner path must be selected before the hosted image is unavailable.
