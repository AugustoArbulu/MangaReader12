# HANDOFF COMPLETO — WebReader iOS12, Fases EA–EJ

**Data:** 13/11/2026 (UTC). **Repo:** AugustoArbulu/MangaReader12. **PR:** #90 Draft. **Branch de trabalho:** feat/chimera-updater-phase1-protocol-audit. **HEAD verificado antes deste documento:** 0492edd3549a3854043a59ec97d957590d0582cb. **main:** 1283a0614acf3a267e3daddcdafc6c0d0cf335a7, sem alterações nas rodadas de auditoria.

## Regras e estado físico

- iPad iOS 12.5.8 com Chimera e Build70 registrada anteriormente como instalada. Nenhum banco SQLite, imagem de capítulo, plano de retomada, histórico, biblioteca ou UserDefaults real foi coletado ou manipulado nesta rodada.
- Não tocar na instalação, desinstalar, limpar, restaurar ou iniciar appinst sem autorização física específica. Não modificar main nem mesclar PR #90 (segue Draft).
- O marcador ci/build71_owner_approved_qa_trigger.txt deve continuar **AUSENTE**. WebReaderUpdateChecker.productionPublicKeyX963=nil; WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil; WebReaderAppinstSocket.liveInstallationEnabled=false.
- Uma futura autorização de **preparar e distribuir IPA71 privada** é distinta de uma futura autorização de **instalar**. Pedido genérico "continue", status verde de CI e hash de cópia externa NÃO são consentimento.
- Todas as CI usadas aqui são host-only com dados sintéticos, sem uploads de informações privadas, sem Releases e sem acesso ao iPad.

## Fases e limites

**EA: cópia externa dos capítulos completos.** ci/build70_ea_external_copy_audit.py. Confere SQLite v1 sem WAL ou rollback journal não vazios, downloads.state=completed, caminhos derivados dos IDs, sequência de page-*.bin e recibos. Abre arquivo externo por FD sem seguir symlink, vincula SHA-256 ao SQLite desserializado na memória e lê/hashia páginas completas. Sem comprovar origem, decodificação ou presença de dados não completos. 23 testes atuais.

**EB: contagens da Build70 versus cópia externa.** ci/build70_eb_copy_vs_device_text.py. Diagnósticos textuais e totais; não atesta bytes originais. 10 testes.

**EC V2: duas cópias completas externas.** ci/build70_ec_full_container_dual_copy.py. Compara caminhos regulares e bytes (incluindo ocultos e vazios), com travessia por FDs e O_NOFOLLOW. Não valida ACLs, xattrs, proteção de arquivos, proveniência ou restaurabilidade. 17 testes; Linux/macOS success no run 43309654650.

**ED: biblioteca SQLite versus .mr12backup sanitizado.** ci/build70_ed_portable_vs_external_library.py. Compara conteúdo das linhas de nove tabelas (progresso, favoritos, histórico etc.), com cópia verificada por hash e SQLite in-memory. Exclui dados que BackupManager limpa do portátil: downloads, sources e chapters.downloaded. 20 testes; Linux/macOS success em revisão anterior no run 43312413312.

**EE: preferências.** ci/build70_ee_portable_preferences_plist.py. Compara chaves explicitamente exportadas e plist externo sem imprimir valores. Não prova cache cfprefsd. 16 testes; Linux/macOS success no run 43312031908, com ED de revisão anterior.

**EF: triagem de assinaturas de imagem.** ci/build70_ef_offline_payload_triage.py. Detecta HTML/JSON e truncamentos evidentes entre páginas completas; assinaturas plausíveis JPEG, PNG, GIF, WebP NÃO são decodificação no iOS 12. 17 testes.

**EG: protocolo CLI fail-closed.** EB–EF retornam exit code 2 sempre que o status contém PREFIX_STOP_, e não 0. Seis testes executam os CLIs como subprocessos. Exit 0 de um resultado informativo não autoriza atualização.

**EH: integridade relacional.** ci/build70_eh_sqlite_relational_integrity.py. PRAGMA integrity_check, foreign_key_check, conferência de declarações das FKs contra schema v1, compatibilidade chapters.downloaded com downloads.state e validação de marcações. Não repara. 17 testes.

**EI: inventário de TODOS os Downloads.** ci/build70_ei_all_downloads_inventory.py. Examina diretórios e metadados de arquivos (inclusive ocultos, parciais e _download-plan.json), cruza caminhos com TODAS as linhas SQLite e identifica material órfão, estado pausado/falho/na fila e colisões. Recusa links especiais, limita tamanhos/profundidades. Endurecimento desta rodada: conta diretórios órfãos VAZIOS de fontes, obras, capítulos e níveis inesperados, para não apresentar "nenhum arquivo não classificado" como prova de que a árvore está íntegra. Downloads não completos ou IDs Unicode exigem revisão e exit 2, sem alegar corrupção. EI não lê conteúdo integral de páginas parciais. 24 testes atuais.

**EJ: metadados de retomada.** ci/build70_ej_recovery_plan_metadata.py. Checa _download-plan.json de trabalhos queued/downloading/paused (obrigatórios), e de failed (opcionais se presentes), com até 16 MiB e páginas até 5.000. Verifica schemaVersion=1, identidades fonte/obra/capítulo, manifest.id, queueOrder e estrutura básica de páginas. Rejeita JSON com chaves duplicadas, formato incoerente, arquivos ausentes/unsafe e plano residual em completed. Não imprime imageUrl, headers, tokens, URLs ou IDs. Não executa Swift JSONDecoder, não testa retomada real e nunca conclui que a atualização é autorizada: um plano estruturalmente plausível ainda exige revisão física. 30 testes novos.

## CI observada

- EI reforçada: run **43338211519**, Ubuntu completed/success com **67 testes** (23 EA + 20 ED + 24 EI); macOS queued na última consulta.
- EJ nova: run **43338928854**, Ubuntu completed/success com **97 testes** (23 EA + 20 ED + 24 EI + 30 EJ); macOS queued.
- EA–J integrada: run **43339061530**, Ubuntu completed/success com **180 testes** (EA23 + EB10 + EC17 + ED20 + EE16 + EF17 + EG6 + EH17 + EI24 + EJ30), incluindo gates de confiança e instalação; macOS queued na última consulta.
- Validações macOS de EC V2, ED e EE em commits anteriores já tiveram sucesso, mas NÃO substituir por isso um resultado macOS pendente nas revisões recentes de EI/EJ.
- Antes de alegar cobertura multiplataforma completa, conferir jobs reais macOS, resultados do comando e gates. Se houver falha, corrigir na branch sem relaxar validações de segurança.

## Limite crítico: backup portátil não contém imagens offline

BackupManager.swift cria .mr12backup com SQLite sanitizado e preferências, **sem os bytes de página**, usando DELETE FROM downloads, UPDATE chapters SET downloaded=0 e DELETE FROM sources. RestoreBackup() substitui banco vivo e remove Downloads. NÃO usar restore portátil como operação padrão de atualização por cima; isso poderia eliminar os capítulos offline e os arquivos de retomada.

Cópias externas de data container só poderão comprovar parte da integridade depois de serem coletadas coerentemente, conferidas e mantidas fora do dispositivo. Hash sem baseline confiável não atesta origem; duas cópias idênticas podem estar igualmente incompletas. Nenhuma fase testou decodificação real das imagens, retomada de download após reinício no iPad ou os entitlements da aplicação de produção instalada.

## Próximos passos condicionais

1. Conferir os macOS jobs ainda pendentes EI/EJ e integrado. Evitar gerar novas versões desnecessárias de CI enquanto há backlog.
2. Quando o usuário autorizar uma inspeção física, primeiro realizar relatórios de identidade DQ e contagens DO/DR **somente leitura** na Build70, e testar o MESMO capítulo offline sem Wi-Fi. Não reinstalar nem fazer restore.
3. Para a preservação real, preparar cópia externa consistente do data container INTEIRO, com SQLite/sidecars, Downloads completos e parciais, planos _download-plan.json, preferências e fontes. Não apagar WAL/journal original nem publicar arquivos privados.
4. Só após confirmar a cópia e a identidade física, auditar uma futura IPA71 FINAL (assinatura, bundle, application-identifier, entitlements, SHA, iOS12). Preparar/distribuir IPA privada requer aprovação específica e a instalação por cima requer aprovação distinta. A atualização automática de produção permanece desativada.
5. Testar no iPad o MESMO capítulo sem Wi-Fi e recontar biblioteca, leitura, favoritos, preferências, downloads parciais e arquivos órfãos antes e depois de eventual instalação autorizada.

**Não confundir aumento de testes sintéticos com prontidão física. Nenhum dos 180 testes é uma prova de backup real ou de que a Build71 já pode ser instalada.**
