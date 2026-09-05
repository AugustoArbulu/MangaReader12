# PROJECT_STATE

## Checkpoint

- Project: MangaReader12 (provisional name)
- Phase: **Milestone 2 — Repositories / Batch M2B**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (3)**

## Milestone 0 validation — COMPLETE

Milestone 0 passed end-to-end on 2026-09-05.

## Milestone 1A validation — ACCEPTED

- PR #1 CI: green
- Post-merge `main` run `33967662348`: green
- Physical iOS 12 diagnostics: **4/4 green**

## Milestone 1B validation — ACCEPTED

- PR #2 CI: green
- Post-merge `main` run `33968911048`: green
- Physical iOS 12 diagnostics: **5/5 green**

## Milestone 1C validation — ACCEPTED

- PR #3 CI: green
- Post-merge `main` run `33969638301`: green
- Physical iOS 12 diagnostics: **6/6 green**

## Milestone 2A validation — ACCEPTED

M2A was accepted on 2026-09-05 after:

- PR #4 CI: green
- Post-merge `main` run `33970456712`: green
- Debug and Release generic-device builds: success
- Release binary verification: success
- IPA packaging: success
- Physical iOS 12 launch: success
- On-device diagnostics: **7/7 green**

## Implemented in M2B source

- HTTPS repository endpoint policy derived from the repository host
- Callback-based remote repository catalog fetch using the hardened `HTTPClient`
- Repository catalog HTTP status handling and decode/validation path
- HTTPS source-script download transport
- Pure Swift SHA-256 implementation compatible with iOS 12
- Optional source-script SHA-256 verification with explicit mismatch failure
- Persistent repository records using the existing SQLite `repositories` table
- Repository refresh timestamp persistence
- Expanded on-device diagnostics to **8 checks**, adding `Repository transport`
- Build number advanced to **3** for device-test identification
- Earlier milestone diagnostics remain as regression checks

## Validation status for M2B

- Local Swift parser/type checks: performed before upload package publication
- SHA-256 known-vector test: performed before upload package publication
- Xcode 15.4 compile: **pending GitHub Actions**
- Physical iOS 12 diagnostics: **pending after green CI build**

## Known limitations / intentionally deferred

- M2B can retrieve and verify repository catalogs/scripts, but does not yet perform atomic script installation on disk.
- Atomic source install/update + rollback is M2C.
- Repository trust/signature model is not implemented yet; SHA-256 verifies integrity when supplied, not publisher identity.
- Cookie storage still uses Foundation's shared cookie store.
- JavaScript execution timeout/cancellation is not yet hardened.
- No real external source is enabled by default.

## Next gate

Upload M2B, obtain a green Xcode 15.4 Actions build, sideload the generated IPA and verify that all eight on-device diagnostics display green check marks.
