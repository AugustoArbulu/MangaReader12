# WebReader Build70 — Fase FM: observação com FD mantido e orçamento de snapshots

**Data:** 13/11/2026 (America/Sao_Paulo) · **PR #90 Draft** · **branch** `feat/chimera-updater-phase1-protocol-audit`.

## Resultado concreto

No **laboratório sintético EV–FD**, o núcleo Swift passou a oferecer dois novos comandos:

- `holdverifysealed`: verifica por bytes o capítulo original e o snapshot com os **dois descritores de diretório abertos durante a comparação**, identidade esperada (device/inode) verificada, `O_NOFOLLOW`, validação do recibo e ausência de `_download-plan.json`. Possui novo limite de **512 MiB por capítulo** imposto durante o laço de verificação, antes de ler a próxima página. Os descritores de cada arquivo se encerram a cada iteração (correção FL preservada). O modo de teste `WEBREADER_EZ_RACE_GATE=1` pausa depois que ambos os diretórios já foram abertos; trocas de basename depois disso são detectadas, sem ler/apagar os arquivos estrangeiros.
- `budgetsealed`: percorre somente os metadados da pasta original aberta por descritor, revalida `fstat/fstatat`, exclui planos potencialmente sensíveis e calcula o custo de armazenamento. Restringe a **5.000 páginas e 512 MiB por capítulo**; reporta também o `fstatvfs` atual da quarentena para um planejamento conservador de espaço. **Não grava arquivo e não reserva espaço**.

Em `ci/build70_fm_held_recovery_budget.py`, `audit_held_recovery` lê o journal v2 via conexão SQLite em modo `ro`, exige correspondência com a **cópia shadow v3** da fase FL e seu contador monotônico de eventos, executa `holdverifysealed → budgetsealed → holdverifysealed` e repete as leituras v2/v3. Divergências implicam revisão. `preview_quota` rejeita duplicidades e mais de 16 candidatos, soma orçamento **até 1 GiB**, e exige reserva consultiva de `2 × bytes + 64 MiB` de espaço livre na leitura. Relatórios mantêm **`can_delete=false`, `can_restore=false`, `can_purge=false`, `can_copy=false`**, quando aplicável.

## Limites e garantias que **não** existem

1. **FDs são mantidos somente até o processo encerrar.** Isto protege o que foi *lido naquela verificação*, mas não amarra o caminho a um inode para um `rename` ou `unlink` futuro. Um escritor externo pode trocar um basename **depois** da última leitura; teste com injeção demonstra esse risco e a proibição permanente de excluir.
2. `statvfs` é um **valor transitório**, não quota de sistema nem reserva atômica. Não há contabilização de snapshots de outro processo, de consumo concorrente ou de duplicação física APFS. Um limite lógico por capítulo/lote ainda não prova haver espaço ao salvar.
3. O banco **v3 é um shadow sintético separado** do journal v2, não o schema do app. As leituras desses dois bancos **não são uma única transação SQLite**. O contador ABA somente vê escritores cooperativos com triggers preservados; se um escritor alterar ou remover triggers, a evidência perde confiabilidade.
4. `holdverifysealed` devolve a string histórica `copy_verified` por compatibilidade com os testes, mas **não fornece autorização de cópia, restauração ou exclusão**. O protocolo final de crash-consistency APFS/WAL e um backup real verificável permanecem indefinidos.
5. A execução é permitida **somente** em pastas temporárias marcadas `EV_SYNTHETIC_ONLY`. O código não está ligado a `ChapterDownloadManager`, `DownloadRepository`, `FileManager.removeItem`, AppInst ou interface do aplicativo. Nunca executar o laboratório em dados do iPad.

## Evidência de testes

- **FM:** 40 testes Linux aprovados, incluindo fonte/snapshot em race gate **após ambos os FDs abrirem**, corrupção, plano sensível, recibo, symlink/hardlink, 5.001 páginas, 513 MiB de arquivos esparsos, janela de corrida após retorno, mudança v2, ABA cooperativo v3 e falsa indicação de espaço.
- **EV–FD:** 250 testes locais Linux repetidos e aprovados após modificar o Swift.
- **FI–FL:** 103 testes que não dependem das fontes do app repetidos. Os **2 testes FI que importam o SQLiteDatabase.swift do app** são executados no checkout completo do CI, não na pasta local isolada; não confundir a ausência da fonte no checkout local com aprovação desse teste.
- **CI proposto:** `.github/workflows/chimera-build70-phase-fm-held-recovery-quota.yml` executará Ubuntu 24.04/macOS 15, checksum de 40 arquivos, os 40 FM + 20 FL + 36 FK + 30 FJ + 17 FI + 2 FI Swift WAL + 250 EV–FD = **395 testes por sistema**; macOS também fará `swiftc -typecheck -target arm64-apple-ios12.0` do laboratório. Confirmar resultado no GitHub antes de alegar sucesso.

## Próxima fase

Projetar um estado de **retenção e liberação controlada** de snapshots sem apagar a origem, com orçamento de armazenamento, cota efetivamente reservada e recuperação após crash. A exclusão física não pode ser promovida sem uma operação condicional ao inode/política comprovada contra escritores externos e validação em iOS 12 real.

**Barreiras invariáveis:** branch `main` intacta; PR #90 Draft; `diagnosticCopyPreviewEnabled=false`; schema SQLite de produção v1; Build70 do iPad e dados reais intactos; sem Build71 autorizada, IPA distribuído, appinst ou chaves de produção.

## Resultado final GitHub Actions — 14/11/2026 UTC

[Workflow FM #43545759069](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43545759069): **SUCCESS — 2/2 jobs** (`ubuntu-24.04`, `macos-15`). Cada runner executou **395 testes**: FM 40 + FL 20 + FK 36 + FJ 30 + FI journal 17 + FI Swift WAL 2 + EV–FD 250, além da verificação de 40 hashes SHA-256 e flags de segurança. O macOS passou também no `swiftc -typecheck -target arm64-apple-ios12.0` do núcleo de laboratório. **Não houve compilação do aplicativo completo nesta fase**, apenas verificação isolada de alvo iOS 12, nem IPA/instalação.

Commits: implementação `b7970f363ec5ace8288729e51c472138d4ca0b84`, documento atualizado no commit seguinte. A branch `main` permaneceu em `1283a0614acf3a267e3daddcdafc6c0d0cf335a7` quando conferida. Mesmo 395 testes bem-sucedidos não demonstram exclusão condicional segura, durabilidade APFS/WAL ou validação em iPad real.
