# Batch M5C–M6B Acceptance

- [ ] Xcode 15.4 guardrail audit passes.
- [ ] Debug generic-device build succeeds.
- [ ] Release generic-device build succeeds.
- [ ] arm64 / minimum iOS 12 binary verification succeeds.
- [ ] IPA packages successfully.
- [ ] Build 9 installs on physical iOS 12.
- [ ] Existing diagnostics remain **11/11**.
- [ ] Reaching the final page marks Chapter 1 as **Lido**.
- [ ] Histórico shows Demo Manga / Chapter 1.
- [ ] Manual read/unread swipe action works.
- [ ] Reader brightness control works and restores after leaving reader.
- [ ] Chapter download completes and shows **Offline**.
- [ ] Offline state survives app relaunch.
- [ ] Downloaded Chapter 1 opens from local files.
- [ ] Removing offline chapter clears its files/state.
- [ ] Dark mode regression remains good.
- [ ] Library regression remains good.

Do not mark accepted from CI alone; reading state, brightness and offline storage require physical-device validation.
