# WebReader Build69 — Fase BN: assinatura ad hoc temporária do aplicativo REAL (sem IPA)

**Data:** 2026-11-09 UTC. **Branch:** `feat/chimera-updater-phase1-protocol-audit`; [PR #90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90). **Não modificar `main`, criar Release, executar AppSync/appinst ou alterar a Build68 instalada.**

## Base validada antes da BN

CI AC–BM [#42570364142](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42570364142) terminou **SUCCESS nos jobs Linux + macOS**. A BL endureceu a futura publicação local com arquivo final somente após preflight e hard-link exclusivo, sem sobrescrever destinos. A BM gravou um recibo oculto de quantidade esperada de páginas **somente para downloads novos**, validando-o em leitura local e no diagnóstico BI. Downloads antigos Build68 **sem recibo continuam válidos**. [Handoff BL–BM](WEBREADER_BUILD69_PHASES_BL_BM_ATOMIC_QA_AND_COMPLETION_RECEIPTS_2026-11-09.md).

Até então, havia dois testes distintos: **preview real Build69 unsigned** (compilado com override `CURRENT_PROJECT_VERSION=69` sem mudar o Xcode original versão 56) e **assinatura ad hoc de uma IPA sintética de aplicativo C**. Faltava validar a assinatura ad hoc **do WebReader real**, sem criar IPA nem pedir autorização de distribuição antecipadamente.

## BN — validar o app real, assinar apenas uma cópia temporária

Novo `ci/build69_bn_real_signed_app_preview.py`, rodando somente em macOS/Xcode e recebendo `--unsigned-app` com o `MangaReader12.app` já compilado na preview BA:

1. Invoca o auditor BA do **app unsigned real** antes de mexer em qualquer arquivo: CFBundleVersion=69, `com.example.MangaReader12`, `WebReader`, arquitetura ARM64, iOS mínimo 12.0, ícone e estados de produção/Chimera fechados na fonte.
2. Calcula hashes de `Info.plist`, `MangaReader12` e `Assets.car` da origem. Verifica limites de tamanho e proíbe symlinks nesses três arquivos.
3. Cria um `TemporaryDirectory` efêmero e copia o **app compilado de verdade** usando `/usr/bin/ditto`. Confere que os hashes coincidem.
4. Executa `codesign --force --sign - --timestamp=none --entitlements ci/chimera_webreader_qa.entitlements` **apenas na cópia**, `codesign --verify`, `codesign -d --entitlements :-` e exige os entitlements exatos da instalação aprovada: `application-identifier=AR5SFJC432.com.example.MangaReader12.AR5SFJC432`. Também extrai o `CDHash` do selo ad hoc nativo.
5. Garante ausência de `*.ipa` no temporário. Fecha o contexto, destruindo automaticamente a cópia assinada e seus arquivos auxiliares. Recalcula hashes da origem unsigned e exige que permaneçam **idênticos** aos valores iniciais.
6. Imprime apenas um relatório JSON com versão, identidade, CDHash temporário e afirmações limitadas. `temporarySignedAppDeleted=true`, `installableIPAProduced=false`, `editorialPublisherAuthenticated=false`, `qaDistributionAuthorized=false`, `installationAuthorized=false`, `installationPerformed=false`. **Assinatura ad hoc NÃO autentica o editor, nem garante instalação no iPad.**

Novo teste `ci/test_build69_bn_real_signed_app_preview_policy.py` valida os guardrails: não chamar ZIP/package/Release/upload/appinst, sempre assinar a cópia descartável após conferir a preview real, verificar fonte intacta e não criar IPA. A workflow integrada AC–BN acrescenta a etapa macOS **depois** da compilação preview Build69 e **antes** das confirmações finais; não habilita `ci/package_webreader_build69_private_qa_ipa.sh`, não passa marcador de aprovação e não usa `upload-artifact`.

## Provas e limites

[CI AC–BN #42570725651](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42570725651) iniciada; confirmar conclusão no GitHub e corrigir quaisquer falhas antes de afirmar aprovado.

**O que uma CI verde autoriza concluir:** o WebReader consegue compilar em iOS12/ARM64 com versionamento 69 isolado; uma cópia do app real aceita o selo ad hoc local e expõe o identificador de assinatura de teste esperado; nenhum pacote IPA foi criado ou distribuído.

**O que ela NÃO comprova:** origem editorial do código/IPA, compatibilidade real de instalação via Filza/AppSync, integridade de backups ou páginas no iPad após um upgrade, ou autorização do proprietário para distribuição e instalação.

## Próximo marco

Somente após CI verde e aprovação **específica** de empacotamento e distribuição privada da Build69, usar o empacotador BK/BL em macOS não automatizado, sobre o app compilado real. O pacote assinado final ainda precisa passar pelos controles BB/BC de ZIP/entitlements/SHA e de cópia, e depois pelos **16 testes físicos** no iPad — especialmente biblioteca, páginas antigas sem Wi-Fi, reabrir offline e não restaurar backup automaticamente. O arquivo `.mr12backup` não inclui imagens de capítulos e a restauração apagaria os downloads existentes.

`main` e Build68 continuam inalteradas; PR #90 Draft; chave ECDSA de produção não provisionada; instalação automática Chimera bloqueada.
