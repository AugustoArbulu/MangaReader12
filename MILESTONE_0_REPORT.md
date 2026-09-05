# Milestone 0 — Feasibility report

Date: 2026-09-05

## Result

The project is technically feasible for iOS 12, but the build toolchain must be treated as a pinned legacy dependency.

### Canonical toolchain

- macOS 14 (Sonoma)
- Xcode 15.4 (build 15F31d)
- iOS 17.5 SDK
- Swift 5.10 compiler, Swift 5 language mode
- `IPHONEOS_DEPLOYMENT_TARGET = 12.0`
- UIKit lifecycle, not SwiftUI

Apple's Xcode requirements page explicitly lists Xcode 15.4 deployment targets as iOS 12–17.5. The same page lists Xcode 16.x deployment targets as iOS 15 or later, so Xcode 16+ is not accepted as the canonical iOS-12 compiler path.

### CI availability

GitHub's hosted `macos-14` image currently includes Xcode 15.4 and makes it the default Xcode on that image. GitHub has announced retirement of macOS 14 hosted runners on 2026-11-02. The workflow therefore pins both `runs-on: macos-14` and `/Applications/Xcode_15.4.app` and intentionally fails closed instead of silently migrating to a newer Xcode.

### Sideload path

Sideloadly's current FAQ states support from iOS 7 through iOS 26+. The generated Milestone 0 IPA is intentionally unsigned; the expected flow is to let Sideloadly re-sign it with the user's Apple account. This exact checkpoint has not yet been installed, so Sideloadly compatibility remains an acceptance test rather than a claimed result.

### Xcode 16 warning

There are 2026 Apple Developer Forums reports of Xcode 16.4 projects manually targeting iOS 12 that work by direct/Ad Hoc installation but fail after TestFlight/App Store distribution on iOS 12. That is supporting evidence for keeping this project focused on direct sideloading and on the officially documented Xcode 15.4 path.

## Verified references

- Apple — Xcode SDK and system requirements: https://developer.apple.com/xcode/system-requirements
- GitHub Actions — macOS 14 runner image: https://github.com/actions/runner-images/blob/main/images/macos/macos-14-Readme.md
- GitHub Actions — macOS 14 retirement announcement: https://github.com/actions/runner-images/issues/13518
- Sideloadly FAQ: https://sideloadly.io/faq
- Apple Developer Forums iOS 12 / Xcode 16.4 distribution regression: https://developer.apple.com/forums/thread/821370

## Status vocabulary

- Implemented: source/config exists in this checkpoint.
- Structurally validated: formats/syntax were checked in the current non-macOS environment.
- Compiles: not yet established.
- CI green: not yet established.
- Tested on simulator: not yet established (and iOS 12 simulator is not part of the Xcode 15.4 simulator matrix).
- Tested on physical iOS 12 device: not yet established.

## Decision

Proceed to the CI build gate. Do not start the SourceRuntime/database/networking implementation until the empty UIKit app has produced a green Xcode 15.4 device build and has launched successfully on the user's actual iOS 12 device.
