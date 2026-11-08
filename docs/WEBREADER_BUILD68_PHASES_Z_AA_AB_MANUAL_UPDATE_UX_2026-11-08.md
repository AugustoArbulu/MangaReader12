# WebReader — Build 68 experimental, Fases Z, AA e AB: download manual mais seguro

**Data:** 2026-11-08 (UTC)  
**Repositório:** `AugustoArbulu/MangaReader12`  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`  
**PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90), base `main`. **Não fazer merge.**  
**Dispositivo:** iPad iOS 12.5.8 com Chimera. Build66 é a última aprovada fisicamente; Build67 continua sem aprovação física registrada; Build68 experimental não foi distribuída como IPA.

## Propósito deste lote

As Fases W/X/Y adicionaram políticas de confiança editorial e revisão
monotônica de laboratório, mas a instalação automática permanece
bloqueada por falta de raiz editorial de produção, identidade segura
do solicitante Chimera e autorização confiável pelo helper.

O presente lote melhora um fluxo já disponível **sem depender desses
requisitos pendentes**: a atualização manual com download de IPA
pelo WebReader e compartilhamento para Filza.

Foram implementadas três melhorias concretas: limite conservador de
espaço livre, progresso/cancelamento de transferências e recibo de
integridade copiável com nova auditoria do arquivo existente.

## Fase Z — proteção do armazenamento e progresso de transferência

**Arquivos:**
- `MangaReader12/Core/WebReaderIPADownloadBudget.swift` (novo).
- `MangaReader12/Core/WebReaderIPAStager.swift` (modificado).
- `MangaReader12/UI/WebReaderAppUpdatesViewController.swift` (modificado).

O novo módulo `WebReaderIPADownloadBudget` é compilado no target
iOS 12 e oferece duas operações:

- `requiredFreeBytes(ipaBytes:)`: exige
  `tamanho_da_IPA + max(32 MiB, 1/8 do tamanho) + 8 MiB`.
  IPAs vazias, negativas ou acima de **512 MiB** são recusadas.
  O cálculo usa aritmética com detecção de overflow.
- `availableFreeBytes(in:)`: abre a pasta exclusiva
  `Application Support/WebReaderUpdates` com `O_NOFOLLOW`,
  confere o tipo do diretório e consulta `Darwin.fstatfs`
  **no descritor aberto**. Diretórios simbólicos, sem
  capacidade ou inacessíveis causam recusa.

O downloader consulta essas operações **antes** de criar
`.webreader-<UUID>.partial` ou disparar qualquer requisição GET.
Espaço insuficiente retorna `.insufficientSpace`; o erro informa
explicitamente que os capítulos offline devem ser preservados.
O app **não exclui arquivos** para liberar espaço.

A checagem é **uma estimativa pré-transferência**. Outro aplicativo
pode utilizar armazenamento enquanto a IPA baixa; o sistema ainda
pode ficar sem espaço. O WebReader não promete reserva de disco,
nem altera cotas ou privilegiamento.

O downloader possui um callback de progresso opcional, atualizado
somente a cada incremento de 5%, limitado a **95%** antes de
SHA-256 e validação ZIP/Info.plist estarem concluídos. A interface
exibe esse percentual como **bytes recebidos**, jamais como prova
de assinatura editorial ou instalação.

## Fase AA — cancelamento dentro da tela

O item ativo de download agora fica selecionável com o rótulo
**Cancelar download em andamento**. Ao tocar, o aplicativo:

1. Cancela a tarefa HTTP ativa, de forma explícita.
2. Encerra stream e sessão; o callback recebe `.cancelled`,
   distinto dos erros de TLS, transporte, integridade e disco.
3. Remove somente seu arquivo `.partial` localizado no
   cache próprio de atualizações.
4. Mostra `Download cancelado • cópia parcial removida`.

Chamadas repetidas de cancelamento não criam novo download.
O fechamento da tela continua cancelando a tarefa.
Nenhuma limpeza atravessa a pasta do WebReader para a Biblioteca,
os capítulos, backups, importações do Filza ou a instalação
existente.

**Limite:** a remoção ocorre sobre o arquivo temporário da sessão
corrente e só depois que a transferência é interrompida. Isso
não substitui a limpeza de arquivos abandonados da Fase Q.

## Fase AB — recibo de integridade para o fluxo Filza

A seção **Atualizações disponíveis** possui um sexto item quando
há metadados de Release: **Copiar recibo de integridade da IPA**.

O item fica inativo até a IPA ser baixada e aprovada.
Antes de copiar qualquer coisa, `copyStagedIPAReceipt` executa
novamente o auditor nativo `WebReaderNativeIPAAuditor.inspect`,
que calcula SHA-256 sobre um descritor regular aberto com
`O_NOFOLLOW`, confere ZIP, `Info.plist`, Bundle ID, Build,
versão iOS e digest final.

O relatório copiável contém:
- Build, Bundle ID e iOS mínimo;
- tamanho em bytes, SHA-256 e número de entradas ZIP;
- procedência declarada;
- avisos de que o editor **NÃO foi autenticado** por GitHub Release
  público, e de que o arquivo pode mudar após a auditoria;
- negação explícita de instalação automática.

Não inclui `/var/mobile/`, caminho da IPA, URL privada,
credenciais, identificadores do dispositivo, conteúdo de capítulos,
biblioteca ou comandos para helper root.

Se a IPA estiver ausente, alterada ou inválida na hora da cópia,
a ação recusa, descarta a referência selecionada e solicita um
novo download. **Nenhum recibo vira uma autorização de instalar.**

## Testes novos e alterados

- `ci/test_native_webreader_ipa_download_budget.py`:
  executa Swift/Darwin de verdade em macOS; testa fórmula de
  espaço, zero/limite 512 MiB, filesystem acessível, pasta ausente,
  symlink e ausência de limpeza.
- `ci/test_native_webreader_ipa_stager.py`:
  integra o módulo real e um `URLProtocol` sintético; exige zero
  requisições GET e zero arquivos parciais com espaço insuficiente,
  progresso monotônico em passos de 5% e download cancelado
  sem depender de resposta final HTTP.
- `ci/test_build68_phase_z_download_budget_policy.py`:
  testes de contrato do orçamento, integração UI e bloqueios de produção.
- `ci/test_build68_phase_aa_ab_manual_controls.py`:
  bloqueios de instalação, revisão local obrigatória, clareza de
  procedência e cancelamento seguro.
- `ci/test_app_updates_screen.py`:
  regressão atualizada para progresso, seis itens e recibo da IPA.
- Quatro suites Swift preexistentes que compilam o stager
  receberam a nova fonte de orçamento na lista de compilação:
  staging, importação QA, inventário local e inventário de cache.

**Workflow:** [GitHub Actions Z/AA/AB](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42452983919)

Este workflow executa contratos estáticos Linux,
regressões de migração e leitura offline, testes Swift
macOS de staging/importação/armazenamento e compilação
integral **Debug e Release ARM64 para iOS 12**, sem IPA
assinada ou publicação.

**Estado final da CI: SUCCESS (2/2 jobs)** em [GitHub Actions #42452983919](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42452983919), commit de código `142a1c0a7f364eab92df42fa3a82325aeab0376d`.
O job Linux aprovou as regressões de espaço, cancelamento, recibo,
compatibilidade e leitura offline. O job macOS executou os testes
**Swift nativos reais**, incluindo transporte sintético, orçamento de
espaço e cancelamento de arquivo parcial; depois concluiu **Debug e
Release ARM64/iOS 12 com sucesso**, verificou a identidade do binário
e a trava de instalação. Não gerou/distribuiu IPA e não testou o iPad.

## Travas de segurança preservadas

- `WebReaderUpdateChannel.productionPublicKeyX963 = nil`.
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256 = nil`.
- `WebReaderAppinstSocket.liveInstallationEnabled = false`.
- Nenhum `appinst`, instalação, daemon root ou credencial de GitHub
  no cliente; esta etapa não executa a IPA.
- A PR #90 permanece Draft; a `main` não é modificada.
- Nada foi instalado no iPad e não houve alteração de biblioteca
  ou capítulos offline.
- O teste físico do novo fluxo depende de uma futura IPA aprovada
  separadamente, após CI e preservação do backup já validado.

## Próxima etapa recomendada

Após a aprovação da CI, revisar como o app se comporta
quando a transferência é interrompida em momentos diferentes
antes e depois da criação da IPA final, sem tocar no
instalador Chimera. O bloqueio de identidade do peer e a
chave editorial de produção devem continuar como iniciativas
separadas, sem usar SHA do GitHub como atalho de autenticação.
