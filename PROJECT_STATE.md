# PROJECT_STATE

## Checkpoint

- Project: MangaReader12 (provisional name)
- Phase: **Milestone 1 — Core / Batch M1B**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (2)**

## Milestone 0 validation — COMPLETE

Milestone 0 passed end-to-end on 2026-09-05:

- GitHub Actions run `33965586070`: success
- Debug device build: success
- Release device build: success
- Release architecture: arm64
- Release Mach-O minimum OS: iOS 12.0
- Release SDK: iOS 17.5
- Sideloadly re-sign/install: success
- Physical iOS 12 device launch: success
- Exact iOS 12.x point release: not yet recorded

## Milestone 1A validation — ACCEPTED

M1A was accepted on 2026-09-05 after:

- Pull request #1 CI: green
- Post-merge `main` run `33967662348`: green
- Debug device build: success
- Release device build: success
- Release binary verification: success
- IPA packaging: success
- Physical iOS 12 launch: success
- On-device diagnostics: **4/4 green**
  - Manifest
  - SQLite
  - Networking
  - JavaScriptCore

## Implemented in M1B source

- Formal Source API v1 required function list:
  - `metadata`
  - `popular`
  - `search`
  - `details`
  - `chapters`
  - `pages`
- Typed DTOs for source metadata and paged manga results
- JavaScriptCore contract validation
- Typed JSON decoding for JavaScript source results
- Local fixture exercising all six source functions
- Installed-source persistence repository over the existing SQLite schema
- Save/fetch/remove round-trip for source manifests
- Expanded on-device diagnostics to **5 checks**, adding `Source contract`
- M1A diagnostics remain in place as regression checks

## Validation status for M1B

- Local source syntax parse: pending before upload package publication
- Xcode 15.4 compile: **pending GitHub Actions**
- Physical iOS 12 diagnostics: **pending after green CI build**

## Known limitations / intentionally deferred

- Response-size cap is still enforced after URLSession returns the response body; streaming cancellation remains a hardening task.
- Cookie storage still uses Foundation's shared cookie store.
- JavaScript execution timeout/cancellation is not yet hardened.
- Repository URL install/update/rollback flow is Milestone 2 work.
- No real external source is enabled yet.

## Next gate

Upload M1B, obtain a green Xcode 15.4 Actions build, sideload the generated IPA and verify that all five on-device diagnostics display green check marks.
