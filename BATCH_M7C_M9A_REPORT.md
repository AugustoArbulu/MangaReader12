# Batch M7C–M9A Report

Date: 2026-10-29

## Goal

Deliver a visually richer manga interface plus several Mihon-style quality-of-life systems in one iOS 12-compatible checkpoint.

## Visual manga interface

Extensions already expose optional cover URLs through `SourceMangaSummary.cover` and `Manga.cover`. Build 11 now renders those values directly. Covers use a bounded memory cache and disk cache, while source browsing respects the manifest domain allowlist.

The UI now uses cover rows in source browsing, Library, History, Updates and Downloads, plus a larger manga-details header.

## Backup / restore

A portable `.mr12backup` contains a consistent SQLite snapshot plus selected app/reader preferences.

The portable snapshot deliberately removes:

- download records and downloaded flags,
- installed-source records.

Downloaded files and source scripts are not included. Repositories/source settings remain in the database so the user can reinstall the required source scripts after restoring.

## Migration

Migration searches other enabled installed sources by title and lets the user choose a visual candidate. It transfers:

- Library membership,
- categories,
- compatible chapter read/last-page state,
- history when a matching chapter is found.

Chapter matching uses chapter number first and normalized name as a fallback. Downloaded files are intentionally source-specific and are not migrated.

## Reader QoL

Added persisted reader settings inspired by useful Mihon controls that are practical on iOS 12:

- black/gray/white background,
- optional page counter,
- keep screen awake,
- side tap navigation,
- center tap chrome toggle,
- double-tap zoom,
- optional Webtoon gaps.

## Storage

A unified Data & Storage screen reports database, download and cache usage, manages Downloads, clears caches, reindexes missing download files and can remove all offline content without deleting Library/progress/history.

## Background updates

iOS 12 Background Fetch is exposed as an opt-in best-effort update mechanism. Manual Library refresh remains authoritative because iOS controls when background fetch is executed.

## Mihon audit

`docs/MIHON_FEATURE_AUDIT_IOS12.md` captures a feature-by-feature adaptation map and future priorities, including features that cannot map exactly from Android to iOS 12.

## Acceptance note

Build 10 passed CI but did not receive a reported physical acceptance before this larger batch started. Build 11 therefore carries both the build-10 physical checks and the new build-11 checks in one device checkpoint.


## Pre-device hardening

After build 11 passed CI and was merged, two runtime-consistency improvements were added before physical testing:

- same-device backup restore preserves locally installed source records when the corresponding active scripts still exist;
- excluded offline download files are cleared during restore;
- existing Library entries refresh persisted cover/metadata after successful details + chapters loading.

The physical acceptance build is therefore **build 12**.
