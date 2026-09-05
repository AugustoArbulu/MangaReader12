# PROJECT_STATE

## Checkpoint

- Project: MangaReader12 (provisional name)
- Phase: **Milestone 2 — Repositories / Batch M2A**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (2)**

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

M1C was accepted on 2026-09-05 after:

- PR #3 CI: green
- Post-merge `main` run `33969638301`: green
- Debug and Release generic-device builds: success
- Release binary verification: success
- IPA packaging: success
- Physical iOS 12 launch: success
- On-device diagnostics: **6/6 green**
  - Manifest
  - SQLite
  - Networking
  - Response limit
  - JavaScriptCore
  - Source contract

## Implemented in M2A source

- Repository Catalog API v1 model
- Catalog validation for:
  - repository name
  - repository API version
  - non-empty source list
  - per-source manifest validation
  - duplicate source IDs
- Numeric dotted-version comparison
- Install/update/unchanged/incompatible planning
- App minimum-version compatibility planning
- Local repository fixture covering new install and source update paths
- Duplicate-source rejection regression check
- Expanded on-device diagnostics to **7 checks**, adding `Repository catalog`
- Existing M1A/M1B/M1C diagnostics remain as regression checks

## Validation status for M2A

- Local Swift syntax/type validation: performed before upload package publication
- Xcode 15.4 compile: **pending GitHub Actions**
- Physical iOS 12 diagnostics: **pending after green CI build**

## Known limitations / intentionally deferred

- M2A parses and plans repository catalogs locally; repository URL downloading is M2B.
- Repository persistence metadata and refresh timestamps are not yet exposed through a user-facing manager.
- Script download + SHA-256 verification is deferred to M2B.
- Atomic install/update rollback is deferred to M2B/M2C.
- Cookie storage still uses Foundation's shared cookie store.
- JavaScript execution timeout/cancellation is not yet hardened.
- No real external source is enabled yet.

## Next gate

Upload M2A, obtain a green Xcode 15.4 Actions build, sideload the generated IPA and verify that all seven on-device diagnostics display green check marks.
