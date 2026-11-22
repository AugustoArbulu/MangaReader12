# WebReader — desenvolvimento posterior à Build 68: Fases AC–AF

**Data:** 2026-11-08 (UTC).
**Branch:** `feat/chimera-updater-phase1-protocol-audit`.
**PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90) — base `main` **não modificada**.
**Referência física congelada:** Build 68, pacote da execução [#42453792657](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42453792657), SHA-256 `fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`.

## Contexto da continuidade

A Build 68 foi instalada pelo usuário via Filza no iPad **iOS 12.5.8**,
e ele confirmou funcionamento da biblioteca e de capítulos offline com
Wi-Fi desligado. Essa aprovação física se aplica à **candidata exata**
do commit `605f607b08d714d8eabfd3270516b77dfaf673e0`.

Este lote é código de **desenvolvimento futuro, previsto para uma
Build 69**. NÃO altera o pacote aprovado da Build 68, NÃO produz nem
distribui uma IPA nova e NÃO configura a chave editorial nem ativa o
instalador automático do Chimera.

### Fase AC — não copiar SHA obsoleto de uma IPA local

O item *Copiar SHA-256 conferido* da seção `IPA LOCAL` copiava o hash
armazenado na primeira importação, sem abrir novamente a cópia. Embora
compartilhamento já fizesse recheck, a ação de cópia ainda poderia
mostrar um digest antigo se o arquivo tivesse sido alterado.

**Corrigido em** `MangaReader12/UI/WebReaderAppUpdatesViewController.swift`:

1. Marca a revisão como ocupada para impedir concorrência com outras
   operações locais.
2. Reexecuta `WebReaderLocalIPAReviewer.recheck` em fila não principal,
   usando inode, arquivo regular, SHA-256, ZIP e identidade.
3. Se o recheck falha, não toca no clipboard, descarta apenas a cópia
   original de QA protegida por identidade e exibe mensagem de erro.
4. Se passa e a tela ainda está visível, copia o hash conferido.
5. Não lê nem remove biblioteca, downloads de capítulos ou arquivos
   originais do Filza.

**Limitação:** o arquivo pode mudar após um recheck. O relatório serve
para conferência manual, não como ticket de instalação imutável.

### Fase AD — respostas CDN completas e não transformadas

**Corrigido em** `MangaReader12/Core/WebReaderIPAStager.swift`:

- Redirecionamentos seguem exigindo HTTPS e hosts exatos da CDN
  GitHub, com no máximo dois redirects. Agora também se exige GET,
  ausência de corpo de requisição, cookies, cabeçalho Authorization,
  fragmento e porta customizada.
- Somente status HTTP 200 e formatos de IPA permitidos são aceitos.
- Respostas com `Content-Encoding` não identidade ou `Content-Range`
  são rejeitadas, mesmo se declararem status 200.
- Os testes nativos usam `URLProtocol` sintético para as negativas
  de gzip e faixa de bytes, além do caso positivo sem transformação.

O digest e auditor ZIP/Info.plist continuam obrigatórios; rejeitar
uma transformação é defesa adicional, não validação editorial.

### Fase AE — roteiro de QA física privativo e copiável

**Novo:** `MangaReader12/Core/WebReaderPhysicalQAChecklist.swift`,
incluído no target ARM64/iOS12.

A seção `SEGURANÇA` do app ganha a sexta linha:
**Copiar roteiro de testes físicos**. O relatório copiado contém
Build e iOS observados, e dez perguntas a preencher pelo proprietário:
instalação pelo Filza, biblioteca, capítulos sem Wi-Fi, leitor,
fontes, importação/Hash, cancelamento, recibo, bloqueio de instalação
automática e backup externo.

Cada resposta começa como **SIM/NÃO/NÃO TESTADO**. O aplicativo
**não finge verificar a biblioteca, o Wi-Fi, capítulos ou o backup**.
Nenhum dado pessoal, senha, caminho de arquivos ou chave é lido.
Um teste Swift real do template em macOS verifica formatação,
ausência de efeitos colaterais e valores inválidos.

### Fase AF — bloqueio de downgrade antes do GET

O downloader revalida o `CFBundleVersion` atual **no momento em que
o download é solicitado**, mesmo quando o resultado da consulta foi
obtido anteriormente. Uma Build igual ou menor que a instalada gera
`.notNewerThanInstalled` antes de qualquer solicitação GET ou
arquivo parcial. A interface explica o motivo.

Para testes, uma substituição de Build só é permitida quando também
há `URLProtocol` injetado; em produção a versão sempre vem do
bundle instalado. O teste nativo verifica versão igual, maior e
candidata nova mas com espaço insuficiente: todos negam o GET
quando não permitido.

**Importante:** essa proteção protege somente o processo não
privilegiado do downloader. Ela NÃO cria antirreplay persistente
ou controle de downgrade dentro de um helper root Chimera.

## Compatibilidade iOS 12 detectada e corrigida na CI

A primeira rodada de testes nativos detectou uma ordem incorreta dos
argumentos de teste Swift; foi corrigida sem alterar a lógica de produção.
Uma segunda rodada passou nos testes Swift de laboratório, mas o
**build real de Debug para iOS12** rejeitou
`HTTPURLResponse.value(forHTTPHeaderField:)`, disponível somente a partir
do iOS 13. Substituí a leitura desse cabeçalho pelo dicionário
`HTTPURLResponse.allHeaderFields`, com busca case-insensitive; este é
compatível com iOS12. Também adicionei regra estática para impedir
reintroduzir esse método exclusivo do iOS13 na resposta HTTP.

A validação atual é o
[run #42455563835](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42455563835),
com **SUCCESS (2/2 jobs)** no commit de código `7852f9f79761f57519d13dbfeef22d89ad915868`. O job Linux aprovou todas as políticas e regressões de biblioteca/offline; o job macOS executou os testes Swift nativos, compilou **Debug e Release ARM64/iOS 12** e conferiu a identidade do binário, sem produzir IPA. Os runs anteriores são tentativas falhas
documentadas, não evidência de aprovação final.

## Testes e integração

Arquivos de testes alterados/adicionados:

- `ci/test_native_webreader_ipa_stager.py`
- `ci/test_native_webreader_physical_qa_checklist.py`
- `ci/test_build69_phase_ac_ad_ae_policy.py`
- `ci/test_build68_phase_tu_readonly_contract.py`

**Workflow:** [Build69 AC–AF integrado #42455563835](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42455563835)

Executa políticas estáticas e testes de migração/leitura offline em
Linux; em macOS executa testes Swift reais do downloader, importação
local, auditorias ECDSA/IPA, cache e do roteiro físico; compila o app
completo em Debug e Release ARM64/iOS12 e verifica a identidade
legada e a desativação do instalador.

**Resultado final: SUCCESS (2/2 jobs)** em [GitHub Actions #42455563835](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42455563835), fonte de código `7852f9f79761f57519d13dbfeef22d89ad915868`. Ambos os builds iOS12 e o bloqueio de instalação foram validados. Isso é CI, **não QA física** da futura Build69.

## Invariantes obrigatórios

- Build 68: aprovada fisicamente, manter seu pacote e SHA intactos.
- Build 66: guardar como referência histórica de recuperação, sem
  downgrade automático.
- Nova IPA Build 69: **não foi produzida, assinada ou instalada**.
- `WebReaderUpdateChannel.productionPublicKeyX963 = nil`.
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256 = nil`.
- `WebReaderAppinstSocket.liveInstallationEnabled = false`.
- A PR #90 continua Draft e `main` intacta.
- Nenhuma exclusão de biblioteca nem capítulos; nenhuma chamada
  a appinst, nenhum contorno de CAPTCHA, nenhum acesso às fontes.

## Próxima continuação

Após aprovação do workflow, consolidar o novo comportamento e preparar
roteiro de QA física futura. Não lançar Build 69 como IPA sem
identificação imutável de commit, testes Debug/Release, assinatura
ad hoc e auditoria de SHA/ZIP, como foi feito na Build 68. A
autenticação editorial e o helper Chimera continuam problemas separados.
