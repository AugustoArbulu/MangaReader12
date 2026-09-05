# IOS12_COMPATIBILITY

## Current verdict

**Feasible, with a time-sensitive CI constraint.**

The canonical build path is Xcode 15.4 on macOS 14. This is the path whose Apple-documented deployment target range includes iOS 12. Newer Xcode 16.x toolchains are not the canonical fallback because Apple documents their deployment target floor as iOS 15.

## Toolchain

| Item | Decision |
|---|---|
| Deployment target | iOS 12.0 |
| Xcode | 15.4 |
| Compiler | Swift 5.10 |
| Swift language mode | Swift 5 |
| CI host | GitHub Actions macos-14 while available |
| Device build architecture | arm64 expected; verified in CI with `lipo` |
| Simulator | Do not claim iOS 12 runtime testing; Xcode 15.4 simulator support starts later than iOS 12 |

## Framework policy

Baseline frameworks selected for later milestones are compatible in principle with the iOS 12 target: UIKit, Foundation/URLSession, JavaScriptCore, WebKit/WKWebView, GCD/OperationQueue, FileManager, Codable, NSCache, and SQLite through the system library. Every concrete API call still requires an availability review when implemented.

## WebView/cookie warning

WKWebView does not share the same cookie store as Foundation's shared `HTTPCookieStorage`. Cookie synchronization between WKWebView and URLSession must therefore be explicit rather than assumed.

## APIs deliberately avoided

- SwiftUI
- Combine
- iOS 13 scene lifecycle as a requirement
- required Swift Concurrency (`async`/`await`)
- modern-only document-picker initializers
- system dynamic colors such as `UIColor.systemBackground` unless availability-gated with an iOS 12 fallback

## CI retirement risk

GitHub will retire the hosted macOS 14 image on 2026-11-02. Before that date, choose one of:

1. a self-hosted GitHub Actions macOS 14 runner with Xcode 15.4;
2. a cloud Mac provider exposing macOS 14 + Xcode 15.4, attached as a self-hosted Actions runner;
3. an explicitly experimental newer-Xcode path, never promoted to canonical until a physical iOS 12 install/launch matrix proves it reliable.

The project must not silently raise the deployment target to keep CI alive.
