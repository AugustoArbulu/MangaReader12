# Mihon Feature Audit → MangaReader12 / iOS 12

Updated: 2026-10-30

This document uses Mihon as a product/UX reference. MangaReader12 is an independent iOS project and is not affiliated with Mihon.

Official references reviewed:

- Mihon 0.21.3 changelog: https://mihon.app/changelogs/v0.21.3
- Reader settings: https://mihon.app/docs/guides/reader-settings
- Backups: https://mihon.app/docs/guides/backups
- Source migration: https://mihon.app/docs/guides/source-migration
- Storage FAQ: https://mihon.app/docs/faq/storage
- Mihon download/current release: https://mihon.app/download/

## Status legend

- **Implemented** — available in MangaReader12 now or in the current build-11 branch.
- **Foundation** — core data/runtime exists, UI/polish remains.
- **Planned** — useful and feasible on iOS 12.
- **iOS-limited** — Android behavior cannot be reproduced exactly on iOS 12.
- **Deferred** — lower priority than core reading/library/source reliability.

| Mihon capability / QoL | MangaReader12 status | iOS 12 adaptation |
| --- | --- | --- |
| Library | Implemented | SQLite-backed Library |
| Categories / filtering | Implemented | Multiple categories per title |
| History / read progress | Implemented | Last page, read state, history |
| Updates feed | Implemented | Manual Library refresh + persistent feed |
| Scheduled library updates | iOS-limited / implemented opportunistically | Background Fetch; iOS decides execution time |
| Browse / Popular | Implemented | JavaScript source API |
| Per-source search | Implemented | JavaScript source API |
| Manga details | Implemented | Native UIKit details screen |
| Cover thumbnails | Implemented in build 11 | Loaded from extension-returned cover URL |
| Cover cache | Implemented in build 11 | Memory + disk cache |
| Extension repositories | Implemented | JSON catalog, install/update/remove |
| Extension origin/integrity | Foundation | Repository URL + SHA-256; publisher signatures still future |
| Extension enable/disable | Implemented | Persisted in SQLite |
| Extension rollback | Implemented | Active/previous filesystem slots |
| Source settings | M11B partial build 25 (device gate pending) | Source info, runtime diagnostics, confirmation-based JS local reset; structured source-defined settings UI future |
| Cookies / headers | Foundation | Runtime HTTP headers and storage exist; cookie isolation hardening future |
| WebView/login/captcha | Planned | Use WKWebView where a source legitimately requires user login/challenge |
| Reader paged LTR | Implemented | UIKit collection reader |
| Reader paged RTL | Implemented | Persisted direction |
| Long strip / Webtoon | Implemented | Continuous vertical mode |
| Long-strip gaps | Implemented in build 11 | Optional persisted gap |
| Pinch zoom | Implemented | Paged reader |
| Double-tap zoom | Implemented in build 11 | 1x ↔ 2.5x |
| Tap zones | Implemented in build 11 | Sides navigate; center hides/shows chrome |
| Reader background black/gray/white | Implemented in build 11 | Persisted |
| Show page number | Implemented in build 11 | Optional |
| Keep screen on | Implemented in build 11 | Restores prior system idle-timer state when leaving |
| Brightness control | Implemented | Restores original brightness |
| Resume last page | Implemented | SQLite progress |
| Page preload | Implemented | UICollectionView prefetch |
| Next-chapter preload | Build 17 (physical gate pending) | Prefetch next chapter metadata/pages near current chapter end |
| Reader scale types | Build 17 (physical gate pending) | Fit screen/width/height/original; smart-fit deferred |
| Crop borders | Planned | Image-processing step; must be memory-safe on older devices |
| Split/rotate wide pages | Planned | Feasible, but image memory limits matter |
| Skip read/filtered/duplicate chapters | Planned | Needs chapter filtering/duplicate rules |
| Volume-key navigation | iOS-limited | No clean public equivalent to Android volume-key page navigation |
| Reader page actions (share/save/copy/set cover) | Planned | UIKit share sheet + Photos/Files where permitted |
| Downloads | Implemented | Sequential chapter pages, source policy preserved |
| Download queue screen | M10C build 23 (physically accepted) | Foreground serialized queue, pause/resume, persistent restart-safe recovery plans and priority; true background URLSession download future |
| Reindex downloads | Implemented in build 11 | Reconciles DB records with missing local paths |
| Storage usage | Implemented in build 11 | Database/download/cache byte totals |
| Clear caches | Implemented in build 11 | Reader + cover caches |
| Delete all downloads | Implemented in build 11 | Leaves Library/history/progress intact |
| Backup | Implemented in build 11 | Portable .mr12backup using consistent SQLite snapshot |
| Restore | Implemented in build 11 | System file picker |
| Backup includes Library/chapters/history/categories/settings | Implemented in build 11 | Database snapshot + selected UserDefaults |
| Backup excludes extension binaries/download files | Implemented by design | Mirrors Mihon’s general separation |
| Source migration | Implemented in build 11 | Searches other enabled installed sources |
| Migration keeps categories/progress/history | Implemented in build 11 | Chapter matching by number, fallback normalized name |
| Migration of downloads | Not implemented by design | Downloads remain source-specific |
| Global search across sources | M11B build 25 (device gate pending) | Search multiple pages, per-source filters, source-tagged results; Build 24 baseline physically accepted |
| Trackers | Planned / deferred | Connector/account model needs design; not required for core reader |
| Local source | Planned | Files/archives/EPUB ingestion can be added without JS source |
| Backup automation | iOS-limited | File access/background rules differ; manual portable backup first |
| Download auto-delete after reading | Planned | Straightforward once user policy/settings exist |
| Incognito reading | Planned | Suppress history/progress updates while enabled |
| Duplicate chapter detection | Planned | Normalize chapter number/name/scanlator |
| Smart update intervals by release cadence | Planned | Can learn next-check hints; actual execution still iOS-controlled |
| Statistics | Planned | Library/read/history/download data already exists |
| Settings search | Deferred | Useful after settings surface grows further |
| Tracker sync | Deferred | Depends on tracker integrations |
| Local archive formats | Planned | ZIP/CBZ easiest first; RAR/CBR needs an additional decoder |
| EPUB local reading | Planned | Requires EPUB parser/rendering path |
| Source diagnostics / clear cache/cookies | Foundation | Diagnostics exists; advanced source maintenance UI future |

## Important differences from Mihon

### Background work

Android can schedule more predictable periodic work. On iOS 12, Background Fetch is opportunistic. MangaReader12 therefore keeps manual update as the reliable path and treats background update as a best-effort enhancement.

### Extensions

Mihon executes Android/Tachiyomi-style extensions. MangaReader12 deliberately uses a JavaScriptCore source API so that extensions stay compatible with iOS 12 and do not require dynamic native-code loading.

### Downloads and migration

Downloaded page files belong to the original source/chapter identifiers and are intentionally not migrated. The migrated Library entry carries categories, compatible progress and history.

### Backup

The build-11 backup captures the SQLite Library state plus selected app/reader settings. It does not package downloaded chapters or installed JavaScript source scripts. Sources can be reinstalled from their repository.

## Priority after build 11

1. Validate covers, backup/restore, migration, storage cleanup and reader QoL on physical iOS 12.
2. Hardening: backup conflict/merge behavior, migration matching, source/cookie isolation.
3. Download queue: retry/pause/order and optional auto-delete after reading.
4. Reader: next-chapter navigation/preload, scale modes, wide-page handling, crop borders.
5. Source UX: global search, source settings, WKWebView login/challenge flow.
6. Local source: CBZ/ZIP first, then EPUB and optional additional archive formats.
7. Optional trackers/statistics/incognito once core reading is mature.


## Current work after Build 23

- Build 23 M10C restart-safe foreground download queue: **physically accepted** on iOS 12.
- Build 24 M11A: first-page global search across enabled installed JavaScript sources; physical gate pending.
- Subsequent candidates: per-source settings UI, WKWebView manual sign-in/challenge where permitted, and wide-page reader polish.
- Native iOS 12 JavaScript source API is still distinct from Android/Keiyoushi APKs; compatibility requires porting or a remote bridge.


## Larger batch workflow — adopted after Build 24

- Device testing moves to grouped acceptance after multiple closely related changes rather than distributing one IPA per small enhancement.
- Build 25 M11B groups source selection, global pagination/deduplication, source information, diagnostics and source-local storage maintenance.
- Advanced source-defined settings forms and true browser login integration remain separate later milestones.


## Build 26 M12A real-source pilot (not yet physically accepted)

- Introduces async source callbacks in the JavaScriptCore runtime, retaining sync source API v1 compatibility.
- Adds experimental MangaDex API catalog+source (separate from Demo) to exercise real metadata, search, chapter listing and chapter images.
- Direct Android Keiyoushi APK repositories still cannot be installed as MangaReader12 JavaScript catalogs.
- HTTPS/source-domain restrictions and MangaDex API attribution remain mandatory.
