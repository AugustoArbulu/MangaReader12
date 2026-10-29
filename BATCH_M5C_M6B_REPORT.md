# Batch M5C–M6B Report

Date: 2026-10-29

## Goal

Activate the reading-state and download foundations that have existed in the SQLite schema since M1A.

## Reading progress

The reader now persists the current page for each chapter. Reaching the final page marks the chapter read. Manga details query those states when they appear and expose a swipe action for manual read/unread control.

## History

The existing `history` table now drives the Histórico tab. One current history entry is kept per manga, matching the schema design, with the most recently read chapter and timestamp.

## Reader controls and cache

Reader controls now include brightness alongside the existing Páginas/Webtoon selector.

Image loading now supports:

- in-memory cache,
- deterministic disk cache in the iOS Caches directory,
- UICollectionView prefetch,
- local `file://` pages for offline content.

## Downloads

The first offline-download lifecycle is implemented without a schema migration:

- source page URLs are resolved normally,
- each page is downloaded with its declared headers,
- progress/state are persisted in `downloads`,
- page files are written under Application Support,
- completed chapters are marked downloaded,
- local pages are preferred by the reader,
- offline data can be removed from manga details.

This is the initial chapter-level download implementation. Queue scheduling, retry policies, storage quotas and a dedicated Downloads screen are deferred.

## iOS 12

All new UI remains UIKit/callback based. No iOS 13 Dark Mode APIs, Combine, SwiftUI or required structured concurrency are introduced.

## Acceptance

Build 9 requires physical validation of progress/history, brightness, persistence and offline chapter reopening.
