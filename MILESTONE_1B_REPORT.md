# Milestone 1B Report — Source Contract + Persistence

Date: 2026-09-05
Status: **SOURCE IMPLEMENTED — XCODE/DEVICE VALIDATION PENDING**

## Scope

M1B turns the M1A runtime foundation into an enforceable extension contract and adds the first real persistence repository for installed sources.

## Added

- Source API v1 required functions: `metadata`, `popular`, `search`, `details`, `chapters`, `pages`.
- Typed DTO decoding from JavaScriptCore results using JSON serialization.
- Contract validation before a source is considered usable.
- Fixture source that exercises all six required functions without network access.
- SQLite `SourceRepository` for saving, fetching and removing installed source manifests.
- Persistence round-trip in the SQLite diagnostic.
- Fifth on-device diagnostic: `Source contract`.

## Device diagnostic contract

M1B is accepted only when the screen shows five green checks:

- Manifest
- SQLite
- Networking
- JavaScriptCore
- Source contract

## Deferred

- Streaming response-size cancellation.
- Per-source cookie isolation.
- JavaScript execution timeout/cancellation.
- Remote repository installation/update/rollback.
- Real external source browsing.
