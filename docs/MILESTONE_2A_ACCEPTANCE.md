# Milestone 2A Acceptance

M2A is accepted only when all items below pass.

- [ ] GitHub Actions audit passes under Xcode 15.4.
- [ ] Debug generic iOS device build succeeds.
- [ ] Release generic iOS device build succeeds.
- [ ] Release binary verification succeeds with arm64 and minimum iOS 12.0.
- [ ] Unsigned IPA is packaged.
- [ ] IPA is re-signed/installed with Sideloadly on a physical iOS 12 device.
- [ ] App launches and displays **Milestone 2A**.
- [ ] All **7/7** diagnostics are green:
  - Manifest
  - SQLite
  - Networking
  - Response limit
  - JavaScriptCore
  - Source contract
  - Repository catalog

Do not mark M2A accepted from local syntax checks alone.
