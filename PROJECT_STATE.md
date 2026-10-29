# PROJECT_STATE

## Checkpoint

- Project: MangaReader12
- Phase: **Batch M7C–M9A — visual covers, backup/restore, migration, reader QoL, storage and opportunistic updates**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (16)**

## Accepted physical checkpoints

- Milestone 0 — COMPLETE
- M1A — ACCEPTED (4/4)
- M1B — ACCEPTED (5/5)
- M1C — ACCEPTED (6/6)
- M2A — ACCEPTED (7/7)
- M2B — ACCEPTED (8/8)
- M2C — ACCEPTED (9/9)
- Batch M2D–M3A — ACCEPTED (11/11 + repository/runtime flow)
- Batch M3B–M4A — ACCEPTED (browse/details/chapters)
- Batch M4B–M5A — ACCEPTED (reader + persistent Library)
- Batch M5B — ACCEPTED (custom iOS 12 Dark Mode)
- Batch M5C–M6B — ACCEPTED (progress/history/cache/offline)

## CI-complete but physical acceptance pending

### Batch M6C–M7B / build 10
- PR #12 merged
- Merge commit `792fc8852da836da5aaf99bb39e3a29d8b9b8991`
- Post-merge run `40823779755`: green
- Physical checks for updates/categories/reader preferences/Downloads UI were not reported before work continued.
- Those checks are included in the build-11 physical gate.

## Implemented in build 12 (build-11 mega-batch + hardening)

### M7C — visual manga UI / covers
- Source-returned `cover` URLs render in Browse/search.
- Cover rows now appear in Library, History, Updates and Downloads.
- Manga details use a larger native UIKit cover/header layout.
- Memory + disk cover cache.
- Source-manifest domain allowlist is enforced while browsing; persisted entries may refetch only their exact cover host.

### M8A — backup / restore
- Portable `.mr12backup` format.
- Consistent SQLite snapshot via SQLite backup API.
- Includes Library/manga/chapter/history/categories/repositories/source settings plus selected app/reader settings.
- Excludes downloaded chapter files and installed JavaScript source scripts.
- Portable snapshot removes download DB state and installed-source records so restore does not claim missing files/scripts exist.
- iOS document picker export/import.
- Restores root UI after import.

### M8B — source migration
- Searches other installed + enabled sources for matching title.
- Visual candidate list with covers.
- Transfers Library entry, categories, compatible read/last-page progress and history.
- Chapter mapping prefers chapter number and falls back to normalized chapter name.
- Offline downloads intentionally do not migrate.
- Controlled second source `fixture.altdemo` allows deterministic physical testing.

### M9A — reader quality of life
- Persisted background: black / gray / white.
- Optional page number.
- Keep screen on with prior idle-timer state restored on exit.
- Tap zones: side navigation + center chrome toggle.
- Double-tap zoom.
- Optional Webtoon gap.
- Existing mode, LTR/RTL, brightness, resume and prefetch remain.

### M9A — data / storage
- Data & Storage settings screen.
- Database/download/cache byte totals.
- Clear reader cache.
- Clear cover cache.
- Reindex downloads whose local files are missing.
- Delete all offline downloads without deleting Library/progress/history.
- Existing per-download management is linked from the same screen.

### M9A — background Library updates
- Optional iOS 12 Background Fetch.
- Manual refresh remains the reliable path.
- Background execution is opportunistic and scheduled by iOS, not guaranteed at a precise time.
- Background fetch writes discoveries to the same persistent Updates feed.

### Product audit
- `docs/MIHON_FEATURE_AUDIT_IOS12.md` records current Mihon-inspired features, iOS adaptations, limitations and future priorities.

### Hardening before physical test
- Same-device restore preserves source records only for sources whose active scripts still exist on disk.
- Restore clears excluded offline chapter files so download state and storage remain coherent.
- Loading details for an existing Library entry refreshes its persisted cover/title/status/description/chapters, so older entries can gain cover metadata from updated sources.

## Regression

- Existing 11/11 core diagnostics must remain green.
- iOS deployment target remains 12.0.
- Build 10 physical gate is carried into build 11.

## Build-12 physical acceptance gate

One consolidated test should validate:
1. Build-10 pending flows: Chapter 2 update detection, categories/filtering, reader mode/direction/resume and Downloads screen.
2. Update demo repository: MangaReader12 Demo should become **1.3.0**; also install **MangaReader12 Alt Demo 1.0.0**.
3. Cover thumbnails appear in source browse and persisted screens after the title has been refreshed/saved.
4. Demo Manga details show a large cover, title, metadata, genres and description.
5. Backup: create/export a `.mr12backup`, make a visible state change, restore the backup and verify the earlier Library/category/progress/settings state returns.
6. Migration: with Demo Manga in Library and Alt Demo installed, Details → Migrar → choose Alt Demo. Category and compatible read progress/history should transfer. Downloads should not transfer.
7. Reader QoL: background color, page-number toggle, side tap zones, center chrome toggle, double-tap zoom, keep-screen-on setting, Webtoon gap.
8. Data & Storage: size rows load; reader/cover cache cleanup works; reindex downloads completes; delete-all-downloads clears Offline state without deleting Library/history.
9. Automatic updates toggle can be enabled/disabled. Actual background execution cannot be deterministically forced because iOS 12 schedules Background Fetch.
10. Dark Mode, History, Library, reader and 11/11 diagnostics remain functional.


## Build 13 hotfix — backup validation

- Physical build 12 report: everything worked except backup restore.
- Failure: generated `.mr12backup` was rejected by the restore validator.
- Root cause: restore validation required exact `PRAGMA user_version == 1`, which is unnecessarily brittle for a structurally valid MangaReader12 SQLite snapshot.
- Fix: validate `PRAGMA quick_check`, accept non-future schema versions, and require the full MangaReader12 table set.
- Existing backups remain format-version 1 and should restore without regeneration.
- Do not mark M7C–M9A fully accepted until the build-13 restore retest passes.


## Build 14 hotfix — iOS 12 SQLite validator syntax

- Build 13 physical restore reached the new validator but failed at the integrity query with:
  `The backup database failed validation: could not execute validation query`.
- This isolates the issue to `PRAGMA quick_check(1);`, not the backup envelope or Base64/SQLite extraction.
- Build 14 uses the legacy-compatible `PRAGMA quick_check;` syntax.
- Validation-query errors now expose the actual SQLite prepare/step code and message.
- The same previously exported `.mr12backup` remains the required retest file.


## Build 15 UI hotfix — reader chrome + source icons

- Carries the build-14 backup restore validation compatibility fix.
- Reader center tap now hides:
  - navigation bar,
  - reader bottom controls,
  - main app tab bar.
- All chrome is restored when toggled back on or when leaving the reader.
- Repository source manifests now validate optional icon URLs as HTTPS.
- Repository catalog and installed-source lists display source icons with cached loading and initials fallback.
- Demo repository publishes icons and bumps demo manifests to 1.3.1 / 1.0.1 so existing installs can persist the new icon metadata.

### Build-15 physical gate
1. Reuse the same `.mr12backup` and confirm restore succeeds.
2. In reader, center tap must hide both top and bottom app chrome; second tap restores them.
3. Refresh demo repository and update Demo/Alt Demo to 1.3.1 / 1.0.1.
4. Confirm extension/source icons appear in repository catalog and installed-source list.
5. Confirm 11/11, Dark Mode and existing reading flows remain functional.


## Build 16 hotfix — portable SQLite WAL normalization + immersive reader

Physical build-15 feedback:
- extension/source icons: **working**
- backup restore: failed with `SQLite 14: unable to open database file` during validation
- reader center tap removed tab labels/content but the main tab-bar band remained visible

### Backup fix
- Portable backup payload now gets its SQLite header checked before opening.
- The restored temporary database is opened read-write and normalized with:
  - `PRAGMA temp_store=MEMORY`
  - `PRAGMA journal_mode=DELETE`
- Validation then checks supported schema version + required MangaReader12 tables.
- `quick_check` is removed from the physical restore path because the old backup can be a WAL-mode database image without companion `-wal/-shm` files.
- Existing `.mr12backup` remains the required retest file.

### Reader fix
- Reader is pushed with `hidesBottomBarWhenPushed = true`.
- The main app tab bar is therefore removed by UIKit for the entire reader screen, including its background band/safe-area layout.
- Center tap still toggles the reader-specific top/bottom controls.
- Leaving the reader restores the app tab bar automatically.

### Physical gate
1. Restore the same old `.mr12backup`.
2. Confirm Library/category/progress/settings return.
3. Open reader and confirm the main app tab bar/band is absent entirely.
4. Center tap must hide/show reader chrome without leaving a bottom app band.
5. Reconfirm extension icons remain visible.


## Build 16 physical acceptance — 2026-10-29

- Physical iOS 12 retest: **backup restore PASS** using the existing backup.
- Physical iOS 12 retest: **immersive reader PASS**, including the main bottom tab bar/band.
- Build 16 was merged by PR #18; merge SHA \`c983091a73506d1c079c24223f8fb38c21925ca3\`.
- Post-merge run \`40833175316\`: green.
- Source icons were already physically approved in build 15.
- The two outstanding build-16 blocking defects are now closed.

## Build 17 — M9B reader chapter lifecycle and scale (physical gate pending)

- Source chapter list is ordered by numeric chapter number when all are numbered; otherwise it follows reverse source listing.
- Reader options expose previous/next chapter without building up a reader navigation stack.
- Chapter page resolution keeps local offline download priority, then the installed JS source runtime.
- Optional next-chapter preload starts near the end of the current chapter and caches up to two upcoming images.
- Reader page scaling: fit screen, fit width, fit height, original image point size.
- Scale mode and preloading preference are persisted and included in future backups; existing backups keep default values.
- The last-page progress write snapshots the chapter identity before asynchronous SQLite persistence.
- iOS 12 / UIKit / Swift 5 / Xcode 15.4 guardrails remain unchanged.

### Build 17 consolidated physical gate

1. Open Demo Manga's chapter 1, use Opções → Próximo to go to chapter 2; then Anterior back to chapter 1.
2. Return to details: there must be one reader screen and no stacked readers; tab bar returns normally.
3. Turn next-chapter preload on/off under Ajustes → Leitor and verify chapter navigation still works both ways.
4. Test Fit screen, width, height and original size in page mode, including zoom and rotation; Webtoon should remain full-width.
5. Restore progress by reopening a chapter; check read/history and offline pages still work.
6. Confirm no regressions to backup restore, source icons and iOS 12 diagnostics (11/11).


## Build 17 physical feedback (partial)

- User reports the build 17 **appears to be functioning** on iOS 12.
- Requested a more convenient way to compare page scales directly within a chapter.
- Do **not** mark the full M9B physical gate as passed yet.

## Build 18 UI adjustment — live scale comparison (physical gate pending)

- The chapter's Opções entry opens a compact floating scale comparison strip over the reader.
- Four options: Tela / Largura / Altura / Original. Switching updates already visible images immediately while keeping the strip open.
- A Fechar button and center-tap hide the strip; changing to Webtoon also closes it.
- The current page and saved chapter progress are not reset by scale comparison.
- Existing reader settings and backup preference persistence are reused; no schema changes.
- Consolidated physical retest: same image, switch four scales repeatedly, check page stays the same, closing controls, Webtoon, and chapter navigation.
- Compatibility: iOS 12.0 target, UIKit, no SwiftUI/Combine/async-await.


## Build 18 physical issue / Build 19 hotfix (2026-10-29)

- User physically reported that pressing the centered **Largura/Altura** segments fires the reader's center-tap hide-controls action.
- Build 18 scale UI is otherwise available but **not fully physically approved** because of this gesture collision.
- Build 19 registers UIGestureRecognizerDelegate on the reader's root-level single/double tap recognizers, excluding taps anywhere in visible in-reader overlay panels and nested UIControls.
- Center taps on the manga image remain enabled, and side tap-zone navigation remains unchanged.
- Branch: hotfix-build19-reader-overlay-gesture. The full build-17 M9B suite still has no complete physical acceptance report.
- Physical gate: open scale panel and alternate Tela/Largura/Altura/Original repeatedly, confirm panel stays open, and verify center tap on the manga image still toggles controls as before.
- iOS 12.0 deployment target and UIKit remain locked.


## Build 19 physically accepted (2026-10-29)

- User reports **"esta funcionando agora"** following Build 19 bug fix on physical iOS 12.
- Build 18's centered Largura/Altura touches no longer hide the reader UI.
- Closes the scale-controls gesture-collision hotfix gate, build 19.
- Does not independently assert that every Build 17 navigation/preload test was repeated.

## Build 20 — M10A download management, partial first increment (physical gate pending)

- Downloads refreshes live state while onscreen (1.5s polling) and supports pull-to-refresh.
- Failed downloads can be retried directly from their row; source loader retrieves the latest available manga, chapter and page data before restarting.
- Disable removal of chapters actively being downloaded because current HTTP downloader lacks cancellation.
- Keeps source-domain policy and native storage paths; no SQLite migration.
- Build 20 is not yet complete download queue management: **pause, resume, persistent ordered queue and reorder are future stages**.
- Physical gate: verify failed row's swipe-to-retry where possible; progress refresh and pull-to-refresh; completed offline chapter opens; no mid-write deletion; 11/11 diagnostics and reader scale remain intact.
