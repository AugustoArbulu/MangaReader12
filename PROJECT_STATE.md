# PROJECT_STATE

## Checkpoint

- Project: MangaReader12
- Phase: **Batch M3B–M4A — installed source browsing, manga details and chapters**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (6)**

## Accepted checkpoints

- Milestone 0 — COMPLETE
- M1A — ACCEPTED (4/4)
- M1B — ACCEPTED (5/5)
- M1C — ACCEPTED (6/6)
- M2A — ACCEPTED (7/7)
- M2B — ACCEPTED (8/8)
- M2C — ACCEPTED (9/9)
- Batch M2D–M3A — **ACCEPTED on physical iOS 12**
  - PR #7 merged
  - Merge commit `b2d06e38cedfe90286a3f37a9b85a62ece373558`
  - Post-merge run `40816795777`: green
  - Diagnostics: **11/11**
  - Demo repository: loaded
  - Demo source: installed
  - Installed runtime: **Runtime OK**
  - Enable/disable: passed
  - No-previous-version rollback path: passed

## Implemented in this batch

### M3B — Installed source browsing
- “Abrir source” action for enabled installed sources
- Runtime is loaded from the installed `active/source.js`
- Popular manga list through `source.popular(page)`
- Pagination hook using `hasNextPage`
- Pull-to-refresh
- Per-source search through `source.search(query,page,filters)`

### M3C — Manga details
- Selecting a manga opens a native UIKit details screen
- `source.details(mangaId)` populates title, author, status, genres and description

### M4A — Chapters / reader bridge
- `source.chapters(mangaId)` populates chapter rows
- Chapter selection invokes `source.pages(chapterId)`
- Current checkpoint shows page count + first image URL
- This validates the final source API step before implementing the actual image reader

## Diagnostics

The regression suite remains **11 checks**. This batch intentionally uses functional UI/device validation for the new browse flow rather than inflating the diagnostic count.

## Acceptance gate

After green CI, sideload build 6 and validate:

1. Existing **11/11** remains green.
2. Explorar → installed MangaReader12 Demo → **Abrir source**.
3. Popular list shows **Demo Manga**.
4. Search returns a manga result.
5. Opening Demo Manga shows details.
6. Chapter 1 appears.
7. Tapping Chapter 1 resolves **1 página** and shows the demo image URL.

After that checkpoint, the next larger block can implement the actual reader + initial library persistence.
