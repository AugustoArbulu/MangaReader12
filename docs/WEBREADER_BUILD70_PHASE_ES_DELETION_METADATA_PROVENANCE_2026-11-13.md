# WebReader — Fase ES: origem dos metadados na exclusão offline
Data: 13/11/2026 · continuação da PR #90 Draft · iPad iOS12.5.8 preservado

## Risco confirmado

A Fase ER permitia ao usuário apagar um capítulo após confirmação destrutiva somente se a pasta tivesse arquivos de nomes/tamanhos conhecidos. Entretanto, `_download-plan.json` e `.webreader-completion-v1` eram tratados como metadados legítimos **sem validar seu conteúdo**. Assim, por colisão de arquivos, restos de uma tentativa anterior ou corrupção, uma pasta poderia conter um plano cujo `sourceID`, manga ou capítulo fossem de outra obra, e o app ainda autorizaria a remoção recursiva.

## Proteção acrescentada

`WebReaderOfflineDeletionPreflight.inspect` agora recebe os três identificadores exatos do registro confirmado no SQLite (`sourceID`, `mangaID`, `chapterID`). Mantém todas as checagens anteriores de diretório real, ancestrais, folhas regulares, tamanho e links. Quando existe plano de recuperação, ele é aberto exclusivamente via `WebReaderOfflineRecoveryPlanReader.read` (leitura limitada a 16 MiB, descritor `O_NOFOLLOW`, tamanho e metadados estáveis) e decodificado pelo **mesmo** `DownloadRecoveryPlan: Codable` usado no startup. A exclusão só pode avançar se o plano usar esquema v1, `sourceID` e `manifest.id` coincidirem com a source, `manga.id` e `chapter.id` coincidirem com o registro, e `pages.count` estiver entre 1 e 5000.

Caso haja recibo de conclusão, o preflight exige páginas sequenciais válidas segundo `WebReaderOfflinePageInventory.inspect` e texto/contagem exatos em `WebReaderOfflineCompletionReceipt.verifyIfPresent`. **Planos/recibos ausentes permanecem permitidos** para capítulos legacy ou pasta parcial sem plano (sob confirmação explícita, identidade exclusiva e demais checagens). Qualquer metadado existente que esteja malformado, não possa ser lido sem segurança ou tenha identidade diferente resulta em `.unsafe` e **nenhum arquivo é apagado**.

## Testes e limites

O teste `ci/test_build70_er_deletion_preflight.py` foi ampliado: contratos estáticos de precedência e compatibilidade com a UI; no macOS, compila **os helpers Swift de leitura, inventário e recibo reais** com uma cópia dos campos reais do plano e modelos sintéticos. Testa plano legítimo, capítulo de outra identidade, manifest de outra source, JSON truncado, recibo inválido, recibo válido sem plano e todas as fixtures adversariais ER precedentes.

A verificação continua anterior ao `FileManager.removeItem` recursivo, portanto não prova ausência de toda corrida de filesystem (TOCTOU). A prova de que um plano pertence ao registro é **interna à cópia**, não uma assinatura criptográfica da origem do download. Sem backup integral do contêiner, não há garantia de recuperação dos dados reais. Nenhuma ferramenta verifica ou altera os arquivos da Build70 instalada no iPad.

## Gates preservados

PR #90 Draft; `main` intocada. Sem Release/IPA71, appinst, restauração, ativação de `liveInstallationEnabled`, publicação da chave de produção ou SPKI, nem gatilho de QA proprietário. O workflow Linux/macOS apenas executa fixtures descartáveis; a compilação ARM64/iOS12 precisa ser revisada separadamente. Antes de atualizar fisicamente, exigir duas cópias integrais independentes, integridade SQLite/Downloads/preferences e leitura offline do mesmo capítulo no próprio iPad.
