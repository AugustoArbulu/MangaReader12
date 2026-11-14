# WebReader — Build 69 experimental: Fases AG, AH e AI

**Data:** 2026-11-08 (UTC).  
**PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90), base `main`, **não mesclar**.  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`.  
**Objetivo deste lote:** robustez do download manual, sem criar ou distribuir uma nova IPA.

## Referência física preservada

A **Build 68** foi instalada e aprovada pelo proprietário no iPad iOS 12.5.8
para abertura do app, preservação da biblioteca e capítulos baixados com Wi-Fi
desligado. Esse aceite refere-se à candidata imutável
`605f607b08d714d8eabfd3270516b77dfaf673e0`, SHA-256
`fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`
([Actions #42453792657](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42453792657)).

**Importante:** o código AC–AI posterior é destinado à futura Build69.
Não é parte da IPA Build68 instalada. Nenhum arquivo da biblioteca foi apagado,
nenhuma atualização foi instalada no iPad e a `main` continua intacta.

## AG — cancelamento atômico com a promoção da IPA

**Arquivo:** `MangaReader12/Core/WebReaderIPAStager.swift`.

### Problema identificado

Antes dessa correção, a fase de auditoria SHA256/ZIP e a promoção da
transferência para um arquivo final `.ipa` ocorriam após fechar o
`OutputStream`, mas o usuário ainda podia pedir cancelamento enquanto
o auditor verificava a cópia. Uma corrida de execução podia:
- cancelar e limpar o `.partial`, mas outro callback tentar mover o arquivo;
- promover `.partial` para `.ipa` perto de uma resposta de cancelamento,
  potencialmente deixando uma cópia final órfã;
- confundir um resultado de transferência com outro.

### Correção

O downloader agora possui `cancelRequested`, sempre protegido por
`stateLock`. O cancelamento marca a decisão **antes** de interromper
a URLSession. O resultado final preserva a decisão de cancelamento se
ela vencer a corrida com uma falha do transporte.

Depois de validar os bytes, a promoção para `.ipa` executa uma seção
crítica única: confirma tarefa atual, presença do callback,
ausência de cancelamento e correspondência do nome `.partial`;
renomeia o arquivo e desassocia a tarefa ainda com a trava retida.
Um cancelamento que chegar **depois** da promoção não pode retirar
a IPA já concluída. Um cancelamento que chegar **antes** bloqueia
a promoção e a remoção fica restrita ao parcial pertencente à sessão.

Ao completar uma operação, o callback é consumido uma única vez. A
mesma instância pode iniciar outra transferência solicitada
explicitamente depois da interrupção.

### Teste adversarial real

`ci/test_native_webreader_ipa_stager.py` usa `URLProtocol` sintético
e duas barreiras de teste, injetáveis **somente** quando o transporte
também é injetado:
1. O arquivo sintético passa no auditor real SHA256/ZIP/Info.plist.
2. O teste bloqueia a execução exatamente **antes** da promoção.
3. Solicita cancelamento enquanto a etapa está suspensa.
4. Verifica callback `.cancelled` e ausência de arquivos parciais.
5. Libera a tentativa de promoção e exige que não apareça nenhuma
   IPA órfã.
6. Verifica que cancelamentos repetidos não têm efeitos colaterais,
   que uma nova transferência pode concluir e que cancelar depois de
   concluir não apaga o arquivo validado.

Essas barreiras jamais são habilitadas no transporte de produção.

## AH — progresso não pode ressurgir depois do cancelamento

**Arquivo:** `MangaReader12/UI/WebReaderAppUpdatesViewController.swift`.

Callbacks de progresso podem estar na fila principal mesmo depois
de interromper a transferência. Agora, ao cancelar pelo item
**Cancelar download em andamento** ou ao sair da tela, a interface
invalida `downloadSessionID` **antes** de chamar `stager.cancel()`.

Qualquer callback pendente só atualiza a interface se o ID ainda
coincidir com a transferência atual. Isso evita sobrescrever
o estado *Cancelando transferência* com um percentual atrasado.
Não altera o leitor, o banco da biblioteca nem os capítulos offline.

## AI — margem de espaço preservada durante o download

**Arquivos:**
- `MangaReader12/Core/WebReaderIPADownloadBudget.swift`.
- `MangaReader12/Core/WebReaderIPAStager.swift`.

A Fase Z já verificava espaço antes do primeiro GET, mas um aplicativo
externo pode preencher o armazenamento **durante** a transferência.
O novo `enoughSpaceDuringTransfer` mantém a mesma reserva calculada
a partir do **tamanho original da IPA**, sem diminuir essa reserva
conforme menos bytes restam.

Fórmula, com todos os valores em bytes:

```
livre_exigido = bytes_restantes_da_IPA
              + max(32 MiB, tamanho_original_da_IPA / 8)
              + 8 MiB
```

O download consulta o filesystem antes do primeiro fragmento e,
em seguida, aproximadamente a cada 4 MiB. Se o filesystem não
informar espaço ou a margem tiver desaparecido, aborta com
`.insufficientSpace` e descarta a `.partial`, sem apagar outros
arquivos do usuário.

A conferência é *best effort*: outros processos podem continuar
consumindo disco e não existe reserva garantida pelo iOS. O objetivo
é evitar prosseguir deliberadamente quando o espaço livre cai abaixo
da margem configurada.

Os testes nativos incluem uma amostragem simulada que começa com
espaço suficiente e cai para zero **entre preflight e primeiro
fragmento**, garantindo recusa e limpeza; outra validação Swift
confirma que o orçamento original não encolhe no último fragmento.

## Segurança e limites mantidos

- `WebReaderUpdateChannel.productionPublicKeyX963 = nil`.
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256 = nil`.
- `WebReaderAppinstSocket.liveInstallationEnabled = false`.
- Sem `appinst`, helper privilegiado, criação de IPA ou publicação Release.
- Metadados de GitHub Releases públicos **não autenticam editor**.
- Não há antirreplay persistente do helper Chimera nesta fase.
- Cópias QA/cache são distintas de Biblioteca, backup e capítulos offline.
- A validação macOS/iOS12 por CI **não substitui QA física** de futura IPA.

## Arquivos de teste e workflow

- `ci/test_native_webreader_ipa_stager.py` — cenários de concorrência,
  cancelamento, retomada explícita, SHA e ZIP/Info.plist.
- `ci/test_native_webreader_ipa_download_budget.py` — fórmula de
  espaço real em Swift e reserva original sem encolhimento.
- `ci/test_build69_phase_ag_ah_ai_transfer_policy.py` — contratos
  estáticos de transição atômica, download sem privilégio, segurança
  do callback de progresso e orçamento dinâmico.
- `ci/test_build68_phase_aa_ab_manual_controls.py` — regressão do
  resultado `.cancelled`/limpeza adaptada ao novo controle atômico.
- [GitHub Actions — Build69 AC–AI](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42456803468)
  (workflow `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml`).

A primeira execução foi interrompida no teste nativo porque seu
contador de requisições não incluía o GET *deliberadamente abortado*
por falta de espaço. Após corrigir a contagem, o teste principal de
concorrência, cancelamento e retry passou. Uma segunda tentativa
detectou uma expressão aritmética excessivamente sobrecarregada
no fixture Swift de orçamento; a constante foi tipada de forma
explícita, sem alterar a fórmula de produção. A versão mais recente
da CI reúne essas duas correções de teste.

**Status final: SUCCESS (2/2 jobs)**, [GitHub Actions #42456803468](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42456803468), commit de código testado `e57be14ae7fc0a2aec7740ad67348c78c4e66e22`. O job Linux aprovou contratos de cancelamento, integridade, orçamento e regressões offline. O job macOS executou os testes Swift reais (inclusive as barreiras de concorrência), compilou o aplicativo completo **Debug e Release ARM64/iOS12** e conferiu identidade do binário e bloqueio do instalador. O workflow **não produziu IPA**; isso não substitui validação física da futura Build69.

## Próxima versão física

Se o lote passar por completo, ainda será preciso preparar uma
candidata independente Build69 ad hoc, auditar a IPA final, registrar
commit e SHA256 e obter aprovação física do usuário. O app Build68
já aprovado não deve ser desinstalado antes de backup externo.
