# Batch M7C–M9A Acceptance

## CI / binary
- [ ] Xcode 15.4 guardrail audit passes.
- [ ] Debug generic-device build succeeds.
- [ ] Release generic-device build succeeds.
- [ ] arm64 / minimum iOS 12 binary verification succeeds.
- [ ] IPA packages successfully.

## Physical iOS 12 regression
- [ ] Build 11 installs and launches.
- [ ] Existing diagnostics remain **11/11**.
- [ ] Dark Mode, Library and History remain functional.

## Carried build-10 checks
- [ ] Demo source update flow / Chapter 2 Updates feed works.
- [ ] Categories create/assign/filter works.
- [ ] Reader mode + LTR/RTL preferences and resume work.
- [ ] Downloads screen reflects/removes offline content.

## Visual covers
- [ ] Demo source updates to **1.3.0**.
- [ ] MangaReader12 Alt Demo **1.0.0** installs.
- [ ] Source browse/search shows cover thumbnails.
- [ ] Library/History/Updates/Downloads show covers when cover metadata is available.
- [ ] Manga details show the large cover/header layout.

## Backup
- [ ] Backup can be exported with the system file picker.
- [ ] Backup can be imported/restored.
- [ ] Library/category/progress/settings state is restored after a visible state change.
- [ ] Restore does not falsely mark missing downloads/source scripts as installed.

## Migration
- [ ] Main Demo Manga can migrate to MangaReader12 Alt Demo.
- [ ] Category assignment transfers.
- [ ] Compatible chapter progress/read state transfers.
- [ ] History maps to the migrated entry when possible.
- [ ] Offline downloads are not transferred.

## Reader QoL
- [ ] Black/gray/white reader backgrounds work.
- [ ] Page-number toggle works.
- [ ] Tap zones navigate and center tap hides/shows reader chrome.
- [ ] Double-tap zoom works.
- [ ] Webtoon gap setting works.
- [ ] Keep-screen-on setting does not leave the app idle timer forced after exiting reader.

## Data / storage
- [ ] Storage-size rows load.
- [ ] Reader cache clear works.
- [ ] Cover cache clear works and covers reload.
- [ ] Reindex downloads completes.
- [ ] Delete-all-downloads clears offline state/files without deleting Library/history.

## Background updates
- [ ] Automatic-update toggle persists.
- [ ] Manual Updates refresh remains functional.
- [ ] No requirement is placed on observing an actual background fetch; iOS 12 decides execution timing.

Do not mark accepted from CI alone.
