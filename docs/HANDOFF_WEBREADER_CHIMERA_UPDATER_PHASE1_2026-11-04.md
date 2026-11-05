# WebReader — Atualizador nativo via Chimera: auditoria e handoff técnico

**Data:** 2026-11-04. **Branch proposta:** `feat/chimera-updater-phase1-protocol-audit`. **Repositório:** `AugustoArbulu/MangaReader12` (**público**, confirmado via API).
**Referência estável:** Build 56, usuário confirmou funcionamento físico em iOS **12.5.8**. `main` no início da auditoria: `1283a0614acf3a267e3daddcdafc6c0d0cf335a7`, CI principal concluído com sucesso. **Não atualizar automaticamente a versão do app para 57.**

## 1. Origem da demanda e estado real

O handoff do usuário descreve um objetivo separado do leitor: `WebReader → verificar nova build → baixar IPA → verificar autenticidade/integridade → solicitar instalação com Chimera → reabrir`, sem Safari, Filza, computador ou Sideloadly a cada build.

| Dependência / estágio | Estado confirmado | Não confundir com |
|---|---|---|
| iOS 12.5.8, Chimera rootful, Sileo, Filza/WebDAV | Usuário confirma funcionamento | Compatibilidade automática de qualquer helper |
| AppSync Unified 116.0 (`iphoneos-arm`) | Usuário confirma instalado | Direito de instalar sem jailbreak ativo |
| `appinst` 2.1.1 (`ai.akemi.appinst`) | Usuário confirma instalado a partir do espelho `Legacy-Me/repo` | Autenticidade do `.deb` ou capacidade do WebReader de invocar o processo |
| Build 56 WebReader | Usuário confirmou teste físico | Existência de updater integrado |
| Atualizador in-app | **Ainda não implementado** | Instalador funcional |

Não pedir ao usuário para reinstalar o Chimera, AppSync, Sileo, Filza ou appinst; as instalações já foram reportadas. Mas **não usar o appinst desse espelho até sua proveniência ser verificada** frente à distribuição original de Karen/あけみ. Documentação oficial: `https://github.com/akemin-dayo/AppSync/tree/master/appinst`; o arquivo `appinst/control` identifica pacote, arquitetura e versão. O README oficial recomenda releases sem modificação de `https://cydia.akemi.ai/`. Nenhum hash oficial do `.deb` 2.1.1 foi confirmado nesta auditoria; não alegar equivalência binária.

### Auditoria adicional do código original do appinst

O código-fonte oficial em `akemin-dayo/AppSync/appinst/appinst.m` usa **`LSApplicationWorkspace installApplication:withOptions:error:` no iOS 8+**, a partir de um caminho temporário da própria ferramenta. O pacote define `appinst_INSTALL_PATH = /usr/bin` e aplica um arquivo específico de **entitlements** (`com.apple.private.mobileinstall.allowedSPI` e acesso ao serviço `com.apple.mobile.installd`). Isso reforça que executar instalação a partir de um app UIKit normal **não é equivalente** a rodar a ferramenta instalada no sistema. A integração privilegiada exige teste de permissões, helper restrito e autorização de solicitações.

O código também realiza cópia temporária e tratamento de instalações concorrentes. Não expor ao helper um caminho arbitrário ou confiar apenas no hash conferido pelo processo normal do WebReader; revalidar o artefato no auxiliar imediatamente antes de chamar o instalador.

**Fontes de código:** `https://github.com/akemin-dayo/AppSync/blob/master/appinst/appinst.m`, `https://github.com/akemin-dayo/AppSync/blob/master/appinst/appinst_entitlements.plist` e `https://github.com/akemin-dayo/AppSync/blob/master/appinst/Makefile`. Inspeção estática não comprova que a instalação funciona com a variante específica do pacote presente no aparelho.

### Avanço de Fase 2: auditoria estática de pacote rootful

Localizei o pacote correspondente ao ambiente do aparelho no espelho **`Legacy-Me/repo`**:

- `debs/ai.akemi.appinst_2.1.1_iphoneos-arm~akemi-git-235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a.deb`
- **Tamanho no espelho:** `59716` bytes;
- **SHA-256 publicado no índice do próprio espelho:** `5997771183c39eb8b5e13fc2bb511b1dfcb7eb39d3f10c9092ab088ec34aae09`;
- o mesmo espelho distribui uma variante `iphoneos-arm64`, que não substitui a variante rootful `iphoneos-arm` usada em iOS12.

**Advertência:** esse SHA-256 **NÃO é um hash oficial autenticado da desenvolvedora**. Conferi o anúncio de arquivo/indexação do espelho, mas ainda **não** confirmei o conteúdo binário do pacote instalado, a identidade com o artefato de `cydia.akemi.ai`, nem a cadeia de assinatura APT. O repositório oficial do projeto AppSync no GitHub publica releases do AppSync Unified, mas a lista consultada **não trouxe um asset separado do `appinst`** para comparar diretamente. É obrigatório manter `official_origin_verified = false`.

Para adiantar a análise sem riscos, acrescentei:

- `ci/audit_appinst_deb.py` — auditor de `.deb` **somente leitura**, executável em host Python3. Inspeciona arquivo `ar`, `debian-binary`, metadados Debian `control`, arquitetura, versão, `data.tar`, localização esperada `usr/bin/appinst`, scripts de manutenção e links/paths perigosos. Imprime hash local e se é igual ao **hash do espelho**, mas **nunca aprova sua autenticidade oficial**.
- `ci/test_audit_appinst_deb.py` — gera `.deb` artificiais offline, testando versão/arquitetura incorretas, caminhos `../`, links simbólicos absolutos, executáveis `setuid`, membros duplicados, scripts de manutenção e formato inválido.
- Integração com GitHub Actions, sem `dpkg -i`, sem chamar `appinst`, sem executar scripts, sem buscar binários por rede.

**Uso futuro, sem instalar nada:** `python3 ci/audit_appinst_deb.py "/caminho/para/appinst-2.1.1-iphoneos-arm.deb"`. A saída deve ser interpretada como *relatório estrutural*, **não** como certificado de procedência. Se houver uma cópia do `.deb` realmente instalado no iPhone, seu hash também deve ser confrontado separadamente com o arquivo do espelho e com um identificador confiável da distribuição oficial, caso seja localizado.

### Resultado da auditoria do `.deb` real do espelho (04/11/2026)

O GitHub Actions analisou **os bytes reais** do pacote rootful disponibilizado pelo espelho, sem instalação, no run de push [41937123759](https://github.com/AugustoArbulu/MangaReader12/actions/runs/41937123759), concluído com sucesso. Verificações:

- `59716` bytes, SHA-256 **igual ao digest do próprio índice do espelho**: `5997771183c39eb8b5e13fc2bb511b1dfcb7eb39d3f10c9092ab088ec34aae09`.
- Metadados internos: `Package=ai.akemi.appinst`, `Version=2.1.1`, `Architecture=iphoneos-arm`.
- Arquivo `ar` efetivo: `debian-binary`, `control.tar.gz` e **`data.tar.lzma`**. O auditor foi ampliado com descompressão LZMA-alone limitada em tamanho, incluindo teste de truncamento.
- O payload contém `usr/bin/appinst`. **Nenhum script Debian de manutenção** foi encontrado. Nenhuma execução ou instalação ocorreu.
- A referência `235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a` do nome do pacote corresponde a um commit existente do repositório oficial `akemin-dayo/AppSync`, com autoria `Karen/あけみ`. **O nome do arquivo não demonstra que seu binário deriva fielmente desse commit.**
- A consulta ao índice HTTPS original `cydia.akemi.ai/Packages.bz2`, `Packages.gz` e `Packages` **não obteve resposta**: três timeouts de leitura. Portanto a comparação entre hash do espelho e um hash publicado pelo próprio autor **continua inconclusiva**.
- O `.deb` que está **instalado no dispositivo** também não foi extraído ou comparado. **`official_origin_verified=false`** e `permission_to_install_granted=false` no relatório.

Código de CI: `ci/audit_pinned_appinst_mirror.py`, `ci/test_audit_pinned_appinst_mirror.py`, `ci/audit_appinst_deb.py` e `ci/test_audit_appinst_deb.py`. Auditoria estrutural bem-sucedida **não equivale** a autenticação do fornecedor ou a permissão para executar o appinst em modo privilegiado.

**Próximo gate físico:** recuperar o `.deb` efetivamente instalado ou um hash confiável do pacote, verificar procedência com a distribuição oficial por um canal autenticado e só então testar instalações de um app descartável, sem tocar na Biblioteca do WebReader.

## 2. Integração verificada no repositório

- **Nome público:** WebReader. **Bundle ID real:** `com.example.MangaReader12`, **executable:** `MangaReader12`, **deployment target** 12.0. **Nunca mudar ID/contêiner** durante atualização. Bundle ID igual é necessário, mas não garante preservação em todo modelo de assinatura/entitlement.
- **Compilação:** `.github/workflows/build.yml` com Xcode 15.4/macOS14, Debug + Release, verificação de Info.plist e IPA não assinada `WebReader-iOS12-unsigned.ipa`; artefato de CI está chamado `WebReader-iOS12-Build56`.
- **Distribuição atual:** GitHub Actions artifacts, que **expiram**. O endpoint de download do GitHub responde com redirect temporário, com controle de autenticação, e **não é um endereço direto permanente apropriado a um atualizador iOS12 sem token**. Nunca embutir PAT ou token GitHub no IPA.
- **GitHub Releases do projeto:** **nenhum Release publicado** na auditoria. Proposta: publicar futuramente um Release público com asset IPA estável **somente mediante autorização explícita e após revisão**; não criar release ou nova build apenas por este trabalho.
- **Biblioteca:** SQLite e diretórios `Application Support/MangaReader12`, downloads e preferências. Backup `.mr12backup` é parcial: não inclui arquivos de capítulos baixados nem scripts das fontes. Não substituir/desinstalar a build atual para testes do instalador.
- **Ajustes:** a entrada de futuras Atualizações pode ficar em `Ajustes → Sobre o WebReader → Atualizações`, mas não adicionar botão de instalar até autenticação, helper e QA concluídos.

## 3. Protocolo de atualização v1 (somente experimento offline)

Entregar inicialmente manifesto pequeno HTTPS **autenticado criptograficamente**: envelope JSON `schemaVersion=1`, `algorithm=ecdsa-p256-sha256`, `payload` base64 e `signature` base64 DER. Assina-se o **payload bruto** (bytes UTF-8) com chave ECDSA P-256; a chave pública de produção deverá estar **fixada no app**. O arquivo privado de assinatura nunca pertence ao repositório, IPA ou logs de CI.

Campos do payload assinado: `schemaVersion`, `application`, `bundleId`, `channel`, `build`, `minimumIOS`, `ipaUrl`, `ipaSize`, `sha256`, `releaseNotes`, `publishedAt`. Comparar `build > instalado`; exigir `bundleId=com.example.MangaReader12` e iOS mínimo <= sistema real. O manifesto precisa identificar somente o canal `development` autorizado e URL HTTPS de um **Release público do projeto** com tag `build<build>` e asset `WebReader-iOS12-unsigned.ipa`.

**Limites:** envelope <=64 KiB; payload <=32 KiB; IPA de até 512 MiB (máximo de protocolo, não garantia de RAM/espaço); SHA-256 de 64 caracteres minúsculos, URLs sem query/fragment, campos JSON exatamente conhecidos, rejeição de chaves duplicadas. Metadados assinados não substituem a validação do **SHA-256 real após o download**.

**Código experimental de host:** `ci/webreader_update_manifest.py` verifica assinatura ECDSA com a ferramenta local `openssl` e valida a política, mas **não efetua rede, downloads, unpack do IPA, alterações no app nem execução do appinst**. `ci/test_webreader_update_manifest.py` gera chave efêmera em diretório temporário e testa assinatura válida, adulteração, build anterior, bundle errado, iOS incompatível, URL de Actions e domínios estranhos, campos adicionais, JSON duplicado e limites. As chaves geradas são **somente fixtures**; não há chave de produção nem Release real.

**Implementação futura no iOS 12:** usar Security.framework `SecKeyVerifySignature` e `URLSession` com verificação TLS padrão e política explícita de redirects; esta camada host Python/openssl **não** roda dentro do iPhone. Antes de confiar no fluxo, verificar em hardware a cadeia TLS de manifesto, `github.com` e asset host final (por exemplo `release-assets.githubusercontent.com`), sem desativar validação de certificado.

### Validação estrutural offline da IPA — etapa preparatória adicional

Para não deixar a validação de arquivo como um plano abstrato, adicionei `ci/validate_webreader_ipa.py` e `ci/test_validate_webreader_ipa.py`. O auditor:

- calcula SHA-256 do arquivo e exige igualdade com o hash esperado;
- lê `Payload/MangaReader12.app/Info.plist` e exige `CFBundleIdentifier=com.example.MangaReader12`, nome público `WebReader`, executável esperado `MangaReader12`, build **mais nova** e `MinimumOSVersion` compatível;
- rejeita duplicatas de entradas ZIP, caminhos `../`, entrada fora do `Payload`, outro bundle de app, links simbólicos, arquivos ZIP criptografados e tamanhos/expansão excessivos;
- **não extrai**, não carrega dylibs, não executa arquivos de instalação e não muda o sandbox do WebReader.

O CI testa casos maliciosos **offline** e executa este auditor sobre a **IPA real** produzida no mesmo job, usando o `.sha256` que o empacotador gerou localmente. Isso oferece proteção contra erros de geração da IPA; **não comprova a autenticidade da publicação**. Na implementação futura, o hash de referência deve vir do **payload autenticado do manifesto**, não ser gerado a partir do próprio download.

Usar no host: `python3 ci/validate_webreader_ipa.py WebReader-iOS12-unsigned.ipa --sha256-file WebReader-iOS12-unsigned.ipa.sha256 --installed-build 55 --installed-ios 12.5.8`.

**Limitação:** a validação host Python não substitui o analisador Swift/iOS12 futuro nem a auditoria de `appinst`, assinatura da publicação ou preservação dos dados durante a instalação.

### Preparação da Fase 3 — verificador nativo (ainda não habilitado)

Adicionada à branch a unidade Swift `MangaReader12/Core/WebReaderUpdateManifestVerifier.swift`, compilada no target iOS12. Utiliza `Security.framework` (`SecKeyCreateWithData`, `SecKeyVerifySignature` com `ecdsaSignatureMessageX962SHA256`) para autenticar o **payload bruto** assinado por ECDSA P-256, seguindo o protocolo host v1. Só aceita chaves públicas EC X9.63 descomprimidas de **65 bytes**, identidade `com.example.MangaReader12`, canal development, build mais nova, tamanho/hash, SO compatível e URL HTTPS do release oficial do projeto.

`ci/test_native_webreader_update_verifier.py` compila **o mesmo arquivo Swift real** em macOS com Security.framework, cria uma chave efêmera (apenas em diretório de teste) e confirma aceitação da mensagem válida, rejeição de assinatura adulterada, host/ID/versão errados, campo extra e **ausência de chave pública**.

**Esta unidade NÃO consulta a internet, NÃO baixa IPA, NÃO inicia appinst, NÃO instala pacotes e NÃO está ligada à interface**. Não contém chave de produção, token, segredo ou endereço ativo de manifesto. Não representa uma Build 57 funcional. O projeto iOS mantém `CURRENT_PROJECT_VERSION=56` e a `main` não é alterada. O verificador só poderá ser usado em produção após provisionamento de chave de release autêntica e mecanismo de publicação autorizado. A inspeção de duplicidade de chaves JSON na implementação Swift ainda precisa ser harmonizada com o validador Python antes de ativação (o payload é verificado *antes* de interpretar qualquer campo).

### Preparação da Fase 3 — UpdateChecker nativo, **sem configuração de produção**

Foi adicionada a unidade `MangaReader12/Core/WebReaderUpdateChecker.swift`, compilada no target iOS 12, mas ainda **não utilizada pela UI**. Ela interpreta resultados de atualização de maneira exclusivamente **read-only** e somente após autenticação pelo `WebReaderUpdateManifestVerifier`.

- O endpoint **fixo e permitido** é `https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/updates/channel-development-v1.json` (endereço planejado; **o manifesto ainda não foi publicado**). Sem suporte a URLs fornecidas por usuário, repositórios de terceiros, redirects ou credenciais.
- A chave `WebReaderUpdateChannel.productionPublicKeyX963` está intencionalmente `nil`. Portanto, no app distribuído, `check()` retorna `.disabled` sem criar sessão ou fazer request. **Nenhum segredo ou chave de release foi criado ou incluído**.
- Para testes locais exclusivamente, o inicializador permite injetar uma chave de **teste efêmera** e `URLProtocol` simulado no host. Não há requisições reais a GitHub nos testes.
- `URLSessionConfiguration.ephemeral`, sem cookies/cache/credential storage, timeouts curtos, GET restrito, TLS padrão sem exceções, redirect recusado. Exige HTTP 200 e `application/json` ou `text/json`, respeita `Content-Length`, interrompe resposta após 64 KiB, rejeita respostas malformadas ou assinatura inválida.
- Resultados tipados: `disabled`, `updateAvailable`, `upToDate` (somente quando há manifesto autenticado mas sem build nova), `failed`. Não salva arquivo nem toca no banco SQLite, dados do usuário, código de fontes, downloads ou execução de processos.
- `ci/test_native_webreader_update_checker.py` compila os **arquivos Swift de produção** e executa `URLProtocol` de simulação, com rejeições de host indevido, chave ausente/errada, 403, HTML e payload maior que 64 KiB; também testa update válido e versão já instalada.
- **Não está habilitada atualização automática, download de IPA, appinst, helper de jailbreak, menu de update ou notificação de versão**. O mesmo `CFBundleVersion=56` permanece. As funções só serão conectadas à interface após provisionamento autenticado da chave de release e aprovação de distribuição.

A rejeição de **chaves JSON duplicadas** foi acrescentada ao verificador Swift e testada offline conforme a seção seguinte. Ainda será necessário definir rotação/revogação de chave, testar HTTPS no iOS 12.5.8 e validar a publicação antes de ativar qualquer atualização.

### Fase 3 — endurecimento do parser de manifesto JSON (2026-11-04)

A Fase 3 tinha uma divergência importante: o validador Python rejeita chaves JSON duplicadas (`object_pairs_hook`), mas `Foundation.JSONSerialization` **não** fornece rejeição equivalente. Isso permite interpretações ambíguas do mesmo documento.

Corrigido na branch com `MangaReader12/Core/WebReaderStrictJSON.swift`, validador **nativo e de uso interno**, compilado no iOS 12:

- Faz a leitura dos bytes UTF-8 com parser recursivo limitado a **32 níveis** e **4.096 valores**, sem requests, alocação ilimitada ou execução dinâmica.
- Rejeita chaves repetidas em **todos os objetos**, incluindo chaves repetidas equivalentes após decodificação de escapes Unicode (ex.: `"name"` e `"\\u006eame"`), dentro de objetos ou arrays; também rejeita strings/escapes/números/trailing data malformados.
- As verificações de **envelope** ocorrem antes de `JSONSerialization`; a verificação de **payload** acontece nos bytes exatos **após autenticação ECDSA** e **antes** da leitura de campos de versão, URL, bundle e SHA.
- As chaves de teste são efêmeras. Não há chave pública de produção, chave privada, manifesto publicado, download de IPA nem invocação de `appinst`.
- As suítes `ci/test_native_webreader_update_verifier.py` e `ci/test_native_webreader_update_checker.py` compilam os arquivos Swift reais no macOS e testam duplicatas em envelopes, payloads **corretamente assinados**, escapes Unicode e profundidade, além das regressões de rede e assinatura.

A alteração reforça o validador, mas **não elimina** os bloqueios para distribuição/instalação: origem do `.deb` instalada ainda não autenticada, sem canal oficial assinado e sem ensaio físico com app descartável. A `main` segue na Build 56.

### Fase 4 — preparação de Release assinado e download verificado (2026-11-04)

Foram implementados **dois componentes novos de pré-produção**, sem ativar qualquer atualização no aparelho:

**1. Preparação offline e auditável do manifesto assinado**

- `ci/prepare_signed_webreader_update.py`: recebe um **IPA existente** e caminhos para chaves privada e pública **provisionadas pelo proprietário fora do repositório**. Lê o `Info.plist`, invoca a auditoria real de identidade/ZIP compatível com iOS 12, calcula SHA-256 e tamanho, inclui notas, versão e URL imutável esperada de `GitHub Releases`.
- Os bytes exatos do payload JSON são assinados com OpenSSL ECDSA P-256/SHA-256; o resultado é conferido com o `ci/webreader_update_manifest.py` usando a chave pública correspondente antes de gravar um **arquivo local com permissões 0600**.
- Rejeita **build antiga, bundle incorreto, notas inválidas, divergência entre chaves, caminhos de chaves dentro do repo, saída já existente, arquivo IPA inválido e versão iOS incompatível**.
- **Não publica Release, não gera nem armazena chaves de produção, não modifica o IPA e não faz requisição à rede.** Publicação do asset e manifesto dependerá de autorização expressa e revisão do canal de entrega. O `ipaUrl` assinado é apenas uma **URL planejada**, não uma prova de que o asset existe.
- `ci/test_prepare_signed_webreader_update.py` usa **IPA sintética, chaves efêmeras e diretório temporário** para testar a assinatura ponta a ponta, rejeição de adulteração e políticas negativas. Não inserir nem mesmo chaves de teste estáticas no GitHub.

**2. Download e staging nativo sob verificação criptográfica**

- `MangaReader12/Core/WebReaderIPAStager.swift` usa `URLSessionDataDelegate`, `OutputStream` e `CommonCrypto CC_SHA256` incremental para baixar em pedaços, sem alocar um arquivo de IPA inteiro em memória.
- Exige um `WebReaderVerifiedUpdate` obtido a partir de manifesto autenticado; compara novamente URL de Release do repo, versão, hash e tamanho, exige **HTTPS**, só aceita redirecionamentos limitados para hosts de assets do GitHub e não envia cookies/credenciais. Rejeita HTTP diferente de 200, conteúdo HTML, arquivo maior/menor, SHA incorreto, ZIP sem magic `PK\x03\x04` e falhas de escrita.
- Trabalha em diretório privado de staging (`Application Support/WebReaderUpdates`); arquivo parcial é descartado após falha, pacote aprovado mantém nome único para inspeção futura. **Não descompacta, não executa, não chama `appinst` e não substitui a versão instalada**.
- **Importante:** o stager valida o hash e o prefixo ZIP, mas **não** substitui a auditoria de `Info.plist`, caminhos do ZIP e identidade do executável na etapa privilegiada. O pacote precisa de uma **segunda validação independente no auxiliar**, com validação de proveniência e autorização de usuário.
- `WebReaderUpdateChannel.productionPublicKeyX963` permanece `nil`, e **nenhuma tela chama o stager**; sem chave provisionada, ele retorna `.disabled` antes de abrir conexão ou criar arquivos.
- `ci/test_native_webreader_ipa_stager.py` utiliza `URLProtocol` simulado, payload SHA-256 assinado com chave de teste efêmera, fragmentação da resposta, arquivo correto, hash errado, arquivo truncado, excesso de bytes, HTTP 403, HTML e ZIP inválido; também verifica limpeza de arquivos parciais e bloqueio sem chave de produção.

**Resultados de hardware ainda não demonstrados:** não foi testada a resposta real do CDN de Releases no TLS do iOS 12.5.8 nem a disponibilidade do staging para futuro helper. Há uma diferença entre **staging autenticado** e **instalação privilegiada funcional**; esta fase só implementa o primeiro.

**Fluxo planejado para releases futuras:** proprietário provisiona chaves fora do repo → CI compila IPA com ID preservado → auditor independente revisa o pacote → script gera manifesto assinado local → proprietário publica **asset público de Release** e manifesto correspondente mediante aprovação → verificador iOS12 autentica → stager salva IPA verificada → somente então helper restrito pode pedir confirmação explícita e instalar. Nenhum desses passos de publicação e instalação foi realizado nesta fase.

### Fase 4B — área de atualizações do aplicativo (05/11/2026)

Foi implementada uma **tela UIKit exclusiva para releases do WebReader** em `MangaReader12/UI/WebReaderAppUpdatesViewController.swift`, acessível por **Ajustes → Atualizações do WebReader**. Ela é separada da aba `Atualizações` de capítulos e do controle de atualização da Biblioteca em background.

- A tela apresenta a **versão efetivamente instalada** consultando `Bundle.main.CFBundleVersion`, status do canal de assinatura, ação de verificação *quando realmente habilitada*, notas do release assinado e estado de segurança do instalador.
- Quando `WebReaderUpdateChannel.productionPublicKeyX963 == nil` (estado atual), exibe **"Verificação indisponível"**, não faz chamadas HTTP, não mostra um botão fictício de instalação nem atribui "atualizado" sem verificação. O texto explica que o canal de atualização ainda não foi publicado/autenticado.
- Quando um dia houver uma chave pública legítima provisionada e um manifesto publicado, o usuário poderá fazer uma consulta **manual**. A ação chama `WebReaderUpdateChecker`, que valida ECDSA, versão e URL. A UI apresenta notas apenas após `.updateAvailable`; também apresenta falhas de rede/assinatura e resultado `.upToDate` sem declarar sucesso indevidamente.
- A interface não chama `WebReaderIPAStager`, `appinst`, `dpkg`, processos privilegiados, download ou IPC. **Não há instalação ou download real habilitados.** Não há checagem automática, notificação push, polling de GitHub nem acesso aos dados da Biblioteca.
- Separação visual: a preferência anterior “Atualização automática” é rotulada **"Atualização da Biblioteca"** para evitar que o usuário a confunda com atualizações do aplicativo. O app mantém a build nativa 56 na branch.
- `ci/test_app_updates_screen.py` valida o wiring do Xcode, entrada em Ajustes, versão dinâmica na tela, condição fail-closed, renderização de release notes e ausência de chamadas de instalação. O GitHub Actions continua compilando iOS12 Debug/Release.
- **Para teste físico** futuramente será necessária IPA nova e deliberada em branch apropriada; esta tela ainda **não está presente na Build 56 instalada no aparelho**. Não promover para `main` nem considerar a interface validada fisicamente só porque compila.

A futura experiência será `Ajustes → Atualizações do WebReader` → consultar **releases oficiais assinados**, e não cada commit do GitHub. O download/instalação dependem de gates de chave real, distribuição HTTPS, origem do `appinst`, helper e testes de preservação de dados.

## 4. Etapas obrigatórias antes de instalar IPAs

### A — Autenticidade de appinst e experimento isolado

1. Conferir a origem do `.deb` instalado, package metadata, payload e checksum contra distribuição oficial confiável; se não houver um artefato oficial equivalente, **não aprovar sua execução privilegiada**.
2. Validar o próprio `appinst` 2.1.1 em ambiente rootful e Chimera **fora** do WebReader, usando um app de teste descartável (outro Bundle ID), não a Biblioteca real.
3. Confirmar paths do executável, dependências, permissões, código de saída, comportamento com AppSync ativo/inativo, respring/reboot e suporte a IPA já instalado; registrar resultados físicos.

### B — Manifesto/distribuição e verificação de download

1. Decidir canal de entrega: somente GitHub Releases públicos com asset imutável (ou HTTPS equivalente devidamente auditado). Não usar URLs de artefatos Actions como versão de produção.
2. Gerar e guardar a chave **privada de release** fora do repositório; fixar a chave pública correta no app; fornecer processo de rotação/revogação auditável.
3. Implementar UpdateChecker **somente leitura** no iOS12; início manual e checagem automática opt-in. Sem acionamento automático de download.
4. Implementar URLSession download em arquivos temporários privados, progresso/cancelamento, restrição de domínios e redirects, limites de espaço, tamanho e SHA-256. Validar ZIP/IPA com entradas de caminho seguras, Info.plist, versão, iOS e bundle ID. Nunca seguir symlinks.

### C — Helper rootful separado, instalado via Sileo

1. Criar auxiliar privilegiado com integração apropriada ao Chimera, somente depois de validar appinst. Não assumir que um app iOS normal pode executar processos do sistema.
2. IPC **local autenticado** com verificação da identidade do cliente e confirmação explícita. Nenhum serviço privilegiado aberto à rede, comandos de shell livres, URLs arbitrárias ou paths livres fornecidos pelo app.
3. O helper deve **revalidar** assinatura/manifeste/hashes/Bundle ID antes da instalação; aceitar apenas arquivo aprovado em diretório protegido. Somente operar sobre o WebReader, não agir como instalador geral.
4. O helper continua após a saída do app, grava resultado e não tenta repetição infinita. Sem rollback automático até existir uma estratégia testada.

### D — Teste de atualização e dados

- Criar `.mr12backup` e **cópia independente dos capítulos offline**, pois o backup portátil não inclui os arquivos de capítulos.
- Comparar bundle ID e os entitlements realmente instalados antes/depois. Atualizar inicialmente um **app de teste**, depois uma cópia de dados de teste do WebReader; registrar progresso SQLite, pins, biblioteca, filtros, fontes, cache e downloads.
- Com jailbreak inativo, o WebReader não deve tentar helper nem instalação; consulta pode permanecer disponível onde URLSession permitir.
- Só promover a funcionalidade após teste real `build N → N+1` por IPA, reinício, preservação de sandbox e recuperação de falha.

## 5. Relação com o roadmap existente

**O roadmap funcional não foi substituído:** Build 57 continua reservada ao aprimoramento de Downloads (fila/lote/cancelamento e feedback); Builds 58/59 seguem para Leitor e Sources, salvo decisão futura do usuário. O atualizador é uma trilha técnica paralela `Updater Fases 1–7`. Evitar chamar o teste do protocolo de “Build 57” ou afirmar instalação pronta. A Build56 é o ponto de referência física.

## 6. Estado deste PR e próxima tarefa

- **Concluído nesta etapa:** auditoria de projeto/distribuição, integração documental, proposta de assinatura, simulador offline de manifestos host, auditoria estática `.deb`, validação offline da IPA real gerada pelo CI e testes adversariais. Nenhum comando privilegiado executado; nenhuma IPA nova publicada; `main` preservada até aprovação do PR.
- **Pendente:** validação independente do `.deb` 2.1.1 vindo do espelho; experimento isolado com appinst no dispositivo; pinagem de chave pública real; publicação autorizada de Release, HTTPS real no iOS12; downloader; helper/IPC; instalação; QA de preservação de dados.
- **Regra de segurança:** não baixar IPAs de manifestos não autenticados e não iniciar instalação a partir do WebReader antes de confirmação expressa do usuário e testes do auxiliar.

## 7. Referências

- Handoff do usuário recebido em 2026-11-04, “Sistema de atualização de IPA diretamente pelo aplicativo utilizando jailbreak Chimera”.
- AppSync e appinst originais: https://github.com/akemin-dayo/AppSync/tree/master/appinst
- GitHub Actions artifacts REST (URLs temporárias): https://docs.github.com/en/rest/actions/artifacts
- GitHub Releases REST (distribuição proposta): https://docs.github.com/en/rest/releases/releases
- Projeto WebReader, estado de referência: https://github.com/AugustoArbulu/MangaReader12/blob/main/docs/BUILD56_SOURCE_ATTRIBUTION_UPDATES_2026-11-04.md
