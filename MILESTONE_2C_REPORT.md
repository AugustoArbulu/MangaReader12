# Milestone 2C Report — Atomic Source Install + Rollback

**Status: ACCEPTED — 2026-10-29**

Date: 2026-10-29

## Goal

Make downloaded JavaScript sources safe to install and update without destroying a previously working version when validation or file promotion fails.

## Added

- Per-source installation root under Application Support.
- Staging directory for new source versions.
- SHA-256 verification before the current installation is modified.
- `active` directory for the running version.
- `previous` directory for the last known installed version.
- Update promotion that moves active → previous before staged → active.
- Best-effort automatic restoration if promotion fails.
- Explicit rollback that swaps active and previous.
- Readback validation of `manifest.json` and `source.js`.
- Corrupt-update rejection without modifying the active version.
- Ninth on-device diagnostic: `Source installer`.
- App build number 4.

## Diagnostic coverage

The on-device diagnostic uses a private temporary directory and performs:

1. Fresh install of source 1.0.0.
2. Update to source 2.0.0.
3. Verification that 1.0.0 remains available as `previous`.
4. Rollback to 1.0.0.
5. Verification that 2.0.0 becomes `previous`.
6. Attempted corrupt 3.0.0 update with a bad SHA-256.
7. Verification that the rejected update leaves 1.0.0 active.

No external site is contacted by this diagnostic.

## Scope boundary

M2C establishes safe on-disk source lifecycle primitives. A later repository-manager layer will connect catalog refresh → download → verify → install/update and expose it through UIKit.

## iOS 12 constraints

The implementation uses Foundation/FileManager APIs available to the iOS 12 target. No SwiftUI, Combine, async/await, SceneDelegate, or CryptoKit dependency is introduced.

## Acceptance gate

- Xcode 15.4 CI green.
- Debug and Release generic-device builds green.
- Release binary still arm64 / minimum iOS 12.0.
- IPA packaging succeeds.
- Physical iOS 12 launches build 4.
- **9/9** diagnostics green.


## Acceptance evidence

- PR #6 merged
- Merge commit: `a32fa264d4dfae868880773a7bf30ac078972910`
- Post-merge GitHub Actions run: `40815165763` — success
- Physical iOS 12 launch: success
- On-device diagnostics: **9/9 green**
