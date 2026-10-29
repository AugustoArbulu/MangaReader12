# PROJECT_STATE

## Checkpoint

- Project: MangaReader12 (provisional name)
- Phase: **Milestone 2 — Repositories / Batch M2C**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (4)**

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

- PR #4 CI: green
- Post-merge `main` run `33970456712`: green
- Physical iOS 12 diagnostics: **7/7 green**

## Milestone 2B validation — ACCEPTED

M2B was accepted on 2026-10-29 after:

- PR #5 merged to `main`
- Merge commit `0b8d85ca6600e7018e68d649ee70ae308839ba2c`
- Post-merge `main` run `33971320506`: green
- Debug and Release generic-device builds: success
- Release binary verification: success
- IPA packaging: success
- Physical iOS 12 launch: success
- On-device diagnostics: **8/8 green**

## Implemented in M2C source

- Transaction-like source script staging in Application Support
- Integrity verification before modifying an installed source
- `active` and `previous` source-version directories
- Safe update flow that preserves the prior working version
- Automatic restoration if staged promotion fails
- Explicit rollback that swaps `active` and `previous`
- Installed source manifest/script readback validation
- Rejected corrupt update leaves the active source unchanged
- Expanded on-device diagnostics to **9 checks**, adding `Source installer`
- Build number advanced to **4**

## Validation status for M2C

- Local Swift parsing/type checks: performed before publication
- Local install/update/rollback integration harness: passed
- Xcode 15.4 compile: **pending GitHub Actions**
- Physical iOS 12 diagnostics: **pending after green CI build**

## Known limitations / intentionally deferred

- Source file installation is rollback-safe, but catalog refresh is not yet wired to a user-facing repository manager UI.
- Repository trust/signatures are not implemented; SHA-256 verifies bytes, not publisher identity.
- Cookie storage still uses Foundation's shared cookie store.
- JavaScript execution timeout/cancellation is not yet hardened.
- No real external source is enabled by default.

## Next gate

Get M2C green in GitHub Actions, sideload build 4 and verify **9/9** diagnostics on physical iOS 12.
