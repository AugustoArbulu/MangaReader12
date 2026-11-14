# WebReader Build70 — Fase EJ: triagem dos planos de retomada (13/11/2026 UTC)

PR #90 Draft, branch feat/chimera-updater-phase1-protocol-audit. Não modificar main ou Build70 no iPad. Nenhuma IPA71 criada, publicada, distribuída ou instalada. Não há dados reais do dispositivo no GitHub.

## Por que a fase existe

A EI preserva e contabiliza arquivos de downloads não concluídos, órfãos e ocultos. Entretanto, uma página parcial preservada não significa que ChapterDownloadManager.restorePreviousSession() conseguirá retomar o trabalho: ele depende de um arquivo _download-plan.json com schemaVersion 1, identidade coerente da fonte/obra/capítulo, manifest.id, ordem de fila e lista de páginas limitada a 5.000.

O leitor nativo WebReaderOfflineRecoveryPlanReader.swift limita o plano a 16 MiB, abre com O_NOFOLLOW e O_NONBLOCK e verifica estabilidade da leitura. Em seguida, o aplicativo aplica JSONDecoder/Swift Codable e verifica IDs e limites antes de retomar. Um plano inválido pode ser ignorado SEM excluir as páginas parciais; o proprietário deve saber desse risco antes de atualizar.

## Implementação

- ci/build70_ej_recovery_plan_metadata.py: audita somente um data container EXTERNO já copiado. Invoca EI e EA, usa banco SQLite hash-bound desserializado em memória, reconstrói os caminhos dos capítulos e lê apenas arquivos _download-plan.json, sem acessar rede ou iPad.
- O leitor reutiliza abertura somente leitura O_NOFOLLOW, valida tamanho máximo 16 MiB e consistência do arquivo entre fstat anteriores/posteriores. Rejeita JSON com chaves duplicadas, números não finitos, estrutura inesperada, schemaVersion diverso de 1, identidade inconsistentes e pages além de 5.000.
- Em cada página são verificados apenas índice sequencial, tipo imageUrl e tipo do dicionário headers; não são exibidos nem registrados URLs, tokens, cookies, cabeçalhos, identificadores de obras ou nomes de pastas.
- Registros de download queued/downloading/paused precisam de plano na cópia para que haja candidato a retomada. Registro failed não exige plano para retomada automática, mas qualquer plano presente é analisado. Plano remanescente em registro completed é classificado como anomalia, sem excluir o arquivo.
- _download-plan.json vazio, ausente, com symlink, tamanho excessivo, JSON ilegível ou identidade divergente provoca EJ_STOP_* com exit code 2. Um plano estruturalmente plausível com download pendente permanece EJ_STOP_RECOVERY_ROWS_REQUIRE_DEVICE_REVIEW (também exit 2): isto evita transformar a simples presença de metadados em autorização para atualizar.
- Nenhuma verificação executa JSONDecoder nativo ou demonstra que o manifesto da fonte é aceitável, que as URLs ainda funcionam, que a retomada após reinício realmente funciona, ou que as páginas parciais são imagens legíveis. Tudo isso exige validação no aparelho quando autorizada.

## Estados principais

- EJ_NO_PENDING_RECOVERY_ROWS_NOT_DEVICE_PROOF: a cópia não contém trabalhos pendentes; NÃO significa que o iPad original está vazio ou que a instalação é segura.
- EJ_STOP_RECOVERY_ROWS_REQUIRE_DEVICE_REVIEW: trabalhos não concluídos ainda exigem observação, mesmo que planos plausíveis existam; não é prova de corrupção.
- EJ_STOP_MISSING_MALFORMED_OR_STALE_RECOVERY_PLANS: plano faltante, inválido, inconsistente ou inesperado em capítulo completed. Requer inspeção sem reparo automático.
- EJ_STOP_UNACCOUNTED_DOWNLOAD_TREE: EI detectou arquivos/diretórios órfãos ou inesperados. Não ignorar nem eliminar.
- Outros EJ_STOP_*: leitura, integridade ou estrutura incompatível. Não modificar a cópia para satisfazer a auditoria.

Os relatórios são exclusivamente agregados, como número de planos ausentes, incompatíveis ou estruturalmente plausíveis. Nenhum conteúdo do plano é impresso. Os arquivos originais não são alterados.

## Testes e CI

- ci/test_build70_ej_recovery_plan_metadata.py: testes com SQLite e JSON fictícios, URLs fictícias e cabeçalhos de teste. Inclui controle de tamanho, IDs, tipos, ordem de páginas, JSON duplicado, symlink, plano completo residual e fail-closed CLI.
- .github/workflows/chimera-build70-phase-ej-plan-metadata.yml: Linux e macOS, com regressões EA/ED/EI/EJ, sem publicação de artefatos. Só declarar aprovação quando houver logs de jobs concluídos.

## Limitações e próximos passos físicos

O .mr12backup continua SEM bytes de páginas; restoreBackup() substitui o SQLite e apaga Downloads. Nunca realizar restore portátil como método de atualização por cima. A EJ não faz snapshot de dados originais e não garante segurança de restauração, cópia externa íntegra ou origem do iPad.

Uso ilustrativo FUTURO no computador, após cópia voluntária coerente do data container: python3 ci/build70_ej_recovery_plan_metadata.py --snapshot "/copia-externa-do-data-container". Nenhum arquivo privado deve ser publicado no GitHub.

A IPA71 só poderá ser considerada mediante validação física, assinatura/identidade de build e autorizações separadas para entrega e instalação. Trigger ci/build71_owner_approved_qa_trigger.txt ausente; productionPublicKeyX963=nil; independentlyProvisionedSPKISHA256=nil; liveInstallationEnabled=false. A CI jamais habilita appinst, updater automático ou restauração.
