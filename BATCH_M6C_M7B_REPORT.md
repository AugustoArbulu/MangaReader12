# Batch M6C–M7B Report

Date: 2026-10-29

## Goal

Turn the remaining Mihon-style shell areas into functional iOS 12 workflows without raising the deployment target.

## Library updates

`LibraryUpdateManager` refreshes each Library manga through its installed source runtime. The checker compares the remote chapter IDs against the chapter IDs already persisted in SQLite, inserts missing chapters, updates `last_checked`, and records discoveries in a bounded UserDefaults-backed update feed.

The controlled demo source advances to 1.2.0 and adds Chapter 2 so the update path can be reproduced on a physical device.

## Categories

The existing category schema is now exposed in UIKit:

- category create/delete,
- multiple category assignments per manga,
- category names in Library rows,
- Library filter by category.

No database migration is required.

## Reader preferences

The reader stores mode and horizontal page direction in UserDefaults. The same preferences are exposed in Ajustes → Leitor and can also be changed inside the reader.

When a chapter is reopened, the reader queries the existing reading-progress state and restores the last saved page.

## Downloads screen

A dedicated Downloads screen reads the persisted `downloads` table and shows state/progress for chapter downloads. Completed entries can reopen manga details, and swipe delete removes both the local chapter directory and persisted download record.

## iOS 12

All UI remains UIKit. No SwiftUI, Combine, SceneDelegate or required structured concurrency is introduced.

## Acceptance

Build 10 requires physical iOS 12 validation of source 1.2.0 update detection, category assignment/filtering, reader preference persistence/resume, and the dedicated Downloads screen.
