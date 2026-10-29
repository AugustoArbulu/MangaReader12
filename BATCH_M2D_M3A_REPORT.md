# Batch M2D–M3A Report

**Status: ACCEPTED — 2026-10-29**

Date: 2026-10-29

## Why this is a larger batch

After M2C passed 9/9 on physical iOS 12, development moved from one-small-gate-at-a-time to a larger checkpoint that combines the source lifecycle backend with the first real app shell.

## M2D — Repository lifecycle

`SourceLifecycleManager` composes:

- `RepositoryRemoteClient`
- `RepositoryCatalogPlanner`
- `SourceScriptInstaller`
- `SourceRepository`
- `RepositoryRepository`

It supports catalog refresh, install/update, persistence coordination, enable/disable, rollback and removal.

## M2E — Installed runtime

`InstalledSourceRuntimeLoader` reads the active installed source from disk, creates `JavaScriptSourceRuntime`, loads `source.js` and validates Source API v1 before returning the runtime.

## M2F — Management

SQLite repositories now provide lists for repositories and installed sources plus source enabled-state changes. This is exposed through the UIKit management screens.

## M3A — First Mihon-style UI shell

The app now launches into:

- Biblioteca
- Atualizações
- Histórico
- Explorar
- Ajustes

Explorar can add a repository, refresh its catalog, install/update a source, and manage an installed source. Ajustes exposes diagnostics.

## Demo repository

A controlled repository/source fixture is included in this same repository. After merge to main, Explorar can add it without the user typing a URL. It exists to validate the complete repository → download → install → JavaScriptCore path without depending on an external manga site.

## New diagnostics

- Source lifecycle
- Installed runtime

Expected total: **11/11**.

## iOS 12 constraints

No SwiftUI, Combine, SceneDelegate, CryptoKit, or required async/await was introduced. UIKit, callbacks, Foundation, JavaScriptCore and SQLite remain the foundation.

## Next physical checkpoint

Build 5 should be tested for both diagnostics and actual UI behavior. A passing checkpoint requires 11/11 plus successful installation/runtime loading of the controlled demo source.


## Acceptance evidence

- PR #7 merged
- Merge commit: `b2d06e38cedfe90286a3f37a9b85a62ece373558`
- Post-merge run `40816795777`: success
- Physical iOS 12: **11/11**
- Demo repository loaded successfully
- Demo source installed successfully
- Installed runtime reported **Runtime OK**
- Enable/disable worked
- Rollback without a previous version produced the expected warning
