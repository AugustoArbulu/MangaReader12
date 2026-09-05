# CHANGELOG

## 0.1.0-m1b-contracts — 2026-09-05

- Accepted M1A after green CI and 4/4 green diagnostics on a physical iOS 12 device.
- Added formal Source API v1 function contract.
- Added typed source DTOs and JavaScript result decoding.
- Added fixture-based validation of `metadata`, `popular`, `search`, `details`, `chapters`, and `pages`.
- Added installed-source persistence repository on SQLite schema v1.
- Expanded on-device diagnostics to five checks.

## 0.1.0-m1a-core — 2026-09-05

- Recorded successful Milestone 0 GitHub Actions + physical iOS 12 launch validation.
- Added core Manga/Chapter/Page models.
- Added source-manifest decoding and validation.
- Added URLSession HTTP client with source-domain policy, HTTPS enforcement, timeout and redirect guard.
- Added JavaScriptCore source runtime and initial Native bridge.
- Added namespaced source storage and cookie bridge foundation.
- Added SQLite database bootstrap and schema v1.
- Added on-device diagnostics for manifest, SQLite, networking policy and JavaScriptCore.
- Kept deployment target locked to iOS 12.0.

## 0.0.1-m0-bootstrap — 2026-09-05

- Established iOS 12.0 as locked deployment target.
- Selected Xcode 15.4 as canonical toolchain.
- Added minimal UIKit bootstrap app.
- Added shared scheme and GitHub Actions workflow.
- Added static iOS 12 guardrails and Mach-O verification.
- Added unsigned IPA packaging and SHA-256 generation.
- Added project state, architecture and compatibility documentation.
