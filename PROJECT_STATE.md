# PROJECT_STATE

> **Updater Fase 6A — PING/PONG NATIVO em processos separados (2026-11-05):** protótipo não privilegiado `ci/webreader_helper_probe.c` recusa root e responde somente a PING por socket UNIX local. Cliente Swift `WebReaderHelperPingProbe.swift` foi integrado à seção de diagnóstico em Ajustes, sem instalar ou iniciar helper, e o CI passou a compilar o programa C para ARM64 iOS12 e testá-lo em processos separados com cliente C/Swift macOS. **Aguardando CI no HEAD exato e teste físico futuro**, ainda sem helper real/rootful ou assinatura/autorização de instalação. [Relatório](docs/WEBREADER_NATIVE_HELPER_PING_PHASE6A_2026-11-05.md). Build 56/`main` intactas, PR #90 Draft.

> **Updater Fase 5G — cópia privada com FD retido; appinst ainda BLOQUEADO (2026-11-05):** ci/webreader_private_snapshot.py cria em laboratório cópia exclusiva de IPA sintética, valida SHA-256 no ingresso e na cópia, conserva FD somente leitura, restringe paths/links e evita substituir ou excluir arquivos preexistentes. **20 testes locais Linux OK**; execução macOS CI do HEAD ainda pendente. A fonte oficial [appinst.m](https://github.com/akemin-dayo/AppSync/blob/master/appinst/appinst.m) pede diretório temporário modo 0777 e recopia a IPA antes do LSApplicationWorkspace, gerando risco de identidade dos bytes após nosso snapshot; acesso real ao diretório não foi comprovado no dispositivo. Sem autorização de instalação, helper, chave de produção, Release ou alteração de Build 56/main. [Relatório](docs/WEBREADER_HELPER_SNAPSHOT_PHASE5G_2026-11-05.md). Fases 5E e 5F têm CI verde nos respectivos commits anteriores.

> **Updater Fase 5F — pré-inspeção fd de IPA, host-only (2026-11-05):** acrescentados ci/webreader_helper_file_preflight.py e testes com arquivos sintéticos para symlink, hardlink, FIFO, permissões, SHA-256/tamanho, troca de inode e mutação durante leitura. **13 testes locais Linux passaram**, macOS CI pendente para o novo HEAD. Não é auditoria de autenticidade do release ou IPA completa, nem proteção durável contra TOCTOU: retorna sempre sem autorização para instalar. [Especificação](docs/WEBREADER_HELPER_FILE_PREFLIGHT_PHASE5F_2026-11-05.md). PR #90 Draft, main/Build 56 intactas, appinst/helper/produção não habilitados.

> **Updater Fase 5E — challenge anti-replay, ainda offline (2026-11-05):** parser da Fase 5D aprovado no GitHub Actions `41974713773`. Acrescentado `ReviewSessionLedger` com challenge de uso único e 30s, contexto de peer, anti-replay/limite de correlações, revogação, verificação de build/digest simulada e **nenhuma permissão de instalação**. Testes adversariais CI e [especificação](docs/WEBREADER_HELPER_REPLAY_PHASE5E_2026-11-05.md) adicionados. **Fase 5E aguardando CI no HEAD**; não há IPC nativo nem execução de `appinst`, chave de produção ou Release. PR #90 Draft; `main` e Build 56 intactas.

> **Updater Fase 5D — contrato de helper somente offline (2026-11-05):** foi criado um parser de solicitações `request-install-review` com JSON estrito e testes adversariais, sem aceitar shell, path, URL, `argv` ou Bundle ID diferente. **Não é um helper executável**, não faz IPC real nem dá permissão para instalação. A [especificação de segurança](docs/WEBREADER_HELPER_IPC_CONTRACT_PHASE5D_2026-11-05.md) exige autenticação de peer, assinatura independente e revalidação de arquivo antes de qualquer implementação privilegiada. **Fase 5C CI aprovada** (run 41973178913), Fase 5D CI ainda pendente neste checkpoint. PR #90 Draft e Build 56/`main` preservadas.

> **Updater Fase 5C — fingerprint read-only de appinst (2026-11-05):** no PR [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90), auditor do DEB agora mede SHA-256/tamanho do **executável** `usr/bin/appinst` e rejeita pseudoarquivos; comparador offline confere hash informado do iPhone com o binário do pacote, sem transferir ou executar o executável. Mesmo que os hashes coincidam, procedência oficial e autorização para instalação permanecem **NÃO verificadas**. CI deve ser conferido no HEAD. Build 56 e `main` preservadas. [Handoff](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).

> **Fase 5B — bloqueio de IPAs malformadas antes do staging (2026-11-05):** PR [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90) agora exige auditoria ZIP/Info.plist completa **após SHA256 e antes de manter uma IPA baixada**. O `WebReaderIPAStager` rejeita mesmo um ZIP com hash assinado correto quando a estrutura é inválida; testes atualizados usam IPA sintética completa via `URLProtocol`. **Aguardando CI deste commit**; nenhuma chave de produção, Release do WebReader, `appinst` ou instalação estão habilitados. [Handoff](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Fase 5A — auditor Swift de IPA (2026-11-05):** branch do [PR #90](https://github.com/AugustoArbulu/MangaReader12/pull/90) incorpora `WebReaderNativeIPAAuditor.swift`, com SHA-256 integral, ZIP central/local, verificação de caminhos/links, `Info.plist`, bundle/build/iOS, sem extração/instalação. Testes host de IPAs malformadas e da **IPA real** do CI; **CI pendente neste checkpoint**. A chave de produção permanece nil, Build 56 de `main` aprovada, sem helper nem `appinst`. [Handoff](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Fase 4D APROVADA FISICAMENTE (2026-11-05, iOS 12.5.8):** usuário testou `WebReader TLS Test` com `URLSession` padrão e somente HEAD. GitHub Raw **HTTP 200**, GitHub Releases **HTTP 200**, raiz do CDN **HTTP 404** (HTTPS válido), e asset real GitHub CLI **HTTP 200 após 1 redirect** `github.com → release-assets.githubusercontent.com`. Isso comprova o caminho TLS e redirects de um asset público real de Releases, **sem download da IPA**. Ainda faltam manifesto assinado/Release próprio, verificação SHA-256 física e autenticação do `appinst` instalado + helper restrito; **não habilitar instalação**. PR [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90) em draft e Build 56 de `main` intacta. [Handoff](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Updater Fase 4C.1 — IPA TLS isolada (2026-11-05):** CI da branch do [PR #90](https://github.com/AugustoArbulu/MangaReader12/pull/90) agora gera `WebReader-TLS-Probe-iOS12-unsigned.ipa` em artefato próprio, com **Bundle ID com.example.MangaReader12.httpsprobe** e nome **WebReader TLS Test**. É uma cópia da Build 56 em sandbox distinto, apenas para medir HEAD/TLS no iOS 12.5.8; não é Build 57, Release oficial ou instalador. Teste de comparativo Info.plist obrigatório no CI; **main estável e banco do WebReader não são modificados**. [Handoff](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Updater Fase 4C — TLS diagnóstico manual (2026-11-05):** PR [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90) implementa `WebReaderReleaseHTTPSProbe.swift` com **HEAD** fixo para `raw.githubusercontent.com`, `github.com` e `release-assets.githubusercontent.com`, sem redirects, cookies ou downloads. Nova seção em Ajustes mostra e copia status HTTP/erros TLS; 403/404 não são contados como atualizações disponíveis. Testes `URLProtocol` totalmente offline; **CI e teste físico ainda pendentes neste checkpoint**. O UpdateChecker de produção segue desativado e **main/Build56 preservados**. [Handoff](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Updater — tela de releases (2026-11-05):** [PR #90](https://github.com/AugustoArbulu/MangaReader12/pull/90) inclui uma entrada distinta em **Ajustes → Atualizações do WebReader**, com versão instalada, situação do canal assinado e notas de release futuro; a antiga atualização em segundo plano agora está rotulada **Atualização da Biblioteca**. Como a chave de produção permanece `nil`, a tela informa **"Verificação indisponível"** sem consultar rede. **Nenhum download/instalador foi habilitado** e a tela ainda não existe na IPA Build 56 aprovada da `main`. Testes e CI pendentes nesta revisão; [handoff](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Updater Fase 4 — manifesto e staging (2026-11-04):** PR [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90) inclui gerador offline `ci/prepare_signed_webreader_update.py` que assina manifestos usando **chaves externas e privadas do usuário**, mais `WebReaderIPAStager.swift` com `URLSession`/CommonCrypto SHA-256 em streaming. Testes adversariais macOS/iOS12 com chave e rede simuladas; **CI pendente**, sem publicação, sem chave de produção, sem downloads reais, sem helper/instalação. **Build56 continua aprovada na main.** [Handoff técnico](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Updater Fase 3 — JSON estrito (2026-11-04):** branch do [PR #90](https://github.com/AugustoArbulu/MangaReader12/pull/90) agora rejeita JSON com chaves duplicadas no **envelope** e no **payload assinado**, incluindo chaves com escapes Unicode e objetos aninhados, por `WebReaderStrictJSON.swift`. Testes Swift compilam o parser real, sem rede nem instalação; **CI desta alteração ainda precisa confirmar aprovação**, e Build 56 permanece referência física em `main`. [Handoff](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Atualizador — UpdateChecker somente leitura (2026-11-04):** branch do PR [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90) agora inclui `WebReaderUpdateChecker.swift` com `URLSession` limitado, assinatura P-256 e endpoint fixo; a chave pública de produção é `nil`, portanto **nenhuma consulta real está habilitada**. Testes com `URLProtocol` simulado são adicionados ao CI. A Build 56 segue aprovada e a `main` permanece inalterada; não há update in-app funcional. [Handoff técnico](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Atualizador Chimera — auditoria estendida (04/11/2026):** PR [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90) em draft. CI fez leitura dos bytes reais do `appinst 2.1.1 iphoneos-arm` do espelho: metadados/estrutura válidos, SHA-256 igual ao índice do espelho, payload `usr/bin/appinst` com `data.tar.lzma`, sem scripts de manutenção. **Origem oficial não verificada** porque `cydia.akemi.ai` não respondeu e o arquivo instalado no iPhone não foi comparado. Nenhuma instalação executada. [Relatório técnico](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md).


> **Checkpoint físico 2026-11-04 — Build 56 aprovada pelo usuário no iOS 12.5.8.** A interface da Biblioteca/Updates da Build 56 foi testada e aprovada. Sistema de atualização in-app via **Chimera + AppSync + appinst** incorporado ao roadmap como trilha paralela, **ainda não funcional no app**. Início da Fase 1 (auditoria e teste offline de manifesto assinado) em branch isolada: [Handoff do Updater Chimera](docs/HANDOFF_WEBREADER_CHIMERA_UPDATER_PHASE1_2026-11-04.md). Nunca usar appinst de espelho não verificado para instalar builds nem modificar a main sem revisão.


> **Build 56 integrada — 2026-11-04:** PR [#88](https://github.com/AugustoArbulu/MangaReader12/pull/88) integrado à `main` no commit `6c3bef88c025205779354b8c53469cd837eb8483`. CI de push e PR no HEAD exato: **sucesso** (inclui iOS12 Debug/Release, teste Swift real de novidades vistas e PNGs Keiyoushi). IPA WebReader Build 56 não assinada gerada e conferida (`CFBundleVersion=56`, mínimo 12.0, mesmo bundle ID). **Falta teste físico do usuário**: Build 55 segue referência fisicamente aprovada. Detalhes: [handoff Build 56](docs/BUILD56_SOURCE_ATTRIBUTION_UPDATES_2026-11-04.md).


> **Build 56 (2026-11-04, implementação em PR):** cada obra agora exibe sua fonte por ID real em Biblioteca lista/grade, detalhes e Atualizações; ícones oficiais Keiyoushi são reutilizados quando há asset. A aba Atualizações inclui `Novas/Todas` e reconhecimento não destrutivo de eventos, distinto de marcar capítulo como lido. Testes Swift offline, iOS 12 Debug/Release e QA física ainda precisam de confirmação antes de promover a versão. Detalhes em [Build 56](docs/BUILD56_SOURCE_ATTRIBUTION_UPDATES_2026-11-04.md).


> **CHECKPOINT FÍSICO ATUAL — Build 55 (2026-11-04):** usuário confirmou “está funcionando” no iOS 12.5.8. PR [#86](https://github.com/AugustoArbulu/MangaReader12/pull/86) integrado à `main` no commit `9657d235b959e5647893889d863be7a82365f355`, após CI verde. Próximo plano [WebReader — Build 56 e roadmap](docs/HANDOFF_WEBREADER_BUILD55_ROADMAP_2026-11-04.md). **Requisito novo da Build 56:** mostrar a fonte real associada a **cada obra** da Biblioteca (nome e ícone disponível, lista e grade), inclusive várias obras com o mesmo título vindas de fontes distintas. Não confundir IDs nem perder dados.


> **Build 55 (2026-11-04):** assets originais Keiyoushi para Asura, WeebCentral, Webtoons e outras fontes mapeadas por ID; `SourceIconCell` prioriza ícones locais sem rede em Fontes instaladas e no catálogo. A fonte `kei.manhwa18net` **não** usa o ícone da extensão upstream `manhwa18.com`, que é um site diferente. [Handoff Build 55](docs/BUILD55_KEIYOUSHI_OFFICIAL_SOURCE_ICONS_2026-11-04.md). A Build 54 foi relatada como funcional no iOS 12.5.8. Build 55 requer CI e QA física.


> **Atualização 2026-11-04 — Build 54:** nome público do aplicativo e ícone alterados para **WebReader** (kanji vermelho 画 sobre preto) (`CFBundleDisplayName`, `CFBundleName` e Ajustes). Identificador `com.example.MangaReader12`, executável, target, diretórios, banco SQLite, backups e extensões permanecem inalterados para preservar dados. Veja [Build 54](docs/BUILD54_WEBREADER_BRANDING_2026-11-04.md). A validação física da Build 54 ainda depende de teste no iOS 12.5.8.


> **CHECKPOINT ATUAL — 2026-11-04 (Build 53):** a parte histórica abaixo começou no Build 16. O estado mais recente está no handoff [docs/HANDOFF_MANGAREADER12_BUILDS51_53_2026-11-04.md](docs/HANDOFF_MANGAREADER12_BUILDS51_53_2026-11-04.md). Build 51 teve feedback físico preliminar positivo; Builds 52/53 foram aprovadas em CI iOS12, mas aguardam validação no dispositivo. Fonte Asura EN 0.1.3 e libwebp 1.6.0. Não alegar AVIF decodificado. A main mais recente após PR #83 é `4923420f918c57772037112c50f93995549b09f3`.


## Checkpoint

- Project: MangaReader12
- Phase: **Batch M7C–M9A — visual covers, backup/restore, migration, reader QoL, storage and opportunistic updates**
- Deployment target: **iOS 12.0 — locked**
- Canonical toolchain: **Xcode 15.4 / Swift 5.10 compiler / Swift 5 language mode**
- CI target: GitHub Actions `macos-14`
- App version: **0.1.0 (16)**

## Accepted physical checkpoints

- Milestone 0 — COMPLETE
- M1A — ACCEPTED (4/4)
- M1B — ACCEPTED (5/5)
- M1C — ACCEPTED (6/6)
- M2A — ACCEPTED (7/7)
- M2B — ACCEPTED (8/8)
- M2C — ACCEPTED (9/9)
- Batch M2D–M3A — ACCEPTED (11/11 + repository/runtime flow)
- Batch M3B–M4A — ACCEPTED (browse/details/chapters)
- Batch M4B–M5A — ACCEPTED (reader + persistent Library)
- Batch M5B — ACCEPTED (custom iOS 12 Dark Mode)
- Batch M5C–M6B — ACCEPTED (progress/history/cache/offline)

## CI-complete but physical acceptance pending

### Batch M6C–M7B / build 10
- PR #12 merged
- Merge commit `792fc8852da836da5aaf99bb39e3a29d8b9b8991`
- Post-merge run `40823779755`: green
- Physical checks for updates/categories/reader preferences/Downloads UI were not reported before work continued.
- Those checks are included in the build-11 physical gate.

## Implemented in build 12 (build-11 mega-batch + hardening)

### M7C — visual manga UI / covers
- Source-returned `cover` URLs render in Browse/search.
- Cover rows now appear in Library, History, Updates and Downloads.
- Manga details use a larger native UIKit cover/header layout.
- Memory + disk cover cache.
- Source-manifest domain allowlist is enforced while browsing; persisted entries may refetch only their exact cover host.

### M8A — backup / restore
- Portable `.mr12backup` format.
- Consistent SQLite snapshot via SQLite backup API.
- Includes Library/manga/chapter/history/categories/repositories/source settings plus selected app/reader settings.
- Excludes downloaded chapter files and installed JavaScript source scripts.
- Portable snapshot removes download DB state and installed-source records so restore does not claim missing files/scripts exist.
- iOS document picker export/import.
- Restores root UI after import.

### M8B — source migration
- Searches other installed + enabled sources for matching title.
- Visual candidate list with covers.
- Transfers Library entry, categories, compatible read/last-page progress and history.
- Chapter mapping prefers chapter number and falls back to normalized chapter name.
- Offline downloads intentionally do not migrate.
- Controlled second source `fixture.altdemo` allows deterministic physical testing.

### M9A — reader quality of life
- Persisted background: black / gray / white.
- Optional page number.
- Keep screen on with prior idle-timer state restored on exit.
- Tap zones: side navigation + center chrome toggle.
- Double-tap zoom.
- Optional Webtoon gap.
- Existing mode, LTR/RTL, brightness, resume and prefetch remain.

### M9A — data / storage
- Data & Storage settings screen.
- Database/download/cache byte totals.
- Clear reader cache.
- Clear cover cache.
- Reindex downloads whose local files are missing.
- Delete all offline downloads without deleting Library/progress/history.
- Existing per-download management is linked from the same screen.

### M9A — background Library updates
- Optional iOS 12 Background Fetch.
- Manual refresh remains the reliable path.
- Background execution is opportunistic and scheduled by iOS, not guaranteed at a precise time.
- Background fetch writes discoveries to the same persistent Updates feed.

### Product audit
- `docs/MIHON_FEATURE_AUDIT_IOS12.md` records current Mihon-inspired features, iOS adaptations, limitations and future priorities.

### Hardening before physical test
- Same-device restore preserves source records only for sources whose active scripts still exist on disk.
- Restore clears excluded offline chapter files so download state and storage remain coherent.
- Loading details for an existing Library entry refreshes its persisted cover/title/status/description/chapters, so older entries can gain cover metadata from updated sources.

## Regression

- Existing 11/11 core diagnostics must remain green.
- iOS deployment target remains 12.0.
- Build 10 physical gate is carried into build 11.

## Build-12 physical acceptance gate

One consolidated test should validate:
1. Build-10 pending flows: Chapter 2 update detection, categories/filtering, reader mode/direction/resume and Downloads screen.
2. Update demo repository: MangaReader12 Demo should become **1.3.0**; also install **MangaReader12 Alt Demo 1.0.0**.
3. Cover thumbnails appear in source browse and persisted screens after the title has been refreshed/saved.
4. Demo Manga details show a large cover, title, metadata, genres and description.
5. Backup: create/export a `.mr12backup`, make a visible state change, restore the backup and verify the earlier Library/category/progress/settings state returns.
6. Migration: with Demo Manga in Library and Alt Demo installed, Details → Migrar → choose Alt Demo. Category and compatible read progress/history should transfer. Downloads should not transfer.
7. Reader QoL: background color, page-number toggle, side tap zones, center chrome toggle, double-tap zoom, keep-screen-on setting, Webtoon gap.
8. Data & Storage: size rows load; reader/cover cache cleanup works; reindex downloads completes; delete-all-downloads clears Offline state without deleting Library/history.
9. Automatic updates toggle can be enabled/disabled. Actual background execution cannot be deterministically forced because iOS 12 schedules Background Fetch.
10. Dark Mode, History, Library, reader and 11/11 diagnostics remain functional.


## Build 13 hotfix — backup validation

- Physical build 12 report: everything worked except backup restore.
- Failure: generated `.mr12backup` was rejected by the restore validator.
- Root cause: restore validation required exact `PRAGMA user_version == 1`, which is unnecessarily brittle for a structurally valid MangaReader12 SQLite snapshot.
- Fix: validate `PRAGMA quick_check`, accept non-future schema versions, and require the full MangaReader12 table set.
- Existing backups remain format-version 1 and should restore without regeneration.
- Do not mark M7C–M9A fully accepted until the build-13 restore retest passes.


## Build 14 hotfix — iOS 12 SQLite validator syntax

- Build 13 physical restore reached the new validator but failed at the integrity query with:
  `The backup database failed validation: could not execute validation query`.
- This isolates the issue to `PRAGMA quick_check(1);`, not the backup envelope or Base64/SQLite extraction.
- Build 14 uses the legacy-compatible `PRAGMA quick_check;` syntax.
- Validation-query errors now expose the actual SQLite prepare/step code and message.
- The same previously exported `.mr12backup` remains the required retest file.


## Build 15 UI hotfix — reader chrome + source icons

- Carries the build-14 backup restore validation compatibility fix.
- Reader center tap now hides:
  - navigation bar,
  - reader bottom controls,
  - main app tab bar.
- All chrome is restored when toggled back on or when leaving the reader.
- Repository source manifests now validate optional icon URLs as HTTPS.
- Repository catalog and installed-source lists display source icons with cached loading and initials fallback.
- Demo repository publishes icons and bumps demo manifests to 1.3.1 / 1.0.1 so existing installs can persist the new icon metadata.

### Build-15 physical gate
1. Reuse the same `.mr12backup` and confirm restore succeeds.
2. In reader, center tap must hide both top and bottom app chrome; second tap restores them.
3. Refresh demo repository and update Demo/Alt Demo to 1.3.1 / 1.0.1.
4. Confirm extension/source icons appear in repository catalog and installed-source list.
5. Confirm 11/11, Dark Mode and existing reading flows remain functional.


## Build 16 hotfix — portable SQLite WAL normalization + immersive reader

Physical build-15 feedback:
- extension/source icons: **working**
- backup restore: failed with `SQLite 14: unable to open database file` during validation
- reader center tap removed tab labels/content but the main tab-bar band remained visible

### Backup fix
- Portable backup payload now gets its SQLite header checked before opening.
- The restored temporary database is opened read-write and normalized with:
  - `PRAGMA temp_store=MEMORY`
  - `PRAGMA journal_mode=DELETE`
- Validation then checks supported schema version + required MangaReader12 tables.
- `quick_check` is removed from the physical restore path because the old backup can be a WAL-mode database image without companion `-wal/-shm` files.
- Existing `.mr12backup` remains the required retest file.

### Reader fix
- Reader is pushed with `hidesBottomBarWhenPushed = true`.
- The main app tab bar is therefore removed by UIKit for the entire reader screen, including its background band/safe-area layout.
- Center tap still toggles the reader-specific top/bottom controls.
- Leaving the reader restores the app tab bar automatically.

### Physical gate
1. Restore the same old `.mr12backup`.
2. Confirm Library/category/progress/settings return.
3. Open reader and confirm the main app tab bar/band is absent entirely.
4. Center tap must hide/show reader chrome without leaving a bottom app band.
5. Reconfirm extension icons remain visible.


## Build 16 physical acceptance — 2026-10-29

- Physical iOS 12 retest: **backup restore PASS** using the existing backup.
- Physical iOS 12 retest: **immersive reader PASS**, including the main bottom tab bar/band.
- Build 16 was merged by PR #18; merge SHA \`c983091a73506d1c079c24223f8fb38c21925ca3\`.
- Post-merge run \`40833175316\`: green.
- Source icons were already physically approved in build 15.
- The two outstanding build-16 blocking defects are now closed.

## Build 17 — M9B reader chapter lifecycle and scale (physical gate pending)

- Source chapter list is ordered by numeric chapter number when all are numbered; otherwise it follows reverse source listing.
- Reader options expose previous/next chapter without building up a reader navigation stack.
- Chapter page resolution keeps local offline download priority, then the installed JS source runtime.
- Optional next-chapter preload starts near the end of the current chapter and caches up to two upcoming images.
- Reader page scaling: fit screen, fit width, fit height, original image point size.
- Scale mode and preloading preference are persisted and included in future backups; existing backups keep default values.
- The last-page progress write snapshots the chapter identity before asynchronous SQLite persistence.
- iOS 12 / UIKit / Swift 5 / Xcode 15.4 guardrails remain unchanged.

### Build 17 consolidated physical gate

1. Open Demo Manga's chapter 1, use Opções → Próximo to go to chapter 2; then Anterior back to chapter 1.
2. Return to details: there must be one reader screen and no stacked readers; tab bar returns normally.
3. Turn next-chapter preload on/off under Ajustes → Leitor and verify chapter navigation still works both ways.
4. Test Fit screen, width, height and original size in page mode, including zoom and rotation; Webtoon should remain full-width.
5. Restore progress by reopening a chapter; check read/history and offline pages still work.
6. Confirm no regressions to backup restore, source icons and iOS 12 diagnostics (11/11).


## Build 17 physical feedback (partial)

- User reports the build 17 **appears to be functioning** on iOS 12.
- Requested a more convenient way to compare page scales directly within a chapter.
- Do **not** mark the full M9B physical gate as passed yet.

## Build 18 UI adjustment — live scale comparison (physical gate pending)

- The chapter's Opções entry opens a compact floating scale comparison strip over the reader.
- Four options: Tela / Largura / Altura / Original. Switching updates already visible images immediately while keeping the strip open.
- A Fechar button and center-tap hide the strip; changing to Webtoon also closes it.
- The current page and saved chapter progress are not reset by scale comparison.
- Existing reader settings and backup preference persistence are reused; no schema changes.
- Consolidated physical retest: same image, switch four scales repeatedly, check page stays the same, closing controls, Webtoon, and chapter navigation.
- Compatibility: iOS 12.0 target, UIKit, no SwiftUI/Combine/async-await.


## Build 18 physical issue / Build 19 hotfix (2026-10-29)

- User physically reported that pressing the centered **Largura/Altura** segments fires the reader's center-tap hide-controls action.
- Build 18 scale UI is otherwise available but **not fully physically approved** because of this gesture collision.
- Build 19 registers UIGestureRecognizerDelegate on the reader's root-level single/double tap recognizers, excluding taps anywhere in visible in-reader overlay panels and nested UIControls.
- Center taps on the manga image remain enabled, and side tap-zone navigation remains unchanged.
- Branch: hotfix-build19-reader-overlay-gesture. The full build-17 M9B suite still has no complete physical acceptance report.
- Physical gate: open scale panel and alternate Tela/Largura/Altura/Original repeatedly, confirm panel stays open, and verify center tap on the manga image still toggles controls as before.
- iOS 12.0 deployment target and UIKit remain locked.


## Build 19 physically accepted (2026-10-29)

- User reports **"esta funcionando agora"** following Build 19 bug fix on physical iOS 12.
- Build 18's centered Largura/Altura touches no longer hide the reader UI.
- Closes the scale-controls gesture-collision hotfix gate, build 19.
- Does not independently assert that every Build 17 navigation/preload test was repeated.

## Build 20 — M10A download management, partial first increment (physical gate pending)

- Downloads refreshes live state while onscreen (1.5s polling) and supports pull-to-refresh.
- Failed downloads can be retried directly from their row; source loader retrieves the latest available manga, chapter and page data before restarting.
- Disable removal of chapters actively being downloaded because current HTTP downloader lacks cancellation.
- Keeps source-domain policy and native storage paths; no SQLite migration.
- Build 20 is not yet complete download queue management: **pause, resume, persistent ordered queue and reorder are future stages**.
- Physical gate: verify failed row's swipe-to-retry where possible; progress refresh and pull-to-refresh; completed offline chapter opens; no mid-write deletion; 11/11 diagnostics and reader scale remain intact.


## Build 20 — Physical acceptance (2026-10-30)

- User explicitly reported **"tudo funcionando"** after physically testing the Build 20 iOS 12 IPA.
- Build 20 Downloads live progress/pull-to-refresh/retry is **physically accepted**.
- Pre-existing Build 19 scale-panel gesture fix remains accepted.

## Build 21 — M10B shared foreground download queue (physical gate pending)

- All callers of ChapterDownloadManager.defaultManager share one retained queue coordinator in the running app.
- One active chapter transfer at a time; further chapters enter **queued** state, retaining source-specific HTTPS/allowed-domain policy.
- Pausing a queued/active download updates SQLite and cancels only its active URLSession task.
- Resuming inside the current app session keeps the atomically completed page files and continues with the first incomplete page.
- Queued chapters may be prioritized via the Downloads row swipe action.
- Removing an active transfer is prohibited to avoid deleting files under a live writer.
- Downloads row swipe: Pausar (queued/downloading), Retomar (paused), Priorizar (queued), retry (failed), remove (other states).
- The Downloads timer only reloads the table when records change; swipe menus remain usable.
- Cold app relaunch cannot reconstruct pending network requests yet. Interrupted queued/running rows become **failed / retryable** on manager initialization. Paused rows are shown as paused; Retomar re-resolves source pages and restarts from page zero if the in-memory job no longer exists.
- Persistent resume across app relaunch, serialized job metadata and durable queue ordering are **future work**, not implemented here.
- All prior offline files, Library/history/backup/source behavior is unchanged. No schema migration.
- Maintains iOS 12.0, UIKit/AppDelegate, Xcode 15.4 / Swift 5 language mode.

### Focused Build 21 physical gate

1. Start a chapter download and pause while progress is visible; ensure percentage stays stable.
2. Resume; percentage should continue from previously completed pages and finish offline.
3. Queue two downloads from the source chapter list; confirm one runs and the other shows "Na fila".
4. Prioritize the queued chapter, pause/resume queued, then confirm the next transfer progresses.
5. Try swiping while a chapter downloads: it must not offer unsafe removal.
6. Optional: force-close app with queued/paused state; reopen, confirm interrupted rows become retryable and "Retomar" on an old paused record restarts via source.
7. Confirm no regressions to reader scale, backup, source icons and on-device 11/11 diagnostics.


## Build 21 physical gate blocker (2026-10-30)

- User cannot practically test the queue: bundled Demo source downloads in approximately **0.1 seconds**.
- This **does not constitute failure or acceptance** of queue/pause/resume; device QA is blocked by an unrealistic fixture duration.
- Do not request pause/priority tests on unrestricted instant Demo again.

## Build 22 — opt-in Demo download slow-test mode (physical gate pending)

- Downloads top-right "Teste 8s: OFF / ON" switch is stored in UserDefaults and defaults to OFF.
- When ON, only fixture.localdemo/fixture.altdemo waits 8 seconds **asynchronously** before each page starts; real sources always download at normal speed.
- Pending delayed work checks active job, paused state, page index and serial before issuing HTTP; pause/resume is safe even during a simulated delay.
- No artificial image data; image bytes and offline verification still come from existing source URL and hardened HTTPClient.
- Physical test: turn on Teste 8s in Downloads, open Demo manga and download a chapter, navigate back to Downloads and pause. Verify stable progress during pause, resume and eventual offline completion; optional two queued/priority test. Disable the switch after QA.
- Test mode is not an app performance setting and does not change the downloading implementation outside fixtures.


## Build 22 — physical feedback / timed Demo QA (2026-10-30)

- User reported "funcionou" after installing Build 22 and using the deterministic Demo speed-control workflow.
- This confirms the timed test path works on-device and removes the original 0.1s manual-test blocker.
- The user did not separately detail every pause, reorder and multiple-download scenario; do not infer a full regression matrix PASS.

## Build 23 — M10C restart-safe foreground download recovery (physical gate pending)

- Writes a private Codable _download-plan.json alongside each queued chapter's page files, with original source manifest, page URLs/headers and saved queue priority. Applies file protection to this sensitive app-sandbox data where available.
- DefaultManager restores valid plans on first creation after launch, checks source/manga/chapter identities, stored directory path and number of pages.
- Restores nextIndex from a verified contiguous prefix of nonempty page-%05d.bin files. A partially downloaded current page is fetched afresh; completed pages are reused.
- Database recovery transitions interrupted queued/active jobs into ordered foreground work and leaves manually paused jobs paused.
- Persists priority promotions across restarts; invalid plans remain retryable and do not destroy existing pages.
- Cleans recovery plan when job succeeds/fails, preserving offline image files. No SQLite migrations.
- iOS 12.0, UIKit/AppDelegate, Swift 5, Xcode 15.4, source-allowed domain policy and no anti-bot bypass remain in force.
- **Limitations:** no guarantee of transfer while backgrounded/terminated. Some sources may expire image URLs or authentication headers; an expired restored job may fail and should be retried to fetch fresh source data.

### Build 23 focused physical gate
1. In Downloads switch on Teste 8s and begin a Demo chapter download.
2. Let at least one page finish; force-close the app while the next page is pending (not just return to home).
3. Reopen Downloads. It should resume the remaining pages without resetting the downloaded prefix. Allow offline completion.
4. Start another chapter, pause it, force-close and reopen: it must remain Pausado until you explicitly select Retomar.
5. Queue multiple chapters, Priorizar one, force-close and reopen: priority should remain.
6. Return Teste 8s to OFF; verify existing offline chapters and reader controls still work.


## Build 23 physical acceptance — 2026-10-30

- User explicitly reported **"tudo funcionando"** on Build 23, following the requested restart-download-recovery tests.
- Record the Build 23 M10C device gate as **PASS (user-reported)**.
- This covers foreground restoration after closing/reopening the app and the prior controlled Demo-download workflow as reported.
- Distinguish foreground restart recovery from true iOS background downloads, which remain unsupported.

## Build 24 — M11A search across installed sources (physical gate pending)

- Explore now presents a magnifying-glass action that pushes **Busca global** without changing bottom tabs.
- Search issues source API v1 search(query, page=1, filters=[]) sequentially to each enabled installed JavaScript source; one failing source does not hide successful results.
- First page only, capped at 40 matching items per source. Status reflects sources queried, total matches, and failures. This bounded search prioritizes old-device memory and runtime safety.
- Results retain the exact source record (manifest/id/domains) and open original MangaDetailsViewController after loading that source's JavaScript runtime.
- Generation token invalidates stale async results after query changes or cancellation.
- User's current iOS 12 source engine is unchanged; Android APK compatibility/Keiyoushi direct execution is **not** implied.
- Does not change download, backup, reader or SQLite schema, and does not bypass site restrictions.
- Physical check: install the two bundled Demo sources, search a shared sample manga title, verify results show source names, tap one result, open details/chapter. Search a nonmatch and cancel. Confirm original per-source search remains functional.


## Build 24 physically accepted — 2026-10-30

- User reports "funcionou" after using Build 24 global search on their iPhone.
- M11A global JS source search baseline is accepted.
- No claim that all source failure/cancellation edge cases received separate physical checks.

## Delivery cadence (requested 2026-10-30)

- User prefers meaningful multi-feature increments and one grouped device test instead of frequent tiny IPA builds.
- Prioritize cohesive milestone bundles, compile/CI and static QA before delivery, reserve focused physical validation only for interface/device interactions not reproducible in CI.
- Work only on feature branches and merge after green push + PR CI; preserve iOS 12, repo main and existing accepted features.

## Build 25 M11B — Global search & source-tools batch (device QA pending)

1. Global search displays a Load more footer for sources advertising hasNextPage. Each source advances its own page counter; up to 5 pages/source and at most 40 results/page are rendered.
2. Fontes opens an enabled-source checklist. All enabled sources are selected by default. Aplicar changes the search scope and invalidates old async callbacks.
3. Repeated manga IDs are de-duplicated within the same source; distinct source records are preserved.
4. Exploration source action "Informações e dados da fonte" displays manifest metadata, allowlisted domains and count of stored source-local JS preference keys.
5. Explicit runtime metadata check and confirmation-gated deletion of only JS sources.<sourceID>.storage.* values. User must opt in; no automatic clearing.
6. The source reset does not touch downloads/Library/history/reader prefs, nor cookies. Source runtime and source API remain unchanged.
7. No alteration of downloader, backup, SQLite schema, reader, or deployment target. Swift 5/UIKit/iOS 12.0.

### Grouped device acceptance

- Open Explorar -> lupa -> Buscar. Search with both Demo sources enabled and confirm source-tagged hits and opening manga details.
- Open Fontes, select only one source, apply, and confirm only that source appears; select Todas to restore.
- If a source returns hasNextPage, use Carregar mais resultados and confirm page append, stable source labels, no duplicates. Demo fixtures may not have pagination; no synthetic extra pages are asserted.
- Open Explorar -> installed source -> Informações e dados da fonte. Inspect manifest and run Verificar runtime.
- In source tools, check confirmation before resetting storage; cancel first. Optional destructive clear only if testing disposable Demo settings, and verify Library/downloads remain intact.
- Verify Backup/Reader/Downloads and 11/11 diagnostics without repeating exhaustive old feature tests.


## Build 25 physical feedback (2026-10-30)

- User reports "tudo parece estar funcionando" after testing Build 25 search filters, source tools and existing experience.
- Mark the examined Build 25 flow as provisional physical PASS; pagination with hasNextPage and source-storage destructive reset were not independently evidenced.
- User prefers larger cohesive batches rather than a new IPA for each tiny feature.

## Build 26 M12A — first real source trial, MangaDex (device QA pending)

- Source API v1 now supports optional asynchronous callbacks as trailing arguments for calls decoded by JavaScriptSourceRuntime. Synchronous source fixture functions remain compatible. A 25-second timeout prevents indefinite waits.
- Separate pinned experimental MangaDex catalog: fixtures/repository-mangadex.json; JS script: fixtures/source-mangadex.js, SHA-256 38b360b0d08cfd7d2ecc204749408471a535b8f405a20ada4d5a50a894f78188.
- Source features: search/popular, covers, manga details, first 100 English chapters, data-saver page URLs. Search uses 20 items per page and allowed-domain HTTPS; API 429 is surfaced, not bypassed.
- Crediting MangaDex and scanlation groups is included; avoid ads, paid access or publication workflows inconsistent with MangaDex API acceptable-use rules.
- Existing demo fixtures and downloaded chapters are not modified; no migrations and no direct Android Keiyoushi APK support.
- Risks: API or CDN may fail from the physical iOS 12 network; MangaDex@Home can issue dynamic delivery hosts outside *.mangadex.network which should remain blocked by HTTPPolicy. Older chapters, alternate translated languages and CDN host fallback remain future scope.
- Real site connection and image loading are NOT marked accepted until on-device test. Mocked Node API responses and Swift CI compilation alone cannot prove it.

### Focused one-shot device test for Build 26

1. Install the new IPA. Under Explorar tap + -> Inserir URL HTTPS and paste https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/repository-mangadex.json
2. In the new MangaDex Experimental catalog install MangaDex (experimental); ensure source active.
3. Open MangaDex. Verify real popular cover/title list and search for an English title.
4. Open real manga details and chapter list, including visible scanlation group attribution.
5. Try opening an English chapter. If the image delivery domain is rejected or MangaDex rate-limits, retain the exact error and do not retry repeatedly.
6. Optionally verify offline download of an accessible chapter and the existing Demo source.
7. Do not use repositories of Android APKs as JS catalog URLs; these remain incompatible.


## Build 26 real MangaDex pilot — physical failure (2026-10-30)

- User installed experimental MangaDex source and received: Source failed: network transport error -1200: An SSL error has occurred and a secure connection to the server cannot be made, when tapping Abrir source.
- First popular call targets https://api.mangadex.org. An SSL/TLS failure occurred before an HTTP response was decoded. Exact failing host and underlying SSL code are still unconfirmed on the device.
- MangaDex source is NOT physically accepted. Do not conflate the error with a 403, 429 or chapter parsing failure.
- -1200 alone cannot determine whether the cause is certificate trust, protocol/cipher incompatibility, route/interception, device clock or URLSession-specific behavior.
- Apple documents TLS 1.3 enabled by default in URLSession starting iOS 12.2; minor OS version not yet confirmed.
- Never disable certificate verification or global ATS to hide the error.

## Build 27 — safe differential TLS diagnostics (physical gate pending)

- Explore -> installed MangaDex -> Informações e dados da fonte -> Diagnosticar HTTPS do MangaDex.
- Read-only tests compare API /ping via the production HTTPClient and URLSession.shared, then MangaDex site, GitHub raw fixture and example.com controls. Shows iOS version and sanitized error codes.
- Copiar relatório copies a diagnostic report with no secret request headers or cookies.
- Safari can independently test https://api.mangadex.org/ping and report whether it displays pong or a certificate/secure connection warning.
- No source script or repository catalog updates, no insecure TLS bypass and no changes to supported iOS 12 baseline.
- Build 27 is diagnostic only; needs device results before a targeted fix.


## Build 27 detailed device feedback — iOS 12.5.8 (2026-10-30)

The user ran the real diagnostic. Full relevant results:
- Safari https://api.mangadex.org/ping => pong
- HTTPClient => NSURLError -1200
- URLSession.shared API => NSURLErrorDomain -1200, kCFNetwork -1200, _kCFStreamErrorCodeKey -9836
- URLSession.shared MangaDex home => same -1200 / -9836
- GitHub raw control => HTTP 200
- example.com control => HTTP 200

Source API remains blocked on device. This distinguishes peer TLS protocol negotiation failure from an app-specific HTTPClient bug. Do not conclude TLS1.3 absence (iOS12.5.8 has default TLS1.3 support in URLSession/Network.framework).

## Build 28 — Alternate default-trust TLS probes (device gate pending)

- Source tools > Diagnosticar HTTPS do MangaDex appends a WKWebView ephemeral isolated WebKit test to https://api.mangadex.org/ping.
- Then performs a Network.framework NWConnection TLS handshake to api.mangadex.org:443 using system certificate/host validation without custom trust overrides.
- Both tests are read-only, have 14s guards, use no credentials, add no broad network permissions and do not change source availability.
- A successful alternate transport indicates a possible secure native client approach; a failed probe rules out that exact path, not all solutions.
- If WKWebView succeeds, the next milestone is a carefully guarded verified WebKit-backed API fetch with host allowlist and strict output limits, not an automatic disabling of URLSession trust.
- If both alternate probes fail, investigate client TLS hellos / server configuration, CDN route policy and permitted server-side compatibility adjustments before proposing a relay.
- Apple peer protocol version -9836: https://developer.apple.com/documentation/security/errsslpeerprotocolversion
- Apple platform TLS note: https://support.apple.com/pt-br/guide/security/sec100a75d12/web

## M13 — nine user-selected Keiyoushi sources (selection recorded 2026-10-30)

- Explicit scope limited to nine requested extensions: Comix, Asura Scans, Webtoons.com ("webtoon"), Vortex Scans, MadaraDex, HotComics, Manhwa18.net, ToonGod, and Manhwa18.cc.
- Source-of-truth repositories: https://github.com/keiyoushi/extensions-source (Kotlin source), https://github.com/AugustoArbulu/MangaReader12 (native Swift iOS12 runtime).
- Source modules exist upstream as of 2026-10-30. Exact technical inventory, shared engines, risk and incremental port design are recorded in docs/M13_SELECTED_KEIYOUSHI_SOURCE_PORTS.md.
- Selection establishes priority only. No selected source is currently installed from Keiyoushi APK, ported, or physically accepted in MangaReader12. Never present the upstream list as an executable iOS catalog.
- Keep the approved Build25 behavior stable. Build28 MangaDex native TLS diagnostics are pending physical feedback. The MangaDex pilot is diagnostic/experimental and not one of the nine selected ports.
- Proposed port development in cohesive bundles: shared safe HTML/HTTP adapters and first independent sites; shared Madara/Iken/Yii engines; complex or restricted sources last. Deliver IPA only after coherent bundle and post-merge CI.
- No anti-bot bypass, forged authorization, unrestricted remote hosts, insecure TLS or persistent unreviewed native APK execution. Respect third-party access terms, license and attribution.


## M13-A Build 29 — first 3 user-selected Keiyoushi source adapters (2026-10-30)

- Current active scope: 9 requested sources from M13 PR #31. MangaDex is paused by explicit user direction; its earlier Build29 TLS fallback PR #32 was CLOSED UNMERGED, not deployed. Do not restart it unless user explicitly requests.
- Selected independent source pack now has three experimental JS ports: HotComics (en, NSFW), Manhwa18.net (en, NSFW), Webtoons.com EN (safe), in fixtures/keiyoushi-{hotcomics,manhwa18net,webtoons-en}.js.
- Dedicated SHA-pinned catalog fixtures/keiyoushi-selected-repository.json. Does not modify bundled Demo or MangaDex catalogs. Scripts honor iOS native source API v1, callback-based HTTP bridge, strict HTTPS allowlist, and route/API metadata from Keiyoushi's Apache-2.0 project.
- Native HTML selector bridge Native.htmlSelect uses inert WebKit DOMParser, CSS selector specs and bounded JSON, with no third-party page script execution or WebView navigation to site domains. This is an iOS12 client parser; iOS physical QA pending.
- CI has Node smoke tests for six required source methods, response parsing and bad URL rejection. Simulated CI and successful Swift build DO NOT prove live site availability.
- First useful physical gate: install Build29 over Build28, add new catalog URL https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/keiyoushi-selected-repository.json; install each source, test catalog + a permitted search + details + chapters + reader; report first exact failure per source.
- Caveats: no official affiliation to Keiyoushi or hosted sites; CDN image domains can differ and be blocked; Webtoons motion toon unsupported, English only; HotComics chapter links may require permitted login; Manhwa18.net payload markup/selector may change. Do not bypass.
- Remaining six user-selected source ports (Vortex Scans, ToonGod, Manhwa18.cc, Asura Scans, MadaraDex, Comix) remain planned/unimplemented. Shared engine groupings in docs/M13_SELECTED_KEIYOUSHI_SOURCE_PORTS.md.
- Do not release Build29 as physically accepted before device test.


## M13-A Build29 user physical QA feedback (2026-10-30, iOS 12.5.8)

- Webtoons.com EN: source loads and chapter content images display on the real device. Series thumbnails/covers absent. Search/details/chapters were not independently detailed by the user; do not claim all functions accepted.
- Manhwa18.net: same: browsing and reading chapter images work, series thumbnails/covers absent.
- HotComics: HTTP 403 on access. This is a server response, not evidence of a JS parser or TLS bug; do not bypass access protection.
- Important: chapter image pipeline has separate lifetime from CoverImageLoader. Native cover loader creates temporary HTTPClient, whose deinit invalidates the URLSession, cancelling image loads. This is a code-verified defect affecting all thumbnails.

## Build30 native cover loader fix (physical QA pending)

- Retain each HTTPClient in a CoverImageLoader in-flight dictionary protected by NSLock until network callback, then remove. Existing cache remains; source allowed host policy checked before cache as well as before requests.
- No new JS scripts or catalog hash changes. Install Build30 over Build29 via Sideloadly; installed source and library data remain intact.
- Device test: open Webtoons.com and Manhwa18.net lists and details, confirm covers after a short normal load, then open an existing chapter to check reading regression. Check Library cover if present.
- If covers still missing, gather actual cover host and HTTP status (may require a focused in-app diagnostic). Do not blindly add unverified third-party CDN domains or bypass trust.
- HotComics remains blocked by HTTP 403 and not physically accepted. No repeated reattempts.
- MangaDex still paused; selected nine Keiyoushi adaptations remain the next engineering milestone.


## M13-A source-only Webtoons cover hotfix 0.1.1 (2026-10-30)

User's Build30 physical report: Manhwa18.net covers NOW display. Webtoons.com EN covers are missing only on the source listing; opening a work shows the cover. Webtoons chapter images still display, per previous QA. This separates global native cover HTTPClient lifetime failure (resolved for Manhwa18.net) from Webtoons list thumbnail extraction. HotComics HTTP403 persists and no bypass is approved.

The Webtoons list JS adapter v0.1.0 only read the first card img src, whereas details use og:image. Some list layouts may use a data image placeholder in src and store the HTTPS thumbnail in data-src or srcset. Source v0.1.1 selects supported native HTTPS URL variants and ignores placeholders. This is a hypothesis-guided source-only fix, not physically verified yet. The allowlist remains webtoons.com / pstatic.net and the script/catalog SHA-256 are pinned and checked in CI.

Do not build an IPA for this source-only change. After PR merge and CI, user should refresh the selected Keiyoushi source repository and apply the offered Webtoons update. Manhwa18.net source unchanged. If Webtoons thumbnails still fail, obtain a safe per-source cover URL/status diagnostic rather than broadening hosts or making N background manga-detail requests. Continue M13 selected ports. MangaDex remains paused.


## M13-A Build31 — Webtoons cover differential diagnostic (2026-10-30)

User physical Build30 and Webtoons 0.1.1 reports: Manhwa18.net covers now appear and chapter images work. Webtoons.com EN cover thumbnails still blank in list after source 0.1.1; cover appears inside manga details, and chapter images load. HotComics HTTP403 remains inaccessible.

Build31 is a **diagnostic-only** change, not another unverified attempt to fix server images. In Webtoons.com EN browse view add navigation button `Testar capas`, available when at least one Popular item loaded. User tap explicitly triggers sequential comparison for the first listed work: source-provided list cover URL -> one HTTPS GET; source existing details() -> details cover URL -> one HTTPS GET. Report logs host, extension, query presence, HTTP status/error, MIME/size, UIKit UIImage decoding yes/no; no full URL, title, headers, cookies, or response bodies. At most 2 image GETs; 15s timeout each, 5MiB cap; stop on HTTP429. Source domains policy remains in force.

Test acceptance: user installs verified Build31 on iOS12.5.8, enters Webtoons.com EN Popular, taps `Testar capas`, selects `Copiar relatório` and pastes full report. Outcome can distinguish null/placeholder list URL, blocked host, SSL, unsupported image type, or a native presentation/cache defect when the same file decodes. Do not claim fixes before results. Manhwa18.net unaffected; scripts and SHA256-pinned catalog stay exactly the same.

## M13-A Webtoons EN v0.1.2 — list CDN normalization candidate (2026-10-30)

- Physical Build31 report, iOS 12.5.8: first list cover on `webtoon-phinf.pstatic.net` returned HTTP 403 text/html (467 bytes, UIImage NO); the same manga details cover on `swebtoon-phinf.pstatic.net` returned HTTP 200 image/jpeg (116259 bytes, UIImage YES).
- Evidence indicates host/path/request-context differences rather than an iOS image decoder failure. Exact list asset on alternate host is not yet physically verified.
- Source-only candidate: normalize precisely `https://webtoon-phinf.pstatic.net` list cover URLs to `https://swebtoon-phinf.pstatic.net`, preserve path and query, no extra metadata requests, no host expansion, no special cookies/headers/cert exceptions. Other image hosts unchanged.
- Increment only Webtoons source manifest/script version to 0.1.2; pin SHA-256 and offline regression tests. No new IPA needed; update source from repository after merge.
- Physical gate: update the selected source and reopen Popular list; confirm covers render, then verify details image and one previously working chapter. If still blank, the alternate host asset may not exist; stop and report without adding broad retries.
- No change to HotComics HTTP403, Manhwa18.net, paused MangaDex, the remaining M13 ports, or deployment target iOS 12.0.

## Build 32 — bounded cover requests and background thumbnail caching (2026-11-01)

- User physically confirms Webtoons EN 0.1.2 shows listing covers, but loading is slow and some covers fail. This establishes **partial physical progress**, not full source acceptance.
- Code review found the global CoverImageLoader starts one ephemeral URLSession/HTTPClient for every visible cover without an application-level concurrency limit; each cache miss also reads disk and decodes a JPEG synchronously along the UITableView cell configuration path.
- Build 32 changes **only the native cover pipeline**: max three in-flight cover transfers app-wide, identical URL requests coalesced under matching host allowlists, image disk work off-main, ImageIO thumbnails capped at 420 pixels, and a 24 MiB decoded memory-cache cost budget.
- Failures and 403/429 remain failures; no retries, invented image URLs, credential alterations, redirect exceptions, bypass, or source script/catalog changes. Validation of each requested HTTPS URL precedes cache and coalescing.
- Clearing cover cache increments a generation so old in-flight network responses cannot re-populate a cleared cache.
- Build checks and device acceptance are separate. Grouped physical gate: compare initial vs repeat Popular loading for Webtoons EN, scroll through multiple cover rows, note whether blanks persist; ensure Manhwa18.net and source icons still display, details/chapter reading works, source tab remains responsive. Do not assert CDN availability or an absolute speedup without on-device measurement.
- Build 31's Testar capas remains available for an explicitly initiated comparison if particular images still fail; retain host/status/error reports rather than repeatedly retrying server denials.

- The existing explicit Webtoons "Testar capas" device tool is extended to sample up to three *visible* listing covers sequentially (user can scroll to failing rows before pressing it), report elapsed time and HTTP/error/host metadata, then compare the first sample's details cover. It never logs titles or full URLs; stops on 429, with at most four image GETs only when the user taps the button. No automated site polling.

## Build 32 packaging version correction (2026-11-01)

- The verified Build32 cover-pipeline commit was merged in PR #38, but the Xcode project still declared `CURRENT_PROJECT_VERSION = 31`. The corresponding PR #38 unsigned IPA is therefore **not to be labeled Build32**.
- Update both Debug and Release project configurations to `CURRENT_PROJECT_VERSION = 32` in a separate version-only release-gate PR. No source/network behavior changes, preserve marketing version 0.1.0 and iOS 12 target.
- Only send the user the artifact from the version-corrected green CI, not the stale version-31 artifact.

## Webtoons EN 0.1.3 source-only cover fallback (2026-11-01)

Physical App32 iOS 12.5.8 diagnostic: first listing cover HTTP 200 JPEG 391ms, second listing cover missing valid URL, third cover HTTP 200 JPEG 169ms; details cover HTTP 200 JPEG 130ms. No HTTP denial observed for sampled covers; no request was made for the missing URL.

Source 0.1.3 candidate extracts additional same-card image attributes and elements when the first img is empty or placeholder, including lazy fields, srcset, picture source, explicit image host, container background-image, and card attributes. Keep HTTPS validation, source domain restrictions and exact CDN normalization. No per-card details calls or extra requests. Source-only; no new IPA. CI fixtures verify recognized shapes and reject invalid URLs. Effect on the missing physical card is unverified until re-test.

## Build33 — exact Webtoons cover diagnostics (2026-11-01)

- User physical App32, Webtoons EN v0.1.3 diagnostic: visible sampled cover #1 HTTP 200 JPEG 67389 bytes 197ms; #2 no valid HTTPS image URL; #3 HTTP 200 JPEG 103697 bytes 160ms; first item's details cover HTTP 200 JPEG 75845 bytes 1937ms. Because the sample moves as the user scrolls, no assumption that #2 refers to a fixed title.
- Build33 adds an iOS12 UITableView swipe action (left swipe on the exact Webtoons EN series row, "Testar capa") which runs a single selected-cover probe plus that selected work's details cover. Existing top action still tests up to three visible rows, for compatibility.
- Source v0.1.4, installed via existing SHA256-pinned catalog, only remembers sanitized card selector presence/attribute names/value class during an existing popular/search response. Optional inspectCover(id) returns redacted metadata without any additional network request. Native diagnostic reports no title, full URLs, HTML, token/cookie, or actual attribute value. Host allowlists and HTTPS unchanged. Trace is bounded at 200 cards per runtime.
- The new per-row action adds only the same two explicit image GET requests plus one normal details fetch as previously authorized; no automatic retries or per-item background details fanout. If source still v0.1.3, the attribute inspector is gracefully unavailable but selected-image probe still works.
- Build33 includes native version 33 and source v0.1.4, requires iOS12 Swift Debug/Release build and offline JS tests green. Correct embedded CFBundleVersion comes from CURRENT_PROJECT_VERSION. No claim of a fix for missing cover URL yet; use precise selected report to guide next parser patch.

## Build 34 — exact Webtoons row snapshot and missing-versus-invalid URL diagnostics (2026-11-01)

- User's three explicit Build33 iOS12.5.8 reports share: source inspector by series ID marked coverFound true, first image selector yielded a pstatic HTTPS attribute, native selected list cover was missing/invalid, and details cover missing/invalid. No HTTP image request was attempted. Importantly, the ID-based trace map could be overwritten by another occurrence of the same manga across rankings/pages; it is not proof of a JS/Swift transfer bug.
- Webtoons source v0.1.5 embeds a redacted coverDiagnostic object directly into each SourceMangaSummary during the same listing() callback as the chosen cover URL. This snapshot is preserved when another listing overrides the legacy inspectCover-by-ID map; optional property is compatible with preexisting source summaries. Snapshot only includes selector/attribute names, value categories, sanitized JS output category and character count; no title, URL path/query, raw URL values or HTML.
- Native Build34 consumes the selected summary's inline snapshot first, with explicit legacy-lookup warning when using old source v0.1.4. It reports the existence of the cover field in decoded Swift and whether JS and Swift agree; the network probe distinguishes nil, empty string, Foundation URL rejection, non-HTTPS scheme, and missing host before any transfer. HTTPS allowlist remains mandatory.
- Webtoons v0.1.5 caches metadata presence and content kind for the already-fetched details() page's og:image; native explicitly inspects the cached trace, without fetching the page twice. This separates absent og:image from a bad URL or HTTP image error.
- New offline tests cover duplicate rankings with immutable prior row snapshot, missing og:image reporting, no duplicate details requests, and existing security/pinning cases. Scope is diagnosis, not a speculative fix to missing covers, and no additional image requests/bypasses/background scans.
- Build34 must have green Xcode Debug/Release, script fixture and embedded CFBundleVersion 34. User then installs fresh unsigned IPA via Sideloadly and updates only Webtoons EN source to 0.1.5. One selected failing row report should now be decisive. This is physical validation gate, not proven repair.

## M13-A Webtoons EN 0.1.6 — iOS 12 legacy URL percent-encoding candidate (2026-11-01)

- Physical App34/iOS12.5.8, source 0.1.5: exact selected row snapshot from JavaScript lists valid pstatic HTTPS output 105 chars; same Swift model receives nonempty string. Foundation URL(string:) returns nil. Details source og:image is present and resolved as pstatic HTTPS, but its 113-char string also fails URL(string:). The invalid-percent escape check says no malformed %HH. No network request/403/429 is involved in either failure. This rules out the former supposed JS/Swift loss for the observed row.
- Apple Foundation URL/NSURL documentation: apps linked and executed on legacy iOS do not automatically percent-encode invalid literal characters as modern frameworks can. Exact offending character remains unknown; do not claim proof of Unicode or spaces from the report alone.
- Webtoons EN v0.1.6 *source-only candidate*: keep exact existing allowed hostname and scheme, reject bad percent sequences/control/bidi and all non-source hosts. For the path/query/fragment suffix only, apply ES5 encodeURI percent-encoding to invalid literals, then restore already-valid percent-encoded bytes from %25HH to %HH. Preserve URL delimiters, query params and existing escapes; retain exact webtoon-phinf.pstatic.net -> swebtoon-phinf.pstatic.net thumbnail host mapping. Apply to list and og:image details thumbnails; do not alter chapter/page URLs, client policy, HTTP transport or domain allowlist.
- Offline regressions: literal spaces/Unicode/brackets, already %-encoded strings, malformed escapes, control characters and external hosts. Simulate iOS12 Native.resolveUrl rejecting malformed absolute URLs by preserving raw string. No extra requests, bypass, cookies or certificate exceptions.
- Physical acceptance: update source 0.1.6 in existing App34 (no new IPA). Retest a previously blank list/detail image and explicit one-row Testar capa. If it still fails URL(string:), stop and add a redacted character-class diagnostic rather than widening the URL repair. If it reaches HTTP, use normal status code; do not treat 403/429 as bypassable.

## Webtoons EN 0.1.6 physically accepted; chapter-page URL hardening 0.1.7 (2026-11-01)

- User confirmed that the previously failing covers now open on iOS 12.5.8 using App 34 + source 0.1.6. This supports the legacy Foundation URL-encoding diagnosis for the selected covers; it does not establish all-series, all-episode, or full-reader correctness.
- Next reviewed flow: details VC invokes source chapters() (m.webtoons.com episodes API), then pages() fetches episode HTML once and selects div#_imageList > img[data-url]; ReaderImageLoader passes each page.imageUrl to HTTPPolicy.validatedURL via URL(string:). In source 0.1.6, only listing covers and details og:image used normalizeWebtoonsImageURL. Episode page image URLs were still passed raw, exposing the same known iOS12 compatibility class.
- Source-only v0.1.7: use the existing strict iOS12 normalization on pages' data-url values, with preserveHost=true to prevent rewriting actual episode media to the alternate thumbnail CDN. Resolve relative values against the fetched episode URL rather than the catalog home. HTTPS, source host allowlist, query delimiters, valid escapes, image order and Referer header preserved. Malformed %, control chars and external hosts are rejected before native loading. No extra GETs, captcha changes or image-host overrides.
- Offline JS regression covers Unicode/spaces/brackets in image path, previously encoded %HH, protocol-relative and root-relative images, invalid % escapes, control bytes, off-domain rejection, original CDN host, Referer and one chapter GET only. Catalogue pin must match script SHA256. Existing iOS12 native compilation unaffected; no new IPA is needed for v0.1.7.
- Physical acceptance gate: update Webtoons EN to 0.1.7 with App34 installed. Open an ordinary non-motion episode, verify the chapter list appears, at least the first three pages render, swiping/vertical scrolling work, and note any exact displayed error. Do not assume API availability or motion-toon support from fixtures. If HTTP 403/429 occurs, treat it as server response and investigate only through allowed normal requests, not bypass.

## Build 35 — memory-bounded iOS12 reader image pipeline (2026-11-01)

- Physical baseline preserved: App 34 with Webtoons EN 0.1.7; user confirmed covers, chapter list, normal multi-page reading, downloads, storage and offline reading work. Do not infer stress stability from this initial physical smoke test.
- Audited ReaderImageLoader in ReaderViewController.swift: prior implementation cached 18 UIImage objects by count only, performed Data(contentsOf:) and UIImage(data:) on the cell caller path, and lacked in-flight request coalescing or transfer concurrency bounds. Prefetch + cell load could issue duplicate GETs for the same page; a tall webtoon strip might occupy far more decoded RAM than its compressed network size.
- Build35 candidate: dedicated serial user-initiated reader image work queue for file reads, UIImage construction and callback bookkeeping. Network transfers limited to three; matching URL/source-domain/request-header keys share one transfer and its result. All callbacks delivered on main queue. HTTPS/domain policy checked before cached data is served, except original file:// offline chapter path. SHA256 digest keys include allowed domains and request headers so one source or Referer cannot reuse another's content; no raw headers stored in on-disk filenames. Preserve HTTP status and failure propagation, no retries or host rewriting.
- Memory NSCache: at most 8 images / estimated 48 MiB decoded pixel footprint, cache discarded on UIApplication memory warning; disk cache: at most 160 files and 192 MiB, trimmed on background work queue at start and every eight successful writes; no cache failure interrupts reading. Existing downloaded local pages remain file-based.
- No changes to webtoon source, chapter parsing, download manager, reader presentation/navigation, or main UI. Native Xcode Debug/Release and CFBundleVersion35/minOS12 validation required. Do not claim physical memory savings until testing on iOS12; work is a performance/stability safeguard.
- Acceptance gate: retain Build34 until Build35 CI passes. After build, install Build35 IPA and check a normal long Webtoon (scrolling without jank/crash), repeated jump within chapter, chapter switching, online images and offline downloaded chapter in airplane mode. Compare behavior to Build34 before declaring Build35 stable.

## Build 36 — offline downloaded chapters must not require a source request (2026-11-01)

- Physical report for Build35 on iOS12.5.8/Webtoons EN 0.1.7: online chapter reading and other features still work, but downloaded chapter cannot be read in airplane mode; UI reports "Source failed: Network transport error -1009: The internet connection appears to be offline".
- Root flow identified: DownloadsViewController.open(completed) formerly fetched installed source runtime and pushed MangaDetailsViewController, which always called source.details + source.chapters (HTTP). Thus -1009 appears BEFORE ReaderImageLoader loads any local page. No evidence that Build35's cache pipeline caused this error; the Downloads routing already required network.
- Build36 routes completed Downloads directly to ReaderViewController via ChapterDownloadManager.localPages(sourceID,mangaID,chapterID) and a read-only SQLite completedOfflineSnapshot. On opening and switching to other fully downloaded chapters, no source runtime or HTTP is used. Original source manifest retained only for ReaderImageLoader policy and local file:// accepted; no disabled-source restriction for local files.
- completedOfflineSnapshot reads persisted Manga.title/cover/description/status/url and chapter.id/name/number/volume/url from SQLite; it filters by exact sourceID+mangaID and completed download state. Necessary because ReaderViewController's progress tracking calls ensureReadingRows, which updates existing Manga/Chapter metadata; placeholder models would silently overwrite saved fields.
- MangaDetailsViewController accessed via Library hydrates the same completedOfflineSnapshot before asynchronous source refresh. Only suppresses the expected -1009 remote error if a usable offline snapshot is present; other errors remain visible. LibraryRepository.add metadata update after refresh now requires **both** remote details and chapters success, preventing a failed offline refresh from replacing saved data with a partial list.
- Static offline route regression in ci/test_m13a_js.cjs checks local-only Downloads open, completed/source/manga query guards, and Library fallback gate, in addition to Swift iOS12 Debug/Release compilation. This structural test does not simulate physical disconnected device.
- Retain working Build34/35 during validation. Build36 requires a new unsigned IPA because changes are native; Webtoons source remains 0.1.7. Test airplane mode starting from Downloads tab and from Library after a fresh app launch; confirm at least three images, progress and adjacent downloaded chapter navigation; then return online and verify chapter numbers and metadata. Do not delete or re-download existing chapters as a prerequisite.

## Handoff do roadmap de produto — 2026-11-01 (documentação somente)

- Documento canônico para retomada futura: **docs/HANDOFF_ROADMAP_MANGAREADER12_2026-11-01.md** (371 linhas).
- Explicita baseline físico **Build36 + Webtoons EN 0.1.7**, correção offline -1009, limites do aceite e inexistência de medições de stress/RAM.
- Consolidou R0–R8: estabilidade; UI Populares/Recentes/filtros; fontes Keiyoushi e monitoramento supervisionado; leitor; Biblioteca; downloads; CBZ/ZIP; hardening; extras.
- Confirma adapters JS próprios, não APKs Keiyoushi; catálogo atualiza fontes, mas não incorpora automaticamente commits Kotlin upstream. Não atribuir disponibilidade a filtros/Recentes sem comprovação por fonte.
- Regras de continuidade: branch → PR → CI verde → squash merge main, nenhum código alterado neste handoff, nenhum novo IPA. Próximo ponto sugerido após autorização do usuário: **R1-A** (capabilities opcionais preservando contrato v1).

## Build 37 — descoberta de obras e categorias Webtoons EN 0.1.8 (2026-11-01)

- Iniciado R1-A/R1-B/R1-D do roadmap pós-Build36: SourceBrowserViewController agora oferece cabeçalho "Explorar" com menu UIKit de categorias por fonte, de forma opcional. O contrato v1 de seis funções é preservado; fontes que não têm browseCategories() continuam usando popular() e search().
- Novo SourceBrowseCategory (id/title/kind ranking|genre|latest), validado por id simples, título limitado e tipo suportado; runtime recebe lista opcional da fonte. O fluxo browse(id,page) é chamado **somente** quando selecionado pelo usuário e anunciado pela fonte.
- Proteção de concorrência: requestEpoch e pendingReload não deixam uma resposta antiga (seção ou busca anterior) sobrescrever a lista após mudanças do usuário durante requisições lentas. Páginas repetidas são deduplicadas pelo id de obra; refresh permanece explícito.
- Webtoons EN sobe a **0.1.8** com pin SHA256 no catálogo: **28bec8e6692e8e564508e448e2dbe19598e2de7c4aec7168c49a1623b4bbcb5f**.
- Webtoons popular(page=1) mapeia **apenas ranking/popular**, page>1 encerra (não passa para outra categoria). browse oferece rankings separados Tendências/Originals/Canvas e filtros de **gênero remoto por páginas oficiais** romance, fantasy, action, drama, comedy, thriller, mystery. Uma escolha = uma listagem e um GET da categoria; nenhum request extra automático.
- A seleção "Recentes" aparece como desabilitada se a fonte não fornece um modo latest verdadeiro. Não reutilizar "Trending" como se significasse última atualização. Por enquanto Webtoons não anuncia latest.
- O parser de cartões foi estendido para alguns seletores HTML de listagem por gênero (.card_list, .genre_list) e título (.subj), mas o DOM de gênero em produção pode diferir: **não marcar gêneros como fisicamente validados sem teste de iOS12**. Rankings e fontes legadas também precisam de QA.
- ci/test_m13a_js.cjs testa integridade SHA, separação dos rankings, modo gênero, validade do caminho, apenas um GET, falta de paginação artificial, recusa de categorias desconhecidas e contrato de UI nativa. Os testes usam mocks, sem confirmar DOM vivo ou endpoint de recência.
- Build37 é nativo por acrescentar UI/DTO Swift; **novo IPA necessário**. Instalar sobre Build36 (preservar dados); atualizar fonte Webtoons EN para 0.1.8 separadamente pelo catálogo; testar Populares, menu Tendências/Originals/Canvas, gêneros Romance/Fantasia/Ação, busca, detalhes, capítulos, leitura e downloads offline. Registrar os casos que retornarem zero itens ou erro.
- Baseline preservada: Build36 + Webtoons EN 0.1.7 permanece referência até aceite físico. CI Debug/Release, checagem binária 37 e testes JS são gate antes do merge.

## R2-A — monitoramento somente de leitura do Keiyoushi (2026-11-01)

- Referência de 12 paths no upstream (9 fontes + 3 engines), em ci/keiyoushi-upstream-baseline.json; commits obtidos via API oficial GitHub em 2026-11-01.
- .github/workflows/keiyoushi-upstream.yml: semanal segunda 07:17 UTC (best-effort) + workflow_dispatch. Actions read-only token e artefatos Markdown/JSON em cada execução; sem PR ou atualização automática de scripts e sem visitas aos sites das fontes.
- Script ci/monitor_keiyoushi_upstream.py: valida paths e commits, consulta último commit de cada diretório via API GitHub, compara com baseline, marca changed/review, unchanged, erro; falha visivelmente se API indisponível.
- Teste offline ci/test_monitor_keiyoushi_upstream.py incorporado à pipeline de build. Documentação em docs/R2_KEIYOUSHI_UPSTREAM_MONITOR_2026-11-01.md.
- Um commit novo demanda revisão humana e port explícito. Não implica compatibilidade com iOS12 nem autoriza contornar restrições. Este PR de monitoramento **não modifica o aplicativo** e não gera nova versão.

## Webtoons EN 0.1.9 — Recentes legítimos sem novo IPA (2026-11-01)

- Revisado upstream oficial Webtoons.kt: getLatestUpdates(page=1) usa a listagem de Originals **do dia da semana local**, com query `sortOrder=UPDATE`, e hasNextPage=false. Não é um feed de todos os capítulos de Canvas ou de todos os dias. URL de origem: https://github.com/keiyoushi/extensions-source/blob/main/src/all/webtoons/src/eu/kanade/tachiyomi/extension/all/webtoons/Webtoons.kt .
- O JS da nossa fonte 0.1.9 passa a declarar categoria opcional `{id:'latest', title:'Recentes (Originals do dia)', kind:'latest'}` e consultar exclusivamente `/en/originals/<dia>?sortOrder=UPDATE`, com nomes de dias fixos e página 2 vazia. Usa o mesmo parser .webtoon_list da implementação upstream e um GET por consulta; sem mudar allowlist/TLS/hosts.
- Atualiza o pin de integridade SHA256 para `d6b0956b88b3a8fcde19ab013178b22044479d9c693df37775dd096920ac3041`. Testes offline verificam rota, lista de dias, categoria declarada, ausência de página artificial, sem GET para modo inválido; sem requisição ao site durante CI.
- **Não precisa de novo IPA**: Build37 é necessário para exibir o novo menu; fonte Webtoons EN deve ser atualizada de 0.1.8 para 0.1.9 pelo catálogo após CI/merge.
- Teste físico pendente: Populares, Tendências, Recentes (Originals do dia), gêneros e leitura normal em iOS12.5.8. Nenhuma alegação de funcionamento real de Recentes/gêneros sem o retorno do usuário.

## Handoff consolidado após sessão longa — 2026-11-01

- Handoff de retomada atual: **docs/HANDOFF_BUILD37_WEBTOONS019_R2_2026-11-01.md**, com PRs #49 (Build37), #50 (monitor read-only upstream), #52 (fonte Webtoons EN 0.1.9), hashes, limites do escopo, roteiro de QA em iOS12.5.8 e lista do que ainda não foi validado fisicamente.
- O handoff original **docs/HANDOFF_ROADMAP_MANGAREADER12_2026-11-01.md** ganhou aviso de execução parcial; mantém o planejamento completo R0–R8 como referência.
- Não foi produzida nova versão nativa após Build37. Release de fonte 0.1.9 é atualização via catálogo, sem novo IPA. Build36 + Webtoons EN 0.1.7 permanece baseline comprovada até retorno físico.

## Build 38 — modern discovery sheet and conservative source-tag exclusions (2026-11-03)

- Physical Build37 report: user states **"parece tudo estar funcionando"**; not a systematic long-duration or per-source QA acceptance, but broad positive initial observation. Preserve Build37/Webtoons EN 0.1.9 as the working fallback until Build38 is physically tested.
- User disliked the old iPad-like UIKit UIAlertController.actionSheet filter menu. Build38 replaces it with a **custom UIKit overFullScreen bottom sheet** (iOS12 supported) with backdrop, rounded corners, scrollable grouped chips for ranking/listing/genre, source-theme colors, a fixed Apply/Clear footer, and consistent presentation on iPhone/iPad. No iOS13+ sheet APIs.
- Existing source optional browseCategories() and browse() preserved. Source v1 six methods unchanged. App filter exclusions persist per source in UserDefaults. Only one remote browse category/genre at a time, because site does not expose reliable multi-genre AND/OR. Browsing and searching remain available to all older sources.
- The sheet includes optional local exclusion of labels BL, GL, LGBTQ+, Harém and Terror. New SourceMangaSummary.tags:[String]? (optional decoding) holds **only explicit source-provided listing labels**. The app never infers labels from title, art, series URL or user attributes. For missing/unknown tag metadata, default is **show**, with optional "Ocultar obras sem tags". This is a conservative best-effort filter, not proof that a work lacks any excluded theme. No automatic per-item HTTP details fetching, both to avoid scraping 403 and to limit requests.
- Webtoons EN 0.1.10 adds optional `tags` extracted from explicit `.genre`, `.tag`, or `[data-genre]` metadata on **the already fetched listing card**. No change to domains, referer, CDN handling or number of requests. Metadata may not be available on the site; in that case tags==nil and exclusion precision is limited. No promise of exact exclusion across entire site.
- SHA256 Webtoons EN 0.1.10: `b6ccafd050f174f40f54543d219a0a646cee1624138d8f1f382763c2c46be821`; catalog pin updated.
- ci/test_m13a_js.cjs covers tag extraction vs titles and no extra HTTP, source v1 compatibility, updated catalog pin, and structural custom-sheet and filtering guards. CI Swift Debug/Release, CFBundleVersion=38 and minOS=12 required. App must be updated to Build38 and source Webtoons EN 0.1.10 separately; preserve existing downloads.
- Physical iOS12 gate: open Webtoons EN, tap Explorar filter, check compact panel on screen, scroll all sections, select ranking/genre, choose BL+GL+LGBTQ+, Apply; if tag metadata missing, check on-screen warning/unknown toggle rather than expecting exact suppression; search after applying, clear filters, switch themes, close/reopen app, read online/offline. Avoid destructive reinstall.
- Build38 has **not** been physically validated as of this documentation. No changes to ReaderImageLoader, offline storage, downloads or SQLite.

## Build 39 — restauração e exclusões manuais + amostra oficial CANVAS BL/GL (2026-11-03)

- Feedback do Build38: a interface e os botões estão funcionando inicialmente, mas parte das obras BL/GL não tem etiquetas explícitas e permanece visível. **Isso não invalida o runtime; mostra que os metadados de terceiros são incompletos.** Build38/Webtoons EN 0.1.10 continua baseline de funcionamento relatado até teste físico do 39.
- Build39 acrescenta swipe **Ocultar** nas obras da fonte (inclusive Webtoons) com identificação exata da obra selecionada. Prefs locais `explore.hidden.<sourceID>` por fonte e persistência ao reabrir, sem excluir downloads, histórico, Biblioteca ou capítulos. Restaurar **todas** as obras ocultas em Explorar > final do painel, com contador.
- Fonte Webtoons EN 0.1.11 oferece método opcional `classificationSample(done)`: consulta **somente quando o usuário toca** `Verificar 1 página do CANVAS BL/GL`, via um HTTPS GET a `https://www.webtoons.com/en/canvas/list?genreTab=BL_GL` (sem paginação autom., sem requests extras por título). Parse de links oficiais de CANVAS, extração de `title_no` numérico único com limite 60. Resposta tem `complete:false` e origem `canvas-blgl-first-page`.
- O app só permite cruzamento se exclusão BL, GL ou LGBTQ+ foi marcada; identifica coincidências por **title_no numérico e URLs de CANVAS** (não aplica a Originals). IDs do índice são mantidos **somente na sessão**; tentativa fracassada remove o índice anterior e retorna erro explícito.
- Esta amostra pode identificar algumas obras BL/GL sem tags na listagem atual, mas **não cobre todas as páginas nem toda a plataforma**; não é classificação infalível. O filtro de tags do Build38 permanece, e obras desconhecidas continuam visíveis por padrão. Não classificar obras pelo texto dos títulos.
- Webtoons EN 0.1.11 SHA256 pin: `98eec4d4ebdc838c147c3ca2bcb2939f8808d4169c18ce5b7c6363572775da42`, atualizado no catálogo. Parser da amostra falha explicitamente se não conseguir extrair nenhum link, sem falsificar ausência de BL/GL.
- Testes de regressão JS cobrem: origem, página única, deduplicação por title_no, rejeição de domínio offsite, rejeição de IDs inválidos, falha em HTML não reconhecido, nenhuma requisição por obra; testes estruturais verificam persistência, restauração, falta de chamadas implícitas, e URL CANVAS somente.
- Alteração nativa Swift requer **Build39**, iOS12.0 mínimo e aprovação CI Debug+Release + teste físico do usuário. Instalar por cima de Build38, atualizar Webtoons EN para 0.1.11 e confirmar: (1) swipe Ocultar; (2) ocultas não retornam em busca/listas; (3) reiniciar app preserva ocultações; (4) restaurar todas; (5) BL/GL excluídos e consultar amostra; (6) leitura online e offline preservadas. Sem alterações em SQLite/Downloads/Reader.

## Build 40 — Biblioteca local: filtros e ordenação modernos (2026-11-03)

- Base: usuário relatou Build39 funcionando em uso inicial. Build39 + Webtoons EN 0.1.11 permanece checkpoint físico até Build40 ser testado. Build40 **não altera adaptadores JavaScript, catálogo, leitor, downloads, DB schema nem fonte**.
- Biblioteca substituiu o menu UIKit antigo `UIAlertController.actionSheet` de Filtrar por um **painel próprio iOS12**, com tema claro/escuro, rolável e botões compactos, semelhante ao novo Explorar. Botões Aplicar/Limpar fixos embaixo; continua existindo botão Categorias para gestão de categorias.
- Busca rápida por título via UISearchController na Biblioteca, aplicando somente em obras já salvas; tolerância a maiúsculas e acentos.
- Ordenação: adicionadas recentemente (padrão anterior), título A–Z, título Z–A, última leitura, mais capítulos não lidos. Empates têm ordem determinística por data adicionada e ID. Preferências persistidas em UserDefaults.
- Filtros combináveis: categoria, status (em andamento, concluído, pausado, cancelado, desconhecido), somente obras com capítulos **já cadastrados** e não lidos, somente obras com **download concluído**. Não lidos não é uma estimativa do total disponível no site; downloaded exige `downloads.state='completed'`, não qualquer job pendente. Preferências por Biblioteca salvas localmente e limpas em Limpar.
- Novo `LibraryRepository.readingMetrics()` faz uma consulta SQLite agrupada (COUNT capítulos, SUM is_read, MAX history.last_read_at, EXISTS download concluído) somente em `library`; **zero chamadas remotas por filtro/ordenação**. Não altera schema, categorias ou dados existentes.
- Subtítulo na Biblioteca indica contagem de capítulos não lidos já cadastrados e presença de offline completo, quando disponíveis.
- Testes CI `ci/test_library_filters.py` validam SQL real em SQLite in-memory com dados de leitura, histórico e downloads completados/pendentes e verificam wiring nativo, offline, persistência de filtros, ordenação e painel UIKit iOS12. Workflow de build executa esse teste antes de compilar.
- Build40 exige aumento de CFBundleVersion 40 (Debug/Release), CI Debug+Release, `ci/verify_binary.sh` e unsigned IPA para Sideloadly. Teste físico: instalar por cima de Build39 preservando dados; abrir Biblioteca, testar buscar título, Filtrar > ordenar por Título, status, categoria, não lidos, downloads concluídos, combinação e Limpar; entrar em obra e ler capítulo offline, alternar tema; confirmar que downloads/Biblioteca permanecem íntegros.
- Aviso: status e contagem podem ser desconhecidos ou desatualizados se o app não sincronizou a lista de capítulos. Não prometer precisão que exigiria requests de fontes ao vivo.

## Build 41 — multi-area product improvements (2026-11-03)

Physical baseline: user confirmed Build40 and prior Build39 "parece estar funcionando"; **Build41 requires independent on-device acceptance** on iOS12.5.8. Do not delete Build40 or app data. JS Webtoons EN remains at **0.1.11**. No change to extension adapter, domains, source catalogs, SQLite schema, backup records or certificate validation.

### PR #57 — reader, continue reading and cover grid
- Custom page navigation overlay in ReaderViewController: page scrub slider (discrete chosen index), live "N/M" label, previous/next chapter buttons when chaptersInReadingOrder + pageResolver support them. Preserves existing pages/Webtoon layout, directions RTL/LTR, page zoom/scale modes and persistence. Double tap zoom now focuses on tapped location. Existing bounded ReaderImageLoader and offline/cached page paths unchanged.
- Continue reading entry from the Library based on most recent HistoryRecord with a real sourceChapterID. HistoryViewController(resumeLatest:true) opens exact manga details, MangaDetailsViewController(resumeChapterID:) automatically resolves **only the matching saved chapter** after details/chapters available, and ReaderViewController loads stored progress. If missing, no invented fallback chapter. Normal History and Library open flows remain unchanged.
- Optional Library grid using UICollectionView with responsive columns and reused CoverImageLoader (count<=120, memory cost<=24MB). Grid inherits active Library filters/sorting through a snapshot; opens original manga details, returns to list, remembers user's grid preference in UserDefaults. Library list and custom Build40 filters remain.
- Test ci/test_build41_features.py added to CI; iOS12 Debug/Release gate required.

### PR #58 — downloads, search, UX, consolidated native version
- Downloads shows counts by state in a compact table header and a Fila action. User can explicitly pause all active/queued tasks or resume **up to 12** paused tasks in-session without new URL resolution. Already completed offline downloads remain intact; paused jobs restored after app restart require **individual** retry, never automatic site requests. Existing retry/priority/single actions remain.
- Manga details adds an opt-in chapter selection picker with up to 5 not-yet-downloaded chapters. Only after confirming, sequentially call source pages() and one download job at a time; no automatic batch, no parallel burst, immediately stop on HTTP 429. Each job uses the existing recovery/SQLite download pipeline.
- Global search: add normalized-title *possible similarity* badge **only** when the same normalized title occurs in 2+ different source IDs. Results remain separate; no automatic cross-source dedup/merge. List source names for search/runtime failures, no token-bearing URLs/error body. Existing selected-source search, bounded 5 pages per source and async generation cancellation unchanged.
- Settings adds toggle "Biblioteca em grade", plus release line Build41; does not change theme backend or UI iOS minimum.
- New structural CI tests cover queue safety, bounded batch, duplication-only hints, and settings. CFBundleVersion=41 in Xcode project Debug/Release and ci/verify_binary.sh, native target iOS12.0 remains.
- No actual crop margins or split double-page renderer this batch: high-risk image transforms deferred until separate research/QAs; already existing ReaderScaleMode fitScreen/fitWidth/fitHeight/original options remain.

QA before calling stable: Install IPA via Sideloadly over Build40 without deleting app. Open Library: list -> Grade -> list; check resume last chapter/page. Reader: scrub pages in pages/webtoon modes, next/previous chapter, zoom around tapped spot, turn controls on/off, check offline reading. Downloads: pause queued in demo, resume in session, inspect state header and batch select a couple chapters on authorized working source, ensure no new request while viewing queue. Search: two sources same title should both show with *possible* label, source failure list should not hide good results. Change dark/light and settings grid preference. Confirm offline cache survives reinstall. No request to Comix or bypass.

## Build 42 — local CBZ/ZIP import and non-destructive reader border trim (2026-11-03)

- Build41 physical report: user stated the application worked and looked good. It remains the **working baseline** until the Build42 installation is physically tested.
- Native iOS 12 Files document picker (.import; accepts .cbz/.zip) opens at Biblioteca > Arquivos. Files are saved separately in Documents/LocalComics/<UUID>. Imported comics are shown in a standalone local shelf, *not* inserted into third-party online source Library records. The online search, Keiyoushi/Webtoons JS adapters, chapter downloader, source domains and SQLite schema are unchanged.
- SafeCBZArchive.swift parses ZIP central directory, supports stored method 0 and raw Deflate 8 through Apple's built-in Compression framework. It **does not support** encrypted archives, ZIP64, password-protected archives, WebP, RAR/CBR, EPUB, other codecs or embedded nested archives. Imported pages support JPEG and PNG only.
- Security and older iOS memory guardrails: archive <=450MB, central index <=8MB, <=2000 records, <=1200 images, each image <=20MB compressed/decompressed, total <=400MB unpacked, expansion ratio <=150x per page, free-storage reserve >=64MB, pixel count <=42M, path traversal/absolute paths/backslash/symlink rejection, member-name/local-header agreement, CRC-32, magic+ImageIO metadata validation. Ignore hidden metadata and non-image files. Generate filenames for pages; never use archive-provided path as the output file name.
- Import is performed on utility queue in a hidden staging folder and moved atomically to Documents after full success; corrupted archives leave no visible partial shelf entry. Imported files can be removed with confirmation. Import does not delete source downloads/history (only matching local reading history on explicit local delete).
- Reader uses already-supported `file://` image loading and its existing memory/zoom/RTL/Webtoon/progress logic; local chapter uses sourceID local.cbz and History.open has an explicit local branch so Continue lendo can return to the saved imported chapter. No HTTPS is attempted for file pages.
- Reader Preferences includes opt-in 3% non-destructive border cropping for standard paginated mode only. Disabled by default; never crop Webtoon strips. No automatic double-page split in this release: geometry/positioning will need dedicated QA on old iPads.
- ci/test_safe_cbz.py compiles **actual** native parser with Swift on GitHub macOS CI and executes 12 fixture tests including deflated/stored PNG, comments, traversal, duplicate, symlink, invalid CRC, encrypted flag, truncated ZIP. ci/test_build42_contract.py validates Files UI integration and privacy boundaries, in addition to existing CI jobs.
- Build42 CFBundleVersion native Debug/Release, minimum iOS12.0, IPA unsigned for Sideloadly. Install over Build41 without uninstalling; test Library > Arquivos > Importar a small .cbz with numbered JPEG/PNG pages, reading offline, Historico resume, screen orientation, reader margin setting, remove imported book and confirm online Library/downloads unaffected. If source content is malformed (corrupt/security) import must fail safely.
- Local ZIP content is currently outside backup export/import; document to users and avoid claiming it is part of the existing backup.

## Comix iOS12 — C0 audit only (2026-11-03)

After Build42, Comix is the user-defined **highest priority source compatibility** goal. The public Keiyoushi current implementation depends on Android native WebView for browse, details, chapters and chapter image discovery. The MangaReader12 JSContext + inert HTML DOM WKWebView does not emulate a live site session, and iOS12 WebKit compatibility is unverified. PR #20159 (all requests via WebView) merged Oct19; PR #20547 (chapter list performance) still open Nov03; PR #19969 (delete extension) also open, **not merged**. Evidence and strict no-bypass/no-site-requests phase plan documented in `docs/COMIX_IOS12_FEASIBILITY_PHASE0_2026-11-03.md`. No Comix source code has been added to MangaReader12; do not claim it works. Next C1 is offline architecture tests; C2 is a user-initiated standard WebView navigation *only if appropriate*, respecting explicit third-party access restrictions.
