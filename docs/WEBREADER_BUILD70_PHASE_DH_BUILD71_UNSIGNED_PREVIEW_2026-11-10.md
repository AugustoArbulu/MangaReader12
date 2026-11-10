# WebReader Build70 — Fase DH: prévia **não assinada** de Build71 para QA (sem IPA)

**Data:** 10/11/2026. Branch experimental: `feat/chimera-updater-phase1-protocol-audit`, PR #90 em rascunho. Não modificar `main`, GitHub Releases, o iPad iOS12.5.8 ou a Build70 instalada e aprovada com biblioteca, favoritos e offline íntegros.

## Por que a Fase DH

A fase DG já compilou o WebReader inteiro para iOS12 com o botão **Atualizações → Segurança → Copiar identidade do processo WebReader**. Mas tal botão está apenas na branch, não no iPad. O próximo objetivo é uma **candidata futura Build71** que, somente se o proprietário aprovar um teste físico e a integridade puder ser validada, possa usar a mesma identidade de aplicação para atualizar manualmente a instalação existente sem criar app paralelo.

O pacote existente `ci/build70_private_qa_ipa_preflight.py` e o fluxo de one-shot estão **congelados em Build70 / baseline físico Build69**; NÃO reutilizar nem adulterar seus campos para fingir que aprovam uma atualização Build70→Build71. A construção futura exige um preflight separado, de base física 70 e target 71, prova real de assinatura/entitlement e auditoria física de preservação offline. Essa aprovação **não existe** na DH.

## Implementação

- `ci/build70_dh_unsigned_build71_preview.py`: verifica a configuração do repositório e, opcionalmente, uma `MangaReader12.app` **unsigned** criada pelo Xcode. Confere `CURRENT_PROJECT_VERSION = 56;` no projeto fonte (duas configurações), pins de produção `nil/nil`, `liveInstallationEnabled=false` e os campos exclusivamente read-only da nova linha do diagnóstico. Lê o arquivo QA de entitlements para comprovar apenas que o **valor histórico registrado na fonte** continua `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`; isso NÃO prova entitlements do app gerado ou identidade da versão atualmente instalada no iPad.
- A inspeção opcional da `.app` exige caminho isolado fora do checkout, `Info.plist` com Build **71**, `CFBundleIdentifier=com.example.MangaReader12`, nome WebReader, executável MangaReader12, `MinimumOSVersion=12.0`, ícone AppIcon/Assets.car e Mach-O ARM64/iOS12 real. Rejeita arquivos ausentes, symlinks no executável, programa de outra arquitetura/plataforma e `_CodeSignature` ou `embedded.mobileprovision` inesperados. A análise é **somente leitura**, baseada no parser Mach-O C/Info.plist já auditado na fase BA.
- `ci/test_build70_dh_unsigned_build71_preview.py`: testes host com fixtures descartáveis, que demonstram versões incorretas, identidade trocada, Mach-O de outra arquitetura/minOS, ícone ausente, diretório de assinatura inesperado, alteração de pin editorial, `liveInstallationEnabled=true`, arquivo de entitlements adulterado, nova opção de diagnóstico ausente, pasta de saída dentro da árvore fonte e assinatura/cópia de IPA ausentes.
- `.github/workflows/chimera-build70-phase-dh-unsigned-71-preview.yml`: Ubuntu executa os testes host e regressão DG; macOS 15 usa Xcode 16.4, gera ícones, prepara libwebp 1.6.0 SHA-pinado e **compila** com `CURRENT_PROJECT_VERSION=71 CODE_SIGNING_ALLOWED=NO`, guardando o app só no `RUNNER_TEMP`. Audita `Info.plist`, Mach-O e fontes pelo script DH. **Não** executa `codesign`, não empacota `Payload` ou IPA/DEB, não faz `upload-artifact`, não publica Release, não instala e não grava nada no iPad.

## Limites de segurança — não promover

Uma `MangaReader12.app` unsigned e analisada localmente **não equivale** a um IPA apto para instalação por cima da Build70. O rótulo da fonte e a string histórica `application-identifier` do fixture não comprovam que uma futura assinatura ad-hoc produzirá entitlements compatíveis com o app instalado. Para aprovar uma nova versão física, continuam obrigatórios: recibo de app e IPA assinados com os bytes exatos; entitlements verificados no código assinado; idêntico Bundle ID e app identifier aprovados no iPad; SHA-256 externo; backup/contagens antes/depois; teste de capítulos baixados com Wi-Fi desligado; e o aceite do proprietário para preparar/distribuir a IPA. Mesmo passando tudo, a instalação automática por `appinst` permanecerá bloqueada.

`inspect_dh_source` retorna apenas **`DH_SOURCE_READY_FOR_UNSIGNED_PREVIEW_ONLY`** e `inspect_dh_unsigned_app` retorna apenas **`DH_UNSIGNED_APP_METADATA_ONLY_NOT_INSTALLABLE`**. Os dois retornos mantêm `ownerDistributionApprovalRecorded=false`, `entitlementsOfCompiledCandidateVerified=false`, `deviceInstallabilityProven=false`, `installationAuthorized=false`, `installationPerformed=false`. O recibo de app unsigned mantém também `installableIPAProduced=false`, `appCodeSignatureVerified=false`, `installedApplicationIdentifierMatchedOnDevice=false`, `libraryDataPreservedOnDevice=false` e `offlineReadingVerifiedOnDevice=false`.

### Próximo passo após aprovação da CI

Se a compilação DH ficar verde, preparar primeiro **um gate de QA privada específico para 70→71**, com todos os checks de assinatura e preservação exigidos, sem nenhum caminho automático de instalação. A Build71 não deve ser oferecida ao usuário como IPA até haver um gatilho do proprietário independente e revisão do código gerado. A versão 70 física não necessita de intervenção durante essa preparação.

**Travas inalteradas:** `WebReaderAppinstSocket.liveInstallationEnabled=false`; `WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`; `main` intacta, PR #90 Draft. Ainda não há helper de IPC autenticado, vault imutável nem publisher editorial provisionado.

**CI DH:** preencher apenas após consultar os jobs e logs finais. Não alegar que compilar uma `.app` prova instalação ou preservação física.
