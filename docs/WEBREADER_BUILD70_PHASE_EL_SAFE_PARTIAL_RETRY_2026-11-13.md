# WebReader — Fase EL: impedir substituição silenciosa de páginas parciais
Data: 13/11/2026. Branch experimental da PR #90, sem merge nem instalação.

## Risco constatado

Antes da EL, downloads normais, downloads em lote e repetição confirmada chegavam ao mesmo ChapterDownloadManager.download. Se a pasta existisse, o gerenciador a removia, incluindo páginas parciais e planos de recuperação. A UI de Downloads pedia confirmação ao proprietário, mas o método compartilhado não exigia essa autorização para os outros chamadores.

## Correção proposta e limites

- ChapterDownloadExistingDataPolicy define preserve (padrão) e replaceAfterExplicitUserConfirmation. Chamadas comuns e em lote mantêm o padrão preservador e retornam existingLocalDataRequiresReview se houver pasta preexistente.
- Somente a tela Downloads, depois do alerta destrutivo Reiniciar este download?, fornece replaceAfterExplicitUserConfirmation. O worker relê a linha SQLite e permite substituição apenas em estado failed ou paused. Capítulos completed continuam bloqueados e jobs ativos não são duplicados.
- WebReaderPartialRetryFolderAudit verifica no-follow para a pasta e os arquivos, nomes page-NNNNN.bin e _download-plan.json, índices abaixo do plano, links únicos, limites de tamanho, ausência de arquivos desconhecidos, recibos completed, subpastas, symlinks e metadados de pasta estáveis antes/depois. Qualquer anomalia recusa a substituição e deixa o conteúdo no lugar.
- A auditoria não decodifica páginas, não garante ausência total de corridas de filesystem entre validação e remoção, nem comprova que o plano original é restaurável. Uma substituição autorizada segue destrutiva: preservar previamente uma cópia externa de Downloads e SQLite antes de qualquer teste físico é obrigatório.
- As verificações de segurança são por código-fonte e, em macOS, compilação/execução do próprio auditor Swift contra fixtures descartáveis, sem acessar o iPad ou rede. Integradas à regressão Linux/macOS e ao build de compatibilidade iOS 12.

## Critérios de conclusão

Executar regressão EL em Linux/macOS e compilação da aplicação iOS 12 em runner macOS. Nenhum resultado sintético deve ser tratado como autorização de instalação. A PR #90 continua Draft e main intocada. O acionador de Build71 não será criado e productionPublicKeyX963, independentlyProvisionedSPKISHA256 e liveInstallationEnabled seguem desativados.

Antes de qualquer Build71 física, exigir prova separada da cópia externa integral, identidade da aplicação instalada e leitura do mesmo capítulo com rede desligada, seguida de autorização explícita de entrega e instalação.

## Complemento EM — substituição em etapas, sem apagar a pasta na admissão

A Fase EL inicialmente exigia confirmação e auditoria, mas ainda excluía a pasta inteira **antes** de salvar o novo plano. A correção EM elimina essa remoção por completo no método de download: pastas existentes e explicitamente admitidas são mantidas; a repetição recomeça do índice zero e só sobrescreve cada página conforme a nova imagem passa pela validação de conteúdo e é gravada atomicamente. Se a obtenção de novas páginas, codificação de plano ou abertura da fila falhar, as páginas previamente armazenadas permanecem no lugar. Pastas com conteúdo inesperado continuam recusadas.

**Limites:** após uma tentativa parcialmente bem-sucedida, a pasta pode conter uma mistura de páginas antigas e novas; somente a auditoria final da contagem pode marcar o capítulo como completo. O plano de recuperação pode ser atualizado mesmo quando o SQLite falha. A opção de repetição ainda exige confirmação humana e não substitui backup externo verificado. A integridade real de imagem, ausência completa de corridas no filesystem e persistência no iPad continuam sem prova física. Em nenhum caso o app apaga automaticamente a pasta pré-existente só para iniciar um retry.
