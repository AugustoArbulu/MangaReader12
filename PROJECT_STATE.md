# PROJECT_STATE

## Checkpoint

- Project: MangaReader12
- Phase: **Batch M5C–M6B — progress, history, reader controls/cache and offline chapters**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (9)**

## Accepted checkpoints

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
- Batch M5B — **ACCEPTED on physical iOS 12**
  - PR #10 merged
  - Merge commit `157aacb0593b717d0186ddc993ac18259aa18456`
  - Post-merge run `40820967384`: green
  - Immediate dark/light switching: passed
  - Main screens + source/details dark rendering: passed
  - Reader regression: passed
  - Theme persistence across relaunch: passed

## Implemented in this batch

### M5C — reading progress
- Reader records the current page into `chapters.last_page_read`
- Reaching the final page automatically sets `is_read = 1`
- Manga detail rows display **Lido** or the last page reached
- Swipe action can manually mark a chapter read/unread
- No schema migration required; existing M1A fields are used

### M5D — history
- Reader updates the existing `history` table
- Histórico tab is now functional
- History is ordered by most recent reading
- Selecting a history item reloads its installed source and opens manga details
- Swipe-to-delete removes a history item

### M6A — reader controls + cache
- Existing Páginas/Webtoon selector remains
- Added brightness slider in reader controls
- Added UICollectionView page prefetch
- Memory image cache expanded
- Added deterministic on-disk reader image cache under Caches
- Reader can load local `file://` pages for offline chapters
- Cache currently trims by file count; more sophisticated size/LRU policy remains future work

### M6B — initial offline downloads
- Chapter download manager stores pages under Application Support
- Per-page headers and source-domain allowlist are preserved during downloads
- Download state/progress/local path use the existing `downloads` table
- Completed download sets `chapters.downloaded = 1`
- Manga details show **Offline**
- Swipe action downloads or removes the offline chapter
- Opening a completed download prefers local files before invoking `source.pages`

## Regression

Existing **11/11 diagnostics** remain the core regression suite.

## Acceptance gate

After green CI, sideload build 9 and validate:

1. Existing 11/11 remains green.
2. Open Demo Manga → Chapter 1 and move to page 2; return to details.
3. Chapter 1 should show **Lido** after reaching the final page.
4. Histórico tab should show Demo Manga / Chapter 1.
5. Swipe Chapter 1 and toggle **Não lido/Lido**; the row state should change.
6. Reader brightness slider should visibly change screen brightness and restore after leaving reader.
7. Swipe Chapter 1 → **Download**; progress should complete and row should show **Offline**.
8. Close/reopen app; **Offline** should remain.
9. With the chapter downloaded, open Chapter 1 again; it should load from local files.
10. Swipe Chapter 1 → **Remover offline**; Offline marker should disappear.
11. Dark mode and Library should remain functional.

If this passes, the next larger block can focus on Updates/new-chapter checks, category management, reader direction/settings persistence and a dedicated Downloads screen.
