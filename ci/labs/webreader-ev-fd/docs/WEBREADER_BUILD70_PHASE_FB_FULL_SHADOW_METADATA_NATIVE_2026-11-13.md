# WebReader Build70 — Fase FB: metadados de capítulo + journal no schema completo (13/11/2026)

## Escopo e resultado

**203/203 testes locais aprovados** no laboratório isolado Linux, com Swift 6.2.1 e Python 3.13.5. A sequência da suíte é EV=13, EW=15, EX=22, EY=26, EZ=33, FA=42, FB=52. Todas as amostras são criadas em `tempfile.TemporaryDirectory` com o marcador literal `EV_SYNTHETIC_ONLY`. Não são executadas operações em arquivos do usuário, iPad, GitHub Releases ou serviço online.

A FB criou `ci/build70_fb_full_shadow_copy_bridge.py` e `ci/test_build70_fb_full_shadow_copy_bridge.py`; expandiu **somente o binário Swift de laboratório** `ci/build70_ev_fd_quarantine.swift` com comandos `inspectmeta`, `snapshotmeta` e `verifycopymeta`. A operação usa descritores da origem e destino, exige arquivos regulares `nlink=1`, `O_NOFOLLOW`, destino novo e exclusivo, cópia + comparação exata e `fsync` de arquivos e diretórios. Não executa `unlink`, `rmdir` nem substituição/remoção da pasta de capítulo original.

## Validação de metadados

O scanner de laboratório agora reconhece, além dos `page-00000.bin` contíguos:

- `.webreader-completion-v1`: conteúdo exato `WR-OFFLINE-COMPLETE-V1:<N>\n`, tamanho <=64 bytes, contagem compatível com inventário;
- `_download-plan.json`: leitura limitada a 16 MiB por FD, verificação pré/pós-stat, decodificação `Decodable` das propriedades **obrigatórias** de `DownloadRecoveryPlan` e modelos aninhados `Manga`, `Chapter`, `Page` e `SourceManifest`, owner e `schemaVersion=1`, número de páginas, sequência de indices e `queueOrder`;
- symlink, hardlink, arquivo especial, pasta aninhada, página esparsa, formato desconhecido, recibo incorreto e presença simultânea de plano+recibo falham fechados (conservador; alguns estados históricos devem ser revisados manualmente).

**Importante:** o validador de laboratório usa structs espelho apenas dos campos obrigatórios e **não** compila a estrutura privada `DownloadRecoveryPlan` nem chama o decodificador `JSONDecoder().decode(DownloadRecoveryPlan.self)` do app original. A equivalência precisa ser demonstrada em CI com o modelo real no SDK de destino antes da integração. Em particular, a aceitação do metadado não é prova de conteúdo de imagem ou validade criptográfica de manifesto.

## SQLite completo e journal não destrutivo

O adaptador se conecta **apenas** a `synthetic_app/shadow_library_v2.sqlite` pré-gerado a partir do v1 sintético integral (11 tabelas, 3 índices). Valida novamente todas as tabelas e vínculos FK e cria, somente na cópia shadow, uma tabela **adicional de laboratório** `offline_copy_journal`, distinta do `offline_deletion_journal` da EY. Não altera `user_version`, schema de produção, nem nenhum dado do banco v1 originário.

A tabela usa `operation_id` hexadecimal, `snapshot_name=ev_<uuid>`, FK para `chapters`, UNIQUE por capítulo e estados `prepared`, `copy_verified`, `needs_review`. A intenção é transacionada **antes** da cópia nativa; o estado verificado só é transacionado **após** `verifycopymeta`, com owner ainda consistente. `recover()` somente confere a cópia e ajusta o **journal**; `reindex_preview()` não altera nenhuma linha, arquivo ou indicador `downloaded`. A cópia original, leituras, categorias, favoritos, status de capítulo e downloads permanecem intocados durante o fluxo normal.

`prepare_single` e `prepare_bulk` exigem consentimento sintético explícito; lote exige worker ocioso e faz preflight integral antes da primeira mutação. A preparação é experimental, **não é a exclusão real do aplicativo**. Os métodos reais `ChapterDownloadManager.remove()`, `removeAllConfirmed()`, `DownloadRepository.removeMissingFiles()` e `SQLiteDatabase` não foram modificados.

## Cenários comprovados no Linux

- Snapshot e verificação de páginas, recibo, plano de recuperação completo e prefixo parcial válido;
- reinício simulado com reabertura da conexão SQLite entre `prepared` e `copy_verified`;
- interrupções antes da cópia, após a cópia e após commit; recuperação idempotente;
- falhas induzidas por triggers antes de inserir journal e antes de marcar cópia como verificada;
- cópia alterada, recibo copiado alterado, página original modificada com mesmo comprimento, plano original alterado;
- diretório de origem movido, snapshot substituído por symlink, swap de pasta durante cópia, edição do plano durante gate adversarial;
- colidência de caminhos canônicos, chapter desconhecido, FK de journal, estado inválido, destino com path injection, jobs pendentes, lote inválido e reindexação sem escrita.

## Gates ainda bloqueantes antes de usar no app

1. **macOS/APFS/iOS 12 não validados**. Workflow manual Linux/macOS está no ZIP, mas ainda não está no repositório, não foi executado via GitHub Actions nem validou o SDK do iOS 12. Não há compilação ou QA em iPad.
2. **Não há garantia de transação conjunta entre filesystem e SQLite**. `fsync` e verificações por inode e bytes reduzem risco, mas não provam durabilidade de APFS em todos os cenários de crash ou proteção contra escritores concorrentes maliciosos em todos os instantes.
3. **Ainda não existe remoção final segura.** O snapshot preservador não justifica liberar exclusão física; a posterior retirada de bytes originais exigirá projeto e provas separadas, incluindo coleta de lixo somente mediante consentimento e proveniência forte.
4. **Plano pode conter cabeçalhos HTTP sensíveis.** A cópia para quarentena duplicaria esses dados se transportada para produção. Antes de adotar, revisar proteção de arquivo iOS, retention, dados privados e possíveis alternativas sem copiar credenciais temporárias.
5. **Migração real não aprovada.** A aplicação continua com `SQLiteDatabase.currentSchemaVersion=1`. O shadow v2 e o journal adicional da FB são duas estruturas experimentais, não uma migração de produção proposta como concluída.
6. **Contêiner Build70 não foi copiado/validado no dispositivo**. A exigência original de backup externo integral verificado + leitura de capítulo offline sem rede continua antes de qualquer instalação, assinatura ou publicação Build71.

## Estado do projeto

PR #90 Draft, branch `feat/chimera-updater-phase1-protocol-audit`, base `main`, **sem commit de código FB**, sem release, sem IPA, sem appinst, sem alteração no iPad ou nos arquivos reais. A meta seguinte é rodar Mac/CI e comparar o decoder espelho com o real; depois, avaliar integração **desativada**, observável e reversível, das três rotas do aplicativo.
