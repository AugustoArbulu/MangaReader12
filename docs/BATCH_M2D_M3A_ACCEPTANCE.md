# Batch M2D–M3A Acceptance

- [x] Xcode 15.4 guardrail audit passes.
- [x] Debug generic-device build succeeds.
- [x] Release generic-device build succeeds.
- [x] Binary remains arm64 with minimum iOS 12.0.
- [x] Unsigned IPA packages successfully.
- [x] Build 5 installs and launches on physical iOS 12.
- [x] Five tabs are visible: Biblioteca, Atualizações, Histórico, Explorar, Ajustes.
- [x] Ajustes → Diagnósticos reports **11/11**.
- [x] Explorar → + → MangaReader12 demo repository loads.
- [x] Demo source shows an install action and installs.
- [x] Installed demo source appears under Explorar.
- [x] “Testar runtime instalado” reports **Runtime OK**.

Do not mark this batch accepted from CI alone; the UI/repository/runtime flow requires a physical-device check.

**Result: ACCEPTED — 2026-10-29. Physical iOS 12: 11/11, demo repo loaded, source installed, Runtime OK, enable/disable worked, rollback correctly reported no previous version.**
