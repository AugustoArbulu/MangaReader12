# CHANGELOG

## 0.1.0-build31-m13a-webtoons-cover-differential — 2026-10-30

- Build30 physically fixed Manhwa18.net cover artwork on iOS 12.5.8, but Webtoons.com EN cover thumbnails are still absent in source lists even though their covers display inside work details. Webtoons source-only v0.1.1 lazy-image URL extraction did not solve the list problem.
- Added an explicitly user-triggered `Testar capas` action to the Webtoons.com EN source browser, without changing any source scripts, app networking settings, or image loading behavior.
- For just the **first listed work**, the new diagnostic compares the source's list cover URL with the cover returned by the existing details API and attempts one ordinary HTTPS GET for each (at most two image GETs + one normal source details request). Strict installed-source allowlist applies to both; no arbitrary hosts, HTTP downgrade, custom WebView injection or captcha/access-control bypass.
- Results: presence of the cover URL, hostname, file extension, query yes/no, HTTP status or transport failure, MIME, response size, UIImage decoder success and final response hostname. No manga title, URL path/query, raw content, auth header or cookies are included in the copied report.
- Stops further requests after HTTP 429. The HTTPClient is retained until the response finishes (consistent with Build30 fix), and each request is bounded to 15s, 5MiB, 3 redirects; no automatic retries.
- Physical gate: on Build31, open Webtoons.com EN Popular then tap `Testar capas`, copy and share the report; compare list vs details. If list URL is absent fix extraction, if host is blocked update only with documented approval, if status 200 and UIImage NO inspect image format support, if status 403 respect site access rules.
- HotComics remains HTTP 403 and is not bypassed; MangaDex remains paused; Manhwa18.net remains unchanged. Six selected Keiyoushi sources still in roadmap.
- Build31 preserves minimum iOS12, Swift5/UIKit and existing source catalog; no source update or reinstall required.

## Source-only hotfix: Webtoons.com EN 0.1.1 (M13-A) — 2026-10-30

- Build30 physical feedback: Manhwa18.net series covers appear after shared HTTPClient lifetime repair, and chapter images already worked. Webtoons.com EN series covers still absent in the list but appear within manga details; the cover loader works for a different thumbnail URL from the same source.
- Webtoons EN JS list thumbnail extraction now prefers validated HTTPS image URLs in lazy-loaded data-src, data-original, data-lazy-src, data-url, data-srcset and srcset attributes over a placeholder src. Uses only the already reviewed webtoons.com and pstatic.net hosts; never downloads data URI placeholders.
- Source manifest updated to v0.1.1 and SHA-256 changed to match new source script, without changing the source ID, iOS bundle/build number or app code.
- Added offline regression cases for lazy thumbnails and srcset and a catalog SHA-256 verification step to CI. No domain wildcard expansion, altered certificate trust or extra HTML/HTTP requests per listed entry.
- Real iOS12 list cover rendering is pending one source update and device check. An unsuccessful retry should be diagnosed by the cover host/status, not a claim of a proven fix. No new IPA required; Build30 remains the app build.
- HotComics still returns HTTP403, no bypass attempted; the remaining 6 selected sources remain in M13 plans. MangaDex stays paused.

## 0.1.0-build30-m13a-cover-network-lifetime — 2026-10-30

- First real device results from Build29 on iOS 12.5.8: Webtoons.com EN and Manhwa18.net both load source browsing and show chapter images when reading, but series cover thumbnails fail to appear. HotComics returns HTTP 403; its availability is not accepted and no bypass has been attempted.
- Diagnosed a native cover image loader lifetime defect: CoverImageLoader.load created a method-local HTTPClient that owns an ephemeral URLSession; HTTPClient.deinit invalidated and cancelled that session immediately after send() returned. This affects *all* cover requests, independently of whether a chapter image URL works.
- CoverImageLoader now strongly retains each active HTTPClient (UUID-keyed in-flight dictionary guarded by NSLock), releases only after the HTTP completion fires, and preserves existing image cache and asynchronous UI update. Prevents premature URLSession invalidation while in flight.
- Enforces source HTTPS domain allowlist before reading the memory/disk cache, preventing cached images from circumventing the currently installed source host policy. Source-icon loader still uses its explicit icon host when no source policy applies.
- No modifications to JavaScript adapters, SHA-256-pinned source catalog, source IDs, downloads, chapter reader or database; existing installed sources need no reinstall.
- No changes to Webtoons/Manhwa18.net chapters that already worked. If some covers still fail, use host-specific follow-up; this build fixes a proven native lifecycle defect but does not assert all cover origins/CDNs are reachable under the domain policy.
- Do not change the HotComics server 403 through artificial headers, proxy, TLS weakening or access-control bypass. Report as access-restricted/unsupported on this network until normal server access is available.
- Keep nine Keiyoushi selected sources as the active project goal; MangaDex frozen. Build30, iOS 12.0 minimum, Swift5/UIKit unchanged; physical QA pending.

## 0.1.0-build29-m13a-selected-keiyoushi-sources — 2026-10-30

- First user-selected Keiyoushi source package (M13-A): three native JavaScript adapters — HotComics, Manhwa18.net and Webtoons.com EN. These are **unofficial experimental ports**, not Android APKs and not fully proven on sites.
- Added a native WebKit DOMParser-based source bridge available as Native.htmlSelect(markup, selectorSpecsJSON, callback). It uses inert markup parsing in a local empty WKWebView, returns sanitized bounded CSS selector results, and does not execute fetched webpage JavaScript.
- Created dedicated pilot repository catalog fixtures/keiyoushi-selected-repository.json with explicit HTTPS host allowlists, SHA-256 integrity pins and source attribution (Keiyoushi Apache-2.0).
- Ported upstream browsing/search/details/chapter/page logic into the existing six-function JavaScript source contract. Manhwa18.net uses Inertia #app[data-page] JSON; HotComics and Webtoons EN use HTML/CSS selectors; Webtoons episode listing uses its known mobile JSON API.
- Source bridge enforces 3 MiB HTML input, 4 MiB result, 2 MiB Inertia data-page attribute, bounded selector count, four pending HTML jobs, and 40s source timeout for selected ports. HTTPS trust and per-source domain allowlists preserved; no captcha, age gate or access-control bypass.
- New offline Node smoke harness ci/test_m13a_js.cjs exercises all 6 methods for all 3 sources using simulated responses and negative URL checks, now run within the existing GitHub Actions CI.
- Does not claim real-world site success, iOS12 WebKit parser success, cover/CDN accessibility or offline chapter reading until physical QA. A public site can reject app access, change markup, require credentials, or fail TLS on iOS12.
- Build number 29 (Build29 MangaDex fallback PR was closed unmerged); Swift5/UIKit/iOS12 baseline, stored Library/downloads and existing Demo fixtures unchanged.

## 0.1.0-build28-m12b-alternate-tls-probes — 2026-10-30

- Physical iOS 12.5.8 report confirmed MangaDex API via Safari works with pong, but both the app HTTPClient and standard URLSession fail with NSURLErrorDomain -1200 and peer TLS stream -9836 (errSSLPeerProtocolVersion).
- GitHub and example.com both returned HTTP 200 from the same iOS URLSession diagnostic, excluding a broad loss of HTTPS trust or total lack of network connectivity.
- Apple identifies -9836 as a TLS protocol version error. iOS 12.5.8 is newer than iOS 12.2, where Apple says TLS 1.3 is enabled by default in URLSession and Network.framework. The exact incompatibility is not yet identified.
- Extended the existing MangaDex HTTPS diagnostics with two more distinct default-trust transport paths:
  - A private, ephemeral WKWebView using WebKit to load API /ping, capturing its content or TLS/URL error.
  - NWConnection from Network.framework to the same domain/443 with TLS options, standard certificate and hostname validation and no custom verify block, reporting handshake success or error.
- Tests are strictly read-only and only run after explicit user action. Both paths have 14-second timeouts, clean up their connections and do not share login/session data.
- No TLS downgrades, disabled ATS, disabled certificate validation, proxies, dynamic unrestricted domain exemptions, or unreviewed source script changes.
- This build does NOT claim MangaDex is fixed; it aims to determine whether a secure alternate iOS-native transport is available.
- Same iOS 12.0 minimum, Swift 5/UIKit, SQL schema and accepted downloaded/reader features. Bundle version 28; physical gate pending.

## 0.1.0-build27-m12a-mangadex-tls-diagnostic — 2026-10-30

- The first live MangaDex test on Build 26 returned NSURLErrorDomain code -1200 on Abrir source, before the manga list loaded. This is a TLS secure-connection error, not yet a verified root cause.
- Added opt-in Diagnosticar HTTPS do MangaDex in Explorar -> MangaDex -> Informações e dados da fonte, visible to MangaDex experimental source only.
- A read-only test compares the app HTTPClient to URLSession.shared on the API /ping endpoint, then checks MangaDex website, GitHub fixture HTTPS and example.com controls.
- Reports iOS point release, HTTP status or a sanitized error domain and code plus underlying TLS/CFNetwork stream code. The report can be copied via the UI.
- No ATS exception, insecure HTTP, trust bypass, arbitrary proxy, new allowlisted domains, persisted credentials or changes to source script.
- MangaDex real browsing, chapters, image pages and offline reading remain unverified; this build is diagnostic, not a fix claim.
- Existing approved Demo source, Library, backup, reader, downloads, Swift 5/UIKit, iOS 12 minimum and SQLite schema unchanged.
- Bundle version 27, device diagnostic pending.

## 0.1.0-build26-m12a-mangadex-pilot — 2026-10-30

- User reported Build 25 source/search batch **"tudo parece estar funcionando"** on an iPhone. Mark tested paths as provisionally accepted, not exhaustive edge-case coverage.
- Introduced optional asynchronous completion callback for each JavaScript source API method. Existing synchronous Demo scripts still work without changes; async completion has 25-second timeout, per-call completion protection, and error mapping.
- Added a live, read-only MangaDex pilot source implementing metadata, popular/search, manga details, English chapter listing, and MangaDex@Home image URLs.
- Created a separate experimental repository catalog in fixtures/repository-mangadex.json. The JS script is SHA-256 pinned, with allowlisted manga domains and HTTPS-only network transport.
- Source rate limit errors are surfaced explicitly; no 429 flooding or captcha/anti-bot bypass. Chapter pages use data-saver images to reduce memory.
- MangaDex and scanlation groups are credited by metadata/chapter fields; API acceptable-use requirements include no monetization and respecting content removal requests.
- Caveats: oldest chapters beyond first 100 English chapters not exposed in pilot; MangaDex@Home hosts outside allowed MangaDex domains may fail safely; links/chapters could expire, and real API cannot be certified by mocked tests.
- The adapter's six functions passed Node mock-transport and syntax tests; final proof requires a physical device and live MangaDex API/CDN.
- Build 26, iOS 12 minimum, UIKit/JavaScriptCore, Swift 5, no SQL migration. Physical validation pending.

## 0.1.0-build25-m11b-search-source-suite — 2026-10-30

- User reported "funcionou" for Build 24 global search on physical iOS 12. Mark M11A as physically accepted.
- Development cadence changed to cohesive feature batches rather than one minor IPA per change, with one consolidated physical regression checklist.
- Global search pagination: source-specific hasNextPage state, explicit Carregar mais resultados footer, bounded to five pages per source with up to 40 rendered matches per page.
- Search source filters: dedicated Fontes picker with checkmarks and Todas / Aplicar actions; only selected, enabled installed JS sources are queried.
- Search result consistency: deduplicate by original source ID + manga ID, ignore stale asynchronous responses after cancellation/filter/query changes; partial source failures do not abort results.
- Source information: new Informações e dados da fonte from Explore source actions, with source ID, language, version, enabled state, allowlisted domains, and count of JS storage entries.
- Per-source diagnostics: explicit runtime metadata check.
- Source-local reset: confirmation-gated clearing of only that source's namespaced JS UserDefaults storage. Never clears chapter downloads, Library, history, reader prefs or source cookies.
- Real source URLs still enforced by the existing JavaScript runtime/domain allowlist; no direct Android APK extension compatibility implied.
- iOS 12.0 UIKit deployment, SQLite, downloader, reader and backups unchanged. Bundle version 25.
- Device QA pending; build may be merged only after green push + PR CI.

## 0.1.0-build24-m11a-global-search — 2026-10-30

- User physically confirmed **"tudo funcionando"** on build 23. Record M10C foreground restart recovery and paused state as accepted on the test iPhone.
- Explore now has a dedicated search button (magnifying glass) for searching across all enabled, installed JavaScript sources.
- Global search requests the first results page per source sequentially, with source name/language on each matching manga row and source-domain-aware covers.
- Selecting a result loads its owning installed source and opens the existing Manga Details screen; Library and reader functions are not duplicated.
- Search cancellation/changed-query generation tokens ignore late results from an earlier search, and individual source failures yield partial results rather than aborting the entire search.
- Does not load Android/Keiyoushi APKs; only MangaReader12 source API v1, with existing HTTPS/source allowed-domain guards.
- No migrations, no changes to Downloads, backup or reader. iOS 12 minimum remains 12.0.
- Build 24 pending physical acceptance.

## 0.1.0-build23-m10c-recover-downloads — 2026-10-30

- Physical feedback for build 22: user confirmed the opt-in slow Demo download test worked on their iOS 12 device; the earlier timing blocker is closed. The complete multi-chapter priority/resume/relaunch matrix remains a focused QA checkpoint rather than assumed entirely accepted.
- Download queue now persists a per-chapter recovery plan in Application Support, including the original source manifest, page list and queue priority. Plans are protected by iOS file protection when supported.
- When the app relaunches, validated plans reconstruct unfinished jobs; already written contiguous nonempty page files are reused, and only remaining pages are requested.
- Queued/in-progress jobs resume in the foreground when the manager initializes. Intentionally paused jobs stay paused until the user selects Retomar.
- Priority promotions are saved to the plan, so queued ordering survives relaunch.
- Missing/corrupt/older plans remain retryable via the existing source resolver; no falsely completed records or intentional deletion of partial images.
- Completed/failed jobs release the recovery plan (including any sensitive page headers) without deleting existing chapter images.
- Recovery is not a guarantee of background downloading and does not bypass source authentication, domains, expired URLs or platform execution limits.
- No SQLite schema migration; iOS 12.0 target, UIKit and Swift 5 remain unchanged.
- Bundle version 23; physical acceptance pending.

## 0.1.0-build22-m10b-demo-download-qa — 2026-10-30

- Physical testing blocker: bundled Demo chapters download in approximately 0.1 seconds, making manual pause/resume/priority QA impractical.
- Downloads now offers "Teste 8s: OFF/ON" (OFF by default). When enabled, only the two bundled fixtures (fixture.localdemo and fixture.altdemo) wait eight seconds asynchronously before each page HTTP request.
- No delay for real sources; source manifest allowed-domain policy, real download byte validation and offline file handling stay intact.
- The delay is cancellable by existing pause state: a pending delayed request checks job identity, generation serial, active state and chapter index before it may start.
- Enable the switch before downloading from the Demo, switch back to Downloads to pause/resume. Turn it OFF when test is finished.
- Build 21 full queue functionality remains pending physical acceptance; build 22 only adds deterministic QA affordance.
- Bundle version 22, iOS 12.0 minimum unchanged.

## 0.1.0-build21-m10b-foreground-queue — 2026-10-30

- Physically accepted Build 20: user confirmed everything tested is functioning on iOS 12.
- Refactored chapter downloading to use a shared single-running-job foreground queue across app screens.
- Added per-chapter pause/resume without re-downloading completed pages during the same app session.
- Added priority promotion for queued chapters through Downloads swipe actions.
- Added queued/paused/active state display and blocked removal of active writers.
- Ignored late cancellation callbacks when a chapter is rapidly paused and resumed.
- Improved live Downloads refresh so unchanged records do not repeatedly close swipe actions.
- On a cold app relaunch, unowned queued/running downloads become retryable failures; old paused jobs can be restarted by resolving fresh source pages.
- **Not implemented yet:** persistent job plans and byte-level restart-safe resumption, durable queue order, background execution guarantee.
- iOS 12.0 minimum, Swift 5/UIKit, unchanged SQLite v1 schema, source domain restrictions retained.
- Advanced build number to 21; physical gate pending.

## 0.1.0-build20-m10a-downloads-retry-refresh — 2026-10-29

- Accepted build 19 physical iOS 12 report: scale changes no longer hide interface when tapping Largura/Altura.
- M10A first download-management increment: Downloads auto-refreshes its rows while visible, plus pull-to-refresh.
- Failed download rows expose "Tentar novamente" directly in Downloads. Retry reloads the installed/active JS source, resolves current details, matches chapter ID, resolves pages and re-downloads with existing source-domain policies.
- Retry is guarded against duplicate same-chapter retries while in progress; progress and errors are shown in the Downloads UI.
- Avoid removing "downloading" rows mid-write because the existing downloader cannot safely cancel in-flight HTTP requests.
- Future queue orchestration, pause/resume, persistent queue and reordering are still deferred. Do not imply these are implemented.
- UIKit/iOS12 deployment 12.0, schema v1 and source API remain unchanged.
- Advanced build number to 20; physical gate pending.

## 0.1.0-build19-reader-gesture-overlay-hotfix — 2026-10-29

- Physical build-18 report: tapping Largura or Altura in the center of the live scale selector also triggered the reader's center-tap action and hid the reader controls.
- Root cause: root-level single/double-tap recognizers did not exclude touches in floating UI controls.
- Reader now filters both tap recognizers via UIGestureRecognizerDelegate before recognition.
- Touches inside the visible scale comparison panel or brightness/direction controls never trigger the page tap-zone handlers, regardless of their horizontal location.
- Future nested UIControl elements are protected as well.
- Taps directly on the image still navigate pages / toggle chrome; scale switching remains immediate and stays on the same page.
- No changes to scale modes, backup schema, iOS 12 deployment target or existing source handling.
- Advanced build to 19; focused physical retest pending.

## 0.1.0-build18-live-reader-scale-comparison — 2026-10-29

- Physical build-17 preliminary report: the app appears to work, but scale comparison requires more immediate control in the open chapter. Full M9B physical acceptance remains pending.
- Within an open chapter, Opções → Comparar escalas reveals an always-visible comparison strip with Tela, Largura, Altura and Original.
- Tapping another scale instantly updates visible pages without closing the strip, resetting chapter progress, reloading the collection, or fetching images again.
- Fechar dismisses the comparison strip; the chosen scale persists using the existing ReaderPreferences key and backup format.
- The strip dismisses automatically when hiding reader controls or switching to Webtoon.
- Keeps UIKit/AppDelegate, locked iOS 12.0 deployment target and Xcode 15.4 CI.
- Build number 18, pending physical acceptance.

## 0.1.0-build17-m9b-chapters-reader-scale — 2026-10-29

- Accepted physical build 16: original backup successfully restored; reader main tab bar/band is absent.
- Added previous/next chapter options inside the reader, without stacking reader controllers.
- Retained offline-first page resolution and native JS source-domain enforcement on chapter transitions.
- Added optional end-of-chapter preloading for next-chapter page references and first two images.
- Added persisted reader image scale modes: fit screen, fit width, fit height and original size.
- Added settings UI for scale and preloading; backup preferences now carry both settings.
- Snapshot chapter identity for asynchronous reading-progress persistence during transitions.
- Advanced app build number to 17; iOS 12 target stays locked.

## 0.1.0-build16-backup-wal-reader-immersive — 2026-10-29

- Physical iOS 12 restore exposed `SQLite 14: unable to open database file` while validating the portable snapshot.
- Root cause is consistent with a portable SQLite snapshot retaining WAL journal mode while being reopened read-only without companion WAL/SHM files.
- Restore now verifies the SQLite header, reopens the temporary snapshot read-write, forces `PRAGMA temp_store=MEMORY` and `PRAGMA journal_mode=DELETE`, then validates supported schema/tables.
- Removed `quick_check` from the restore gate so validation no longer depends on read-only WAL/temp-file behavior on iOS 12.
- Reader now uses native `hidesBottomBarWhenPushed` so the main Biblioteca/Atualizações/Histórico/Explorar/Ajustes tab bar is fully removed during reading and the content extends into that area.
- Center tap continues to hide/show the reader navigation bar and reader controls.
- Extension/source icons from build 15 remain unchanged.
- Advanced app build number to 16.

## 0.1.0-build15-reader-chrome-source-icons — 2026-10-29

- Reader center tap now hides the bottom tab bar together with the navigation bar and reader controls.
- Bottom tab bar is restored when controls return or when leaving the reader.
- Added visual source/extension icons from the repository manifest `icon` field.
- Source icons render in repository catalogs and installed-source lists with cached network loading and initials fallback.
- Source icon URLs are required to be HTTPS when present.
- Demo sources advance to 1.3.1 / 1.0.1 so already-installed demo sources can update and persist their repository-provided icons.
- Build 15 includes the build-14 iOS 12 backup validator compatibility hotfix.
- Advanced app build number to 15.

## 0.1.0-build14-ios12-backup-validation — 2026-10-29

- Physical iOS 12 restore reached the improved validator and exposed the exact failing query.
- Replaced `PRAGMA quick_check(1);` with the older, broadly compatible `PRAGMA quick_check;` syntax.
- Validation-query errors now include SQLite prepare/step result codes and the native SQLite message.
- Existing `.mr12backup` files remain compatible and should be reused.
- Advanced app build number to 14.

## 0.1.0-build13-backup-validation — 2026-10-29

- Fixed restore rejecting a valid MangaReader12 backup because validation required an exact SQLite `user_version == 1`.
- Backup validation now checks SQLite `quick_check`, supported schema version range and the complete required MangaReader12 table set.
- Existing `.mr12backup` files remain compatible; users do not need to recreate the backup.
- Validation errors now include the specific reason when a backup is genuinely invalid.
- Advanced app build number to 13.

## 0.1.0-m7c-m9a-hardening — 2026-10-29

- Preserves locally installed/enabled sources across same-device backup restore when their active source scripts still exist on disk.
- Clears excluded offline chapter files during restore so the post-restore download database and filesystem do not disagree.
- Automatically refreshes persisted Library cover/metadata after manga details + chapters finish loading.
- Advanced app build number to 12.

## 0.1.0-m7c-m9a-visual-backup-migration-qol — 2026-10-29

- Added cover images from extension-provided `cover` URLs across source browse, Library, History, Updates, Downloads and manga details.
- Added memory + disk cover caching with source-domain policy enforcement.
- Reworked manga details with a large cover/header presentation.
- Added portable `.mr12backup` creation and restore using consistent SQLite snapshots and the iOS document picker.
- Backup includes Library/database state plus selected app/reader settings; download files and installed source scripts are deliberately excluded.
- Added source migration with global search across other enabled installed sources.
- Migration transfers Library membership, categories, compatible read/last-page states and history; offline downloads are deliberately not migrated.
- Added controlled MangaReader12 Alt Demo source for deterministic migration testing.
- Updated main demo source to 1.3.0 with cover metadata.
- Added reader background black/gray/white, optional page counter, keep-screen-on, tap zones, double-tap zoom and optional Webtoon gaps.
- Added Data & Storage screen with storage usage, cache cleanup, reindex downloads and delete-all-downloads.
- Added best-effort iOS 12 Background Fetch for Library updates with an explicit opt-in toggle.
- Added Mihon → iOS 12 feature/QoL audit and roadmap document.
- Advanced app build number to 11.

## 0.1.0-m6c-m7b-updates-categories-reader-downloads-ui — 2026-10-29

- Accepted M5C–M6B after successful physical iOS 12 validation of read state, history, brightness, offline chapter persistence and removal.
- Added functional Library update checking with a persistent update feed.
- Added controlled demo source 1.2.0 with Chapter 2 for update detection validation.
- Added category creation, deletion, manga assignment and Library filtering.
- Added persistent reader mode and page-direction preferences.
- Reader now resumes from the saved last page.
- Added dedicated reader settings screen.
- Added dedicated Downloads screen with status/progress and removal.
- Connected Atualizações to the main tab and Reader/Downloads to Ajustes.
- Advanced app build number to 10.

## 0.1.0-m5c-m6b-progress-history-downloads — 2026-10-29

- Accepted M5B after successful physical iOS 12 dark-mode switching and persistence validation.
- Added reading progress persistence using the existing chapter state columns.
- Added automatic read completion when the final page is reached.
- Added functional Histórico tab backed by SQLite.
- Added swipe actions to mark chapters read/unread.
- Added chapter progress and offline indicators in manga details.
- Added reader brightness control.
- Added adjacent-page prefetch with memory + disk image cache.
- Added initial chapter download manager with progress persistence and offline page files.
- Added swipe actions to download/remove a chapter for offline reading.
- Offline chapters now open from local files before asking the source runtime for page URLs.
- Advanced app build number to 9.

## 0.1.0-m5b-dark-mode — 2026-10-29

- Accepted M4B–M5A after successful physical iOS 12 validation of the real reader, zoom, Webtoon mode and persistent Library.
- Added a custom dark theme compatible with iOS 12.
- Added persistent theme preference via UserDefaults.
- Added instant light/dark switching from Ajustes.
- Themed navigation bars, tab bar, tables, cells, text, search UI, placeholders, Library, source browsing, manga details and diagnostics.
- Kept the reader black independently of the app theme.
- Advanced app build number to 8.

## 0.1.0-m4b-m5a-reader-library — 2026-10-29

- Accepted M3B–M4A after complete physical iOS 12 browse/details/chapter validation.
- Added actual image reader backed by source page URLs and per-page headers.
- Added page mode with horizontal paging and pinch zoom.
- Added basic vertical/Webtoon mode.
- Added source-domain enforcement and image response-size limits through the hardened HTTP client.
- Added persistent SQLite-backed Library.
- Added add/remove Library action from manga details.
- Added reopening library entries through their installed source runtime.
- Updated the controlled demo source to 1.1.0 with two real PNG reader fixtures hosted in the repository.
- Advanced app build number to 7.

## 0.1.0-m3b-m4a-source-browse — 2026-10-29

- Accepted the M2D–M3A batch after green Xcode 15.4 CI and full physical iOS 12 validation: 11/11 diagnostics, demo repository install, Runtime OK, enable/disable, and expected no-previous-version rollback handling.
- Added installed-source browsing UI.
- Added popular manga loading with pagination support.
- Added per-source search.
- Added manga details screen backed by Source API v1.
- Added chapter listing.
- Added chapter page resolution preview as the bridge into the future reader.
- Advanced app build number to 6.

## 0.1.0-m2d-m3a-batch — 2026-10-29

- Accepted M2C after green post-merge Xcode 15.4 CI and 9/9 diagnostics on physical iOS 12.
- Added repository lifecycle coordination across catalog planning, script transport, atomic files and SQLite state.
- Added installed-source runtime loading directly from the active on-disk JavaScript extension.
- Added source list, enable/disable, rollback and removal management.
- Added a controlled demo repository and source for end-to-end validation.
- Added first Mihon-style UIKit navigation shell: Biblioteca, Atualizações, Histórico, Explorar and Ajustes.
- Added repository/source management UI under Explorar.
- Moved diagnostics into Ajustes with a scalable table UI.
- Expanded diagnostics to 11 checks.
- Advanced app build number to 5.

## 0.1.0-m2c-atomic-source-install — 2026-10-29

- Accepted M2B after green post-merge CI and 8/8 diagnostics on a physical iOS 12 device.
- Added staged on-disk source installation.
- Added active/previous version preservation for source updates.
- Added rollback support that swaps current and previous source versions.
- Added integrity verification before installed source files are touched.
- Added failure restoration so a promotion error does not destroy the prior working version.
- Added a ninth on-device diagnostic for source install/update/rollback.
- Advanced app build number to 4.

## 0.1.0-m2b-repository-transport — 2026-09-05

- Accepted M2A after green CI and 7/7 green diagnostics on a physical iOS 12 device.
- Added HTTPS remote repository catalog transport.
- Added remote source-script transport using the hardened HTTP client.
- Added pure Swift SHA-256 for iOS 12.
- Added optional source-script SHA-256 verification and mismatch rejection.
- Added repository record + last-refresh persistence over SQLite.
- Added an eighth on-device diagnostic for repository transport/integrity.
- Advanced app build number to 3.

## 0.1.0-m2a-repository-catalog — 2026-09-05

- Accepted M1C after green CI and 6/6 green diagnostics on a physical iOS 12 device.
- Added Repository Catalog API v1 decoding and validation.
- Added duplicate-source detection.
- Added numeric dotted-version comparison.
- Added install/update/unchanged/incompatible planning.
- Added app minimum-version compatibility handling for repository sources.
- Added a seventh on-device diagnostic for repository catalog planning.

## 0.1.0-m1c-networking — 2026-09-05

- Accepted M1B after green CI and 5/5 green diagnostics on a physical iOS 12 device.
- Reworked HTTP response handling to stream through URLSession delegate callbacks.
- Enforced response-size limits while data is being received instead of after full download.
- Added early oversized `Content-Length` rejection.
- Revalidated redirect destinations and enforced explicit redirect limits.
- Added timeout/cancellation/transport error classification.
- Added a sixth on-device diagnostic for streaming response limits.

## 0.1.0-m1b-contracts — 2026-09-05

- Accepted M1A after green CI and 4/4 green diagnostics on a physical iOS 12 device.
- Added formal Source API v1 function contract.
- Added typed source DTOs and JavaScript result decoding.
- Added fixture-based validation of `metadata`, `popular`, `search`, `details`, `chapters`, and `pages`.
- Added installed-source persistence repository on SQLite schema v1.
- Expanded on-device diagnostics to five checks.

## 0.1.0-m1a-core — 2026-09-05

- Recorded successful Milestone 0 GitHub Actions + physical iOS 12 launch validation.
- Added core Manga/Chapter/Page models.
- Added source-manifest decoding and validation.
- Added URLSession HTTP client with source-domain policy, HTTPS enforcement, timeout and redirect guard.
- Added JavaScriptCore source runtime and initial Native bridge.
- Added namespaced source storage and cookie bridge foundation.
- Added SQLite database bootstrap and schema v1.
- Added on-device diagnostics for manifest, SQLite, networking policy and JavaScriptCore.
- Kept deployment target locked to iOS 12.0.

## 0.0.1-m0-bootstrap — 2026-09-05

- Established iOS 12.0 as locked deployment target.
- Selected Xcode 15.4 as canonical toolchain.
- Added minimal UIKit bootstrap app.
- Added shared scheme and GitHub Actions workflow.
- Added static iOS 12 guardrails and Mach-O verification.
- Added unsigned IPA packaging and SHA-256 generation.
- Added project state, architecture and compatibility documentation.
