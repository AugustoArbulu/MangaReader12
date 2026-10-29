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
