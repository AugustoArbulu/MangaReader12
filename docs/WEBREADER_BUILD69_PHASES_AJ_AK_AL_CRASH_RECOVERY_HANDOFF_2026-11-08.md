# WebReader — Build 69 experimental: recuperação segura de downloads, Fases AJ–AL

**Data:** 2026-11-08 UTC.
**Branch:** `feat/chimera-updater-phase1-protocol-audit`.
**PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90); `main` não modificada.
**Status de distribuição:** código-fonte experimental apenas, sem criar IPA Build69.

## Referência física congelada

A **Build68** instalada pelo proprietário no iPad iOS12.5.8 foi aprovada
fisicamente para abertura do WebReader, manutenção da biblioteca e leitura
offline com Wi-Fi desligado. Arquivo exato:
- candidata `605f607b08d714d8eabfd3270516b77dfaf673e0`;
- SHA-256 `fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`;
- [GitHub Actions #42453792657](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42453792657).

A Build69 é uma continuidade independente e **não substitui ou altera**
o pacote que já funciona. Nenhuma intervenção no iPad é necessária
para este lote de CI.

## Problema abordado

Quando o iOS é encerrado durante uma transferência (travamento, bateria,
reinicialização ou encerramento forçado), a pasta privada
`Application Support/WebReaderUpdates` pode ficar com uma
`.webreader-<UUID>.partial` incompleta.

Esses bytes **não são uma IPA validada** e não devem ser usados como
ponto de partida para um download parcial ou como arquivo de instalação.
Ao mesmo tempo, o aplicativo não deve eliminar arquivos sem o
conhecimento do usuário, muito menos tocar nos dados do leitor.

As Fases Q e AG–AI já ofereciam limpeza restrita com confirmação,
cancelamento atômico e proteção de disco. AJ–AL acrescenta
**diagnóstico de recuperação no próximo acesso** e impede que
uma nova tentativa reutilize arquivos não confiáveis.

## Fase AJ — inventário de recuperação estritamente read-only

**Arquivo:** `MangaReader12/Core/WebReaderIPAStager.swift`.

Nova estrutura `WebReaderReleaseRecoverySummary` deriva de um inventário
existente e previamente validado, sem fazer nenhuma nova operação
de I/O. Ela separa:
- arquivos `.partial` interrompidos, com quantidade e bytes;
- IPAs completas antigas, com quantidade e bytes;
- entradas ignoradas/preservadas por idade, nomenclatura, link
  ou por representarem a IPA selecionada.

A estrutura declara explicitamente:
`canResumePartial=false`,
`cleanupRequiresOwnerConfirmation=true` e
`installationAuthorized=false`.

A seleção continua sujeita ao inventário da Fase Q:
- apenas o diretório exato `WebReaderUpdates`, aberto com `O_NOFOLLOW`;
- arquivos com nome gerado pelo próprio downloader;
- arquivos regulares, `nlink=1`, tamanho limitado;
- idade mínima **24 horas** desde mtime e ctime;
- identificação de dispositivo/inode/ctime/mtime para uma eventual
  exclusão **separada** e confirmada;
- limite de 512 nomes em cada inventário;
- arquivos de Biblioteca/Filza, links simbólicos, hardlinks
  e a IPA atualmente selecionada não entram na limpeza.

## Fase AK — reinício completo, nunca retomada parcial

**Arquivos:** `WebReaderIPAStager.swift`,
`ci/test_native_webreader_ipa_stager.py`.

Uma tentativa explícita do proprietário sempre gera um novo
`.webreader-<UUID>.partial`, abre o stream com
`append: false` e faz um **GET completo**. A verificação SHA-256 e
ZIP/Info.plist continua obrigatória antes de promover a cópia
para `.ipa`.

O teste Swift cria uma `.partial` antiga com conteúdo diferente,
faz uma nova transferência completa via `URLProtocol` sintético e
exige:
1. a nova IPA possui os bytes exatos do fixture;
2. a `.partial` antiga continua inalterada;
3. um GET normal foi executado, sem pedido Range;
4. não houve instalação ou exclusão automática.

**Decisão deliberada:** não implementar HTTP Range/retomada neste
momento. Reaproveitar fragmentos em uma plataforma antiga criaria
requisitos adicionais de ETag, If-Range, integridade por segmentos,
persistência de estado e validação editorial. É mais seguro fazer
um GET completo e revalidar todos os bytes.

## Fase AL — visualização automática, sem limpeza automática

**Arquivo:** `MangaReader12/UI/WebReaderAppUpdatesViewController.swift`.

No primeiro `viewDidAppear` da tela normal de atualizações:
- executa-se **uma única inspeção read-only** de `WebReaderUpdates`;
- o usuário vê quantos downloads incompletos antigos e quantas
  IPAs completas antigas foram encontrados, além das entradas
  preservadas;
- a mensagem explica que não existe retomada de `.partial`;
- não é feito nenhum download, `removeItem`, `unlinkat` ou
  instalação sem ação do usuário;
- para limpar, a ação já existente **Limpar downloads antigos…**
  continua exibindo um alerta de confirmação, seguido de rechecagem
  de identidade do arquivo candidato antes de excluí-lo.

A tela diagnóstica IPC permanece excluída desses recursos.
Uma inspeção que falhe ou exceda os limites não executa limpeza.

## Testes de regressão

**Novos:** `ci/test_build69_phase_aj_ak_al_crash_recovery_policy.py`
verifica os contratos estáticos, ausência de limpeza automática,
ausência de Range, retenção de 24h, links, identidade e
bloqueios de instalação.

**Ampliados:** `ci/test_native_webreader_release_cache_storage.py`
exercita o resumo com arquivos recentes, arquivos envelhecidos,
links simbólicos, hardlinks, entradas estranhas e arquivos protegidos.

**Ampliados:** `ci/test_native_webreader_ipa_stager.py` simula
reinício com arquivo `.partial` antigo e obriga uma nova IPA
completa, preservando os dados anteriores até a remoção explícita.

**Workflow integrado:** [Build69 AC–AL #42457377035](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42457377035),
que executa políticas Linux, testes nativos Swift/macOS e compilação
integral Debug/Release ARM64/iOS12, sem empacotar IPA.

**Estado final da CI: SUCCESS (2/2 jobs)** no [run #42457465974](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42457465974), commit de código `d4a6ab15ba1f029de7cfd117c6c39ead3a110a67`. O job Linux aprovou os testes de política e regressões da biblioteca/offline. O job macOS executou os testes Swift nativos — incluindo arquivo `.partial` abandonado e download completo sem retomar —, compilou o aplicativo completo **Debug e Release ARM64/iOS12** e confirmou a identidade do binário e o bloqueio do instalador. **Nenhuma IPA Build69 foi produzida ou instalada**. A CI não substitui QA física.

## Segurança e estado do projeto

- `WebReaderUpdateChannel.productionPublicKeyX963 = nil`.
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256 = nil`.
- `WebReaderAppinstSocket.liveInstallationEnabled = false`.
- Nenhum helper privilegiado ou appinst executado.
- Nenhuma exclusão de Biblioteca, backup, downloads de capítulos,
  dados de fontes ou arquivos de origem do Filza.
- A assinatura ad hoc de uma IPA de teste não autentica editor.
- PR #90 permanece Draft e `main` intacta.
- Nenhuma IPA Build69 foi publicada/instalada e nenhuma alteração
  física foi realizada no iPad neste lote.

## Próxima etapa técnica

Depois da CI, validar o resultado no futuro pacote Build69
somente quando o proprietário desejar testar fisicamente:
reinicialização durante download com conteúdo incompleto,
entrada na tela de atualizações e inspeção do cache
**sem apagar capítulos ou biblioteca**.

Não acelerar a autenticação do helper Chimera usando o SHA-256
dos metadados públicos do GitHub; são mecanismos distintos.
