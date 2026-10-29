# Batch M5B Report — Custom Dark Mode

Date: 2026-10-29

## Goal

Provide a real dark appearance while preserving the locked iOS 12 deployment target.

iOS 12 predates Apple's system-wide Dark Mode API, so MangaReader12 uses an application-owned theme system instead of relying on iOS 13 dynamic colors.

## Theme manager

`ThemeManager` owns:

- Light and Dark palettes
- persisted preference in `UserDefaults`
- UIKit appearance defaults for bars, tables, switches and table headers
- a theme-change notification for immediate updates
- helpers for styling table views, cells and search bars

## Covered UI

- tab bar
- navigation bars
- Biblioteca
- Atualizações / Histórico placeholders
- Explorar
- repository catalogs
- installed-source browser
- source search
- manga details and chapter list
- Ajustes
- diagnostics

The reader remains black in both themes, which avoids changing image presentation and reader behavior.

## Acceptance

Build 8 requires a physical iOS 12 check for immediate switching and persistence across relaunch.
