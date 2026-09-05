# PROJECT_STATE

## Checkpoint

- Project: MangaReader12 (provisional name)
- Phase: Milestone 0 — feasibility/bootstrap
- State: **SOURCE BOOTSTRAP CREATED, NOT YET COMPILED IN XCODE**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`

## Implemented in this checkpoint

- Minimal UIKit app without Storyboard-driven app lifecycle
- Shared Xcode scheme
- Explicit iOS 12.0 deployment target at project and app-target levels
- GitHub Actions workflow for unsigned Debug/Release device builds
- Binary audit for Mach-O `minos 12.0`
- Architecture audit
- Unsigned IPA packaging + SHA-256
- Guard script against accidental SwiftUI/Combine/async-await usage

## Validation status

- File/plist structural validation: pending local validation in this checkpoint report
- Xcode project compilation: **not run here** (no macOS/Xcode environment in this session)
- GitHub Actions build: **not run yet**
- Physical iOS 12 test: **not run yet**
- Sideloadly installation: **not run yet**

## Blocking risk

GitHub's hosted `macos-14` runners are scheduled for retirement on 2026-11-02. A post-retirement CI host capable of macOS 14 + Xcode 15.4 must be selected before that date if strict official iOS 12 toolchain support is to be preserved.

## Next gate

Push this bootstrap to a GitHub repository and obtain a green `iOS 12 Milestone 0` Actions run. Then install the generated unsigned IPA through Sideloadly on the target iOS 12 device and record device model, exact iOS version, install result, launch result, and logs.
