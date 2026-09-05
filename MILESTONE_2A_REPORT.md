# Milestone 2A Report — Repository Catalog Foundation

Date: 2026-09-05

## Goal

Establish a deterministic repository-catalog format and update planner before enabling network repository installation.

## Added

- `RepositoryCatalog` Codable model, API version 1.
- Catalog-level validation and duplicate source ID rejection.
- Reuse of existing `SourceManifest.validate()` for every catalog entry.
- Numeric dotted-version comparator.
- Source action planner:
  - `install`
  - `update`
  - `unchanged`
  - `incompatible`
- Minimum-app-version handling.
- Fixture diagnostic that proves an installed 1.0.0 source is planned as an update to 2.0.0 while a missing source is planned as a new install.
- Negative duplicate-source test.
- Seventh on-device diagnostic: `Repository catalog`.

## Scope boundary

This batch does not fetch a repository URL or source script from the internet. It deliberately separates catalog semantics from transport and atomic installation. M2B will add HTTPS catalog/script retrieval, integrity verification, and persistent repository refresh state.

## iOS 12 constraints

No SwiftUI, Combine, async/await, SceneDelegate dependency, or post-iOS-12-only API was introduced.

## Acceptance gate

1. GitHub Actions with Xcode 15.4 must pass Debug and Release generic-device builds.
2. Release binary verification must remain arm64 with minimum OS 12.0.
3. IPA packaging must succeed.
4. Physical iOS 12 device must show 7/7 diagnostics green.
