# PROJECT_STATE

## Checkpoint

- Project: MangaReader12
- Phase: **Batch M6C–M7B — updates, categories, persistent reader settings and Downloads UI**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (10)**

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
- Batch M5B — ACCEPTED (custom iOS 12 Dark Mode)
- Batch M5C–M6B — **ACCEPTED on physical iOS 12**
  - PR #11 merged
  - Merge commit `e5a3f2bea37c59864598f4255b4ba7d5d0321eee`
  - Post-merge run `40822171633`: green
  - Read state + Histórico: passed
  - Brightness control + restore: passed
  - Offline chapter download/relaunch/reopen/removal: passed
  - Dark Mode + Library regression: passed

## Implemented in this batch

### M6C — Library updates
- Atualizações tab is now functional
- Manual refresh checks every manga currently in Biblioteca
- Installed/enabled source runtime is used for chapter refresh
- Existing persisted chapter IDs are compared with the source chapter list
- New chapters are synchronized into SQLite
- `library.last_checked` is updated after successful checks
- New discoveries are kept in a bounded persistent update feed
- Tapping an update reopens manga details
- Controlled demo source 1.2.0 adds **Chapter 2** for deterministic testing

### M7A — categories
- Uses existing `categories` and `manga_categories` tables
- Create/delete categories
- Assign multiple categories to a Library manga
- Manga rows show category names
- Filter Biblioteca by category or show all

### M7B — reader settings
- Reader mode Páginas/Webtoon persists in UserDefaults
- Page direction LTR/RTL persists in UserDefaults
- Direction can be changed in reader controls
- Ajustes → Leitor exposes mode and direction preferences
- Reader restores the saved `last_page_read` when reopening a chapter

### M7B — Downloads UI
- Ajustes → Downloads lists persisted download records
- Shows manga, chapter, state and progress
- Completed entries can reopen manga details
- Swipe delete removes local files and persisted download state

## Regression

Existing **11/11 diagnostics** remain the core regression suite. Deployment target remains 12.0.

## Acceptance gate

After green CI, sideload build 10 and validate:

1. Confirm existing 11/11 remains green.
2. Explorar → demo repository → update MangaReader12 Demo to **1.2.0**.
3. Confirm Demo Manga is still in Biblioteca and Chapter 2 is not yet persisted as an update.
4. Open **Atualizações** and tap refresh.
5. Result should report **1 capítulo novo** and show Demo Manga → Chapter 2 in the feed.
6. Open that update and confirm Chapter 2 appears in manga details.
7. Biblioteca → Categorias → create **Teste**.
8. Swipe Demo Manga → Categorias → assign **Teste** → Salvar.
9. Biblioteca → Filtrar → Teste should show Demo Manga; Todos should restore all.
10. Ajustes → Leitor: set Webtoon, reopen Chapter 1 and confirm Webtoon is selected by default.
11. Set Páginas + Direita → Esquerda, reopen reader and confirm the saved direction.
12. Read only to page 2, leave and reopen; reader should resume at the saved page.
13. Download Chapter 1 and confirm Ajustes → Downloads shows it as Offline.
14. Remove it from Downloads and confirm the Offline marker disappears in manga details.
15. Dark Mode and existing History/Library flows remain functional.

If this passes, the next large block can focus on richer Updates scheduling/automation inside iOS limits, backup/restore, migration between sources and reader quality-of-life controls.
