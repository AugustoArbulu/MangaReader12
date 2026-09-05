# PROJECT_STATE

## Checkpoint

- Project: MangaReader12 (provisional name)
- Phase: **Milestone 1 — Core / Batch M1A**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version prepared by this patch: **0.1.0 (2)**

## Milestone 0 validation — COMPLETE

Milestone 0 passed end-to-end on 2026-09-05:

- GitHub Actions run `33965586070`: success
- Debug device build: success
- Release device build: success
- Release architecture: arm64
- Release Mach-O minimum OS: iOS 12.0
- Release SDK: iOS 17.5
- Unsigned IPA SHA-256: `dee30c6024156ed740dff9a358f0804f768d6a8a41f024009e0d398e2e5fa10b`
- Sideloadly re-sign/install: success
- Physical iOS 12 device launch: success
- Exact iOS 12.x point release: not yet recorded

## Implemented in M1A source

- Core `Manga`, `Chapter`, `Page` models
- Source manifest Codable model + validation
- Native URLSession networking foundation
- HTTPS/domain allowlist policy
- request timeout, redirect guard and response-size guard
- JavaScriptCore source runtime
- `Native` JavaScript bridge foundation:
  - log
  - namespaced source storage
  - cookie get/set
  - URL resolution
  - GET/POST
  - generic JSON HTTP request
- SQLite database bootstrap and schema v1
- Initial tables for library, manga, chapters, categories, history, downloads, sources, repositories, source settings and migration map
- On-device M1A diagnostics for manifest, SQLite, network policy and JavaScriptCore bridge

## Validation status for M1A

- Swift syntax parse: passed locally for every new/changed Swift source
- `SourceManifest` type-check on available non-Apple host compiler: passed
- plist syntax: passed locally
- pbxproj plist syntax: passed locally
- Xcode 15.4 compile: **pending GitHub Actions after patch upload**
- Physical iOS 12 diagnostics: **pending after green CI build**

## Known limitations / intentionally deferred

- Response-size cap is currently enforced after URLSession returns the response body; streaming cancellation is deferred to hardening.
- Cookie storage currently uses Foundation's shared cookie store. Per-source cookie isolation and WKWebView cookie synchronization are later work.
- JavaScript execution timeout/cancellation is not yet hardened.
- Repository install/update/rollback flow is Milestone 2 work.
- No real external source is enabled yet.

## Next gate

Upload M1A, obtain a green Xcode 15.4 Actions build, sideload the generated IPA and verify that all four on-device diagnostics display green check marks.
