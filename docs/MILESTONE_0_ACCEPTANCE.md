# Milestone 0 acceptance checklist

Milestone 0 is complete only after every mandatory gate below is recorded as PASS.

- [ ] Xcode 15.4 selected in CI (`xcodebuild -version`).
- [ ] iOS SDK 17.5 detected.
- [ ] Project and shared scheme load successfully.
- [ ] Debug generic-device build succeeds with code signing disabled.
- [ ] Release generic-device build succeeds with code signing disabled.
- [ ] Release binary contains arm64.
- [ ] Release Mach-O reports minimum OS 12.0.
- [ ] Unsigned IPA is generated and SHA-256 recorded.
- [ ] IPA is accepted by Sideloadly for re-signing.
- [ ] App installs on the user's target iOS 12 device.
- [ ] App launches and displays the Milestone 0 screen.
- [ ] Device model + exact iOS 12.x version are recorded.
- [ ] No runtime crash is observed during a short launch/background/foreground smoke test.

A green GitHub Actions build alone is **not** sufficient to call Milestone 0 complete; physical iOS 12 launch is the final gate.
