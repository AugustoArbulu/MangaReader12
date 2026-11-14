# WebReader Build70 — Fase FJ: reconciliação não destrutiva por observações pareadas

Data de desenvolvimento: 13/11/2026 (São Paulo; 14/11 UTC) · PR #90 Draft.

## Contrato

O laboratório **somente sintético** passa a comparar três camadas antes de produzir uma classificação diagnóstica:

1. O estado de um journal `offline_copy_journal` em um SQLite **shadow v2** artificial, com `SQLITE_OPEN_READONLY`, `PRAGMA query_only=ON`, `BEGIN` e leitura limitada a 5.000 linhas. O arquivo original v1 permanece intocado.
2. A identidade do capítulo, estado `completed`, indicador `chapters.downloaded=1`, vínculo exato entre `operation_id` e `snapshot_name`, consentimento de fixture e ausência de drift entre banco e linhas da própria operação.
3. A integridade byte-a-byte da cópia e da pasta original usando o **verificador Swift real** `verifycopysealed`, que abre diretórios por descritores, recusa nomes inseguros e symlinks, confere `dev`/`inode` e relê as páginas e o recibo. Nenhum `stage/rename`, `remove`, `purge` ou `restore` é chamado.

Uma observação só é classificada como `paired_observation_only` quando duas leituras independentes do SQLite e duas invocações independentes do Swift são coerentes. Os campos `reason`, `created_at` e `updated_at` também entram na comparação. Qualquer divergência, falha do binário, tentativa de ocultar plano de recuperação privado, estado `prepared`, `needs_review` ou execução com orçamento excedido resulta em revisão, sem alteração de metadados.

O verificador expõe **somente totais agregados**, sem imprimir source IDs, caminhos, URLs, tokens ou dados pessoais de capítulos.

## Importante: observação positiva não autoriza exclusão

Não existe uma transação ACID que abranja SQLite e filesystem simultaneamente. O arquivo pode mudar **depois** da última checagem, e o SQLite pode fazer coordenação de WAL e `-shm`. Portanto, mesmo um resultado positivo é apenas uma evidência instantânea e **NUNCA** é autorização para remover, restaurar, publicar, atualizar flags ou marcar um capítulo como não baixado. `can_delete`, `can_restore`, `can_purge`, `can_mark_downloaded` são constantes `False`.

**Bloqueio grave conhecido:** o antigo `stage` baseado em `renameat2`/`renameatx_np` pode mover a pasta errada sob troca adversarial do basename; esse modo **continua proibido** para dados reais.

## Escopo dos testes

- 30 testes novos FJ, compilando o Swift do laboratório real. Cenários: cópia íntegra e com recibo, crashes após journal e após cópia, owner/SQL state/flag drift, corrupção da origem ou do snapshot, pasta inexistente, swap de inode, symlink/hardlink, plano sensível injetado, alteração do journal ou do arquivo entre fases, schema futuro, campos extras, marker ausente, binary symlink, saída JSON inválida, limite de CPU, transação WAL ainda não confirmada e idempotência sem writes.
- Regressão independente EV–FD: 250 testes Linux aprovados novamente antes do commit. FI: 17 testes SQLite sintéticos já aprovados na fase anterior, e teste nativo de WAL/Swift já aprovado no CI FI.
- Workflow FJ proposto: Ubuntu e macOS, regressão EV–FD, FI e FJ, e typecheck arm64 iOS 12 do verificador, sem criar ou instalar IPA.

## Integração e próximos gates

O arquivo `ci/build70_fj_paired_readonly_reconciliation.py` é **somente de laboratório** e **não entra** no bundle iOS, tampouco adiciona novas telas, migração DB v2 ou chamadas nos três pontos de exclusão legados. O app continua com `SQLiteDatabase.currentSchemaVersion = 1`, `diagnosticCopyPreviewEnabled = false`, instalação desativada e código de journal v2 separado em `ci/labs/webreader-ev-fd`.

Próxima prioridade: assegurar duração/identidade estável do armazenamento em APFS, planejamento de espaço e política explícita para arquivos parcialmente transferidos, antes de sequer projetar habilitar uma operação destrutiva. O PR continua Draft e nenhuma autorização de Build 71 ou de instalação foi dada.
