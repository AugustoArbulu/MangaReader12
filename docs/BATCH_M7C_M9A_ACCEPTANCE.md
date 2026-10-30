# Batch M7C–M9A Acceptance

## CI / binary
- [ ] Xcode 15.4 guardrail audit passes.
- [ ] Debug generic-device build succeeds.
- [ ] Release generic-device build succeeds.
- [ ] arm64 / minimum iOS 12 binary verification succeeds.
- [ ] IPA packages successfully.

## Physical iOS 12 regression
- [ ] Build 12 installs and launches.
- [x] Existing diagnostics remain **11/11**.
- [x] Dark Mode, Library and History remain functional.

## Carried build-10 checks
- [x] Demo source update flow / Chapter 2 Updates feed works.
- [x] Categories create/assign/filter works.
- [x] Reader mode + LTR/RTL preferences and resume work.
- [x] Downloads screen reflects/removes offline content.

## Visual covers
- [x] Demo source updates to **1.3.0**.
- [x] MangaReader12 Alt Demo **1.0.0** installs.
- [x] Source browse/search shows cover thumbnails.
- [x] Library/History/Updates/Downloads show covers when cover metadata is available.
- [x] Manga details show the large cover/header layout.

## Backup
- [x] Backup can be exported with the system file picker.
- [ ] Backup can be imported/restored.
- [ ] Library/category/progress/settings state is restored after a visible state change.
- [ ] Restore does not falsely mark missing downloads/source scripts as installed.

## Migration
- [x] Main Demo Manga can migrate to MangaReader12 Alt Demo.
- [x] Category assignment transfers.
- [x] Compatible chapter progress/read state transfers.
- [x] History maps to the migrated entry when possible.
- [x] Offline downloads are not transferred.

## Reader QoL
- [x] Black/gray/white reader backgrounds work.
- [x] Page-number toggle works.
- [x] Tap zones navigate and center tap hides/shows reader chrome.
- [x] Double-tap zoom works.
- [x] Webtoon gap setting works.
- [x] Keep-screen-on setting does not leave the app idle timer forced after exiting reader.

## Data / storage
- [x] Storage-size rows load.
- [x] Reader cache clear works.
- [x] Cover cache clear works and covers reload.
- [x] Reindex downloads completes.
- [x] Delete-all-downloads clears offline state/files without deleting Library/history.

## Background updates
- [x] Automatic-update toggle persists.
- [x] Manual Updates refresh remains functional.
- [ ] No requirement is placed on observing an actual background fetch; iOS 12 decides execution timing.

Do not mark accepted from CI alone.


## Hardening checks
- [ ] Restoring a backup on the same device keeps locally installed sources available when their scripts are still present.
- [ ] Download files excluded by the backup are cleared during restore and do not remain as ghost storage.
- [ ] Opening details of an older Library entry refreshes its persisted cover metadata.


## Build 12 physical result — partial acceptance

User reported that all requested functionality worked **except backup restore**. Export succeeded, but restoring the generated backup failed with:

`The backup database failed validation.`

Build 13 fixes the overly strict validation rule. The existing exported `.mr12backup` should be reused for the retest.

Remaining physical gate:
- [ ] Restore the existing backup successfully on build 13.
- [ ] Confirm restored Library/category/progress/reader-settings state.
- [ ] Confirm installed source scripts on the same device remain usable after restore.


## Build 13 physical result

Restore still failed, now with the more specific message:

`The backup database failed validation: could not execute validation query.`

This confirms the backup reaches SQLite validation successfully. Build 14 replaces the iOS-12-incompatible `PRAGMA quick_check(1)` syntax with `PRAGMA quick_check`.

Remaining physical gate:
- [ ] Restore the same existing `.mr12backup` successfully on build 14.
- [ ] Confirm restored Library/category/progress/reader-settings state.
- [ ] Confirm installed source scripts on the same device remain usable after restore.


## Build 15 UI additions

- [ ] Reuse the same existing `.mr12backup` and confirm restore succeeds.
- [ ] Reader center tap hides the navigation bar, reader controls **and main bottom tab bar**.
- [ ] Second center tap restores all reader/app chrome.
- [ ] Leaving reader while chrome is hidden restores the tab bar for the rest of the app.
- [x] Refresh demo repository; source icons appear in the repository catalog.
- [ ] Update MangaReader12 Demo to **1.3.1** and Alt Demo to **1.0.1**.
- [x] Installed-source list shows the repository-provided icons after update.
- [ ] Sources without an icon still show a readable initials fallback.


## Build 16 final restore/reader retest

Build-15 physical result:
- [x] Repository/installed-source icons work.
- [ ] Backup restore still failed with `SQLite 14: unable to open database file`.
- [ ] Main tab-bar background band still remained in reader after center tap.

Build-16 required retest:
- [ ] Restore the same existing `.mr12backup` successfully after WAL→DELETE normalization.
- [ ] Restored Library/category/progress/settings state is correct.
- [ ] Installed source scripts remain usable after restore.
- [ ] The main app tab bar (including its background band) is absent throughout the reader screen.
- [ ] Center tap hides/shows reader-specific navigation/controls cleanly.
- [ ] Leaving reader restores the main app tab bar.


## Build 16 — physical acceptance report (2026-10-29)

User tested the build-16 IPA on physical iOS 12 and reported both required gates as approved:
- [x] Backup restore with the previous \`.mr12backup\` — PASS.
- [x] Immersive reader: bottom app tab bar/band removed — PASS.

The build-16 blockers are closed. The additional legacy unchecked rows above
record earlier checkpoints and should not be mistaken for new build-16 failures.

## Build 17 — M9B physical gate (pending)

- [ ] Reader previous/next chapter opens correct chapter and returns without stacking.
- [ ] Next-chapter preload toggle persists; source failures do not interrupt current reading.
- [ ] Offline-first chapter switching works without needing source network access.
- [ ] Fit-screen / fit-width / fit-height / original scale modes are usable with zoom.
- [ ] Webtoon remains continuous and full width after selecting a scale option.
- [ ] Chapter read progress, History and last-page resume remain correct.
- [ ] Bottom tab bar, backups, icons and 11/11 diagnostics remain regression-free.


## Build 17 feedback / Build 18 focused retest

- [x] Build 17 preliminary device report: appears to function.
- [ ] Full build 17 physical acceptance not yet confirmed.
- [ ] While reading, Opções → Comparar escalas displays Tela/Largura/Altura/Original.
- [ ] Switching scale repeatedly gives immediate visual comparison on the SAME image without a reader reload.
- [ ] Fechar, center tap, and switching to Webtoon hide the comparison controls.
- [ ] Chosen scale persists for the next chapter; current page, zoom, offline, and reader tab bar remain functional.


## Build 18 feedback / Build 19 gesture hotfix

- [x] Build 18 scale comparison panel is available in physical iOS 12 reader.
- [ ] Build 18 scale controls not fully approved: Largura/Altura center touches also hide chrome.
- [ ] Build 19: all four scale controls can be tapped, repeatedly, without hiding the panel.
- [ ] Build 19: center tap on manga **image** still toggles the reader chrome.
- [ ] Build 19: side tap-zones still navigate in LTR/RTL; brightness/direction controls do not turn pages.
- [ ] Build 19: page, progress, Webtoon, back navigation and immersive bottom-tab-bar behavior remain intact.


## Build 19 — physical acceptance

- [x] User confirms live reader scale controls work after the gesture fix in Build 19.
- [x] The specifically reported center tap / Largura/Altura collision is resolved.
- [ ] Remaining independent M9B regression checks are not all explicitly reconfirmed.

## Build 20 — Downloads M10A (physical gate pending)

- [ ] Downloads progress/state updates automatically while view is onscreen.
- [ ] Pull-to-refresh updates the list.
- [ ] A failed download can be retried by swiping and selecting Tentar novamente.
- [ ] Retry uses original source and chapter, and downloads become usable offline.
- [ ] A currently downloading row cannot be removed mid-write.
- [ ] No regression to reader gestures, backups, source icons, iOS 12 diagnostics.


## Build 20 physical acceptance (2026-10-30)

- [x] User reports **all tested build-20 features working** on physical iOS 12.
- [x] The build-20 physical gate for progress refresh/retry accepted as reported.
- [x] The build-19 reader-scale gesture bug remains resolved.

## Build 21 M10B foreground queue — pending device QA

- [ ] Two downloads are serialized (one running, one queued).
- [ ] Pause active and queued downloads using swipe; state/progress remain correct.
- [ ] Resume during the same app session keeps completed page files.
- [ ] Prioritize queued job and observe order change.
- [ ] Completed chapter opens offline.
- [ ] Active job cannot be removed mid-write.
- [ ] After app restart, stale running/queued jobs become retryable; paused resume falls back to fresh URLs.
- [ ] No regression to scale comparison, iOS 12 diagnostics, Library and backup.


## Build 21 physical testability blocker / Build 22 focused QA

- [x] User reports Demo chapter downloads finish in ~0.1s; manual Pause/Resume is not possible in this time.
- [ ] Build 21 queue feature still requires physical acceptance (0.1s completion proves only completion).
- [ ] Build 22 Downloads → "Teste 8s: ON" slows **only** fixture.localdemo/fixture.altdemo.
- [ ] After enabling, start Demo download and confirm 8s window allows Pausar from Downloads.
- [ ] Retomar completes and offline pages remain readable.
- [ ] With multiple chapters, verify queued state and Priorizar without timing race.
- [ ] Turn "Teste 8s: OFF" again; confirm Demo downloads restore normal speed.
- [ ] Real sources and existing Backup/Reader behavior unaffected.


## Build 22 physical feedback (2026-10-30)

- [x] The user confirmed the controlled slow Demo test works on a physical iOS 12 device.
- [x] The original 0.1s Demo-download limitation no longer blocks manual testing.
- [ ] Individual multi-chapter queue/priority/relaunch cases were not independently detailed.

## Build 23 restart recovery (focused QA pending)

- [ ] Begin Teste 8s chapter download, let one page finish, force-close; reopen and complete using existing page files.
- [ ] Paused chapter remains paused after relaunch and only resumes when selected.
- [ ] Queued priority survives force-close/reopen.
- [ ] Interrupted or expired source URLs fail safely and permit retry.
- [ ] No regression to offline chapter reading, backup and reader scale.


## Build 23 physical acceptance (2026-10-30)

- [x] User explicitly reports "tudo funcionando" after Build 23 physical iPhone test.
- [x] M10C foreground restart download restoration accepted as user-reported.
- [x] Retained Build 22 slow Demo testing and Build 19 live reader scale improvements.
- [ ] True background transfer while the app is terminated is outside the implementation scope.

## Build 24 M11A — global search QA (pending)

- [ ] Explorar's magnifying-glass button opens Busca global.
- [ ] Query with two enabled Demo sources shows source-qualified results.
- [ ] Tapping result opens that exact source's Manga Details and existing reader.
- [ ] A nonmatching query gives clear empty results; cancel/re-search ignores earlier asynchronous responses.
- [ ] Disable one source; only enabled sources are searched; partial failures do not crash.
- [ ] Reader, downloads, backup and iOS 12 diagnostics remain stable.


## Build 24 physical acceptance — 2026-10-30

- [x] User reports Build 24 global search worked on iPhone.
- [x] Build 24 M11A baseline accepted as user-reported.
- [ ] Independent partial-error and cancellation edge cases not separately reported.

## Build 25 M11B — consolidated new-feature test (pending)

- [ ] Explore -> Global Search returns results from active Demo sources and opening a result works.
- [ ] Fontes picker filters to a single source, then Todas restores both.
- [ ] Search cancellation and changed query do not append stale matches.
- [ ] Carregar mais appears only for a source with hasNextPage; new pages append without source/manga duplicates.
- [ ] Explore -> source actions -> Informações e dados displays correct manifest values.
- [ ] Runtime metadata diagnostic completes.
- [ ] Source JS storage reset requires confirmation and does not affect Library, downloads, history, reader settings.
- [ ] Existing reader scales, offline downloads and iOS 12 diagnostics work.


## Build 26 MangaDex physical test (2026-10-30)

- [x] Extension installed and reached a live network request.
- [x] On-device SSL transport error -1200 reported on Abrir source.
- [ ] Live MangaDex searching, chapter reading, downloading not yet accepted.

## Build 27 TLS diagnostic test

- [ ] Safari result from https://api.mangadex.org/ping recorded.
- [ ] App probe compares MangaDex via HTTPClient and URLSession.shared.
- [ ] GitHub and example.com HTTPS controls help distinguish host-only and all-host failures.
- [ ] Underlying TLS/CFNetwork error plus iOS minor version copied.
- [ ] Source remains installed, no trust exception or altered TLS policy.


## Build 27 confirmed device differential results

- [x] iOS 12.5.8 reported.
- [x] Safari ping => pong.
- [x] HTTPClient and URLSession on MangaDex API => -1200 / -9836.
- [x] Standard URLSession on MangaDex site => -1200 / -9836.
- [x] GitHub raw and example.com HTTPS controls => HTTP 200.
- [ ] Secure alternate transport for MangaDex is not yet verified.

## Build 28 additional controlled TLS probes

- [ ] WKWebView to MangaDex API returns pong, a TLS error, or controlled timeout.
- [ ] NWConnection native TLS handshake returns ready, concrete error or controlled timeout.
- [ ] Full report can be copied from Source Information screen.
- [ ] No modification to installed source, library/downloads or certificates; Demo still works.
