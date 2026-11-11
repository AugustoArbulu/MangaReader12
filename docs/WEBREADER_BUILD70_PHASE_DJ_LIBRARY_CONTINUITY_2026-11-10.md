# WebReader Build70 — Fase DJ: continuidade da biblioteca entre Builds 70 e 71, sem instalação

**Data:** 10/11/2026 (horário de Brasília). Repositório `AugustoArbulu/MangaReader12`; branch experimental `feat/chimera-updater-phase1-protocol-audit`; PR #90 Draft, sem merge na `main`. A Build70 instalada no iPad iOS12.5.8, a biblioteca, os favoritos, os downloads offline e os dados pessoais permanecem intocados.

## 1. Base já comprovada

A Fase DI terminou **SUCCESS 2/2**, https://github.com/AugustoArbulu/MangaReader12/actions/runs/42935290104. Seu teste macOS validou **assinaturas ad-hoc reais em IPAs sintéticas descartáveis**, incluindo rejeições de entitlement errado, pacote sem assinatura, alteração pós-assinatura, versão errada e iOS13 disfarçado de iOS12. **Nenhuma IPA real foi gerada ou distribuída.**

DF (3/3), DG (2/2), DH (2/2) também foram aprovadas. A DH compilou a **Build71 unsigned** e auditou o Mach-O ARM64/iOS12, mas não assinou, gerou IPA ou instalou o app. O usuário ainda executa a Build70 aprovada; não existe prova física de preservação após upgrade para 71.

## 2. Lacuna: não confundir atualização binária com preservação de dados

Já existia `MangaReader12/Core/WebReaderUpgradeContinuitySnapshot.swift`, usado pela tela `Atualizações → Segurança → Copiar contagens da biblioteca para comparar`.

Esse componente abre uma conexão SQLite **somente leitura**, em transação consistente e verifica `PRAGMA user_version=1`. Ele copia um texto de diagnóstico sem nomes, títulos ou caminhos com nove contagens:

1. Obras na biblioteca;
2. Capítulos registrados;
3. Capítulos lidos;
4. Capítulos com página registrada;
5. Capítulos favoritos;
6. Downloads marcados completos no banco;
7. Registros de histórico;
8. Categorias;
9. Vínculos obra/categoria.

Esses são **registros no banco**, não conteúdo dos registros nem prova das imagens no armazenamento. Um capítulo pode continuar marcado como completo e faltar uma página física; uma tabela pode manter a mesma cardinalidade e trocar o conteúdo. Portanto, nenhum contador substitui o teste de um capítulo com Wi-Fi desligado.

## 3. Implementação da Fase DJ

Novos artefatos:

- `ci/build70_dj_continuity_report_compare.py`: analisador **somente leitura** dos textos exatos da própria rotina Swift. Exige cabeçalho, Build física **70** antes, Build **71** depois, iOS **12.5.8**, schema legível v1, os nove rótulos na ordem correta, inteiros não negativos até `INT64_MAX` e todos os cinco avisos originais — inclusive que o backup não contém páginas offline. Rejeita relatórios indisponíveis, campos extra, valores com sinais, zeros à esquerda, alterações de versão, caminhos, formatos não canônicos, UTF-8 inválido e NUL/CR. Limite por entrada de 4 KiB.
- A CLI pode funcionar em **modo prévia de base**: `--before arquivo.txt`, para conferir se o relatório da Build70 tem formato correto antes de qualquer IPA. Na comparação `--before pre.txt --after pos.txt`, exige que os dois documentos indiquem as Builds e iOS exatos. O sistema lê os arquivos regulares por `O_NOFOLLOW`, compara `fstat` antes/depois, não segue symlinks e **não escreve no sistema de arquivos**.
- Se os nove textos são iguais, retorna **`DJ_NINE_COUNTS_TEXTUALLY_EQUAL_NOT_OFFLINE_PROOF`**, jamais `upgrade_safe` ou `ready_to_install`.
- Se **qualquer número mudou** (mesmo crescendo legitimamente após uma atualização de capítulos), retorna `DJ_COUNT_DIFFERENCE_REQUIRES_MANUAL_REVIEW` com **somente os nomes dos rótulos que mudaram**, sem exportar contagens, nomes, IDs ou títulos. Isso é uma triagem conservadora: aumentos não são automaticamente perda de dados, mas precisam de interpretação do proprietário.
- Os textos de clipboard **não são autenticados**. Um atacante poderia inventar dois relatórios com contagens iguais. Mesmo se forem genuínos, comparar totais não comprova integridade de cada linha nem existência das imagens.

Em todos os recibos ficam permanentemente `false`: `originalReportsAuthenticated`, `physicalBeforeAndAfterExecutionAttested`, `sqliteContentsVerified`, `libraryTitlesOrProgressIntegrityVerified`, `offlinePageImageBytesVerified`, `offlineReadingWithoutWifiVerified`, `externalPortableBackupVerified`, `onDeviceBuild71Installed`, `publisherAuthenticated`, `ownerQADistributionApprovalRecorded`, `readyToDistributeIPA`, `readyToInstallIPA`, `installationAuthorized` e `installationPerformed`.

## 4. Testes e CI

- `ci/test_build70_dj_continuity_report_compare.py`: testes adversariais de relatório sintético, comparação de todos os nove indicadores, alterações positivas e negativas, downgrade, falsificação de Build/iOS/schema, reordenação e duplicação, avisos de leitura offline removidos, inteiros inválidos, alterações de bytes e symlinks/FIFO. Inclui 250 mutações determinísticas, teste de não escrita e de flags de autoridade sempre false.
- `.github/workflows/chimera-build70-phase-dj-library-continuity.yml`: Linux + macOS executam a mesma suíte; conferem que todos os nove rótulos e avisos ainda correspondem **ao código Swift**, que a conexão SQLite é somente leitura e que as três travas de produção não foram removidas. Não gera IPA/DEB, não roda appinst, não lê arquivos privados e não executa nenhum dispositivo.

## 5. Como isto ajudará no teste físico futuro — somente após QA aprovada

Antes de sequer preparar uma IPA física, continuar exigindo identidade real do app instalado e aceite explícito para distribuir uma candidata. Quando uma Build71 de QA for legitimamente aprovada, comparar as contagens `ANTES` e `DEPOIS` da atualização por cima da Build70. O diagnóstico já está disponível na Build70. Em seguida verificar biblioteca, favoritos e progresso abrindo algumas obras; verificar ao menos um capítulo **já baixado antes da atualização**, página por página, com Wi-Fi **desligado**, fechar/reabrir o app ainda offline e repetir. Não restaurar backup sobre a instalação existente sem avaliação: o backup `.mr12backup` **não contém os arquivos de imagens** e a restauração pode apagar downloads.

O comparador DJ não requer nem executa nenhuma dessas ações. Sua saída não autoriza instalação nem substitui o aceite humano. Pode ser reusado numa fase de pós-instalação caso uma IPA privada seja autorizada no futuro.

## 6. Estado de segurança e próximos gates

`WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`; `WebReaderAppinstSocket.liveInstallationEnabled=false`. A autenticação do helper em iOS12/Chimera, vault independente, recuperação crash-safe, assinatura editorial production-v2, cadeia de bytes da IPA até instalador e consentimento individual **continuam bloqueios independentes**. Não promover um texto de continuidade a certificação de publisher, autorização de QA ou instalação.

**CI DJ:** registrar status exato após verificação dos jobs, sem alegar sucesso antes de observar os logs.

**Handoff:** próxima etapa possível é vincular os dois relatórios de contagem a um checklist físico já existente, mantendo a aceitação offline humana e a captura de backup como etapas distintas; depois, **somente após autorização específica do usuário**, preparar uma entrega privada Build71, com SHA, CDHash e entitlement auditados antes de instalar por cima. Não reiniciar a investigação e não modificar `main`.
