# Batch M3B–M4A Report

Date: 2026-10-29

## Goal

Turn installed JavaScript sources from managed extensions into browsable content inside the iOS 12 app.

## M3B — Source browser

`SourceBrowserViewController` loads an installed source through `InstalledSourceRuntimeLoader` and calls the Source API v1 contract directly.

Supported in this checkpoint:

- Popular
- Pagination foundation
- Pull-to-refresh
- Search
- Navigation from source list to manga details

## M3C — Manga details

`MangaDetailsViewController` calls `details(mangaId)` and displays:

- title
- author
- status
- genres
- description

## M4A — Chapters and page resolution

The same details screen loads `chapters(mangaId)`. Selecting a chapter calls `pages(chapterId)`.

This checkpoint intentionally stops at showing the resolved page count and first image URL. That validates the source contract and navigation before introducing image caching, zooming, Webtoon mode and reader memory management.

## iOS 12

Everything remains UIKit/callback based and compatible with the locked iOS 12 deployment target.

## Acceptance

Build 6 must preserve 11/11 diagnostics and complete the demo flow:

source → Popular → manga → details → Chapter 1 → page resolution.
