# Batch M5B Acceptance — Dark Mode

- [x] Xcode 15.4 guardrail audit passes.
- [x] Debug generic-device build succeeds.
- [x] Release generic-device build succeeds.
- [x] arm64 / minimum iOS 12 binary verification succeeds.
- [x] IPA packages successfully.
- [x] Build 8 installs on physical iOS 12.
- [x] Existing diagnostics remain **11/11**.
- [x] Ajustes → Modo escuro changes the UI immediately.
- [x] Main tabs and tables render correctly in dark mode.
- [x] Source browser and manga details render correctly in dark mode.
- [x] Reader still works and remains black.
- [x] Light mode can be restored immediately.
- [x] Dark mode preference survives closing and reopening the app.

Do not mark accepted from CI alone; visual switching and persistence require a physical-device check.

**Result: ACCEPTED — 2026-10-29. Physical iOS 12: dark mode switched immediately, covered the requested screens, reader remained functional, light mode restored correctly, and the dark preference survived relaunch.**
