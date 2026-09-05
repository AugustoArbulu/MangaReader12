# Milestone 1A Report — Core Foundation

Date: 2026-09-05
Version: 0.1.0 (2)
Status: **SOURCE IMPLEMENTED — XCODE/DEVICE VALIDATION PENDING**

## Scope

This batch moves the project from feasibility/bootstrap into the first functional Core layer without yet implementing repository browsing or a real manga source.

## Added

1. Core data models for Manga, Chapter and Page.
2. Source manifest decoding and fail-closed validation.
3. URLSession HTTP client with domain/scheme policy.
4. JavaScriptCore runtime with a `Native` bridge foundation.
5. Namespaced source key/value storage.
6. Foundation cookie get/set bridge.
7. SQLite schema v1 and Application Support database creation.
8. On-device diagnostics visible in the bootstrap UI.

## Device diagnostic contract

After a successful build and sideload, the screen must show four green checks:

- Manifest — Decode + validation OK
- SQLite — Schema v1 + WAL OK
- Networking — HTTPS allowlist OK
- JavaScriptCore — Native bridge OK

Any red item blocks promotion of M1A.

## What is not claimed yet

- No claim that M1A compiles under Xcode 15.4 until GitHub Actions runs it.
- No claim that SQLite3/JavaScriptCore execute correctly on the target iOS 12 device until the diagnostic build is launched.
- No real external source, repository installer, reader, library UI or download manager is implemented in M1A.

## Milestone 1 continuation after M1A acceptance

M1B should add persistence APIs/repositories, stronger networking response streaming limits, source runtime method contracts and fixture-based bridge tests. Milestone 2 then starts the actual repository/source installation flow.
