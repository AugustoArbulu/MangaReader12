# Batch M6C–M7B Acceptance

- [x] Xcode 15.4 guardrail audit passes.
- [x] Debug generic-device build succeeds.
- [x] Release generic-device build succeeds.
- [x] arm64 / minimum iOS 12 binary verification succeeds.
- [x] IPA packages successfully.
- [ ] Build 10 installs on physical iOS 12.
- [ ] Existing diagnostics remain **11/11**.
- [ ] Demo source updates to **1.2.0**.
- [ ] Atualizações refresh detects **Chapter 2** as a new chapter.
- [ ] Update feed persists and opens Demo Manga details.
- [ ] Category creation works.
- [ ] Demo Manga can be assigned to category Teste.
- [ ] Library category filtering works.
- [ ] Reader Páginas/Webtoon preference persists.
- [ ] Reader LTR/RTL direction preference persists.
- [ ] Reader resumes at the saved last page.
- [ ] Ajustes → Downloads lists completed offline content.
- [ ] Removing a download from Downloads clears offline state/files.
- [ ] Dark Mode regression remains good.
- [ ] History/Library regression remains good.

Do not mark accepted from CI alone; source refresh, UI persistence and reader direction/resume require physical-device validation.


CI evidence:
- PR #12 merged.
- Merge commit: `792fc8852da836da5aaf99bb39e3a29d8b9b8991`.
- Post-merge run `40823779755`: success.
- Physical acceptance remains pending and is intentionally carried into the build-11 checkpoint.
