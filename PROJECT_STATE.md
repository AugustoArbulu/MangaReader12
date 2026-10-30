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


## Build 20 — Physical acceptance (2026-10-30)

- User explicitly reported **"tudo funcionando"** after physically testing the Build 20 iOS 12 IPA.
- Build 20 Downloads live progress/pull-to-refresh/retry is **physically accepted**.
- Pre-existing Build 19 scale-panel gesture fix remains accepted.

## Build 21 — M10B shared foreground download queue (physical gate pending)

- All callers of ChapterDownloadManager.defaultManager share one retained queue coordinator in the running app.
- One active chapter transfer at a time; further chapters enter **queued** state, retaining source-specific HTTPS/allowed-domain policy.
- Pausing a queued/active download updates SQLite and cancels only its active URLSession task.
- Resuming inside the current app session keeps the atomically completed page files and continues with the first incomplete page.
- Queued chapters may be prioritized via the Downloads row swipe action.
- Removing an active transfer is prohibited to avoid deleting files under a live writer.
- Downloads row swipe: Pausar (queued/downloading), Retomar (paused), Priorizar (queued), retry (failed), remove (other states).
- The Downloads timer only reloads the table when records change; swipe menus remain usable.
- Cold app relaunch cannot reconstruct pending network requests yet. Interrupted queued/running rows become **failed / retryable** on manager initialization. Paused rows are shown as paused; Retomar re-resolves source pages and restarts from page zero if the in-memory job no longer exists.
- Persistent resume across app relaunch, serialized job metadata and durable queue ordering are **future work**, not implemented here.
- All prior offline files, Library/history/backup/source behavior is unchanged. No schema migration.
- Maintains iOS 12.0, UIKit/AppDelegate, Xcode 15.4 / Swift 5 language mode.

### Focused Build 21 physical gate

1. Start a chapter download and pause while progress is visible; ensure percentage stays stable.
2. Resume; percentage should continue from previously completed pages and finish offline.
3. Queue two downloads from the source chapter list; confirm one runs and the other shows "Na fila".
4. Prioritize the queued chapter, pause/resume queued, then confirm the next transfer progresses.
5. Try swiping while a chapter downloads: it must not offer unsafe removal.
6. Optional: force-close app with queued/paused state; reopen, confirm interrupted rows become retryable and "Retomar" on an old paused record restarts via source.
7. Confirm no regressions to reader scale, backup, source icons and on-device 11/11 diagnostics.


## Build 21 physical gate blocker (2026-10-30)

- User cannot practically test the queue: bundled Demo source downloads in approximately **0.1 seconds**.
- This **does not constitute failure or acceptance** of queue/pause/resume; device QA is blocked by an unrealistic fixture duration.
- Do not request pause/priority tests on unrestricted instant Demo again.

## Build 22 — opt-in Demo download slow-test mode (physical gate pending)

- Downloads top-right "Teste 8s: OFF / ON" switch is stored in UserDefaults and defaults to OFF.
- When ON, only fixture.localdemo/fixture.altdemo waits 8 seconds **asynchronously** before each page starts; real sources always download at normal speed.
- Pending delayed work checks active job, paused state, page index and serial before issuing HTTP; pause/resume is safe even during a simulated delay.
- No artificial image data; image bytes and offline verification still come from existing source URL and hardened HTTPClient.
- Physical test: turn on Teste 8s in Downloads, open Demo manga and download a chapter, navigate back to Downloads and pause. Verify stable progress during pause, resume and eventual offline completion; optional two queued/priority test. Disable the switch after QA.
- Test mode is not an app performance setting and does not change the downloading implementation outside fixtures.


## Build 22 — physical feedback / timed Demo QA (2026-10-30)

- User reported "funcionou" after installing Build 22 and using the deterministic Demo speed-control workflow.
- This confirms the timed test path works on-device and removes the original 0.1s manual-test blocker.
- The user did not separately detail every pause, reorder and multiple-download scenario; do not infer a full regression matrix PASS.

## Build 23 — M10C restart-safe foreground download recovery (physical gate pending)

- Writes a private Codable _download-plan.json alongside each queued chapter's page files, with original source manifest, page URLs/headers and saved queue priority. Applies file protection to this sensitive app-sandbox data where available.
- DefaultManager restores valid plans on first creation after launch, checks source/manga/chapter identities, stored directory path and number of pages.
- Restores nextIndex from a verified contiguous prefix of nonempty page-%05d.bin files. A partially downloaded current page is fetched afresh; completed pages are reused.
- Database recovery transitions interrupted queued/active jobs into ordered foreground work and leaves manually paused jobs paused.
- Persists priority promotions across restarts; invalid plans remain retryable and do not destroy existing pages.
- Cleans recovery plan when job succeeds/fails, preserving offline image files. No SQLite migrations.
- iOS 12.0, UIKit/AppDelegate, Swift 5, Xcode 15.4, source-allowed domain policy and no anti-bot bypass remain in force.
- **Limitations:** no guarantee of transfer while backgrounded/terminated. Some sources may expire image URLs or authentication headers; an expired restored job may fail and should be retried to fetch fresh source data.

### Build 23 focused physical gate
1. In Downloads switch on Teste 8s and begin a Demo chapter download.
2. Let at least one page finish; force-close the app while the next page is pending (not just return to home).
3. Reopen Downloads. It should resume the remaining pages without resetting the downloaded prefix. Allow offline completion.
4. Start another chapter, pause it, force-close and reopen: it must remain Pausado until you explicitly select Retomar.
5. Queue multiple chapters, Priorizar one, force-close and reopen: priority should remain.
6. Return Teste 8s to OFF; verify existing offline chapters and reader controls still work.


## Build 23 physical acceptance — 2026-10-30

- User explicitly reported **"tudo funcionando"** on Build 23, following the requested restart-download-recovery tests.
- Record the Build 23 M10C device gate as **PASS (user-reported)**.
- This covers foreground restoration after closing/reopening the app and the prior controlled Demo-download workflow as reported.
- Distinguish foreground restart recovery from true iOS background downloads, which remain unsupported.

## Build 24 — M11A search across installed sources (physical gate pending)

- Explore now presents a magnifying-glass action that pushes **Busca global** without changing bottom tabs.
- Search issues source API v1 search(query, page=1, filters=[]) sequentially to each enabled installed JavaScript source; one failing source does not hide successful results.
- First page only, capped at 40 matching items per source. Status reflects sources queried, total matches, and failures. This bounded search prioritizes old-device memory and runtime safety.
- Results retain the exact source record (manifest/id/domains) and open original MangaDetailsViewController after loading that source's JavaScript runtime.
- Generation token invalidates stale async results after query changes or cancellation.
- User's current iOS 12 source engine is unchanged; Android APK compatibility/Keiyoushi direct execution is **not** implied.
- Does not change download, backup, reader or SQLite schema, and does not bypass site restrictions.
- Physical check: install the two bundled Demo sources, search a shared sample manga title, verify results show source names, tap one result, open details/chapter. Search a nonmatch and cancel. Confirm original per-source search remains functional.


## Build 24 physically accepted — 2026-10-30

- User reports "funcionou" after using Build 24 global search on their iPhone.
- M11A global JS source search baseline is accepted.
- No claim that all source failure/cancellation edge cases received separate physical checks.

## Delivery cadence (requested 2026-10-30)

- User prefers meaningful multi-feature increments and one grouped device test instead of frequent tiny IPA builds.
- Prioritize cohesive milestone bundles, compile/CI and static QA before delivery, reserve focused physical validation only for interface/device interactions not reproducible in CI.
- Work only on feature branches and merge after green push + PR CI; preserve iOS 12, repo main and existing accepted features.

## Build 25 M11B — Global search & source-tools batch (device QA pending)

1. Global search displays a Load more footer for sources advertising hasNextPage. Each source advances its own page counter; up to 5 pages/source and at most 40 results/page are rendered.
2. Fontes opens an enabled-source checklist. All enabled sources are selected by default. Aplicar changes the search scope and invalidates old async callbacks.
3. Repeated manga IDs are de-duplicated within the same source; distinct source records are preserved.
4. Exploration source action "Informações e dados da fonte" displays manifest metadata, allowlisted domains and count of stored source-local JS preference keys.
5. Explicit runtime metadata check and confirmation-gated deletion of only JS sources.<sourceID>.storage.* values. User must opt in; no automatic clearing.
6. The source reset does not touch downloads/Library/history/reader prefs, nor cookies. Source runtime and source API remain unchanged.
7. No alteration of downloader, backup, SQLite schema, reader, or deployment target. Swift 5/UIKit/iOS 12.0.

### Grouped device acceptance

- Open Explorar -> lupa -> Buscar. Search with both Demo sources enabled and confirm source-tagged hits and opening manga details.
- Open Fontes, select only one source, apply, and confirm only that source appears; select Todas to restore.
- If a source returns hasNextPage, use Carregar mais resultados and confirm page append, stable source labels, no duplicates. Demo fixtures may not have pagination; no synthetic extra pages are asserted.
- Open Explorar -> installed source -> Informações e dados da fonte. Inspect manifest and run Verificar runtime.
- In source tools, check confirmation before resetting storage; cancel first. Optional destructive clear only if testing disposable Demo settings, and verify Library/downloads remain intact.
- Verify Backup/Reader/Downloads and 11/11 diagnostics without repeating exhaustive old feature tests.


## Build 25 physical feedback (2026-10-30)

- User reports "tudo parece estar funcionando" after testing Build 25 search filters, source tools and existing experience.
- Mark the examined Build 25 flow as provisional physical PASS; pagination with hasNextPage and source-storage destructive reset were not independently evidenced.
- User prefers larger cohesive batches rather than a new IPA for each tiny feature.

## Build 26 M12A — first real source trial, MangaDex (device QA pending)

- Source API v1 now supports optional asynchronous callbacks as trailing arguments for calls decoded by JavaScriptSourceRuntime. Synchronous source fixture functions remain compatible. A 25-second timeout prevents indefinite waits.
- Separate pinned experimental MangaDex catalog: fixtures/repository-mangadex.json; JS script: fixtures/source-mangadex.js, SHA-256 38b360b0d08cfd7d2ecc204749408471a535b8f405a20ada4d5a50a894f78188.
- Source features: search/popular, covers, manga details, first 100 English chapters, data-saver page URLs. Search uses 20 items per page and allowed-domain HTTPS; API 429 is surfaced, not bypassed.
- Crediting MangaDex and scanlation groups is included; avoid ads, paid access or publication workflows inconsistent with MangaDex API acceptable-use rules.
- Existing demo fixtures and downloaded chapters are not modified; no migrations and no direct Android Keiyoushi APK support.
- Risks: API or CDN may fail from the physical iOS 12 network; MangaDex@Home can issue dynamic delivery hosts outside *.mangadex.network which should remain blocked by HTTPPolicy. Older chapters, alternate translated languages and CDN host fallback remain future scope.
- Real site connection and image loading are NOT marked accepted until on-device test. Mocked Node API responses and Swift CI compilation alone cannot prove it.

### Focused one-shot device test for Build 26

1. Install the new IPA. Under Explorar tap + -> Inserir URL HTTPS and paste https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/repository-mangadex.json
2. In the new MangaDex Experimental catalog install MangaDex (experimental); ensure source active.
3. Open MangaDex. Verify real popular cover/title list and search for an English title.
4. Open real manga details and chapter list, including visible scanlation group attribution.
5. Try opening an English chapter. If the image delivery domain is rejected or MangaDex rate-limits, retain the exact error and do not retry repeatedly.
6. Optionally verify offline download of an accessible chapter and the existing Demo source.
7. Do not use repositories of Android APKs as JS catalog URLs; these remain incompatible.


## Build 26 real MangaDex pilot — physical failure (2026-10-30)

- User installed experimental MangaDex source and received: Source failed: network transport error -1200: An SSL error has occurred and a secure connection to the server cannot be made, when tapping Abrir source.
- First popular call targets https://api.mangadex.org. An SSL/TLS failure occurred before an HTTP response was decoded. Exact failing host and underlying SSL code are still unconfirmed on the device.
- MangaDex source is NOT physically accepted. Do not conflate the error with a 403, 429 or chapter parsing failure.
- -1200 alone cannot determine whether the cause is certificate trust, protocol/cipher incompatibility, route/interception, device clock or URLSession-specific behavior.
- Apple documents TLS 1.3 enabled by default in URLSession starting iOS 12.2; minor OS version not yet confirmed.
- Never disable certificate verification or global ATS to hide the error.

## Build 27 — safe differential TLS diagnostics (physical gate pending)

- Explore -> installed MangaDex -> Informações e dados da fonte -> Diagnosticar HTTPS do MangaDex.
- Read-only tests compare API /ping via the production HTTPClient and URLSession.shared, then MangaDex site, GitHub raw fixture and example.com controls. Shows iOS version and sanitized error codes.
- Copiar relatório copies a diagnostic report with no secret request headers or cookies.
- Safari can independently test https://api.mangadex.org/ping and report whether it displays pong or a certificate/secure connection warning.
- No source script or repository catalog updates, no insecure TLS bypass and no changes to supported iOS 12 baseline.
- Build 27 is diagnostic only; needs device results before a targeted fix.
