# Milestone 1B Acceptance

M1B is accepted only when all conditions below are true.

- [ ] GitHub Actions uses Xcode 15.4.
- [ ] iOS 12 audit passes.
- [ ] Debug generic-device build succeeds.
- [ ] Release generic-device build succeeds.
- [ ] Mach-O still reports `minos 12.0`.
- [ ] Release binary remains arm64.
- [ ] IPA artifact is generated.
- [ ] IPA installs through Sideloadly on the physical iOS 12 test device.
- [ ] App launches without terminating.
- [ ] Manifest diagnostic is green.
- [ ] SQLite persistence diagnostic is green.
- [ ] Networking policy diagnostic is green.
- [ ] JavaScriptCore Native bridge diagnostic is green.
- [ ] Source contract diagnostic is green.

Do not promote M1B as canonical if any check is missing.
