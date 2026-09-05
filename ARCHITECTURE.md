# ARCHITECTURE

## ADR-0001 — iOS 12 remains the hard floor

Status: Accepted

The application deployment target is fixed at iOS 12.0. Any future dependency or API that raises the minimum must be rejected or isolated behind an iOS-12-compatible alternative unless the user explicitly changes this constraint.

## ADR-0002 — UIKit application lifecycle

Status: Accepted

The bootstrap uses `UIApplicationDelegate` and a programmatic `UIWindow`/root view controller. No SwiftUI lifecycle or SceneDelegate requirement is introduced.

## ADR-0003 — Canonical compiler is Xcode 15.4

Status: Accepted

Xcode 15.4 is the newest Apple-documented Xcode generation in the currently audited set whose deployment target range explicitly includes iOS 12. It uses the Swift 5.10 compiler and supports Swift 5 language mode.

## ADR-0004 — Fail closed on CI toolchain drift

Status: Accepted

The CI audit aborts if Xcode is not 15.4 or if the deployment target is not exactly 12.0. Silent migration to `macos-latest` is forbidden.

## Planned architecture after Milestone 0

App / Core / Database / Networking / Sources / SourceRuntime / Library / Reader / Downloads / RepositoryManager / Migration / Settings / UI.
