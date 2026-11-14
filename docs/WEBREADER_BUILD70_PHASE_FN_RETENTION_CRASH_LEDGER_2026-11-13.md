# WebReader Build70 — Fase FN: ledger sintético de retenção e recuperação sem descarte

**Data:** 13/11/2026 (America/Sao_Paulo) · **PR:** #90 Draft · **branch:** `feat/chimera-updater-phase1-protocol-audit`.

## Motivação

A Fase FM comprovou leitura comparada por descritores de arquivo (FDs) durante a operação e limites **consultivos** de 512 MiB por capítulo e 1 GiB por lote. Contudo, um valor de espaço livre observado em `fstatvfs` **não reserva capacidade**. Em caso de crash, simplesmente esquecer o espaço previamente consumido poderia permitir recontagem indevida. A FN adiciona um terceiro **banco de laboratório independente**, `synthetic_app/fn_retention_v1.sqlite`, exclusivo de um diretório previamente marcado `EV_SYNTHETIC_ONLY`. **Não é uma migração do SQLite da aplicação**.

## Operações implementadas

`init_synthetic_ledger` cria exclusivamente um novo SQLite, com versão 1, as tabelas `fn_retention` e `fn_retention_event` e triggers de imutabilidade. A operação idempotente recusa schemas estranhos, links e base reaproveitada indevidamente. Usa `O_CREAT|O_EXCL|O_NOFOLLOW` e modo 0600 no laboratório. O banco de produção continua na versão 1, separado do journal de cópia shadow v2 e da cópia v3 do contador FL.

`reserve_snapshot` exige uma operação `copy_verified` existente, owner consistente no journal v2, correspondência com a cópia shadow v3, comparação nativa dos bytes e cotas FM. Faz uma transação `BEGIN IMMEDIATE` no **ledger sintético**, rejeita duplicidade por ID/capítulo, máximo de 16 tickets, orçamento acumulado de 1 GiB, capítulo de até 512 MiB, e uma margem consultiva `2 × (total contabilizado + novo bytes) + 64 MiB`. A reserva cria apenas um **ticket contábil**; ela **não copia nem aloca fisicamente páginas**, não fornece bloqueio entre FS+SQLite e não autoriza nova cópia. O gatilho monotônico registra um evento por inserção/atualização cooperativa.

`recover_retention` revalida evidence v2/v3/FD antes de alterar **somente o ledger FN**. Uma reserva `reserved` válida passa a `retained`; se inválida, vira `needs_review`. Em ambos os casos, o número original de bytes **continua sendo cobrado**. Ticket `retained` que perde prova vira `needs_review`, e um ticket `needs_review` não retorna automaticamente ao estado válido mesmo se os arquivos forem consertados. A recuperação é idempotente e pode ser reiniciada após falhas injetadas **antes do BEGIN**, **antes do COMMIT** ou **depois do COMMIT**.

`request_manual_release` apenas registra `release_requested`; **não diminui a cota**, não remove tickets/eventos, não apaga diretórios, não restaura arquivos e não modifica `downloads` nem `chapters`. Os tickets e seu orçamento sobrevivem até revisão manual fora deste protótipo. `inspect_retention` é somente leitura, usa SQLite `mode=ro` + `query_only=ON` e verifica schema, triggers, número de eventos e geração. O relatório expõe apenas números/estados agregados, nunca credenciais ou caminhos privados, com `can_delete`, `can_purge`, `can_restore`, `can_release_bytes`, `can_mark_downloaded`, `can_copy` **sempre falsos**.

## Modelo de ameaça e limites não resolvidos

- Um processo externo que possa substituir o caminho ou manipular os próprios triggers de SQLite **pode alterar o sentido das evidências**. O contador só detecta eventos de escritores cooperativos; não é anti-tamper criptográfico.
- As consultas v2/v3, FDs e o commit do ledger **não formam transação atômica entre os três bancos e o APFS**. Há TOCTOU imediatamente após a última leitura.
- `SQLite OPEN_READONLY` pode usar sidecars `-wal`/`-shm` e mecanismos de coordenação do sistema de arquivos; não significa atestado de nenhuma alteração física.
- O ticket **contabiliza**, mas não cria reserva de espaço no sistema operacional. Corridas de capacidade livre, deduplicação APFS, limpeza de disco pelo sistema e alocação concorrente permanecem sem prova.
- Não existe operação de *purge*, rollback físico, troca condicional de inode de origem, exclusão de páginas ou restauração de downloads. A tentativa histórica de `renameatx_np(RENAME_EXCL)` não é CAS do inode verificado e **não pode ser promovida**.
- Nenhuma função FN é chamada pelo app real. Não há UI, instalação, migração do banco v1 do app ou geração de IPA. A Build 71 continua não autorizada.

## Evidência

- **FN:** 51 testes sintéticos (Swift FD real do laboratório + Python SQLite): reserva e recuperação persistentes, corrupção, swapping de pasta fonte/destino, plano privado, drift v2/v3, WAL, ABA, triggers, schema incorreto, orçamentos, concorrência de duas reservas, limite de 16 tickets, crashes e pedidos de liberação sem purge.
- Regressão prevista no GitHub Actions: 51 FN + 40 FM + 20 FL + 36 FK + 30 FJ + 17 FI + 2 FI Swift WAL + 250 EV–FD = **446 testes por runner**. O workflow não gera IPA, nem modifica o aplicativo ou o iPad.
- Verificar o resultado efetivo do CI antes de afirmar aprovação Linux/macOS e compatibilidade com iOS12. Compilação integral iOS12 já foi realizada anteriormente na FH, mas não é reexecutada neste workflow FN porque o aplicativo não recebe alterações.

**Propriedades invariáveis:** branch `main` intacta; PR #90 Draft; `diagnosticCopyPreviewEnabled=false`; `liveInstallationEnabled=false`; `currentSchemaVersion=1`; nenhuma operação física no iPad, nos downloads reais, na Build70 ou no mecanismo AppInst.

## Execução local concluída em 13/11/2026 (America/Sao_Paulo)

A execução local do laboratório com Python 3.13/Swift 6.2.1 concluiu **FN 51/51, FM 40/40, FL 20/20, FK 36/36, FJ 30/30, FI metadata 17/17, EV–FD 250/250**, totalizando **444/444 testes aprovados**. A suíte EV–FD foi repetida isoladamente e terminou com `Ran 250 tests ... OK`; uma tentativa agregada anterior excedeu o limite temporal do comando, motivo pelo qual não foi usada como evidência de aprovação. A suíte FI Swift WAL adicional (**2 testes**) exige o código integral do app, ausente neste checkout local de laboratório e presente no checkout completo do GitHub Actions; será verificada exclusivamente no CI FN.

O resultado local **não constitui validação física no iPad**, não assegura quotas de armazenamento do APFS nem autoriza deleção/restore. O CI precisa executar o conjunto completo de 446 testes por sistema antes que se possa declarar a FN validada em macOS/Ubuntu.
