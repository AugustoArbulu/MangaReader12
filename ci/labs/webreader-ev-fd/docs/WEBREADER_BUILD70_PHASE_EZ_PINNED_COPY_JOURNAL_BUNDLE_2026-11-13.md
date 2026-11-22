# WebReader Build 70 — Fase EZ (bloco ampliado): snapshot por fd + journal persistente

**Data:** 13/11/2026 · **Escopo:** laboratório sintético Linux Swift/SQLite, não integrado ao WebReader · **PR:** #90 Draft · **App real:** sem alterações.

## Problema real identificado em EY

`renameatx_np(RENAME_EXCL)` (Darwin) e `renameat2(RENAME_NOREPLACE)` (Linux) recusam overwrite do destino, mas não vinculam a origem a um inode prevalidado. Um atacante que troca o nome `chapter` entre preflight e `rename` pode fazer o processo mover uma pasta de terceiros. Em EY a violação foi **detectada após o movimento**, tarde demais para demonstrar segurança de alteração de arquivos.

## Nesta rodada: dois incrementos funcionais e uma regressão integral

1. **`snapshot` nativo Swift, somente laboratório**: estende `ci/build70_ev_fd_quarantine.swift` com cópia de arquivos `page-NNNNN.bin` por descritores já abertos. Verifica marcador específico do laboratório, pais por `openat` com `O_NOFOLLOW`, inode de origem persistido, inventário limitado e stat de cada página antes de pausar o teste adversarial. Cria destino via `mkdirat` exclusivo, arquivo de saída por `openat(O_CREAT|O_EXCL|O_NOFOLLOW)`, preserva original. Faz leitura e comparação exata do conteúdo por dois descritores abertos, revalida stats/inventário/names, chama `fsync` e mantém cópia parcial em falha — **sem apagar, restaurar ou mover a origem**.
2. **`verifycopy` nativo Swift, read-only**: reabre origem e snapshot por pais ancorados, verifica inode original, lista e bytes de todos os arquivos, symlink/hardlink, origem e snapshot reparented. Não retira metadados SQLite nem autoriza purge.
3. **`build70_ez_copy_journal_bridge.py`**: orquestrador Python para SQLite descartável `lab.sqlite`, journal específico `ez_snapshot_journal`, com estados `prepared`, `copy_verified`, `needs_review`, controle de operação única por capítulo, `PRAGMA synchronous=FULL`, confirmação sintética explícita, revalidação do proprietário, recuperação de reinício sem alteração de conteúdos e sem `DELETE FROM downloads`. Reabre após crash e pode reconhecer snapshot completo, ou marcar revisão em caso de ambiguidade. O journal Python **não é uma migração do esquema real do app**.
4. **Testes**: `test_build70_ez_pinned_snapshot.py` (19), `test_build70_ez_copy_journal_bridge.py` (14). Total da suíte acumulada EV–EZ: **109/109** no ambiente Linux/Swift 6.2.1. Nenhum CI macOS/SDK iOS 12 executado.

## Evidências de falhas testadas

| Cenário | Comportamento observado |
|---|---|
| Snapshot regular + arquivo múltiplo | Bytes iguais, origem intacta, SQLite intacto |
| Source basename trocado no gate | Cópia feita do **fd original**; pasta estrangeira não movida nem copiada; mismatch de origem impede aprovação |
| Source symlink trocado no gate | Symlink estrangeiro não movido; cópia original isolada para revisão |
| Arquivo de página trocado durante gate | Identidade do arquivo muda; não certifica cópia |
| Quarantine reparented | Detecta pai canônico alterado; cópia fica preservada no antigo diretório |
| Symlink, hardlink, destino ocupado | Recusa, nunca sobrescreve destino |
| Processo encerrado após primeira página | Retém original e cópia parcial; nenhuma exclusão |
| Crash após registro prepared | Reabertura exige revisão quando faltam bytes |
| Crash após cópia antes do commit | `verifycopy` confere conteúdo e avança journal, mantendo downloads |
| Bytes alterados após cópia | `needs_review`, sem purge nem correção silenciosa |
| Falha em UPDATE do journal SQLite | Estado antigo mantido; origem e cópia existentes |

## Resultados objetivos e limites

**Resultado mais relevante:** o ataque EY que movimentava um diretório de terceiro por troca de basename **não movimenta o terceiro** no fluxo EZ. O código lê do descriptor do diretório original aberto antes da troca. O teste comprova essa propriedade no cenário determinístico Linux, não é uma prova geral de segurança do sistema de arquivos.

**Não concluído:** o arquivo original **não é apagado** no EZ. Assim, a operação **não implementa exclusão segura completa**; ela prepara uma cópia verificável e comprovadamente não destrutiva, com recuperação de journal. Ainda não há autorização para excluir a origem nem para considerar o snapshot backup adequado aos dados privados do usuário.

Pontos impeditivos para produção:

- `verifyPages` e snapshot EZ suportam **somente `page-NNNNN.bin`**. A pasta real também pode conter `_download-plan.json` e receipt; falta validar a proveniência/limites dessas estruturas e inventário completo de capítulos.
- A identidade `(device,inode)` pode ser reutilizada após remoção e não substitui uma identidade persistente criptograficamente ligada aos bytes. `verifycopy` compara bytes naquele instante, não impede mutação depois da verificação. Falta digest persistente por arquivo, cota de armazenamento e proteção contra concorrência intra-processo/entre processos.
- `fsync` isolado não prova a durabilidade cruzada entre APFS e SQLite; faltam análises de `F_FULLFSYNC`/durability macOS e falhas de energia.
- Não há prova de que toda corrida de pai foi bloqueada sem efeito lateral: destino de cópia é um novo diretório e pode ser criado em pai reparented; erro preserva conteúdo. Nenhum conteúdo antigo do terceiro é removido.
- A ferramenta `build70_ey_shadow_schema_migration.py` ainda valida *critical subset* v1, não `schemaV1` completo do `SQLiteDatabase.swift`. O `SQLiteDatabase.currentSchemaVersion` do app continua **1**.
- O real `ChapterDownloadManager.remove()`, `removeAllConfirmed()` e `DownloadRepository.removeMissingFiles()` ainda não são conectados ao journal. Ativar parcialmente seria perigoso.
- Não foi testado no macOS/iOS 12, nem em cópia integral real verificada, sem instalar na Build70 física.

## Próximo bloco de integração recomendável (sem produção)

1. Executar CI Swift macOS+Linux em branch de feature, registrar logs e resolver diferenças Darwin.
2. Testar **schema v1 completo** em banco shadow, WAL, rollback e compatibilidade de downgrade.
3. Construir uma **camada única de coordenação** para exclusão individual, lote e reindexação: `prepare -> copy_verified -> ready_for_owner_review`, sem apagar arquivos originais até os gates de durabilidade/consentimento/ownership.
4. Somente depois avaliar exclusão física atrelada a descritores, com prova contra source swapping; alternativas baseadas em `rename` por pathname seguem reprovadas. Sem essa prova, permanecer **copy-only**.
5. Manter PR #90 Draft e `main` intacta; nenhuma Build71 ou operação real no iPad.

## Como reproduzir

```sh
cd webreader_ev_lab
python3 -m unittest discover -s ci -p 'test_build70_*.py' -q
```

Este pacote é **experimento de laboratório**. Nenhum componente deve ser instalado no iPad ou importado como código de produção sem revisão independente.
