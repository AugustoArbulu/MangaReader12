# WebReader Build70 — Fase DM: regressão nativa com Swift real para biblioteca e páginas offline

**Data:** 11/11/2026. Repositório privado `AugustoArbulu/MangaReader12`, branch `feat/chimera-updater-phase1-protocol-audit`, PR #90 em rascunho. A **Build70 instalada no iPad iOS12.5.8 permanece intacta**. Nenhum dado físico do usuário foi acessado, nenhuma IPA/DEB ou release foi produzida, `main` não foi alterada.

## Antecedente confirmado

A Fase DL já teve **SUCCESS 2/2** em https://github.com/AugustoArbulu/MangaReader12/actions/runs/42950638784:
- Ubuntu: **12 testes negativos DL e 16 regressões DK aprovados**;
- macOS: **Build71 completa Release compilada**, cópia temporária assinada ad-hoc, entitlement efetivamente selado conferido e o **mesmo pacote IPA efêmero** verificado pelas Fases DI/DK (SHA-256, CDHash, ZIP, ARM64 e iOS12). A IPA temporária foi descartada pelo workflow; nenhum artifact foi publicado nem instalado.

Essa evidência elimina parte da incerteza de empacotamento da Build71, mas ainda não comprova dados/instalação física do iPad. A fase DM volta-se à integridade **do código real de persistência**, que é um risco independente.

## Implementação e escopo

`ci/build70_dm_real_swift_preservation_fixture.py` extrai **trechos literais do código de produção** no commit sob teste:

1. A classe `SQLiteDatabase`, a migração `schemaV1`, a abertura com `PRAGMA foreign_keys`/WAL e `SQLiteDatabaseError` diretamente de `MangaReader12/Database/SQLiteDatabase.swift`, antes do marcador dos repositórios auxiliares;
2. `OfflineDownloadPath` real de `MangaReader12/Downloads/ChapterDownloadManager.swift` entre os marcadores `BEGIN/END OFFLINE_PATH_RELOCATION`;
3. `WebReaderOfflinePageInventory.swift` real (apenas metadados: arquivos sequenciais, regulares, não vazios e sem symlinks);
4. `WebReaderOfflineCompletionReceipt.swift` real (verificação do número de páginas e rejeição de recibos divergentes).

Não há reimplementação do esquema SQLite em Python: no **runner macOS**, os fontes Swift reais são concatenados a um pequeno teste sintético, compilados com `xcrun --sdk macosx swiftc` e executados em `TemporaryDirectory`. Esta é uma execução **nativa macOS**, não execução dentro do sandbox ou runtime do iOS12.

### Cenário da regressão

O teste cria, **somente no runner**, um banco `library.sqlite` vazio no caminho `Application Support/MangaReader12` sintético e chama a própria `SQLiteDatabase.openAndMigrate()` de produção para construir schema-v1. Insere uma obra fictícia, um capítulo lido com página salva, favorito, download completo, histórico, categoria e vínculo obra/categoria; guarda propositalmente um `downloads.local_path` antigo com UUID de contêiner fictício, reproduzindo a situação histórica de migração.

Cria duas páginas `page-00000.bin` e `page-00001.bin` de bytes sintéticos e um recibo v1 declarando duas páginas no diretório derivado do **contêiner atual**, usando exatamente `OfflineDownloadPath.chapterDirectory`. Após fechar o banco, instancia novamente `SQLiteDatabase` e chama **a mesma** `openAndMigrate()`. Compara os valores SQL de cada registro antes/depois, os bytes originais de páginas e a validade da sequência/recibo. Se a página **final** for removida apenas dentro do fixture, o inventário registra uma sequência curta e o recibo deve rejeitar a divergência; o teste restaura os bytes fictícios e finaliza.

Isso verifica regressões na abertura de schema-v1 e nos guardas offline reais. **Não simula a instalação de um IPA pelo Apple installd**, não prova que o contêiner real sobreviveria a uma assinatura diferente, nem exercita todo o lançamento do app `AppDelegate`, downloads de rede, WebP, versões/arquivos de fontes externas ou bibliotecas de usuário.

### Guardas de fonte e negativos

`ci/test_build70_dm_real_swift_preservation_fixture.py` possui testes para detectar:
- mudança do `currentSchemaVersion`, do guard de migração, ou da transação SQLite;
- remoção de tabela essencial ou alteração do diretório `MangaReader12/Downloads`, inclusive `safeComponent()`;
- relaxamento do inventário de arquivos sequenciais ou da verificação por recibo;
- alteração inadvertida no comportamento destrutivo de `BackupManager.restoreBackup()` e `StorageManager.clearAllDownloads()` que precisa ser explicitamente reavaliada antes de QA;
- criação de alegações de autoridade para instalar ou distribuir;
- limites dos trechos de código Swift compilados, mantendo `main` e dados reais sem acesso.

Esse gate diferencia duas operações que **não podem** ser confundidas: **instalar uma versão por cima preservando contêiner** e **restaurar um backup**. O `.mr12backup` não guarda páginas offline; `BackupManager.restoreBackup` chama `clearExcludedDownloadFiles()` e remove os arquivos do diretório Downloads. Uma rotina de "rollback" que restaure backup sem decisão humana seria destrutiva.

## CI DM

Workflow `.github/workflows/chimera-build70-phase-dm-swift-preservation.yml`:
- Ubuntu: testes Python estáticos, regressões DJ/DK, invariantes de esquema e bloqueios de produção;
- macOS Xcode16.4: mesmos invariantes e **compilação/execução Swift real** de banco e páginas em diretório temporário, com saída de um recibo `DM_REAL_SWIFT_SQLITE_AND_OFFLINE_HOST_FIXTURE_PASS` apenas se todos os registros e páginas fictícios forem preservados. A suíte e o programa não distribuem nem instalam nada.

A CI da DM está pendente da confirmação dos logs; não confundir teste host verde com prova de upgrade no iPad.

## O que falta para a Build71 física

Confirmar identidade e entitlement atual da Build70 no iPad, consentimento explícito para **produzir e entregar** uma IPA privada de QA, checksum/CDHash da versão final e backup externo. Após uma instalação manual consentida por cima da Build70, comparar relatórios DJ, conferir biblioteca/favoritos/progresso e **abrir o mesmo capítulo previamente baixado inteiro com Wi-Fi desligado**, incluindo fechar/reabrir o app offline. Se algum capítulo exigir re-download, isso não é preservação offline; não usar restauração de backup como correção automática.

O objetivo final de atualização automática tem exigências adicionais: autenticação independente do helper em iOS12/Chimera, vault/journal protegidos, confiança editorial production-v2 com chave/SPKI provisionados, cadeia do conteúdo da IPA até o instalador e consentimento local. Os hard stops continuam exatamente `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`, `liveInstallationEnabled=false`.


## Proteção de esquema desconhecido após a DZ (12/11/2026)

Revisão preventiva de continuidade: a versão original de `SQLiteDatabase.migrateUnlocked()` retornava silenciosamente para qualquer `PRAGMA user_version >= 1`, inclusive versões **futuras e incompatíveis**. O código foi reforçado para rejeitar explicitamente versões maiores do que `currentSchemaVersion=1` antes de configurar `journal_mode=WAL` ou executar migrações. Erro informativo `unsupportedSchemaVersion(Int)`; não faz downgrade, restauração nem exclusão. Bancos v1 preservam a mesma abertura e dados.

A fixture DM nativa Swift agora marca **somente o banco sintético temporário** como `user_version=2`, tenta abrir por `openAndMigrate()`, exige a rejeição de esquema desconhecido, verifica que os registros de biblioteca, favoritos, capítulos, histórico e downloads ainda coincidem e restaura a fixture para v1. Arquivos offline sintéticos são conferidos também. O CI DM foi configurado para rodar em mudanças do próprio `SQLiteDatabase.swift`, e o workflow DL recompila o aplicativo inteiro iOS12 para detectar regressões no binário.

Esta mudança exige **reaprovação das CIs macOS nativas**. Não comprova atualização física nem altera a Build70 instalada. As flags de instalador/publicador permanecem desabilitadas.
