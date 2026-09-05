# Milestone 1C — Networking Hardening Report

Date: 2026-09-05

## Goal

Close the most important networking limitation left by M1A/M1B without raising the iOS 12.0 deployment target.

## Changes

M1C replaces whole-body URLSession completion buffering with `URLSessionDataDelegate` streaming. The source response cap is now checked as bytes arrive, so an oversized source response can be cancelled before the entire body is retained in memory. Declared `Content-Length` is also checked before body delivery when available.

Redirects are revalidated against the same HTTPS/domain source policy and the configured redirect count now produces an explicit failure. URL transport failures are normalized into timeout, cancellation or generic transport categories.

## Diagnostics

The device diagnostic screen now contains six checks. The new `Response limit` fixture fills a small streaming buffer to its exact limit and verifies that the next byte is rejected.

## Acceptance gate

M1C is accepted only after:

1. Xcode 15.4 Debug generic-device build succeeds.
2. Xcode 15.4 Release generic-device build succeeds.
3. Release binary still reports arm64 and minimum iOS 12.0.
4. IPA packaging succeeds.
5. Physical iOS 12 launch succeeds.
6. All **6/6** diagnostics are green.
