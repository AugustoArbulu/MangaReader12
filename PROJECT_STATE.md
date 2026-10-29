# PROJECT_STATE

## Checkpoint

- Project: MangaReader12
- Phase: **Batch M5B — custom dark mode for iOS 12**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (8)**

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
- Batch M4B–M5A — **ACCEPTED on physical iOS 12**
  - PR #9 merged
  - Merge commit `eb029f628ce5947709b5f448a602c926976a49ff`
  - Post-merge run `40819659824`: green
  - Real two-page reader: passed
  - Horizontal paging + pinch zoom: passed
  - Webtoon mode: passed
  - Persistent Library across relaunch: passed
  - Reopen Library manga to Chapter 1: passed

## Implemented in M5B

### Custom iOS 12 theme system
- Manual Light/Dark selection because iOS 12 has no system Dark Mode API
- Theme preference stored in `UserDefaults`
- Theme applied at launch before the root controller is presented
- Runtime theme-change notification updates the current UI immediately
- Navigation bars and tab bar themed
- Table backgrounds, cells, separators and header text themed
- Search bar themed
- Placeholder/empty-state text themed
- Biblioteca, Explorar, repository catalogs, source browser, manga details and diagnostics themed
- Reader remains intentionally black in both themes

### Settings
- `Ajustes → Modo escuro` switch
- Switch state reflects persisted preference
- No restart required

## Regression

Existing **11/11 diagnostics** remain unchanged.

## Acceptance gate

After green CI, sideload build 8 and validate:

1. Existing 11/11 remains green.
2. Ajustes → Modo escuro switches the app to dark immediately.
3. Biblioteca, Atualizações, Histórico, Explorar and Ajustes all use dark backgrounds/text.
4. Open Demo source → Demo Manga → details and confirm tables/text stay dark.
5. Open Chapter 1; reader remains black and works normally.
6. Turn dark mode off and confirm light theme returns immediately.
7. Turn dark mode on, close the app completely, reopen it and confirm dark mode is still enabled.

If that passes, the next larger block can combine reading progress/history, reader controls and initial download support.
