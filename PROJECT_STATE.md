# PROJECT_STATE

## Checkpoint

- Project: MangaReader12 (provisional name)
- Phase: **Batch M2D–M3A — repository lifecycle + first Mihon-style UI**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (5)**

## Accepted checkpoints

- Milestone 0 — COMPLETE
- Milestone 1A — ACCEPTED (4/4 physical iOS 12)
- Milestone 1B — ACCEPTED (5/5 physical iOS 12)
- Milestone 1C — ACCEPTED (6/6 physical iOS 12)
- Milestone 2A — ACCEPTED (7/7 physical iOS 12)
- Milestone 2B — ACCEPTED (8/8 physical iOS 12)
- Milestone 2C — **ACCEPTED on 2026-10-29**
  - PR #6 merged
  - Merge commit `a32fa264d4dfae868880773a7bf30ac078972910`
  - Post-merge run `40815165763`: green
  - Physical iOS 12 diagnostics: **9/9 green**

## Implemented in this larger batch

### M2D — repository lifecycle coordination
- Catalog refresh → install/update planning
- Script download → SHA-256 verification → atomic installer
- SQLite source metadata save after filesystem promotion
- Rollback/cleanup path when persistence fails
- Enable/disable installed source state
- Remove source with best-effort database restoration on filesystem failure
- Repository/source listing APIs

### M2E — installed source runtime
- Reads `active/manifest.json` + `active/source.js`
- Creates JavaScriptCore runtime from the installed manifest
- Loads the installed script
- Validates all six Source API v1 methods before exposing the runtime

### M2F — installed source management foundation
- Installed-source listing
- Enable/disable
- Rollback
- Remove
- Repository refresh and install/update actions

### M3A — first real UIKit app shell
- Tab bar: Biblioteca / Atualizações / Histórico / Explorar / Ajustes
- Explorar lists repositories and installed sources
- Add custom HTTPS repository URL
- Built-in controlled MangaReader12 demo repository option
- Repository catalog screen with install/update state
- Installed-source action sheet with enable/disable, rollback, remove and runtime test
- Diagnostics moved into Ajustes and rendered as a scrollable table

## Diagnostics

The batch expands the on-device suite from **9 to 11 checks**:

10. Source lifecycle — coordinated DB + disk install/update/toggle/rollback/remove
11. Installed runtime — installed `source.js` loads through JavaScriptCore and passes the source contract

## Controlled end-to-end fixture

The repository contains:

- `fixtures/repository.json`
- `fixtures/source.js`

The UI exposes a one-tap option to add this demo repository after the batch is merged to `main`. It is only a controlled validation source and does not enable third-party sources by default.

## Validation status for this batch

- Swift parser checks for new backend/UI files: passed locally
- Info.plist validation: passed locally
- Linux full typecheck: unavailable for SQLite-backed files because the local Linux environment lacks the `SQLite3` module
- Xcode 15.4 Debug/Release build: **pending GitHub Actions**
- Physical iOS 12 validation: **pending after green CI**

## Acceptance gate

After green CI, sideload build 5 and verify:

- App opens into the five-tab UIKit shell.
- Ajustes → Diagnósticos reports **11/11**.
- Explorar → + → MangaReader12 demo repository loads.
- Demo source installs successfully.
- Selecting the installed demo source → “Testar runtime instalado” reports **Runtime OK**.
