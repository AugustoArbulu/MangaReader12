# WebReader Build70 — Fase DO: validação da linha de base offline ANTES da Build71

**Data:** 11/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR:** #90 Draft. Não alterar `main`, GitHub Releases, iPad iOS12.5.8, Build70 instalada, biblioteca, favoritos, progresso ou capítulos offline.

## Entrada: Fases DL–DN fechadas

A Fase DL concluiu 2/2 no GitHub Actions: WebReader completo em Release, versão 71, compilado para ARM64/iOS12, assinatura ad-hoc de cópia isolada no runner e auditorias DI/DK sobre os mesmos bytes de IPA temporária; nenhum pacote persistido. A Fase DM concluiu 2/2, inclusive compilação e execução do **Swift real** de SQLite v1, resolução de caminhos e inventário de duas páginas offline fictícias, preservando os dados durante reabertura do banco e detectando falta da última página. A Fase DN concluiu 2/2 no Linux/macOS, garantindo por fonte que abrir as telas não chama diretamente rotinas de restauração/descarte e que backup, reindexação e apagamento continuam ações manuais. **Nenhuma dessas evidências é teste da instalação no iPad.**

## Foco concreto da DO

A **Build70 que já está instalada** tem duas ações read-only em **Atualizações do WebReader → Segurança**:

- **Copiar contagens da biblioteca para comparar:** emite relatório SQLite-v1, com nove contagens (inclui `Downloads marcados completos no banco`) e versão iOS; não abre páginas.
- **Conferir presença dos capítulos offline:** examina no máximo **64 registros por lote**, seguindo o diretório de downloads do contêiner atual; observa a sequência de arquivos não vazios e o recibo de quantidade quando existente. Em cada toque a tela copia um lote, avança o índice por 64 e **retorna a zero após o último lote**. Não lê o conteúdo binário de imagens, não decodifica WebP e não modifica nada.

Antes, a Fase DJ só tinha o comparador de **relatórios de contagens antes/depois** de uma eventual instalação. A DO cria uma ferramenta de triagem **pré-instalação**, que compara o número total de downloads completos no SQLite com o número indicado em cada lote do inventário, a sequência esperada dos offsets, a aritmética dos resultados e qualquer possível capítulo faltante.

## Arquivos novos

- `ci/build70_do_preupgrade_baseline_audit.py`: analisador Python **somente leitura**. Recebe relatório de contagens Build70/iOS12.5.8, mais um ou mais relatórios de lotes offline **do mesmo Build70**. Usa o parser de contagem DJ e `_read_file_once()` (arquivos regulares de até 4 KiB, `O_NOFOLLOW`, conferência `fstat` durante a leitura). Exige textos canônicos, dez campos por lote, cabeçalho e quatro avisos de segurança idênticos aos do Swift, sem CR/NUL/linhas extras, inteiros decimais não negativos limitados a 64 bits, total de capítulos limitado a 1 bilhão e máximo 256 lotes por auditoria.
- `ci/test_build70_do_preupgrade_baseline_audit.py`: **28 testes** contra relatórios sintéticos, lotes com 0, 3, 64, 65 e 130 capítulos, sequência parcial, lote duplicado/pulado, última página, campos de contagem contraditórios, registros sem recibo, ausência de capítulos, números negativos, totais de banco divergentes, falsificações de Build e iOS, 250 alterações de bytes e ausência de permissão para instalação.
- `.github/workflows/chimera-build70-phase-do-offline-baseline.yml`: Ubuntu e macOS, executam os mesmos testes DO/DJ, verificam que os dez rótulos e avisos reproduzem **literalmente o código Swift existente**, que o botão avança o offset e que os três hard stops do instalador/confiança editorial continuam ativos.

A DO não altera nenhuma linha Swift nem o comportamento da Build70.

## Semântica de saída — nenhum estado equivale a autorização

| Resultado | Interpretação |
|---|---|
| `DO_TEXT_FULL_COVERAGE_NO_IMAGE_BYTE_PROOF` | Os textos fornecidos representam uma cobertura **sem lacunas** dos capítulos registrados como completos e suas contagens internas são consistentes; **não** é prova da existência real de imagens decodificáveis |
| `DO_PARTIAL_SAMPLE_NEEDS_MORE_BATCHES` | Existem outros lotes não inspecionados; o campo `expectedNextAuditOffset` indica a próxima posição esperada |
| `DO_LEGACY_WITHOUT_RECEIPT_NEEDS_PHYSICAL_READING` | Há capítulos com arquivos aparentemente sequenciais porém sem recibo de quantidade; não deduzir integridade das páginas |
| `DO_OFFLINE_METADATA_FAILURE_OWNER_REVIEW_REQUIRED` | O texto aponta capítulos faltantes/incompletos/inseguros; **não** restaurar backup nem reindexar automaticamente |
| `DO_NO_COMPLETE_OFFLINE_CHAPTERS_IN_TEXT_NOT_DEVICE_PROOF` | As contagens relatam zero capítulos completos; não inferir que o banco/biblioteca física esteja vazia |

Relatórios inconsistentes ou fora de ordem não geram recibo: falham fechado. **Todos os textos são fornecidos pelo usuário sem assinatura/atestação**; podem ser copiados incorretamente ou até falsificados. O diagnóstico de 64 capítulos também só lê metadados de arquivo e recibo, não o payload da imagem. Um resultado completo e sem falhas **NÃO** prova a leitura offline ou preservação através de upgrade.

Em todo resultado:
`inputTextsIndependentlyAuthenticated=false`,
`sqliteRowContentsVerified=false`,
`offlinePagePayloadBytesRead=false`,
`offlineImageDecodingVerified=false`,
`physicalReadingWithoutWiFiVerified=false`,
`physicalBuild70AppIdentifierAttested=false`,
`physicalBuild71Installed=false`,
`dataContainerSurvivesUpgradeProven=false`,
`backupRetainedOutsideDeviceVerified=false`,
`publisherAuthenticated=false`,
`ownerQADistributionApprovalRecorded=false`,
`readyToDistributeIPA=false`,
`readyToInstallIPA=false`,
`installationAuthorized=false` e `installationPerformed=false`.

## Exemplo de uso futuro (nenhuma ação física necessária agora)

Os textos foram produzidos pelo app com ações de copiar. Se o proprietário decidir fornecer os relatórios, podem ser salvos em arquivos locais de texto **sem títulos, caminhos ou páginas privadas** e passados assim ao verificador:

```bash
python3 ci/build70_do_preupgrade_baseline_audit.py \
  --counts /dados-qa/contagens-build70.txt \
  --offline /dados-qa/lote-0.txt \
  --offline /dados-qa/lote-64.txt \
  --offline /dados-qa/lote-128.txt
```

O terceiro lote só faz sentido para quem tem mais de 128 capítulos completos. Se houver até 64, um único lote basta. **Nunca** executar uma atualização, exclusão, reindexação ou restauração apenas porque as contagens conferem. Capturar esses textos não requer jailbreak/root nem instalação de IPA adicional: a Build70 já tem os botões de cópia. O relatório de presença offline permanece um **diagnóstico parcial baseado em contagens**, e não substitui o teste humano do mesmo capítulo baixado com Wi-Fi desligado.

## Próximo bloqueio prático

Antes de distribuir **qualquer** IPA privada Build71 ainda faltam: identidade do aplicativo e entitlements da Build70 **atualmente instalada** confirmados no iPad, backup físico e plano de retenção de downloads, aprovação explícita para preparar/distribuir QA, código assinado final e SHA/CDHash independentes, verificação do mesmo pacote por instalador, e teste de leitura offline **antes e depois** em atualização por cima, sem restaurar backup. `.mr12backup` não contém imagens e uma restauração pode apagar Downloads.

Para automação futura de atualização há barreiras adicionais (autenticação do helper/IPC em iOS12/Chimera, vault independente e protegido, trusted publisher production-v2, origem e consentimento local), mantidas fechadas: `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`, `liveInstallationEnabled=false`.

**CI DO:** confirmar jobs e logs antes de declarar a fase aprovada; um teste host só valida regras textuais.
