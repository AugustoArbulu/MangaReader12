# WebReader Build70 — Fase FI: WAL concorrente e inspeção somente leitura do journal shadow

Data: 13/11/2026 (America/Sao_Paulo) · PR #90 Draft · branch `feat/chimera-updater-phase1-protocol-audit`

## Implementação e evidências

1. `ci/build70_fi_readonly_shadow_audit.py` é **somente laboratório**. Requer diretório sintético descartável com marcador `EV_SYNTHETIC_ONLY`, `synthetic_app/shadow_library_v2.sqlite` já criado e um SQLite com `user_version=2`. Abre conexão URI `mode=ro`, define `PRAGMA query_only=ON` e executa leitura transacional limitada a 5.000 registros. Nunca cria/migra banco, remove/download, faz restore, renomeia ou purga pastas.
2. A leitura do `offline_copy_journal` do laboratório FB cruza metadados com `manga`, `chapters` e `downloads` para classificar `prepared`, `copy_verified` e `needs_review`. Falha fechada se há deriva de owner, estado do download, `downloaded` ou estrutura do journal. **O indicador `copy_verified_metadata_only` não é comprovação da integridade atual dos bytes**. Não inspeciona os arquivos de snapshot; nenhuma saída autoriza exclusão, restauração ou purge.
3. `ci/test_build70_fi_readonly_shadow_audit.py`: testes sintéticos de estados, drift, schema, limites, symlink/hardlink, marker e WAL. Em WAL, o leitor não observa uma escrita ainda não confirmada e uma transação read-only mantém a versão anterior após `COMMIT` concorrente.
4. `ci/test_build70_fi_native_wal_snapshot.py`: compila **trechos do `SQLiteDatabase.swift` real e do método FH** em um executável Swift temporário com SQLite3. Valida o comportamento do read-only contra writer WAL, snapshot transacional, recusa de `UPDATE` e recusa de `user_version=2` no aplicativo. Nenhum código do app é modificado por FI.
5. Workflow de CI executa Ubuntu + macOS com os testes FI e regressões FF/FG/FH; uma etapa independente verifica novamente a compilação iOS 12 **sem assinatura, IPA, release, artifact upload ou instalação**.

## Limites de segurança

- Snapshot SQLite/WAL não é uma transação atômica entre filesystem e SQLite. Entre a leitura de metadados e o preflight dos arquivos ainda existe janela de concorrência.
- `SQLITE_OPEN_READONLY` não prova ausência de escritas físicas nos sidecars WAL/-shm pelo subsistema SQLite. Os testes verificam conteúdos lógicos.
- O marcador EV apenas restringe o **escopo do teste**, não é isolamento criptográfico ou sandbox de produção. A ferramenta não deve receber diretórios reais do usuário.
- O relatório é agregado: não exporta URLs, cabeçalhos HTTP, caminhos de capítulos ou credenciais do plano.
- `WebReaderOfflineDeletionV2ShadowGate.diagnosticCopyPreviewEnabled=false`, `liveInstallationEnabled=false`, `SQLiteDatabase.currentSchemaVersion=1`, nenhum journal v2 instalado no app, nenhuma exclusão física migrada.
- EV–FD permanece em `ci/labs/webreader-ev-fd`; FI lê suas fixtures sem alterá-las. A main, Build70 instalada, downloads reais, AppInst, trust SPKI e releases não são modificados.

**Não considerar a fase aprovada em macOS ou a compilação iOS12 revalidada até os respectivos jobs do GitHub Actions terminarem com sucesso.**


## Resultado CI confirmado — 14/11/2026 UTC

O workflow [FI #43536661321](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43536661321) concluiu **SUCCESS, 3 de 3 jobs** no commit `7c11dfcbfe5692c974a2b56376f52756dd71a29f`:

- `wal-native-readonly (ubuntu-24.04)`: SUCCESS — 17 testes sintéticos de journal/WAL, 2 testes nativos Swift/WAL e regressões FH/FG/FF.
- `wal-native-readonly (macos-15)`: SUCCESS — mesma auditoria e regressões no Darwin/macOS.
- `ios12-unsigned-recompile`: SUCCESS — compilação integral do aplicativo no destino `generic/platform=iOS`, sem assinatura, IPA, upload, release ou instalação.

O programa `FISummary` **sempre** retorna `can_delete=false`, `can_restore=false`, `can_purge=false`. O journal não foi integrado no aplicativo; somente a inspeção sintética foi testada. O código real do app não foi modificado pela FI. Os resultados não autorizam operações destrutivas.

A branch `main` foi confirmada em `1283a0614acf3a267e3daddcdafc6c0d0cf335a7` e o PR #90 continuou Draft na conferência do CI.
