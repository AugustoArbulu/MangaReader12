# MangaReader12 — Milestone 0 bootstrap

Provisional project name for the iOS 12 manga/manhwa/manhua reader project.

## Canonical constraints

- Minimum OS: **iOS 12.0**
- UI: UIKit
- Canonical compiler/toolchain: **Xcode 15.4 / Swift 5.10 compiler in Swift 5 language mode**
- Canonical hosted CI while available: **GitHub Actions `macos-14`**
- No SwiftUI, Combine, or required async/await
- No third-party dependencies in Milestone 0

## What this checkpoint proves when CI is green

1. The Xcode project parses under Xcode 15.4.
2. Debug and Release compile for a generic physical iOS target.
3. `IPHONEOS_DEPLOYMENT_TARGET` remains exactly `12.0`.
4. The produced Mach-O reports `minos 12.0`.
5. The device build contains the expected architecture(s).
6. An unsigned `.ipa` can be packaged for later re-signing by Sideloadly.

## What it does NOT prove

- That the app has been run on an iOS 12 simulator (Xcode 15.4 does not provide one).
- That it has been run on a physical iOS 12 device.
- That Sideloadly has successfully installed this particular IPA yet.
- That JavaScriptCore/WKWebView/source runtime features are implemented.

## Local/cloud build

The repository workflow pins `/Applications/Xcode_15.4.app` explicitly. Do not change `runs-on` to `macos-latest`.
