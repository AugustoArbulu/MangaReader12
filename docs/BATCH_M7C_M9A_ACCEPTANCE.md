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
