# Batch M5C–M6B Acceptance

- [x] Xcode 15.4 guardrail audit passes.
- [x] Debug generic-device build succeeds.
- [x] Release generic-device build succeeds.
- [x] arm64 / minimum iOS 12 binary verification succeeds.
- [x] IPA packages successfully.
- [x] Build 9 installs on physical iOS 12.
- [x] Existing diagnostics remain **11/11**.
- [x] Reaching the final page marks Chapter 1 as **Lido**.
- [x] Histórico shows Demo Manga / Chapter 1.
- [x] Manual read/unread swipe action works.
- [x] Reader brightness control works and restores after leaving reader.
- [x] Chapter download completes and shows **Offline**.
- [x] Offline state survives app relaunch.
- [x] Downloaded Chapter 1 opens from local files.
- [x] Removing offline chapter clears its files/state.
- [x] Dark mode regression remains good.
- [x] Library regression remains good.

Do not mark accepted from CI alone; reading state, brightness and offline storage require physical-device validation.

**Result: ACCEPTED — 2026-10-29. Physical iOS 12: 11/11 regression, read/unread, Histórico, brightness restore, offline download persistence/reopen/removal, Dark Mode and Library all worked.**
