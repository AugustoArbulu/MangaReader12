# WebReader Build70 — FH: consulta SQLite v1 em conexão estritamente read-only
Data: 13/11/2026 · PR #90 Draft · após FG

## Implementação
- SQLiteDatabase.withStrictReadOnlyConnection: uma conexão separada `SQLITE_OPEN_READONLY|SQLITE_OPEN_FULLMUTEX` e `PRAGMA query_only=ON`, leitura transacional do `user_version` **exatamente 1**; sem `openAndMigrate`, `PRAGMA journal_mode`, CREATE/DELETE ou atualização de schema. Falha se banco ausente, v0 ou v2.
- DownloadRepository.listDownloadsForAuditReadOnly: lê somente JOINs v1; `LIMIT 5001` e exceção acima de 5000. O estado `downloads.state=completed` com `chapters.downloaded!=1` é marcado `inconsistent-completed` apenas na visão diagnóstica, jamais como candidato provisório.
- ChapterDownloadManager.previewOfflineDeletionCandidatesFromSQLiteReadOnly: chama leitura SQLite independente, depois preview FG serializado; não armazena snapshot nem executa operações destrutivas. **Sem call site/UI**, flag de cópia ainda false, journal v2 não integrado.

## Guarantees / limites
`SQLITE_OPEN_READONLY` impede escrita de esquema e linhas pelo handle, mas **WAL/-shm pode envolver coordenação do SQLite e do filesystem**; não é evidência de zero alterações físicas nos sidecars. O snapshot SQL é consistente durante o SELECT, mas entre leitura SQLite e preflight de diretórios não existe uma transação FS+SQLite. Estado provisório nunca autoriza apagar arquivos.

## Testes
`ci/test_build70_fh_strict_readonly_sqlite.py` compila o núcleo real `SQLiteDatabase` + método SQL extraído contra SQLite/Swift host em fixture descartável, injeta tentativas de DELETE negadas, versão futura, mais de 5000 capítulos, estado inconsistente e banco inexistente. Contratos adicionais verificam que o manager não chama listagem migratória. O workflow FH executa Ubuntu/macOS e compila o app inteiro sem assinatura no macOS, no destino generic iOS. Essa compilação produz apenas objeto .app temporário no runner, **não gera IPA ou release**, e não autoriza instalação.

O CI de FH só pode ser declarado aprovado após inspeção dos jobs. O código EV–FD permanece em `ci/labs/webreader-ev-fd` e sem uso live; `main`, iPad, biblioteca/offline, instalação, updater e Build70 permanecem intactos.
