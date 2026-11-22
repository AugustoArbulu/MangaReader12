# WebReader — Fase BA: pré-candidata compilada em sandbox, sem IPA

**Data:** 09/11/2026 UTC. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90). Nunca modificar a `main` sem nova autorização.

## Estado anterior confirmado

- A Build68 permanece instalada, aprovada e não alterada no iPad iOS 12.5.8. O backup da biblioteca **não contém as páginas offline**; restaurar backup exclui os downloads. Preservar os arquivos sem desinstalar ou restaurar automaticamente.
- [CI AC–AZ #42552255733](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42552255733): **SUCCESS**, 2/2 jobs (testes host e Swift, compilação iOS12 Debug/Release).
- O código no Xcode usa **`CURRENT_PROJECT_VERSION=56` em Debug e Release**. A expressão “Build69” designava as fases de engenharia e não o `CFBundleVersion` do aplicativo compilado. Rotular esse binário como IPA Build69 seria incorreto.
- O root de confiança de produção não está provisionado, `productionTrustGeneration=0`, o instalador Chimera está bloqueado e nenhuma IPA da candidata Build69 foi distribuída.

## Implementação BA — Build69 somente em diretório efêmero do GitHub Actions

Adicionados:

- `ci/build69_ba_unsigned_candidate_audit.py` — lê **somente** uma árvore `MangaReader12.app` local já compilada, exige `CFBundleVersion=69`, bundle ID `com.example.MangaReader12`, executable `MangaReader12`, nome `WebReader`, ícone compilado, `MinimumOSVersion=12.0` e **Mach-O 64 bits thin ARM64 com um único LC_BUILD_VERSION iOS 12.0** (ou comando legado equivalente). Garante as constantes fail-closed do root de produção e Chimera na fonte original. Confere versão de origem=56 **sem alterar o projeto**.
- `ci/test_build69_ba_unsigned_candidate_audit.py` — cria pequenos arquivos temporários **sintéticos** `Info.plist` e Mach-O para testar o auditor, incluindo identidades diferentes, números falsos, iOS13, CPU x86_64, plataforma errada, arquivo truncado e symlink. Um fixture aprovado nunca declara assinatura ad hoc, compatibilidade de instalação no iPad ou autorização de publicação.
- Atualizado `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml` para executar novos testes Linux e **terceira compilação Release iOS12** no macOS, após as compilacões convencionais Debug/Release. O comando passa um override somente para a invocação:
  ```bash
  xcodebuild -project MangaReader12.xcodeproj \
    -scheme MangaReader12 -configuration Release \
    -sdk iphoneos -destination 'generic/platform=iOS' \
    -derivedDataPath "$RUNNER_TEMP/wr69-ba-unsigned-preview" \
    CURRENT_PROJECT_VERSION=69 \
    CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO clean build
  python3 ci/build69_ba_unsigned_candidate_audit.py \
    "$RUNNER_TEMP/wr69-ba-unsigned-preview/Build/Products/Release-iphoneos/MangaReader12.app"
  ```
- O build permanece dentro de `$RUNNER_TEMP`. **Não há `package_ipa.sh`, `ditto`, `zip`, `codesign --sign` ou `upload-artifact` para a candidata** nesse workflow. Checamos ausência de `.ipa` na árvore temporária e `git diff --exit-code` de `project.pbxproj`/`Info.plist`. O relatório inclui SHA-256 do **executável somente**, que não é o SHA de uma IPA assinada.
- [CI AC–BA #42556136980](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42556136980). Verificar resultado ao final; teste positivo **não produz uma IPA instalável**.

## Decisões que não são automatizadas

| Gate | Resultado BA |
|---|---|
| Xcode consegue compilar com `CURRENT_PROJECT_VERSION=69`? | CI macOS avaliará |
| Bundle ID/minimum iOS/ARM64 dentro do `.app` | Auditor BA avaliará |
| Versão 56 continua na fonte sem alterações | Exigido |
| Apple ad-hoc signature e `application-identifier` instalado | **NÃO AUDITADOS, artefato unsigned** |
| Assinatura editorial ECDSA de produção | **AUSENTE, root não provisionado** |
| IPA Build69 assinada, hash exato, receipt e distribuição privada | **NÃO PRODUZIDOS** |
| Upgrade física in-place sobre Build68 sem perder páginas | **NÃO TESTADO** |
| GitHub Release público, alterações na `main` ou instalador Chimera | **NÃO AUTORIZADOS / NÃO EXECUTADOS** |

## Protocolo para uma IPA privada futura, somente após consentimento

A futura candidata QA não é um GitHub Release de produção. Quando autorizada a geração e distribuição privada, será necessário garantir **o mesmo bundle ID e application-identifier do WebReader instalado**, assinatura ad hoc nativa válida e arm64 iOS12; conferir `CFBundleVersion=69`, SHA-256 do **IPA assinado**, tamanho, estrutura ZIP e entitlements. O `ci/build66_code_signature_gate.py` já possui uma rotina nativa de auditagem dos bytes idênticos verificados. O proprietário decide instalação manual pelo Filza, **por cima**, nunca `Uninstall`. Antes de instalar, exportar backup da biblioteca para outro dispositivo; o backup não preserva páginas. Testar abertura e reabertura offline depois. Não ativar nem usar a ponte de instalação Chimera.

Não mudar as constantes reais de key trust para um pin gerado em testes. Não copiar chaves privadas para GitHub Actions. Manter `main` intacta e PR #90 Draft.

## Próxima decisão

Ao receber resultado verde para a compilação BA, revisar a emissão de **uma única candidata QA privada e conscientemente autorizada**, com versão, código assinado e SHA verificáveis, **sem** confundir isso com a ativação do canal editorial de produção. O código atual e a Build68 permanecem preservados até essa autorização.
