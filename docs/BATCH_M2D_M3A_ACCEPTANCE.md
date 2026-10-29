# Batch M2D–M3A Acceptance

- [ ] Xcode 15.4 guardrail audit passes.
- [ ] Debug generic-device build succeeds.
- [ ] Release generic-device build succeeds.
- [ ] Binary remains arm64 with minimum iOS 12.0.
- [ ] Unsigned IPA packages successfully.
- [ ] Build 5 installs and launches on physical iOS 12.
- [ ] Five tabs are visible: Biblioteca, Atualizações, Histórico, Explorar, Ajustes.
- [ ] Ajustes → Diagnósticos reports **11/11**.
- [ ] Explorar → + → MangaReader12 demo repository loads.
- [ ] Demo source shows an install action and installs.
- [ ] Installed demo source appears under Explorar.
- [ ] “Testar runtime instalado” reports **Runtime OK**.

Do not mark this batch accepted from CI alone; the UI/repository/runtime flow requires a physical-device check.
