# PROJECT_STATE

## Checkpoint

- Project: MangaReader12 (provisional name)
- Phase: **Milestone 1 — Core / Batch M1C**
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

M1B was accepted on 2026-09-05 after:

- PR #2 CI: green
- Post-merge `main` run `33968911048`: green
- Debug and Release generic-device builds: success
- Release binary verification: success
- IPA packaging: success
- Physical iOS 12 launch: success
- On-device diagnostics: **5/5 green**
  - Manifest
  - SQLite
  - Networking
  - JavaScriptCore
  - Source contract

## Implemented in M1C source

- URLSession data-delegate response streaming instead of whole-body completion buffering
- Response-size enforcement while bytes are arriving
- Early `Content-Length` rejection when the declared body exceeds source policy
- Redirect destination revalidation against HTTPS/domain policy
- Redirect-count enforcement with explicit `tooManyRedirects` failure
- Transport error classification for timeout, cancellation and other URL errors
- Shared streaming buffer primitive used by networking and diagnostics
- Expanded on-device diagnostics to **6 checks**, adding `Response limit`
- M1A/M1B diagnostics remain in place as regression checks

## Validation status for M1C

- Local Swift parser: required before upload package publication
- Xcode 15.4 compile: **pending GitHub Actions**
- Physical iOS 12 diagnostics: **pending after green CI build**

## Known limitations / intentionally deferred

- Cookie storage still uses Foundation's shared cookie store.
- JavaScript execution timeout/cancellation is not yet hardened.
- Repository URL install/update/rollback flow is Milestone 2 work.
- No real external source is enabled yet.

## Next gate

Upload M1C, obtain a green Xcode 15.4 Actions build, sideload the generated IPA and verify that all six on-device diagnostics display green check marks.
