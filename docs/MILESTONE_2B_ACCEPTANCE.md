# Milestone 2B Acceptance

M2B is accepted only when all items below pass.

- [ ] GitHub Actions audit passes under Xcode 15.4.
- [ ] Debug generic iOS device build succeeds.
- [ ] Release generic iOS device build succeeds.
- [ ] Release binary verification succeeds with arm64 and minimum iOS 12.0.
- [ ] Unsigned IPA is packaged.
- [ ] Build number is 3.
- [ ] IPA is re-signed/installed with Sideloadly on a physical iOS 12 device.
- [ ] App launches and displays **Milestone 2B**.
- [ ] All **8/8** diagnostics are green:
  - Manifest
  - SQLite
  - Networking
  - Response limit
  - JavaScriptCore
  - Source contract
  - Repository catalog
  - Repository transport

Do not mark M2B accepted from local syntax checks alone.
