# WebReader Build70 — Fase EX: journal SQLite + Swift real por descritores (somente laboratório)

Data: 13/11/2026 · Continuação das Fases EU/EV/EW · PR #90 Draft · **sem integração no app**

## Objetivo e resultado

O laboratório `ci/build70_ex_persistent_journal_bridge.py` conecta um **journal SQLite descartável** ao **binário Swift compilado a partir de `ci/build70_ev_fd_quarantine.swift`**. O journal é gravado antes do `rename` e reconciliado por leituras seguras de descritores, sem restauração, purge ou acesso à biblioteca real do iPad. O módulo Python apenas coordena a fixture; **o WebReader e seu SQLite de produção ainda não contêm essa implementação**.

O teste `ci/test_build70_ex_persistent_journal_bridge.py` compila Swift 6.2.1 no Linux e executa **22/22 testes**, incluindo reinício real do processo via `os._exit(89)` após a movimentação, erros injetados em `DELETE` e `UPDATE` do banco, recuperação idempotente, troca de diretório após `rename` mas antes de aposentar metadados, e exclusão em lote sintética. Após revisão da política de restauração, os **13 testes EV** e **15 testes EW** permanecem aprovados: total local **50/50**. Nenhum teste macOS/iOS12 foi concluído nesta execução local.

## Máquina de estados

| Estado no journal | Diretório | Download SQLite | Ação em reinício |
|---|---|---|---|
| `prepared` | ainda na origem e identidade preservada | mantido | marcar `aborted`, sem movimentar bytes |
| `prepared` | já na quarentena, após `rename` | mantido | `needs_review`, preservar tudo |
| `quarantined` | quarentena | mantido | `needs_review`, preservar tudo |
| `retired_quarantined` | quarentena | excluído; `chapters.downloaded=0` | manter como concluído, quarentena preservada |
| qualquer estado pendente | symlink, inode diferente, caminhos ausentes/inconsistentes | não alterar | `needs_review` |
| `aborted` / `needs_review` | qualquer | não alterar | idempotente, revisão manual |

A trilha sintética é: `inspect` Swift -> `BEGIN IMMEDIATE / INSERT prepared / COMMIT` -> `stage` Swift por `renameat2(RENAME_NOREPLACE)` ou `renameatx_np(RENAME_EXCL)` -> `UPDATE quarantined` -> `classify` final do inode -> `BEGIN IMMEDIATE / UPDATE journal retired_quarantined / DELETE downloads / UPDATE chapters / COMMIT`. Em qualquer falha de SQLite após a etapa Swift, as transições SQL retornam ao estado anterior e os bytes continuam na quarentena. Não há transação atômica entre SQLite e APFS; a reconciliação funciona como protocolo de compensação conservador.

## Política de segurança

1. **Somente fixture:** exige raiz já existente, marcador `EV_SYNTHETIC_ONLY`, árvore `synthetic_app` e banco `lab.sqlite`. O Swift exige o mesmo marcador e valida componentes via `openat`/`fstatat` sem seguir symlinks. Não utilizar em pastas reais nem adaptar por troca de caminho. Nunca acessa appinst, IPA, rede ou iPad.
2. **Consentimento:** `stage_confirmed(..., confirmed=True)` e `stage_bulk_confirmed(..., confirmed=True)` simulam consentimento expresso, mas não constituem consentimento nativo confiável. Lote faz preflight de todas as entradas antes da primeira movimentação; a execução não é atômica entre capítulos.
3. **Journal:** transições condicionais (compare-and-swap de estado), índice exclusivo para operações não resolvidas, identidade `(st_dev, st_ino)` e dono `(chapter_id, source, manga, leaf)` registrados no SQLite. Não usar `local_path` antigo como autoridade.
4. **Recuperação:** função `startup_reconcile()` apenas consulta a classificação do Swift e modifica estados do **journal sintético**. Não renomeia nem apaga arquivos. Uma operação `needs_review` bloqueia nova exclusão e a simulação de reindexação.
5. **Compatibilização EV:** a antiga função Python `recover()` da Fase EV fazia restauração com `os.rename` (possibilidade de sobrescrever origem entre a checagem e o rename). Foi **endurecida** nesta revisão: mantém o diretório em quarentena e marca `needs_review`. Os testes EV foram alterados para confirmar a preservação.
6. **Não há GC:** a quarentena é retida indefinidamente no laboratório. Política real de retenção, aprovação de descarte e recuperação manual ainda não existem.

## Falhas ainda não resolvidas

- `renameatx_np(RENAME_EXCL)` / `renameat2(RENAME_NOREPLACE)` impedem sobrescrita **de destino**, mas não comparam atomicamente o **inode de origem** antes da movimentação. Uma troca hostil exatamente na janela entre `inspect` e o `rename` ainda pode mover outra árvore. A comparação posterior detecta parte do problema, mas não recupera automaticamente o conteúdo deslocado. **Não liberar para dados reais.**
- O processo Python coordena operações Swift que são executadas em processos separados; ainda não existe uma função Swift iOS12 integrada na fila de downloads. O SQLite do laboratório (`chapters` / `downloads`) tem **esquema reduzido**, não é uma migração do `library.sqlite` real.
- Ainda faltam versão de esquema real, migração robusta de SQLite v1, compatibilidade com `DownloadRecoveryPlan`, recibos de conclusão, nomes longos/canonização, proteção contra concorrência interprocesso, UI de revisão/consentimento, tratamento de backup/restauração, checkpoint WAL e validação de `fsync`/APFS sob falhas de alimentação.
- A prova Linux **não equivale** a compilação macOS ou iOS 12. O CI proposto roda laboratório Linux e macOS e poderá apontar problemas Darwin `RENAME_EXCL`/flags; seus resultados precisam ser checados separadamente.
- `reindex_guard()` apenas simula um bloqueio no laboratório e **não modifica** `DownloadRepository.removeMissingFiles`. As rotas reais `remove`, `removeAllConfirmed`, `removeMissingFiles` permanecem iguais às da Fase EU.

## Arquivos

- `ci/build70_ev_recoverable_quarantine_lab.py` — EV modelo revisado: sem restauração `os.rename` em recovery
- `ci/test_build70_ev_recoverable_quarantine.py` — 13 cenários EV revisados
- `ci/build70_ev_fd_quarantine.swift` — núcleo Swift fd da EW (inalterado)
- `ci/test_build70_ev_native_swift_fd.py` — 15 cenários EW
- `ci/build70_ex_persistent_journal_bridge.py` — novo coordenador/journal EX
- `ci/test_build70_ex_persistent_journal_bridge.py` — 22 cenários EX, inclusive crash de processo real
- `.github/workflows/webreader-build70-phase-ex-journal-native-qa.yml` — proposta CI isolada Linux/macOS

## Reproduzir localmente

```sh
python3 ci/test_build70_ev_recoverable_quarantine.py -v
python3 ci/test_build70_ev_native_swift_fd.py -v
python3 ci/test_build70_ex_persistent_journal_bridge.py -v
```

A ausência de `swiftc` faz os testes nativos serem marcados como ignorados; **nunca** contar skip como sucesso.

## Próxima etapa — EY proposta

Revisão independente de segurança de TOCTOU/fonte e concorrência com evidência APFS; verificar compilação Darwin no CI; desenhar migração de schema v1->v2 + modelo Swift nativo **sem conectar ao build instalado**, com barramento exclusivo para todas as rotas e preservação de capítulos legados. Uma versão para produção exige prova em backup físico externo, UI de revisão e autorização explícita do proprietário, além de testes completos de iOS12. **Não autorizar Build71, Release, alteração da `main`, appinst real, trust SPKI ou migração de dados físicos nesta fase.**
