# Milestone 2B Report — Repository Transport + Integrity

Date: 2026-09-05

## Goal

Move the repository system from local catalog semantics to a real HTTPS transport foundation while keeping iOS 12 compatibility and source integrity checks explicit.

## Added

- HTTPS-only repository endpoint policy.
- Remote catalog download through the existing hardened `HTTPClient`.
- HTTP status validation and typed catalog decode/validation.
- Source-script download transport with an independent HTTPS host policy.
- Pure Swift SHA-256 implementation, avoiding CryptoKit so iOS 12 remains supported.
- Optional manifest SHA-256 verification and explicit mismatch failure.
- SQLite repository persistence using the existing schema-v1 `repositories` table.
- Last-refresh timestamp persistence.
- Eighth on-device diagnostic: `Repository transport`.

## Diagnostic coverage

The new diagnostic does not depend on an external server. It verifies locally:

- SHA-256 known vector for `abc`
- HTTPS repository policy
- HTTP repository rejection
- matching script-integrity verification
- repository catalog decode through the transport decode path
- repository persistence round-trip
- repository refresh timestamp update

Actual HTTPS requests are compiled into the app and will be exercised when a real repository is configured in the next UI/integration stages.

## Scope boundary

M2B intentionally does not commit downloaded JavaScript to an installed-source directory. Atomic staging, install/update replacement, and rollback are M2C.

SHA-256 proves downloaded bytes match the manifest when a digest is supplied; it does not authenticate who published the manifest. Publisher trust/signatures are a separate security layer.

## iOS 12 constraints

No SwiftUI, Combine, required async/await, SceneDelegate, or CryptoKit dependency was introduced.

## Acceptance gate

1. GitHub Actions under Xcode 15.4 passes.
2. Debug + Release generic-device builds pass.
3. Release binary remains arm64 with minimum OS 12.0.
4. IPA packaging succeeds.
5. Physical iOS 12 device launches build 3.
6. All 8/8 diagnostics are green.
