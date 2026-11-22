# WebReader — Fase EU: metadados de exclusão e diretórios ausentes protegidos
Data: 13/11/2026 · PR #90 Draft · continuação após ET

## Achados no código da Build 70 em desenvolvimento

A Fase ER permitia `.absent` imediatamente quando `lstat` do diretório do capítulo devolvia ENOENT. O caminho poderia estar ausente porque algum diretório-pai havia sido substituído por um symlink ou por uma árvore inconsistente. Mesmo sem apagar páginas, a exclusão confirmada seguia removendo o registro SQLite do capítulo, perdendo a referência a dados que exigiam revisão.

`ChapterDownloadManager.remove()` também eliminava o job e a fila em memória **antes** de `DownloadRepository.remove()` retornar. Se SQLite rejeitasse a operação, a memória já havia perdido a referência/closure do job e podia ficar dessincronizada do banco.

Por fim, `DownloadRepository.remove()` usava `DELETE FROM downloads` e `UPDATE chapters SET downloaded=0` sem transação. Se a segunda operação falhasse, os metadados poderiam ficar parcialmente modificados.

## Proteções EU

1. **Pasta ausente não ignora os ancestrais:** `WebReaderOfflineDeletionPreflight.absentWithSafeAncestors` verifica os quatro diretórios-pai internos, aceitando ausência legítima de partes da árvore, mas recusando symlinks, arquivos não diretório e erros inesperados. Revalida o estado do arquivo ausente e os ancestrais antes de autorizar exclusão **somente do registro**. Uma pasta completamente inexistente, sem anomalias de ancestrais observáveis, ainda permite manutenção de metadados sob consentimento.
2. **Falha SQLite não elimina job em memória:** em `ChapterDownloadManager.remove()`, as alterações de `jobs` e `pending` agora ocorrem **após** `try repository.remove(...)`. Se a exclusão SQLite falhar, o método lança erro e preserva o estado em memória para revisão e eventual repetição.
3. **Linha SQLite e indicador downloaded na mesma transação:** `DownloadRepository.remove()` usa `BEGIN IMMEDIATE TRANSACTION` e `COMMIT`, com `ROLLBACK` em qualquer falha de consulta ou atualização. As três prepared statements são finalizadas antes de `COMMIT`. Erros reais de `sqlite3_step` não são mais confundidos com ausência de linha.
4. **Compatibilidade:** a UI continua exigindo confirmação de exclusão; o lote ET continua validando todas as pastas antes de começar e não remove `Downloads` por inteiro; as Fases EQ/ER/ES permanecem em vigor.

## Validação

- `ci/test_build70_er_deletion_preflight.py`: adiciona contrato estático e cenários nativos macOS para diretório de capítulo ausente com ancestrais reais, árvore interna inteiramente ausente, symlink de ancestral com folha ausente e ancestral transformado em arquivo regular.
- `ci/test_build70_et_safe_bulk_deletion.py`: compila novamente o **método Swift real de exclusão individual** em fixture descartável, injeta falha no repositório e verifica que `jobs`/`pending` continuam intactos; na segunda execução, após remover o erro do repositório, confirma limpeza normal. Inclui testes de contrato para o estado SQLite e o `BEGIN/COMMIT/ROLLBACK` e teste SQLite em memória com trigger que falha na segunda operação.
- CI já chama esses arquivos na matriz Linux/macOS da regressão EA–ET e no workflow de build iOS12, sem acesso a arquivos privados do iPad.

**Limite que continua explícito:** a operação não é atômica **entre filesystem e SQLite**. Se `removeItem` apagar páginas e a operação SQLite falhar, o diretório pode ter sido excluído mesmo que o banco e job ainda existam; o teste sintético demonstra exatamente essa distinção. A transação EU garante atomicidade **somente entre os dois comandos SQLite**. A corrida entre preflight e remoção recursiva física (TOCTOU) também permanece. A próxima etapa segura continua sendo cópia integral externa verificada do contêiner físico Build70 e leitura de um capítulo offline sem rede, antes de qualquer atualização.

**Barreiras:** PR #90 continua Draft; não modificar `main`. Sem autorizar Build71 IPA, assinatura de produção, trust SPKI ou `appinst` real; `liveInstallationEnabled=false`, chave pública de produção nil e gatilho proprietário ausente. Nenhum dado do iPad foi acessado, restaurado ou apagado.
