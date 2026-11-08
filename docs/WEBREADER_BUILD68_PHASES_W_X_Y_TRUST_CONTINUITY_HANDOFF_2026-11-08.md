# WebReader — Build 68 experimental, Fases W, X e Y

**Data:** 2026-11-08 UTC  
**Repositório:** `AugustoArbulu/MangaReader12`  
**Branch exclusiva:** `feat/chimera-updater-phase1-protocol-audit`  
**PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90), base `main`. **Não fazer merge.**  
**Estado físico:** Build66 é a última versão aprovada no iPad iOS 12.5.8; Build67 aguarda validação física; Build68 continua código experimental sem IPA distribuída.

## Escopo do lote

Prosseguir na preparação de atualizações autenticadas **sem publicar uma
chave de produção e sem criar instalador Chimera**. Separar três
responsabilidades que não podem ser confundidas:

- **W — raiz editorial de produção**: só considerar um manifesto
  autenticado se chave pública e SPKI SHA-256 tiverem sido provisionados
  independentemente em um build revisado do WebReader.
- **X — ciclo de vida editorial**: verificar, em laboratório e
  exclusivamente offline, candidatos de rotação de duas chaves e uma
  lista explícita de fingerprints revogados.
- **Y — sequência monotônica de QA**: impedir, somente durante a mesma
  sessão de revisão, reapresentar uma Build menor/igual depois de uma
  previamente conferida e aceita.

As três partes não têm side effects de instalação, não executam appinst,
não criam privilégios, não configuram chave privada e não modificam
Biblioteca, Backup, capítulos offline ou arquivos do Filza.

## Fase W — porta editorial exclusiva do código de produção

**Novos arquivos:**
`MangaReader12/Core/WebReaderProductionPublisherTrust.swift`;
`ci/test_build68_phase_w_production_publisher_policy.py`.

O verificador de desenvolvimento da Fase S recebe chave pública X9.63
e fingerprint independente injetados pelos testes. Isso é correto para
um laboratório, mas não pode ser confundido com a API que futuramente
seria chamada pelo atualizador real.

O novo método
`WebReaderProductionPublisherTrust.inspectProductionManifestReadOnly`
recebe **somente envelope, Build instalada e versão iOS**. Ele **não**
aceita parâmetros de chave pública ou fingerprint do chamador. Busca
os dois exclusivamente nas constantes compiladas:

- `WebReaderUpdateChannel.productionPublicKeyX963 = nil`;
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256 = nil`;
- `productionTrustGeneration = 0`;
- `revokedPublisherPins = []`.

Dessa maneira, enquanto o proprietário não provisionar e validar de
forma independente a chave pública, `isProvisioned` é falso e a
porta de produção lança `noProvisionedOwnerTrust`, **mesmo quando
um testador apresenta um manifesto ECDSA assinado corretamente por
uma chave de fixture**. Um valor vindo do GitHub, clipboard,
`UserDefaults`, assinatura ad hoc de IPA ou argumento do cliente
não ativa esse caminho.

O código compila no target iOS 12 (arquivo 38 do projeto). A CI
exercita a recusa com um par de chaves descartáveis. Rotação futura
exigirá uma revisão independente do material público, identidade
editorial efetiva, revogação e atualização do binário com nova política.

**Importante:** essas constantes estão propositalmente desativadas.
Não se recomenda criar chave de produção, publicar segredo no chat ou
assinar material de publicação sem procedimento de custódia e
revisão operacional.

## Fase X — rotação e revogação, sem promoção de chave

**Novos arquivos:**
`ci/build68_release_key_lifecycle_review.py`;
`ci/test_build68_release_key_lifecycle_review.py`.

A Fase B do projeto já tinha um verificador de rotação de chave com
assinaturas ECDSA P-256 **da chave anterior e da sucessora**. A Fase X
fortalece o gate de avaliação:

1. Fingerprint SPKI anterior obrigatoriamente separado, validado
   com OpenSSL e confrontado ao material público.
2. Lista de revogação imutável (tuple/frozenset), limitada a 64
   fingerprints canônicos, sem entradas inválidas ou duplicadas.
3. A chave antiga revogada e a chave sucessora revogada **não
   podem** participar de uma rotação mesmo com assinaturas válidas.
4. A sucessora deve ser distinta, e o número de geração tem de avançar
   exatamente uma unidade.
5. A build de ativação no manifesto de rotação deve ser maior que a
   instalada.
6. Assinaturas antigas, novas, incorretas, falsas aprovações e
   campos adicionais são recusados.
7. O resultado `KeyLifecycleReview` **não modifica** constantes,
   não chama APIs de instalação e mantém
   `production_key_configured=false`,
   `owner_independent_consent_verified=false`,
   `installation_authorized=false` e
   `installation_performed=false`.

A lista passada ao laboratório não prova sua própria origem.
Uma lista de revogação confiável de produção precisaria ser mantida
por política/canal independente no dispositivo. A Fase X **não é**
uma infraestrutura de revogação remota, apenas um pré-ensaio.

## Fase Y — replay e downgrade durante uma sessão de revisão

**Novos arquivos:**
`MangaReader12/Core/WebReaderSignedPreviewSequence.swift`;
`ci/test_native_webreader_signed_preview_sequence.py`;
`ci/test_build68_phase_y_monotonic_preview_policy.py`.

O novo `WebReaderSignedPreviewSequence` mantém `highestReviewed`
em memória e protegido por `NSLock`. O ponto inicial é a Build
instalada e cada tentativa real passa por
`WebReaderSignedIPAReview.inspectReadOnly`, que combina manifesto
assinado e auditoria nativa da IPA local.

- Somente uma Build **maior** que a já revisada pode avançar a marca.
- Erros de assinatura, pin ou IPA não avançam a marca.
- Chamadas concorrentes são serializadas para que a mesma candidata
  não passe duas vezes simultaneamente.
- Não persiste qualquer histórico em disco nem em `UserDefaults`.
- Fechar/reabrir o app **reinicia** a marca na Build instalada.
- Isso **não** é proteção contra rollback de armazenamento, reinstalação,
  invasor com acesso root, nem replay de comandos de instalação.

O relatório mantém `isPersistent=false`,
`installerLedgerVerified=false`,
`installationAuthorized=false` e
`installationPerformed=false`. A UI principal não utiliza a
nova classe; nenhum fluxo de instalação foi habilitado.

A suíte executa o **código Swift real de serialização de revisões**
com uma substituição de laboratório só para o verificador de conteúdo.
Os testes criptográficos e de IPA real continuam em suíte separada,
no mesmo workflow. Há um cenário de 40 tentativas concorrentes de
revisar exatamente a mesma Build, que deve resultar em **uma**
aceitação na sessão.

## Workflows de integração

**Fases W/X:** [GitHub Actions](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42452070164)

`.github/workflows/chimera-build68-phase-wx-publisher-policy.yml`
executa regressões de pin independente, duas assinaturas, revogação,
recusas de produção, integração anterior T/U/V, Swift nativo real
(Security.framework) e compilação ARM64/iOS12 Release completa.

**Fase Y:** [GitHub Actions](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42452134488)

`.github/workflows/chimera-build68-phase-y-monotonic-preview.yml`
executa contrato Linux de não privilégio, teste de concorrência em
Swift nativo, regressão da verificação de manifesto/IPA e compilação
ARM64/iOS12 Release completa.

**Resultado final:** preencher somente após as duas execuções
terminarem com sucesso. Falhas exigem correção antes de declarar
a Build68 validada nestas fases.

## Bloqueios fundamentais que permanecem

1. **Identidade editorial real:** nenhum fingerprint/chave pública
   de produção foi instalado; o operador ainda precisa definir
   custódia/assinatura/revogação e validar a origem independentemente.
2. **Identidade do processo solicitante ao helper Chimera:** no
   experimento físico da Build66 como mobile, o diagnóstico retornou
   `LOCAL_PEERTOKEN=UNAVAILABLE`. O motivo exato é inconclusivo; o
   projeto não tem uma prova confiável que vincule um pedido IPC à
   assinatura do WebReader no iOS12.
3. **Consentimento confiável:** a interface do cliente não pode ser
   a única autoridade; o helper precisaria de um consentimento
   inequívoco, independente, de uso único.
4. **Imutabilidade da IPA instalada:** uma revisão do cliente
   não garante os bytes que um helper privilegiado venha a abrir.
   O helper precisaria adquirir/verificar a própria referência
   imutável e a assinatura do executável antes de qualquer operação.
5. **Replay/downgrade persistente:** o estado volátil da Fase Y é
   insuficiente; journal e política precisam residir em domínio
   protegido e ser testados no iOS12 real.

**Gates de produção continuam:**

- `WebReaderUpdateChannel.productionPublicKeyX963: Data? = nil`
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256 = nil`
- `WebReaderAppinstSocket.liveInstallationEnabled = false`
- PR #90 Draft; `main` intacta; nenhuma IPA Build68 publicada.
- Biblioteca, leitura offline, backup e Build66 física preservados.

**Nenhuma ação no iPad necessária para estas fases.**
