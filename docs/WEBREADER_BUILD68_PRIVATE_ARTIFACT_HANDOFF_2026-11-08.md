# WebReader — Build 68: IPA de QA manual criada, auditada e disponibilizada

**Data:** 2026-11-08 UTC.  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`.  
**PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90), base `main`, não mesclada.  
**GitHub Actions:** [Run #42453792657 — SUCCESS](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42453792657).  
**Commit exato da candidata:** `605f607b08d714d8eabfd3270516b77dfaf673e0`.  
**Status:** IPA aprovada em CI macOS/iOS12 **somente para QA manual**, **ainda sem aprovação física do usuário**.

## Artefato real entregue

O workflow `.github/workflows/chimera-build68-private-manual-qa.yml`
foi acionado **uma única vez** por
`ci/build68_candidate_trigger.txt` nessa branch de desenvolvimento.

O artefato privado do GitHub Actions é:

`WebReader-Build68-PRIVATE-ManualQA-Filza-iOS12`

Contém:
- `WebReader-Build68-iOS12-adhoc.ipa`
- `WebReader-Build68-iOS12-adhoc.ipa.sha256`
- `WebReader-Build68-private-rehearsal-audit.json`
- `WebReader-Build68-private-manual-qa-delivery.json`
- `WebReader-Build68-source-provenance.json`
- `docs/WEBREADER_BUILD68_PRIVATE_MANUAL_QA_CHECKLIST_2026-11-08.md`.

**SHA-256 final da IPA:**
`fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`.

**Tamanho:** 17.802.736 bytes.  
**GitHub Actions artifact:** `13607280532`, tamanho ZIP reportado ~17,7 MB, retenção de 14 dias.  
**Publicação em GitHub Releases:** NÃO.  
**Instalação em iPad:** NÃO executada pela CI.

## Verificação em várias etapas

1. Código compilado com Xcode 16.4 em Debug e Release para ARM64/iOS12; ambos aprovados.
2. `ci/verify_binary.sh` confirmou iOS mínimo, identidade
   `com.example.MangaReader12`, executável, nome WebReader e catálogo de ícones.
3. `ci/package_webreader_build68_rehearsal.sh` empacotou a aplicação
   **sem** usar root/Filza/appinst; o `Info.plist` passou de Build 56
   (versão do projeto-fonte, preservada durante desenvolvimento) para
   **Build 68** **dentro do pacote QA**, sem alterar a versão do projeto no repositório.
4. `codesign --force --sign -` assinou ad hoc a cópia isolada de
   `MangaReader12.app` com o entitlement antigo
   `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`;
   `codesign --verify` passou.
5. `ci/audit_webreader_build68_rehearsal.py` rejeitou divergências de
   versão, ZIP, Bundle ID, entitlement, SHA-256, ARM64 e assinatura do executável.
6. `ci/build68_private_manual_qa_delivery.py` reabriu e re-hashou
   a IPA final, conferiu o sidecar SHA-256 e o relatório, e retornou
   `privateManualQAArtifactEligible=true` **somente para entrega pessoal**.
7. `WebReader-Build68-source-provenance.json` vinculou
   commit, workflow run, Build e SHA final.
8. Depois do download do artefato para esta conversa, houve
   **revalidação local**: o ZIP continha exatamente os seis itens esperados,
   e o SHA-256 da IPA extraída conferiu com ambos os JSONs e o sidecar;
   a IPA continha o `Info.plist` de Build 68 e o Bundle ID antigo.

Resultados de auditoria **positivos**:
- `nativeAdHocCodeIntegrityVerified=true`;
- `thinArm64Verified=true`;
- `sameInstalledEntitlementIdentifier=true`.

Limitações que continuam **explicitamente falsas**:
- `productionPublisherAuthenticated=false`;
- `releaseManifestIndependentlySigned=false`;
- `ios12DeviceInstallTested=false`;
- `userConsentVerified=false`;
- `helperPeerAuthenticated=false`;
- `installationAuthorized=false`;
- `installationPerformed=false`;
- `approvedForAutomaticRelease=false`.

## Instalação e validação física

Antes de testar, o usuário deve abrir a Build 66 ainda instalada,
criar e guardar **backup da biblioteca fora do iPad**, confirmar
alguns capítulos offline, e só então decidir se deseja instalar
a IPA sobre o WebReader existente usando **Filza/AppSync no Chimera**.

Não desinstalar a Build 66, não apagar Documents ou Application Support,
não tocar em versões estáveis de fontes nem limpar capítulos baixados.
Após instalar, confirmar Build 68, biblioteca, favoritos,
capítulos offline sem Wi-Fi, fontes e leitor, depois testar
os recursos de segurança, download e recibo se houver Release disponível.

Ver checklist completo em
[WEBREADER_BUILD68_PRIVATE_MANUAL_QA_CHECKLIST_2026-11-08.md](WEBREADER_BUILD68_PRIVATE_MANUAL_QA_CHECKLIST_2026-11-08.md).

A Build 66 continua a **última aprovada fisicamente** até o usuário
reportar o resultado da instalação e dos testes. A Build 67 pode ser
ignorada para esta rodada, desde que a Build 68 preserve os dados e
seja instalada sobre a Build 66, com backup prévio.

## Travas imutáveis na candidata

- `WebReaderUpdateChannel.productionPublicKeyX963 = nil`.
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256 = nil`.
- `WebReaderAppinstSocket.liveInstallationEnabled = false`.
- A PR #90 permanece Draft e `main` intocada.
- Nenhuma chave privada de produção ou identidade editorial foi
  provisionada. Assinatura ad hoc **não equivale** a assinatura editorial.
- Nenhum helper privilegiado recebeu IPC de instalação pela CI.
- Não publicar a IPA como Release oficial nem ativar atualização
  automática antes de confiança editorial, autorização do peer,
  proteção de replay/rollback e QA física.
