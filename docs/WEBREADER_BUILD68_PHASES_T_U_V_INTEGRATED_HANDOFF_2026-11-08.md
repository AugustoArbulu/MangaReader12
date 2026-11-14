# WebReader / MangaReader12 — Build68 experimental, Fases T + U + V

**Data:** 2026-11-08 (UTC)  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`  
**PR:** [#90 — Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90), base `main`; **não mesclar**.  
**Dispositivo:** iPad iOS 12.5.8, Chimera, AppSync Unified; biblioteca SQLite e leitura offline aprovadas na **Build66**.  
**Build67:** IPA manual já disponível, QA física ainda não confirmada.  
**Build68:** apenas código de desenvolvimento; **nenhuma IPA publicada ou instalada**.

## Objetivo

Realizar uma entrega maior sem promover a funcionalidade de instalação:
integrar a verificação de manifesto editorial assinado **com os bytes
efetivos da IPA** (T), tornar o estado da segurança legível dentro do app
(U), e consolidar os obstáculos do autorizador Chimera baseados nas
observações físicas e nos ensaios de laboratório (V).

A autenticação editorial depende de uma chave pública previamente
estabelecida por um canal independente do GitHub Release. A chave de
produção continua **ausente**. Mesmo uma assinatura válida com chave
fornecida em fixture **não** equivale a provar a identidade do editor.

## Fase T — prévia conjunta assinada v2 + IPA em disco

**Novo arquivo:** `MangaReader12/Core/WebReaderSignedIPAReview.swift`.

O método `WebReaderSignedIPAReview.inspectReadOnly` recebe:
- Manifesto JSON assinado **v2**.
- Chave pública X9.63 EC P-256 e seu SHA-256 SPKI que deverá ser
  provido por um canal independente.
- URL **local** da IPA a ser inspecionada, versão instalada e versão iOS.

Em duas camadas estritamente separadas:
1. `WebReaderSignedReleaseTrustGate.inspectReadOnlyV2` compara o hash
   SPKI local com o pin independente e confere a assinatura ECDSA e os
   metadados de manifesto v2, incluindo Bundle ID, application-identifier,
   build crescente, compatibilidade iOS, nome do Release e hash.
2. `WebReaderNativeIPAAuditor.inspect` abre o arquivo local uma vez com
   `O_NOFOLLOW`, usa o **mesmo descritor** para SHA-256 completo, ZIP,
   estrutura do executável, Info.plist e hash final; checa inode, tamanho,
   mtime e ctime no início e fim. O recibo compara build, versão mínima,
   Bundle ID e SHA aos valores do manifesto.

**O que NÃO cobre:** verificação nativa da assinatura ad hoc do
executável no iPad, identidade editorial do proprietário, autenticação
do solicitante Chimera, estabilidade permanente do arquivo **depois**
da auditoria ou decisão de instalar. O código não possui rede, UI,
instalador ou side effects em Biblioteca/Downloads.

O recibo `WebReaderSignedIPAReviewResult` guarda observações técnicas,
mas os campos `nativeExecutableSignatureChecked`,
`publisherIdentityProvenByDevice`, `fileLockedForLaterUse`,
`peerAuthenticated`, `consentForInstallVerified`,
`installationAuthorized` e `installationPerformed` são falsos.

**Teste nativo:** `ci/test_native_webreader_signed_ipa_joint_audit.py`.
Utiliza OpenSSL com chave descartável e IPA ZIP sintética, com:
manifesto válido; arquivo de mesmo tamanho com bytes trocados;
manifesto assinado para IPA de Bundle ID errado; CRC ZIP adulterado
mas hash correspondente assinado; assinatura ECDSA adulterada;
link simbólico para IPA válida; pin incorreto ou ausente; mesma build
instalada. O resultado final do teste é somente revisão ou recusa.

## Fase U — painel de status de segurança dentro do aplicativo

**Novo arquivo:** `MangaReader12/Core/WebReaderUpdaterSecuritySnapshot.swift`.  
**Interface alterada:** `MangaReader12/UI/WebReaderAppUpdatesViewController.swift`.

A seção "SEGURANÇA" agora tem **cinco linhas**, em vez de um rótulo
genérico:

1. **Segurança das atualizações:** explica que HTTPS e SHA-256 do
   GitHub não autenticam o publicador.
2. **Assinatura editorial:** mostra ausência da chave pública de produção.
3. **Autorização do Chimera:** informa que a identidade do solicitante
   ainda não foi atestada pelo sistema.
4. **Operações permitidas:** consulta, auditoria, importação e
   compartilhamento manual; instalação automática bloqueada.
5. **Copiar diagnóstico de segurança:** relatório curto com Build/iOS,
   origem, limitações e status, sem caminhos internos, biblioteca,
   credenciais nem comandos de instalação.

A seção é apresentada **somente no WebReader normal**, nunca nas IPAs
de diagnóstico IPC Test. Usa UIKit compatível com iOS12.

O relatório somente valida e mostra número da Build e string de iOS
limitada, sem copiar dados pessoais arbitrários. A ação copia texto
local e exibe confirmação: **não instala, não baixa IPA e não altera
preferências da Biblioteca**.

**Teste:** `ci/test_native_webreader_update_security_snapshot.py`
executa o código Swift real em macOS com stubs das propriedades de
produção, mais regressão estática de integração `ci/test_build68_phase_tu_readonly_contract.py`.

## Fase V — matriz de prontidão do autorizador Chimera

**Código host-only:** `ci/build68_chimera_readiness_matrix.py`.  
**Teste:** `ci/test_build68_chimera_readiness_matrix.py`.

Consome o diagnóstico de sete linhas da Fase E, já executado
fisicamente como `mobile` no Chimera em 07/11/2026:

- `UNIX_PEERTOKEN=UNAVAILABLE`;
- `CSOPS_TOKEN_BINDING=NOT_TESTED`;
- Três símbolos de inspeção Security.framework não encontrados;
- `FINAL_INSTALL_AUTHORIZATION=DENIED`.

Não se deve inferir **por que** o PEERTOKEN estava indisponível:
API ausente, política sandbox, tamanho do buffer e condições do
processo podem produzir observações indistinguíveis.

O modelo lista **oito gates bloqueados**:

| Gate | Condição ainda necessária |
|---|---|
| IOS12_KERNEL_PEER_TOKEN | Observação real de token obtido pelo helper no socket do cliente |
| IOS12_RUNNING_APP_CODE_IDENTITY | Correspondência de assinatura/CodeDirectory de código executado vinculada ao token |
| PER_MESSAGE_ORIGIN | Garantia de autoria de cada pedido, inclusive frente a descritores retransmitidos ou mensagens enfileiradas |
| RELEASE_EDITOR_TRUST_ANCHOR | Chave editorial legítima previamente confiável |
| RELEASE_BYTES_IN_HELPER | Verificação independente dos **mesmos bytes** recebidos pelo instalador |
| TRUSTED_OWNER_CONSENT | Confirmação independente de operação única pelo proprietário |
| PRIVILEGED_REPLAY_AND_DOWNGRADE | Journal durável e proteção de versão implementados no helper real |
| PHYSICAL_IOS12_REPRODUCTION | Prova física no iOS12 com Chimera após desenvolvimento dos mecanismos anteriores |

O parser de relatórios nunca converte alegações de UID, PID, token,
CDHash ou símbolos `PRESENT` em autenticação. Ele retorna
`installation_authorized=False`, inclusive para logs falsificados
que parecem perfeitamente favoráveis. **Não existe helper privilegiado
novo nesta fase.**

A alternativa manual Filza continua disponível, e nenhum comando é
enviado ao iPad pelo laboratório.

## Validação e preservação

**CI integrada T/U:** [GitHub Actions #42451263546](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42451263546)

- Job Linux com contratos da UI, assinatura e biblioteca: **SUCCESS**.
- Job macOS: testes Swift nativos, auditorias herdadas e compilação Debug +
  Release iOS12 ARM64 **SUCCESS**. Checagem final do executável, bundle,
  iOS mínimo e bloqueio de instalação **SUCCESS**.
- **Estado final T/U: SUCCESS (2/2 jobs)**, run #42451263546 no commit de código
  `70a7ee15b62f6b910e06929d9f4a2a60ad33f05e`.
- A aprovação é de CI Linux/macOS; **não** substitui QA física no Chimera.
- Não empacota nem publica IPA, não instala apps e não utiliza chave real.

**CI Chimera V:** [GitHub Actions #42451360332](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42451360332) — **SUCCESS**, testes de entradas falsas, relatório físico observado e políticas anteriores.

**Gates de produção inalterados:**
`WebReaderUpdateChannel.productionPublicKeyX963 = nil`;
`WebReaderAppinstSocket.liveInstallationEnabled = false`.
A UI não invoca o examinador de IPA assinada antes de existir
uma chave editorial confiável provisionada fora dos releases.

## Ordem para um próximo incremento

1. Conferir CI final das Fases T/U e reparar eventuais regressões.
2. Melhorar políticas de distribuição e rotação da **chave pública** sem
   comprometer a chave privada do proprietário nem confiar em chave/pin
   entregues juntos com um Release.
3. Para o iOS12/Chimera, testar APIs somente em utilitários **não
   privilegiados** sob autorização do usuário; um sucesso macOS não prova
   disponibilidade no iPad.
4. Caso autenticação kernel-bound não seja viável ou não seja auditável,
   preservar a instalação manual via Filza e evitar habilitar instalação
   automática por PING, HMAC ou nome de processo.
5. Somente após requisitos confiáveis, plano de backup/rollback e QA
   física, propor uma nova IPA para testes, sem alterar a `main`
   nem a Biblioteca existente.

**Não é necessário executar nenhum teste no iPad agora.**
