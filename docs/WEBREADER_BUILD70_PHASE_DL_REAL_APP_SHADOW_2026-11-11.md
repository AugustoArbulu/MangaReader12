# WebReader Build70 — Fase DL: aplicação WebReader 71 completa, assinada e auditada SOMENTE no CI

**Data:** 11/11/2026. Repositório privado `AugustoArbulu/MangaReader12`; branch `feat/chimera-updater-phase1-protocol-audit`; PR #90 **Draft**, sem merge na `main`. Build70 já instalada no iPad iOS12.5.8 e dados da biblioteca/offline **não modificados**.

## Estado de entrada: DI, DJ e DK fechadas

- Fase DI: **SUCCESS 2/2** — https://github.com/AugustoArbulu/MangaReader12/actions/runs/42935290104. Testes de preflight Build70→71 e code seal ad-hoc Apple em IPAs sintéticas efêmeras.
- Fase DJ: **SUCCESS 2/2** — https://github.com/AugustoArbulu/MangaReader12/actions/runs/42944438413. 21 testes por plataforma; comparação exata dos nove registros SQLite no texto readonly da Build70 e da futura 71. **Contagens não verificam imagens.**
- Fase DK: **SUCCESS 2/2** — https://github.com/AugustoArbulu/MangaReader12/actions/runs/42945513059. Integração da DI com relatórios DJ; teste macOS em IPA **sintética**, sem converter os resultados em autoridade.
- Fase DH já havia compilado um **WebReader 71 completo porém unsigned**, validado no Mac; faltava testar o **código real completo após a assinatura ad-hoc** e inspecionar os bytes comprimidos do pacote no mesmo processo de CI, não apenas um miniprograma sintético.

## Fase DL — diferença material

Criado `ci/build70_dl_full_app_signed_shadow.py`: aceita apenas, dentro de um runner macOS GitHub Actions específico, uma `MangaReader12.app` **Release, unsigned, Build71** recém-compilada. Primeiro executa `inspect_dh_unsigned_app` contra a **fonte do repositório** (três hard stops continuam `nil/nil/false`) e exige que o bundle esteja **dentro de `RUNNER_TEMP`**.

Em um único `TemporaryDirectory` privado no runner, somente nesse teste:
1. Copia a aplicação real via `/usr/bin/ditto`, **sem alterar a fonte unsigned**;
2. Assina a **cópia** ad-hoc com o arquivo histórico `ci/chimera_webreader_qa.entitlements`. O app identifier declarado é `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`; a prova é limitada ao bundle do CI, **não** reatesta identidade da Build70 instalada no iPad;
3. Confirma `codesign --verify`, relê os entitlements efetivamente selados e verifica `Info.plist` Build71, bundle ID original e iOS mínimo 12.0;
4. Empacota uma **IPA de sombra efêmera** com `zip` dentro do mesmo `TemporaryDirectory`. Este arquivo **NÃO** é uma IPA de QA liberada: nenhum link ou upload será oferecido;
5. Obtém SHA-256 dos bytes, constrói uma linha checksum **local, não autenticada externamente**, e executa o preflight DI na exata IPA do CI, com código Apple nativo de verificação de assinatura, CodeDirectory hash, ARM64, Info.plist e ZIP;
6. Executa a **mesma integração DK** usando **relatório Build70 completamente sintético** com contagens zero — apenas para exercitar o formato, nunca para inferir que a biblioteca do usuário está vazia. Exige que DK retorne `DK_HOST_PACKAGE_CHECKED_BASELINE_TEXT_ONLY_NO_DISTRIBUTION` e não marque autorização ou offline;
7. Retorna unicamente **um pequeno recibo técnico** (hash da IPA de sombra, CodeDirectory CDHash e metadados não privados), e remove automaticamente a IPA/cópia assinada do diretório temporário antes de terminar.

Assim, a fase mede a assinatura da **aplicação WebReader real**, diferentemente dos testes sintéticos anteriores, e continua incapaz de publicar ou instalar.

## Gatilhos e barreiras de CI

Workflow `.github/workflows/chimera-build70-phase-dl-full-app-shadow.yml`:

- `contents: read` (nenhum token de escrita);
- Só branch experimental e workflow de nome exato. O script exige `GITHUB_REPOSITORY`, `GITHUB_REF`, `GITHUB_WORKFLOW_REF`, `GITHUB_SHA` e runner macOS, e recusa execução como ferramenta genérica local;
- A fonte exata do commit é reproduzida via `git archive` para subdiretório temporário: ícone original e libwebp 1.6.0 SHA-pinado são preparados nessa **cópia isolada**;
- `xcodebuild -configuration Release -sdk iphoneos -destination generic/platform=iOS -arch arm64 implícito no projeto`, `CURRENT_PROJECT_VERSION=71 CODE_SIGNING_ALLOWED=NO`. A Build71 é produzida unsigned, fora do checkout, inspecionada por DH e apenas então assinada em cópia descartável;
- Executa `ci/test_build70_dl_full_app_signed_shadow.py` em Linux com cenários negativos de branch, evento, SHA, workflow, ambiente, temp root, configurações de permissão e comprovação de que nenhuma ferramenta instaladora foi incluída;
- **Não possui `actions/upload-artifact`**, publicação de Release, entrega privada, e-mail, WebDAV, Filza, appinst, `launchd` ou transferência ao dispositivo.

**A assinatura e o empacotamento existem apenas como operação temporária de QA dentro de CI.** Isso não é a permissão de preparar ou distribuir uma IPA real para o usuário. O script contém um gate de processo restritivo que protege contra execução casual, mas é uma medida de workflow, **não uma prova criptográfica da origem da execução**.

## Sem promessas de segurança não verificadas

O resultado `DL_FULL_APP_SHADOW_SIGNED_AND_AUDITED_HOST_ONLY` significa **somente**:

- Swift, C/Swift wrappers, ícones e fonte WebP do WebReader completo compilaram na configuração Release para o alvo iOS12;
- O bundle completo foi assinado temporariamente ad-hoc no macOS;
- O mesmo arquivo efêmero passou DI e DK com SHA local, code seal verificado pelo `codesign` da Apple e recibos com autoridade negada.

Os seguintes indicadores permanecem obrigatoriamente **false**: `physicalLibraryCountsCaptured`, `physicalOfflineReadingVerified`, `physicalBuild70AppIdentifierReattested`, `realDeviceIOS12ExecutionVerified`, `realDeviceInstallationCompatibilityProven`, `publisherCryptographicallyAuthenticated`, `helperIdentityAuthenticated`, `editorialProductionKeyConfigured`, `ownerDistributionApprovalRecorded`, `readyToDistributeIPA`, `readyToInstallIPA`, `installationAuthorized`, `installationPerformed`, `persistentIPAProduced`, `artifactUploaded`, `releasePublished` e `mainModified`.

**Falta para uma IPA privada aprovada:** confirmação física da identidade e dos entitlements atuais do WebReader Build70 no iPad; aprovação explícita do usuário para **criar/distribuir** a Build71; checksum externo independente e CDHash final; backup e teste offline antes/depois; verificar se o iOS12/Chimera realmente aceitaria a mesma identidade de atualização; avaliar rollback. Esses requisitos são distintos dos gates para a **atualização automática**, que ainda carece de helper autenticado, armazenamento resistente a adulteração, assinatura editorial provisionada e consentimento local independente.

**Hard stops inalterados:** `static let productionPublicKeyX963: Data? = nil`, `static let independentlyProvisionedSPKISHA256: String? = nil`, `static let liveInstallationEnabled = false`. A PR #90 permanece Draft.

## CI DL

O estado deve ser atualizado **somente após inspecionar os logs e resultados do workflow**. Uma compilação com êxito é um avanço técnico, não autorização nem prova de instalação física.
