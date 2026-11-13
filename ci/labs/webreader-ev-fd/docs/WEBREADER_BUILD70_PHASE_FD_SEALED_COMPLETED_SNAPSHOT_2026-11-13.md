# WebReader — Fase FD: snapshot completo com plano sensível bloqueado

**Data:** 13/11/2026 | **Branch de referência:** `feat/chimera-updater-phase1-protocol-audit` | **PR:** #90 (Draft)

## Contexto e decisão

Fases EV–FC desenvolveram um núcleo Swift de cópia por descritores e um journal sintético SQLite. O modo FB/FC `snapshotmeta` ainda podia copiar `_download-plan.json` quando os headers estavam vazios. Isso não prova confidencialidade: URLs no JSON (`pages[].imageUrl`, `manga.url`, `chapter.url`, `manifest.script` etc.) podem conter tokens em consulta, fragmento ou caminho, ou futuros campos desconhecidos. Inspecionar apenas `Page.headers` não basta.

**Decisão FD:** em uma rota nova **opt-in `sealed_only`**, não abrir nem copiar *nenhum* `_download-plan.json`. Conservar planos parciais na origem e exigir revisão, sem tentar sanitizar URLs. Somente capítulos `downloads.state='completed'` e `chapters.downloaded=1` são candidatos. Páginas `page-#####.bin` e recibo opcional `.webreader-completion-v1` continuam auditados, copiados por FD e verificados. Esta é uma regra deliberadamente conservadora para que capítulos com estado incompleto ou planos sensíveis não ganhem cópia secundária desnecessária.

## Alterações no laboratório local (não no app instalado)

1. `ci/build70_ev_fd_quarantine.swift`: novos comandos `inspectsealed`, `snapshotsealed`, `verifycopysealed`. `fbInventory(..., allowRecoveryPlan:false)` bloqueia pelo nome **antes de ler ou decodificar** o conteúdo do plano, e revalida a restrição no final da cópia e da reconciliação. Mantém `openat/fstatat/O_NOFOLLOW`, identidade por `(st_dev, st_ino)`, verificação byte a byte, `fsync` e falha fechada diante de desvio.
2. `ci/build70_fb_full_shadow_copy_bridge.py`: opção `sealed_only=True` mapeia as três operações para os comandos seguros; exige `completed/1` na seleção, na persistência da intenção e no CAS do journal. A opção padrão **continua False para regressão legada e não é apropriada para uso de produção**.
3. `ci/test_build70_fd_sealed_full_shadow.py`: **27 testes** de rota completa Swift + 11 tabelas do schema SQLite sintético; cobre sem recibo/com recibo, plano com token em URL, Authorization/Cookie, plano inválido, injeção de plano após o preflight, troca da pasta depois do fd, falhas SQLite simuladas, reabertura/reconciliação, duas cópias de capítulos concluídos, lote com segundo capítulo parcial, consentimento, corrida do estado e reindexação estritamente read-only.

## Resultado

**250/250 testes locais Linux aprovados** (`EV 13 + EW 15 + EX 22 + EY 26 + EZ 33 + FA 42 + FB 52 + FC 20 + FD 27`). Compilação do núcleo Swift no Linux aprovada. O CI Apple **FC** [#43523192504](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43523192504) foi concluído com `success`, mas executou somente o smoke test Darwin anterior: **não validou o núcleo FD, os 250 testes nem a lógica SQLite em macOS**.

## Limites/pendências críticos

- `sealed_only` ainda é **somente laboratório**: não integra as funções reais `ChapterDownloadManager.remove`, `removeAllConfirmed`, `DownloadRepository.removeMissingFiles` nem `SQLiteDatabase` no app; não modifica o schema v1 de produção.
- O método `snapshotmeta` antigo continua disponível no laboratório para teste de compatibilidade; **não usá-lo para dados reais**. A opção nova não constitui purga segura nem transação entre filesystem e SQLite.
- Falta Mac/APFS com teste da implementação FD completa; falta análise de confidencialidade de caminhos/logs, proteção de backups, política de retenção de cópias, consistência de estados de download e sinalização da UI.
- Snapshot não é garantia de atomicidade do filesystem; `fsync` por arquivo e diretório não prova durabilidade conjunta com o WAL. Os testes de corrida conservam dados, não fornecem bloqueio entre processos concorrentes.
- Nenhum conteúdo real do iPad foi acessado ou alterado. Sem IPA, Build71, appinst, trust de produção, Release, alteração em `main` ou habilitação de exclusão.

## Próximo gate técnico

Executar a regressão FD no macOS com o mesmo código Swift e os fixtures SQLite sintéticos. Depois, criar um contrato de integração Swift inativo que mostre `quarantine eligibility` / `needs review` na UI **sem acionar `DELETE` ou `removeItem`**, e validar cópia/recuperação em sandbox. Só discutir descarte físico após prova separada de autorização, idempotência, vínculo com inodes e recuperação.
