# PROJECT_STATE

## Checkpoint

- Project: MangaReader12
- Phase: **Batch M4B–M5A — real reader + persistent Library**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (7)**

## Accepted checkpoints

- Milestone 0 — COMPLETE
- M1A — ACCEPTED (4/4)
- M1B — ACCEPTED (5/5)
- M1C — ACCEPTED (6/6)
- M2A — ACCEPTED (7/7)
- M2B — ACCEPTED (8/8)
- M2C — ACCEPTED (9/9)
- Batch M2D–M3A — ACCEPTED (11/11 + repository/runtime flow)
- Batch M3B–M4A — **ACCEPTED on physical iOS 12**
  - PR #8 merged
  - Merge commit `ece765472bffca0ebfc2e75a117d2580b6d35db7`
  - Post-merge run `40817968324`: green
  - Source Popular/search: passed
  - Manga details: passed
  - Chapter list: passed
  - Page resolution: passed

## Implemented in this batch

### M4B — image reader
- Native UIKit reader receives `Page[]` from installed source runtime
- Image requests enforce the source manifest domain allowlist
- HTTPS-only transport by default
- Response body capped at 20 MiB per image
- Per-page headers are forwarded
- Page-mode horizontal paging
- Pinch-to-zoom up to 4x in page mode
- Basic Webtoon/continuous vertical mode
- Dynamic vertical cell heights after image dimensions are known

### M5A — persistent Library
- Add/remove Library action on manga details
- Manga + chapters are persisted into the existing SQLite schema
- Biblioteca tab is now functional
- Library survives app relaunch
- Tapping a Library manga reloads its installed source runtime and opens details
- Swipe-to-delete removes it from Library

### Controlled reader fixture
- Demo source version advanced to 1.1.0
- Two real PNG pages stored in `fixtures/page1.png` and `fixtures/page2.png`
- Demo manifest now allows `raw.githubusercontent.com`
- Demo source SHA-256 updated for integrity validation

## Regression

Existing **11/11 diagnostics** remain the regression suite. New reader/library behavior is validated functionally on device.

## Acceptance gate

After green CI, sideload build 7 and:

1. Confirm 11/11 remains green.
2. Explorar → demo repository → update MangaReader12 Demo from 1.0.0 to **1.1.0**.
3. Open source → Demo Manga → Chapter 1.
4. Reader displays two actual images.
5. Horizontal page mode moves between page 1 and 2.
6. Pinch zoom works in page mode.
7. Switch to Webtoon and scroll vertically through both pages.
8. Back on manga details, add it to Biblioteca.
9. Biblioteca shows Demo Manga.
10. Close and reopen app; Demo Manga remains in Biblioteca.
11. Open Demo Manga from Biblioteca and reach Chapter 1 again.

If that passes, next large block can add reading progress/history, reader controls/brightness/direction, image preload/cache and initial download support.
