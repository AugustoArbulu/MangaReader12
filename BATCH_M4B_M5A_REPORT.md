# Batch M4B–M5A Report

**Status: ACCEPTED — 2026-10-29**

Date: 2026-10-29

## Goal

Move from page URL resolution to an actual iOS 12 reader and make the first user-facing content state persistent.

## Reader

The new reader uses the existing hardened `HTTPClient` rather than bypassing source policies. Image URLs must be HTTPS and belong to domains declared by the installed source manifest.

Two modes are included:

- **Páginas** — horizontal paging; each page supports pinch-to-zoom.
- **Webtoon** — vertical continuous list with heights updated from the downloaded image aspect ratio.

## Library

`LibraryRepository` uses the schema that has existed since M1A. No database migration is needed.

Adding a manga:

- updates/inserts the manga row,
- adds it to `library`,
- synchronizes the currently loaded chapters.

The Biblioteca tab lists persisted manga and can reopen them through the installed source runtime.

## Demo source 1.1.0

The controlled fixture now returns two real images from this repository. This lets physical-device testing exercise:

repository update → source update → pages API → HTTPS image loading → reader → Library.

## iOS 12 constraints

UIKit, URLSession/Foundation, SQLite and callbacks only. Deployment target remains 12.0.

## Next physical checkpoint

Build 7 should validate reader page mode, zoom, Webtoon mode and Library persistence in one pass.

## Acceptance evidence

- PR #9 merged
- Merge commit: `eb029f628ce5947709b5f448a602c926976a49ff`
- Post-merge run `40819659824`: success
- Physical iOS 12: all requested reader and persistent Library checks passed
