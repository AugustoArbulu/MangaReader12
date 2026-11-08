# WebReader — Build 69 futura: Fases AM, AN e AO, canal de atualizações autenticado

**Data:** 2026-11-08 (UTC)  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`  
**PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90), base `main` sem merge  
**Referência física:** Build 68 aprovada pelo proprietário no iPad iOS 12.5.8, com biblioteca e capítulos offline preservados  
**Natureza da entrega:** código experimental para uma futura Build 69, **sem IPA nova, sem instalação, sem chave editorial de produção**

## Descoberta operacional importante

Consulta atual pelo conector GitHub ao repositório `AugustoArbulu/MangaReader12`:

- O repositório está **PÚBLICO** (`private=false`, `visibility=public`), e a branch padrão é `main`.
- `GET /repos/AugustoArbulu/MangaReader12/releases/latest` respondeu **404**.
- `GET /repos/AugustoArbulu/MangaReader12/contents/updates/channel-production-v2.json?ref=main` respondeu **404**.
- As Builds privadas de QA do GitHub Actions **não equivalem** a GitHub Releases públicos. Um artefato de workflow pode exigir sessão autenticada no GitHub; o WebReader não deve embutir um personal access token ou coletar a senha do proprietário.

Portanto, um WebReader sem token **ainda não tem um release público real para descobrir**, mesmo que a verificação HTTPS e o downloader estejam implementados. O botão de verificação assinado também não tem chave/pin editorial provisionados, de maneira deliberada.

**Não** criar um Release público, um canal de produção ou modificar a `main` sem aprovação explícita do proprietário e uma política editorial de assinatura.

## Fase AM — caminho concreto para Builds privadas sem token embutido

**Arquivo:** `MangaReader12/UI/WebReaderAppUpdatesViewController.swift`.

A seção **CANAL DO APLICATIVO** passa de duas para quatro linhas:

- `Canal de lançamentos` (GitHub Releases públicos; consulta via HTTPS, mas sem assinatura editorial independente).
- `Abrir GitHub Releases`.
- `Verificar canal assinado`.
- `Abrir Builds privadas no GitHub Actions`, que abre o endereço `https://github.com/AugustoArbulu/MangaReader12/actions` no navegador do sistema sem tokens nem uso de APIs autenticadas do app.

A nova linha de Actions **não faz** a importação do artefato via URLSession. Serve como ponte explícita para o canal manual já utilizado pelo proprietário: verificar no navegador moderno (por exemplo, Android/PC) e transferir a IPA pelo Filza. O botão avisa que a interface do GitHub pode não funcionar no Safari antigo do iOS 12.

O navegador pode exigir login. O WebReader não recebe o login, senha, cookie de sessão ou PAT. Nenhuma IPA é instalada por esse atalho.

## Fase AN — consulta HTTPS real de produção com bloqueio de origem

**Arquivo novo:** `MangaReader12/Core/WebReaderProductionSignedReleaseChecker.swift`, incluído no target Xcode iOS 12 (ID 42).

A API `WebReaderProductionSignedReleaseChecker.check` usa um `URLSessionConfiguration.ephemeral` sem cookies, cache ou armazenamento de credenciais, solicita JSON a um **URL HTTPS fixo**, nega redirects, exige resposta HTTP 200 de JSON, aplica limite total de **64 KiB** e mantém timeout. O endereço é destinado **futuramente** ao canal de produção:

`https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/updates/channel-production-v2.json`

**Este arquivo ainda não existe no `main`.** Uma URL programada não significa um canal publicado.

Antes de iniciar o URLSession, a nova classe chama `WebReaderProductionPublisherTrust.isProvisioned`. Como a Build atual mantém:

- `WebReaderUpdateChannel.productionPublicKeyX963: Data? = nil`;
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256: String? = nil`;
- `productionTrustGeneration=0`;

a requisição é recusada **antes de qualquer rede**, com `.disabled`.

Quando existir uma política editorial genuinamente revisada e provisionada em binário futuro, a resposta será validada por `WebReaderProductionPublisherTrust.inspectProductionManifestReadOnly`:

- pin SHA-256 SPKI independentemente conferido;
- chave EC P-256 X9.63 do binário, jamais extraída do manifesto;
- envelope JSON estrito, versão 2;
- assinatura ECDSA-SHA256 sobre os bytes exatos;
- identidade do WebReader, Bundle ID e application-identifier;
- Build maior que a instalada e iOS mínimo compatível;
- URL de IPA exata de GitHub Releases com nome `WebReader-BuildN-iOS12-adhoc.ipa`, tamanho e SHA256.

O retorno `upToDate` só pode resultar de um manifesto autenticado que passou pela verificação criptográfica antes da comparação de Build. HTTP 404, HTML, assinatura inválida e indisponibilidade do servidor **não** equivalem a `upToDate`.

A seleção e o download também exigem `.signedManifest` **E** confiança editorial provisionada quando não se tratar do canal público. O canal público continua explicitamente rotulado **sem assinatura editorial** e só oferece instalação manual; nunca instala.

## Fase AO — rejeição criptográfica entre ambientes

**Arquivos modificados:**

- `WebReaderUpdateManifestVerifier.swift` ganha parâmetro `expectedChannel: String = "development"`; somente `development` ou `production` são aceitos.
- `WebReaderSignedReleaseTrustGate.swift` propaga o canal exigido ao verificador ECDSA.
- `WebReaderProductionPublisherTrust.swift` chama a verificação com `expectedChannel: "production"`.

Isso impede que **uma assinatura de desenvolvimento genuína** seja apresentada ao canal de produção, mesmo assinada com a mesma chave. Também rejeita manifestos de produção no verificador de desenvolvimento e nomes arbitrários de canal.

**Novo teste nativo** `ci/test_native_webreader_release_channel_separation.py`: gera uma chave descartável P-256, assina dois manifests válidos de versão 2, valida os casos positivos nos canais corretos e rejeita os casos cruzados, mantendo `installationAuthorized=false`.

**Novo teste nativo** `ci/test_native_webreader_signed_production_discovery.py`: compila a implementação real de transporte/trust no macOS e exige resposta `.disabled` sem acesso à rede e sem chave/pin de produção.

**Novo teste estático** `ci/test_build69_phase_am_an_signed_discovery_policy.py`: exige proveniência, HTTPS, limites, ausência de autenticação GitHub inserida e fluxo de produção sem chave/pin externos.

## O que ainda falta para o botão realmente encontrar uma atualização assinada

1. **Identidade editorial / custódia de chave:** criar procedimento privado e confiável de geração e custódia de chave de publicação P-256, sem salvar a chave privada no repositório, IPA, GitHub Actions logs ou chat.
2. **Provisionamento independente:** obter/conferir a chave **pública** e seu fingerprint SHA-256 SPKI por um canal autenticado independente, revisar e embarcá-los em novo binário do WebReader. O proprietário deve aprovar esse passo. Uma chave de teste jamais vira chave de produção automaticamente.
3. **Disponibilização pública e controle editorial do feed:** hospedar manifest v2 assinado em um endpoint público fixo. Caso seja `main/updates/...`, sua publicação exige aprovação para alterar `main`. Outra localização pública pode ser escolhida, mas a URL do app terá de ser revisada para corresponder.
4. **Release real com IPA:** criar GitHub Release público `buildN` com IPA auditada, `CFBundleVersion=N`, mesmo Bundle ID/entitlement e os mesmos bytes da assinatura e do manifesto. A ausência atual de `releases/latest` impede o caminho de descoberta pública.
5. **QA em iOS 12:** testar HTTPS, obtenção do manifesto, assinatura, download da IPA, SHA256/ZIP, exportação para Filza e preservação da biblioteca na nova candidata.
6. **Somente depois — instalação automática:** autenticação de processo peer Chimera, consentimento independente de uso único, antirreplay/rollback durável e verificação do arquivo exato pelo helper privilegiado. Nenhum dos passos 1–5 autoriza auto-instalar.

**Não assumir** que a publicação ou assinatura editorial foi feita nesta fase. Ainda estamos preparando o código do cliente.

## Validação

Workflow integrado `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml` (cobertura agora AC–AO), Linux + macOS:

[GitHub Actions — AM/AN/AO e iOS12](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42460488168)

O workflow executa regressões da Biblioteca/offline, validações de segurança da UI, Swift nativo ECDSA/dev-prod, verificação de canal signed fail-closed e compilação Debug/Release ARM64 para iOS 12, sem produzir IPA.

**Status:** verificar o resultado final antes de declarar SUCCESS. O código foi atualizado após esta referência; o run definitivo pode ter outro número. O handoff deve ser atualizado com o último run que concluiu sem erros.

## Estado de produção preservado

- Build68 aprovada fisicamente: candidata `605f607b08d714d8eabfd3270516b77dfaf673e0`, SHA `fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`.
- Build69 experimental sem IPA nova.
- `WebReaderAppinstSocket.liveInstallationEnabled = false`.
- `productionPublicKeyX963 = nil`, `independentlyProvisionedSPKISHA256 = nil`.
- PR #90 Draft; `main` não modificada.
- Biblioteca, backup, capítulos offline e dados do Filza não acessados/alterados por este lote.
