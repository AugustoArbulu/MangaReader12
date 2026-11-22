# WebReader — Fase EV: protótipo sintético de quarentena recuperável

Data: 13/11/2026 · Referência: `AugustoArbulu/MangaReader12`, PR #90 Draft.

## Escopo executado

Foi criado um laboratório **Python host-only**, separado do aplicativo, que usa unicamente um diretório temporário descartável e um SQLite fictício. O objetivo é avaliar a sequência das transições; **não** altera `ChapterDownloadManager.swift`, `SQLiteDatabase.swift`, `StorageManager.swift`, o banco da Build 70, o iPad ou a branch `main`. Não existe publicação de IPA, Build 71, instalação via appinst, nem rotina de limpeza definitiva.

O modelo registra a intenção em `delete_intents` no SQLite antes de modificar arquivos; abre a árvore de diretórios a partir de descritores com `O_DIRECTORY | O_NOFOLLOW`; avalia tipo, inode, dispositivo e entradas; executa `rename` relativo aos descritores (`src_dir_fd` / `dst_dir_fd`) para uma quarentena situada no mesmo filesystem; depois atualiza o estado persistente. Finalmente, remove a linha de download e marca `chapters.downloaded=0` **na mesma transação SQLite** em que registra `retired_quarantined`. Os bytes permanecem na quarentena. Nada os elimina automaticamente.

Recuperação de início, simulada por reinício do objeto SQLite:

| Estado e observação | Política sintética |
|---|---|
| `prepared`, capítulo original ainda intacto e destino ausente | Encerrar a intenção como `aborted`, preservar dados e linha SQLite |
| `prepared`/`quarantined`, diretório com mesmo dispositivo/inode em quarentena, origem ausente e linha SQLite existente | Restaurar por `rename` e marcar `aborted` |
| `retired_quarantined` | Preservar quarentena e registro de intenção, sem restauração silenciosa nem purge |
| Inodes incompatíveis, origem e destino simultâneos, árvore trocada, banco inconsistente | `needs_review`: nunca apagar ou sobrescrever automaticamente |

## Testes locais

`python3 ci/test_build70_ev_recoverable_quarantine.py -v`

13/13 testes PASS no host Linux: operação completa; crash após intenção; crash após rename; crash após registro de quarentena; crash após commit SQLite; falha SQLite injetada com trigger + rollback e restauração; symlink em ancestral; symlink na folha; arquivo estranho; troca de quarentena; troca do diretório original. Só há páginas sintéticas num `TemporaryDirectory`.

## Lacunas que impedem integração de produção

1. **TOCTOU final não resolvido:** `renameat` POSIX não é uma operação condicional sobre o inode observado. Um adversário com capacidade de substituir a entrada no instante da mudança pode deslocar outro diretório. A inspeção posterior evita descarte silencioso, mas não elimina a corrida. Na implementação Darwin, avaliar operações exclusivas suportadas pelo SO, privilégio e bloqueio de writers, desenho de descritores e revalidação de ancestrais.
2. **Quarentena não é exclusão permanente:** a política real de retenção, restauração e limpeza (com consentimento explícito, backup verificado, limite de espaço e rotina de revisão) não foi desenvolvida. Não anunciar economia de espaço enquanto os bytes permanecem.
3. **Sem integração Swift / iOS 12:** nenhuma rota real (`remove`, `removeAllConfirmed`, `removeMissingFiles`) usa o laboratório. A reindexação real continua precisando ser unificada; diretórios com `_download-plan.json` e receipt legítimos não foram modelados. A proteção contra colisões canônicas deve ser preservada.
4. **SQLite e filesystem não são uma única transação:** `fsync` em diretórios e SQLite WAL não provam ACID entre ambos. Picos de energia e comportamento APFS/iOS exigem testes nativos de durabilidade. Recuperação deve ser idempotente e falhar fechada.
5. **Backup do iPad:** não executar alteração destrutiva física antes de obter cópia integral externa do contêiner da Build 70, verificar a cópia e testar leitura offline sem rede.

## Próxima implementação proposta

Criar adaptador Swift iOS12 sob feature flag desativada; desenhar esquema SQLite versionado e migração reversível; adicionar API de quarentena e reconciliação na inicialização; canalizar exclusão individual, lote e reindexação pela mesma política; executar suíte nativa macOS/iOS12 com falhas injetadas. Manter PR #90 Draft e `main` intacta até revisão e aceite físico. Nenhum gatilho de instalação deve ser habilitado (`liveInstallationEnabled=false`).
