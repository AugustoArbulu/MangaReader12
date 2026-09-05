# ARCHITECTURE

## ADR-0001 — iOS 12 remains the hard floor

Status: Accepted

The application deployment target is fixed at iOS 12.0. Any future dependency or API that raises the minimum must be rejected or isolated behind an iOS-12-compatible alternative unless the user explicitly changes this constraint.

## ADR-0002 — UIKit application lifecycle

Status: Accepted

The bootstrap uses `UIApplicationDelegate` and a programmatic `UIWindow`/root view controller. No SwiftUI lifecycle or SceneDelegate requirement is introduced.

## ADR-0003 — Canonical compiler is Xcode 15.4

Status: Accepted

Xcode 15.4 is the canonical toolchain. Milestone 0 proved a Release arm64 binary with Mach-O `minos 12.0` and successful launch on a physical iOS 12 device.

## ADR-0004 — Fail closed on CI toolchain drift

Status: Accepted

The CI audit aborts if Xcode is not 15.4 or if the deployment target is not exactly 12.0. Silent migration to `macos-latest` is forbidden.

## ADR-0005 — Native networking, callback-based source bridge

Status: Accepted

Sources do not depend on JavaScript `fetch`. Native networking is implemented with URLSession and exposed to JavaScriptCore using callback-based bridge methods. This avoids requiring Promise/fetch support from the iOS 12 JavaScriptCore environment.

## ADR-0006 — SQLite system library, no ORM dependency

Status: Accepted

Milestone 1 starts with the system SQLite library directly. This keeps binary/dependency overhead low and allows explicit control over migrations and threading.

## ADR-0007 — Source execution is serialized

Status: Accepted

Each JavaScript source runtime owns a serial DispatchQueue. JavaScript evaluation and asynchronous callback delivery are routed to that queue to avoid concurrent access to a source context.

## ADR-0008 — Source permissions start with a domain allowlist

Status: Accepted

Each source runtime receives its allowed domains from the validated manifest. Native requests reject unlisted domains and non-HTTPS schemes by default. More complete sandbox hardening remains a later milestone.

## Layer map

- App
- Core — domain models and diagnostics
- Database — SQLite persistence and migrations
- Networking — URLSession and request policy
- Sources — manifests and source contracts
- SourceRuntime — JavaScriptCore + Native bridge
- Library — planned
- Reader — planned
- Downloads — planned
- RepositoryManager — planned
- Migration — planned
- Settings — planned
- UI — UIKit only
