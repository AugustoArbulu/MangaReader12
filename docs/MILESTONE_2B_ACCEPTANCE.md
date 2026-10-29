# Milestone 2B Acceptance

M2B is accepted only when all items below pass.

- [x] GitHub Actions audit passes under Xcode 15.4.
- [x] Debug generic iOS device build succeeds.
- [x] Release generic iOS device build succeeds.
- [x] Release binary verification succeeds with arm64 and minimum iOS 12.0.
- [x] Unsigned IPA is packaged.
- [x] Build number is 3.
- [x] IPA is re-signed/installed with Sideloadly on a physical iOS 12 device.
- [x] App launches and displays **Milestone 2B**.
- [x] All **8/8** diagnostics are green:
  - Manifest
  - SQLite
  - Networking
  - Response limit
  - JavaScriptCore
  - Source contract
  - Repository catalog
  - Repository transport

Do not mark M2B accepted from local syntax checks alone.

**Result: ACCEPTED — 2026-10-29 (8/8 green on physical iOS 12).**
